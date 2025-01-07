from concurrent.futures import ThreadPoolExecutor
from itertools import count
from queue import Empty, Queue
from threading import Condition, current_thread, Event, Lock, Thread
from time import sleep
from typing import Callable

from django.conf import settings

from the_wall_api.utils.concurrency_utils.base_concurrency_utils import BaseWallBuilder

MAX_CONCURRENT_NUM_CREWS_THREADING = settings.MAX_CONCURRENT_NUM_CREWS_THREADING
MAX_SECTION_HEIGHT = settings.MAX_SECTION_HEIGHT
VERBOSE_MULTIPROCESSING_LOGGING = settings.VERBOSE_MULTIPROCESSING_LOGGING
SECTION_COMPLETION_GRACE_PERIOD_THREADING = settings.SECTION_COMPLETION_GRACE_PERIOD_THREADING


class ThreadingWallBuilder(BaseWallBuilder):

    def __init__(self, wall_construction):
        super().__init__(wall_construction)
        if self.num_crews > MAX_CONCURRENT_NUM_CREWS_THREADING:
            from the_wall_api.utils.error_utils import WallConstructionError
            # Threading limitations, due to:
            # -the nature of the build simulation - 1 crew (thread) per section
            raise WallConstructionError(
                f'Max. allowed number of sections for multi-threading is {MAX_CONCURRENT_NUM_CREWS_THREADING}'
            )
        self.init_concurrent_config()
        self.logger = BaseWallBuilder.setup_logger(self.filename, self.log_stream, source_name='threadName')
        self.start_abort_signal_listener_thread()

    def init_concurrent_config(self):
        self.thread_counter = count(1)
        self.counter_lock = Lock()
        self.thread_days = {}
        self.active_crews = self.num_crews
        self.finished_crews_for_the_day = 0
        self.init_sim_mode_attributes()

    def init_sim_mode_attributes(self) -> None:
        if self.CONCURRENT_SIMULATION_MODE == 'threading_v2':
            self.day_event = Event()
            self.day_event_lock = Lock()
        else:
            self.day_condition = Condition()

    def create_queue(self) -> Queue:
        return Queue()

    def calc_wall_profile_data_concurrent(self) -> None:
        """
        Concurrent construction process simulation.
        Using a limited number of crews.
        """
        with ThreadPoolExecutor(max_workers=self.num_crews) as executor:
            for _ in range(self.num_crews):  # Start with the available crews
                executor.submit(self.build_section)

        self.wall_profile_data['profiles_overview']['construction_days'] = max(self.thread_days.values())
        self.extract_log_data()

    def build_section(self) -> None:
        """
        Single wall section construction simulation.
        Logs the progress and the completion details in a log file.
        """
        thread = current_thread()

        try:
            self.assign_thread_name(thread)
            self.process_sections(thread)
        except Exception as bld_sctn_err:
            self.logger.error(f'Error in thread {thread.name}: {bld_sctn_err}', extra={'source_name': thread.name})
            raise

    def assign_thread_name(self, thread: Thread) -> None:
        """
        Assigns a shorter thread name for better readability in the logs.
        """
        with self.counter_lock:
            if not thread.name.startswith('Crew-'):
                thread.name = f'Crew-{next(self.thread_counter)}'

    def process_sections(self, thread: Thread) -> None:
        """
        Processes the sections for the crew until there are no more sections available.
        """
        log_message_prefx = ' ' * (len(str(self.num_crews)) - len(str(thread.name.partition('-')[2])))

        while not self.sections_queue.empty():
            try:
                profile_id, section_id, height = self.sections_queue.get_nowait()
            except Empty:
                # No more sections to process
                break

            self.initialize_thread_days(thread)
            self.process_section(profile_id, section_id, height, thread, log_message_prefx)
            if self.celery_task_aborted:
                break

        # When there are no more sections available for the crew, relieve it
        manage_crew_release = self.get_manage_crew_release_func()
        manage_crew_release(log_message_prefx, thread)

    def initialize_thread_days(self, thread: Thread) -> None:
        """
        Initialize the tracking for the number of days worked by the thread.
        """
        if thread.name not in self.thread_days:
            self.thread_days[thread.name] = 0

    def process_section(self, profile_id: int, section_id: int, height: int, thread: Thread, log_message_prefx: str) -> None:
        """
        Processes a single section until the required height is reached.
        """
        while height < MAX_SECTION_HEIGHT:
            # Perform daily increment
            height += 1
            self.thread_days[thread.name] += 1

            # Daily progress
            self.log_daily_progress(profile_id, section_id, thread, height)

            # Test data
            self.testing_wall_construction_config[profile_id - 1][section_id - 1] = height

            # Section finalization
            self.log_section_completion(
                height, log_message_prefx, profile_id, section_id, thread
            )

            # Synchronize with the other crews at the end of the day
            end_of_day_synchronization = self.get_end_of_day_synchronization_func()
            end_of_day_synchronization(self.thread_days[thread.name], profile_id, thread)

            # Ensure proper conditions for abort signal during tests
            if self.cncrrncy_test_sleep_period:
                sleep(self.cncrrncy_test_sleep_period)

            if self.celery_task_aborted:
                return

    def log_daily_progress(self, profile_id: int, section_id: int, thread: Thread, height: int) -> None:
        if VERBOSE_MULTIPROCESSING_LOGGING:
            section_progress_msg = BaseWallBuilder.get_section_progress_msg(
                profile_id, section_id, self.thread_days[thread.name], height
            )
            self.logger.debug(section_progress_msg, extra={'source_name': thread.name})

    def log_section_completion(
        self, height: int, log_message_prefx: str, profile_id: int, section_id: int, thread: Thread
    ) -> None:
        if height == MAX_SECTION_HEIGHT:
            # Grace period to ensure finish section records are at the end of the day's records
            sleep(SECTION_COMPLETION_GRACE_PERIOD_THREADING)
            section_completion_msg = log_message_prefx + BaseWallBuilder.get_section_completion_msg(
                profile_id, section_id, self.thread_days[thread.name]
            )
            self.logger.debug(section_completion_msg, extra={'source_name': thread.name})

