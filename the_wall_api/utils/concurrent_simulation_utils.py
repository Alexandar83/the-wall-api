# Different implementations of the concurrent wall build simulation
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from itertools import count
import logging
import os
from queue import Queue, Empty
import re
from secrets import token_hex
from threading import Condition, current_thread, Lock, Thread

from django.conf import settings

BUILD_SIM_LOGS_DIR = settings.BUILD_SIM_LOGS_DIR
ICE_PER_FOOT = settings.ICE_PER_FOOT
MAX_SECTION_HEIGHT = settings.MAX_SECTION_HEIGHT


class ConcurrentWallBuilder:

    def __init__(self, wall_construction):
        self._wall_construction = wall_construction
        self.init_concurrent_config()

    def __getattr__(self, name):
        # Delegate attribute access to the wall_construction instance
        return getattr(self._wall_construction, name)

    def init_concurrent_config(self):
        self.max_crews = min(self.sections_count, self.num_crews)
        self.thread_counter = count(1)
        self.counter_lock = Lock()
        self.thread_days = {}
        timestamp = datetime.now().strftime('%Y_%m_%d_%H_%M_%S_%f')
        self.filename = os.path.join(
            BUILD_SIM_LOGS_DIR,
            f'{timestamp}_{self.wall_config_hash}_{self.num_crews}_{token_hex(4)}.log'
        )
        self.logger = self._setup_logger()

        # Initialize the queue with sections
        self.sections_queue = Queue()
        for profile_id, profile in enumerate(self.wall_construction_config, 1):
            for section_id, height in enumerate(profile, 1):
                self.sections_queue.put((profile_id, section_id, height))

        # Init a condition for crew threads synchronization
        self.active_crews = self.max_crews
        self.day_condition = Condition()
        self.finished_crews_for_the_day = 0

    def _setup_logger(self):
        """
        Set up the logger dynamically.
        Using the Django LOGGING config leads to Celery tasks hijacking
        each other's loggers in concurrent mode.
        """
        # Ensure the directory exists
        log_dir = os.path.dirname(self.filename)
        os.makedirs(log_dir, exist_ok=True)

        logger = logging.getLogger(self.filename)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        # File handler
        file_handler = logging.FileHandler(self.filename, mode='w')
        file_handler.setLevel(logging.DEBUG)

        # Formatter
        formatter = logging.Formatter('%(asctime)s %(levelname)s [%(threadName)s] %(message)s')
        file_handler.setFormatter(formatter)

        # Handler to the logger
        logger.addHandler(file_handler)

        return logger

    def calc_wall_profile_data_concurrent(self) -> None:
        """
        Concurrent construction process simulation.
        Using a limited number of crews.
        """
        with ThreadPoolExecutor(max_workers=self.max_crews) as executor:
            for _ in range(self.max_crews):  # Start with the available crews
                executor.submit(self.build_section)
        executor.shutdown(wait=True)  # Ensure all threads finish

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
            self.logger.error(f'Error in thread {thread.name}: {bld_sctn_err}')

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
        with self.day_condition:
            self.active_crews -= 1
            self.check_notify_all_workers_to_resume_work()

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
            self.log_section_progress(profile_id, section_id, self.thread_days[thread.name], height)
            self.testing_wall_construction_config[profile_id - 1][section_id - 1] = height

            # Log the section finalization
            if height == MAX_SECTION_HEIGHT:
                self.log_section_completion(profile_id, section_id, self.thread_days[thread.name], total_ice_used, total_cost)

            # Synchronize with the other crews at the end of the day
            self.end_of_day_synchronization()

            if self.celery_task_aborted:
                return

    def end_of_day_synchronization(self) -> None:
        """
        Synchronize threads at the end of the day.
        """
        with self.day_condition:
            self.finished_crews_for_the_day += 1
            if self.check_notify_all_workers_to_resume_work():
                return
            else:
                # Wait until all other crews are done with the current day
                self.day_condition.wait()

    def log_section_progress(self, profile_id: int, section_id: int, day: int, height: int) -> None:
        message = (
            f'HGHT_INCRS: Section ID: {profile_id}-{section_id} - DAY_{day} - '
            f'New height: {height} ft - Ice used: {ICE_PER_FOOT} cbc. yrds. - '
            f'Cost: {self.daily_cost_section} gold drgns.'
        )
        self.logger.debug(message)

    def log_section_completion(self, profile_id: int, section_id: int, day: int, total_ice_used: int, total_cost: int) -> None:
        message = (
            f'FNSH_SCTN: Section ID: {profile_id}-{section_id} - DAY_{day} - finished. '
            f'Ice used: {total_ice_used} cbc. yrds. - Cost: {total_cost} gold drgns.'
        )
        self.logger.debug(message)

    def log_work_interrupted(self) -> None:
        message = 'WRK_INTRRPTD: Work interrupted by a celery task abort signal.'
        self.logger.debug(message)

    def extract_log_data(self) -> None:
        if self.celery_task_aborted:
            self.log_work_interrupted()
            return

        with open(self.filename, 'r') as log_file:
            for line in log_file:
                # Extract profile_id, day, ice used, and cost
                match = re.search(
                    r'HGHT_INCRS: Section ID: (\d+)-\d+ - DAY_(\d+) - .*Ice used: (\d+) cbc\. yrds\.', line)
                if match:
                    profile_id, day, ice_used = map(int, match.groups())

                    self.wall_profile_data.setdefault(profile_id, {}).setdefault(day, {'ice_used': 0})
                    self.wall_profile_data[profile_id][day]['ice_used'] += ice_used

    def check_notify_all_workers_to_resume_work(self) -> bool:
        if self.finished_crews_for_the_day == self.active_crews or self.celery_task_aborted:
            # Last crew to reach this point resets the counter and notifies all others,
            # or a revocation signal is received and the simulation is interrupted
            self.finished_crews_for_the_day = 0
            # Wake up all waiting threads
            self.day_condition.notify_all()

            return True

        return False
