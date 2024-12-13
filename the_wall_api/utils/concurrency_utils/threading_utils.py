from concurrent.futures import ThreadPoolExecutor
from itertools import count
from queue import Empty, Queue
from threading import Condition, current_thread, Event, Lock, Thread
from time import sleep
from typing import Callable

from django.conf import settings

from the_wall_api.utils.concurrency_utils.base_concurrency_utils import BaseWallBuilder

ICE_PER_FOOT = settings.ICE_PER_FOOT
MAX_SECTION_HEIGHT = settings.MAX_SECTION_HEIGHT


class ThreadingWallBuilder(BaseWallBuilder):

    def __init__(self, wall_construction):
        super().__init__(wall_construction)
        self.init_concurrent_config()
        self.logger = BaseWallBuilder.setup_logger(self.filename, source_name='threadName')
        self.start_abort_signal_listener_thread()

    def init_concurrent_config(self):
        self.thread_counter = count(1)
        self.counter_lock = Lock()
        self.thread_days = {}
        self.active_crews = self.max_crews
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
        with ThreadPoolExecutor(max_workers=self.max_crews) as executor:
            for _ in range(self.max_crews):  # Start with the available crews
                executor.submit(self.build_section)

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
        while not self.sections_queue.empty():
            try:
                profile_id, section_id, height = self.sections_queue.get_nowait()
            except Empty:
                # No more sections to process
                break

            self.initialize_thread_days(thread)
            self.process_section(profile_id, section_id, height, thread)
            if self.celery_task_aborted:
                break

        # When there are no more sections available for the crew, relieve it
        manage_crew_release = self.get_manage_crew_release_func()
        manage_crew_release()

    def initialize_thread_days(self, thread: Thread) -> None:
        """
        Initialize the tracking for the number of days worked by the thread.
        """
        if thread.name not in self.thread_days:
            self.thread_days[thread.name] = 0

    def process_section(self, profile_id: int, section_id: int, height: int, thread: Thread) -> None:
        """
        Processes a single section until the required height is reached.
        """
        total_ice_used = 0
        total_cost = 0

        while height < MAX_SECTION_HEIGHT:
            # Perform daily increment
            height += 1
            self.thread_days[thread.name] += 1
            total_ice_used += ICE_PER_FOOT
            total_cost += self.daily_cost_section

            # Log the daily progress
            section_progress_msg = BaseWallBuilder.get_section_progress_msg(
                profile_id, section_id, self.thread_days[thread.name], height, self.daily_cost_section
            )
            self.logger.debug(section_progress_msg, extra={'source_name': thread.name})
            self.testing_wall_construction_config[profile_id - 1][section_id - 1] = height

            # Log the section finalization
            if height == MAX_SECTION_HEIGHT:
                sleep(0.02)     # Grace period to ensure finish section records are at the end of the day's records
                section_completion_msg = BaseWallBuilder.get_section_completion_msg(
                    profile_id, section_id, self.thread_days[thread.name], total_ice_used, total_cost
                )
                self.logger.debug(section_completion_msg, extra={'source_name': thread.name})

            # Synchronize with the other crews at the end of the day
            end_of_day_synchronization = self.get_end_of_day_synchronization_func()
            end_of_day_synchronization()

            if self.celery_task_aborted:
                return

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
                self.day_event.clear()      # Reset the event for the next day
            else:
                # default - Condition
                self.day_condition.notify_all()

            return True

        return False

# === Common logic (end) ===

# === v1 Condition sync. ===
    def manage_crew_release_v1(self) -> None:
        with self.day_condition:
            self.active_crews -= 1
            self.check_notify_all_workers_to_resume_work()

    def end_of_day_synchronization_v1(self) -> None:
        with self.day_condition:
            self.finished_crews_for_the_day += 1
            if self.check_notify_all_workers_to_resume_work():
                return
            else:
                # Wait until all other crews are done with the current day
                self.day_condition.wait()

# === v1 Condition sync. (end) ===

# === v2 Event sync. ===
    def manage_crew_release_v2(self) -> None:
        with self.day_event_lock:
            self.active_crews -= 1
            self.check_notify_all_workers_to_resume_work()

    def end_of_day_synchronization_v2(self) -> None:
        with self.day_event_lock:
            self.finished_crews_for_the_day += 1
            other_crews_notified = self.check_notify_all_workers_to_resume_work()

        if not other_crews_notified:
            self.day_event.wait()

# === v2 Event sync. (end) ===