# === Common logic ===
    def get_manage_crew_release_func(self) -> Callable:
        if self.CONCURRENT_SIMULATION_MODE == 'threading_v2':
            return self.manage_crew_release_v2

        return self.manage_crew_release_v1

    def get_end_of_day_synchronization_func(self) -> Callable:
        if self.CONCURRENT_SIMULATION_MODE == 'threading_v2':
            return self.end_of_day_synchronization_v2

        return self.end_of_day_synchronization_v1

    def check_notify_all_workers_to_resume_work(self) -> bool:
        if self.finished_crews_for_the_day == self.active_crews or self.celery_task_aborted:
            # Last crew to reach this point resets the counter and notifies all others,
            # or a revocation signal is received and the simulation is interrupted
            self.finished_crews_for_the_day = 0

            # Wake up all waiting threads
            if self.CONCURRENT_SIMULATION_MODE == 'threading_v2':
                # Event
                self.day_event.set()        # Wake up all waiting threads
                sleep(0.05)                 # Grace period to ensure the other threads register the event set
                self.day_event.clear()      # Reset the event for the next day
            else:
                # default - Condition
                self.day_condition.notify_all()

            return True

        return False

# === Common logic (end) ===

# === v1 Condition sync. ===
    def manage_crew_release_v1(self, log_message_prefx: str, thread: Thread) -> None:
        with self.day_condition:
            relieved_crew_msg = log_message_prefx + BaseWallBuilder.get_relieved_crew_msg(self.thread_days[thread.name])
            self.logger.debug(relieved_crew_msg, extra={'source_name': thread.name})
            self.active_crews -= 1
            self.check_notify_all_workers_to_resume_work()

    def end_of_day_synchronization_v1(self, day: int, profile_id: int, thread: Thread) -> None:
        with self.day_condition:
            BaseWallBuilder.update_wall_profile_data(self.wall_profile_data, day, profile_id)

            self.finished_crews_for_the_day += 1
            if self.check_notify_all_workers_to_resume_work():
                return
            else:
                # Wait until all other crews are done with the current day
                self.day_condition.wait()

# === v1 Condition sync. (end) ===

# === v2 Event sync. ===
    def manage_crew_release_v2(self, log_message_prefx: str, thread: Thread) -> None:
        with self.day_event_lock:
            relieved_crew_msg = log_message_prefx + BaseWallBuilder.get_relieved_crew_msg(self.thread_days[thread.name])
            self.logger.debug(relieved_crew_msg, extra={'source_name': thread.name})
            self.active_crews -= 1
            self.check_notify_all_workers_to_resume_work()

    def end_of_day_synchronization_v2(self, day: int, profile_id: int, thread: Thread) -> None:
        with self.day_event_lock:
            BaseWallBuilder.update_wall_profile_data(self.wall_profile_data, day, profile_id)

            self.finished_crews_for_the_day += 1
            other_crews_notified = self.check_notify_all_workers_to_resume_work()

        if not other_crews_notified:
            # In rare occasions the waiting crews may not be notified
            # for the set event in threading_v2
            wait_period = None if self.CONCURRENT_SIMULATION_MODE == 'threading_v1' else 1.0
            self.day_event.wait(wait_period)

# === v2 Event sync. (end) ===
