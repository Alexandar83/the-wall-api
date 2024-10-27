from copy import deepcopy
import logging
import os
import re
from secrets import token_hex

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from itertools import count
from queue import Empty, Queue
from threading import Condition, Lock, Thread, current_thread
from typing import Any, Dict

from django.conf import settings

from the_wall_api.utils import error_utils
from the_wall_api.utils.wall_config_utils import generate_config_hash_details, CONCURRENT, SEQUENTIAL

BUILD_SIM_LOGS_DIR = settings.BUILD_SIM_LOGS_DIR
MAX_SECTION_HEIGHT = settings.MAX_SECTION_HEIGHT
ICE_PER_FOOT = settings.ICE_PER_FOOT
ICE_COST_PER_CUBIC_YARD = settings.ICE_COST_PER_CUBIC_YARD


class WallConstruction:
    """
    A class to simulate the construction of a wall using crews,
    tracking the usage of ice and the associated costs.
    The concurrent implementation is done explicitly with a file (and not in the memory)
    to follow the task requirements
    """
    def __init__(
            self, wall_construction_config: list, sections_count: int, num_crews: int,
            wall_config_hash: str, simulation_type: str = SEQUENTIAL
    ):
        self.wall_construction_config = wall_construction_config
        self.testing_wall_construction_config = deepcopy(wall_construction_config)     # For unit testing purposes
        self.simulation_type = simulation_type
        self.daily_cost_section = ICE_PER_FOOT * ICE_COST_PER_CUBIC_YARD

        if simulation_type == CONCURRENT:
            self.max_crews = min(sections_count, num_crews)
            self.thread_counter = count(1)
            self.counter_lock = Lock()
            self.thread_days = {}
            timestamp = datetime.now().strftime('%Y_%m_%d_%H_%M_%S_%f')
            self.filename = os.path.join(
                BUILD_SIM_LOGS_DIR,
                f'{timestamp}_{wall_config_hash}_{num_crews}_{token_hex(4)}.log'
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

        self.wall_profile_data = {}
        self.calc_wall_profile_data()
        self.sim_calc_details = self._calc_sim_details()

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

    def calc_wall_profile_data(self):
        if self.simulation_type == CONCURRENT:
            self.calc_wall_profile_data_concurrent()
        else:
            self.calc_wall_profile_data_sequential()

    def calc_wall_profile_data_sequential(self) -> None:
        """
        Sequential construction process simulation.
        All unfinished sections have their designated crew assigned.
        """
        for profile_index, profile in enumerate(self.wall_construction_config):
            day = 1
            daily_ice_usage = {}
            # Increment the heights of all sections until they reach MAX_SECTION_HEIGHT
            while any(height < MAX_SECTION_HEIGHT for height in profile):
                ice_used = 0
                for i, height in enumerate(profile):
                    if height < MAX_SECTION_HEIGHT:
                        ice_used += ICE_PER_FOOT
                        profile[i] += 1  # Increment the height of the section
                        self.testing_wall_construction_config[profile_index][i] = profile[i]

                # Keep track of daily ice usage
                daily_ice_usage[day] = {'ice_used': ice_used}
                day += 1
            # Store the results
            self.wall_profile_data[profile_index + 1] = daily_ice_usage

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

        # When there are no more sections available for the crew, relieve it
        with self.day_condition:
            self.active_crews -= 1
            if self.finished_crews_for_the_day == self.active_crews:
                # Reset the counter and notify all other threads
                self.finished_crews_for_the_day = 0
                self.day_condition.notify_all()

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

    def end_of_day_synchronization(self) -> None:
        """
        Synchronize threads at the end of the day.
        """
        with self.day_condition:
            self.finished_crews_for_the_day += 1
            if self.finished_crews_for_the_day == self.active_crews:
                # Last crew to reach this point resets the counter and notifies all others
                self.finished_crews_for_the_day = 0
                # Wake up all waiting threads
                self.day_condition.notify_all()
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

    def extract_log_data(self) -> None:
        with open(self.filename, 'r') as log_file:
            for line in log_file:
                # Extract profile_id, day, ice used, and cost
                match = re.search(
                    r'HGHT_INCRS: Section ID: (\d+)-\d+ - DAY_(\d+) - .*Ice used: (\d+) cbc\. yrds\.', line)
                if match:
                    profile_id, day, ice_used = map(int, match.groups())

                    self.wall_profile_data.setdefault(profile_id, {}).setdefault(day, {'ice_used': 0})
                    self.wall_profile_data[profile_id][day]['ice_used'] += ice_used

    def _daily_ice_usage(self, profile_id: int, day: int) -> int:
        """
        For internal testing purposes only.
        """
        return self.wall_profile_data.get(profile_id, {}).get(day, {}).get('ice_used', 0)

    def _calc_sim_details(self) -> Dict[str, Any]:
        """
        Calculate and return a detailed cost overview including:
        - Total cost for the whole wall.
        - Cost per profile.
        - Ice usage per profile per day.
        - Detailed breakdown of cost and ice usage per profile per day.
        - Maximum day across all profiles.
        """
        overview = {
            'total_cost': 0,
            'profile_costs': {},
            'profile_daily_details': {},
            'construction_days': 0
        }

        for profile_id, daily_data in self.wall_profile_data.items():
            profile_total_cost = 0
            profile_daily_details = {}

            for day, day_data in daily_data.items():
                cost = day_data['ice_used'] * ICE_COST_PER_CUBIC_YARD
                profile_total_cost += cost
                profile_daily_details[day] = {
                    'ice_used': day_data['ice_used'],
                    'cost': cost
                }
                overview['construction_days'] = max(overview['construction_days'], day)

            # Update the overview dictionary
            overview['total_cost'] += profile_total_cost
            overview['profile_costs'][profile_id] = profile_total_cost
            overview['profile_daily_details'][profile_id] = profile_daily_details

        return overview


def initialize_wall_data(
        profile_id: int | None = None, day: int | None = None, request_num_crews: int | None = None
) -> Dict[str, Any]:
    """
    Initialize the wall_data dictionary to hold various control data
    throughout the wall construction simulation process.
    """
    return {
        'request_profile_id': profile_id,
        'request_day': day,
        'request_num_crews': request_num_crews,
        'error_response': None,
        'concurrent_not_needed': None,
        'wall_construction': None,
    }


def set_simulation_params(
        wall_data: Dict[str, Any], num_crews: int, wall_construction_config: list, request_type: str
) -> None:
    """
    Set the simulation parameters for the wall_data dictionary.
    """
    sections_count = wall_data.get('sections_count')
    if not sections_count:
        sections_count = get_sections_count(wall_construction_config)
        wall_data['sections_count'] = sections_count

    simulation_type, wall_config_hash_details, num_crews_final = evaluate_simulation_params(
        num_crews, sections_count, wall_construction_config, wall_data
    )
    wall_data['num_crews'] = num_crews_final
    wall_data['wall_construction_config'] = deepcopy(wall_construction_config)
    wall_data['simulation_type'] = simulation_type
    wall_config_hash = wall_data.get('wall_config_hash')
    if not wall_config_hash:
        wall_data['wall_config_hash'] = wall_config_hash_details['wall_config_hash']
    wall_data['profile_config_hash_data'] = wall_config_hash_details['profile_config_hash_data']
    wall_data['request_type'] = request_type


def get_sections_count(wall_construction_config: list) -> int:
    return sum(len(profile) for profile in wall_construction_config)


def evaluate_simulation_params(
        num_crews: int, sections_count: int, wall_construction_config: list, wall_data: Dict[str, Any]
) -> tuple[str, dict, int]:
    # num_crews
    simulation_type, num_crews_final = manage_num_crews(num_crews, sections_count, wall_data)

    # configuration hashes
    wall_config_hash_details = generate_config_hash_details(wall_construction_config)

    return simulation_type, wall_config_hash_details, num_crews_final


def manage_num_crews(num_crews: int, sections_count: int, wall_data: Dict[str, Any] = {}) -> tuple[str, int]:
    if num_crews == 0:
        # No num_crews provided - sequential mode
        simulation_type = SEQUENTIAL
        num_crews_final = 0
    elif num_crews >= sections_count:
        # There's a crew for each section at the beginning
        # which is the same as the sequential mode
        simulation_type = SEQUENTIAL
        num_crews_final = 0
        # For eventual future response message
        if wall_data:
            wall_data['concurrent_not_needed'] = True
    else:
        # The crews are less than the number of sections
        simulation_type = CONCURRENT
        num_crews_final = num_crews

    return simulation_type, num_crews_final


def run_simulation(wall_data: Dict[str, Any]) -> None:
    """
    Run the simulation, create and save the wall and its elements.
    """
    try:
        wall_construction = WallConstruction(
            wall_construction_config=wall_data['wall_construction_config'],
            sections_count=wall_data['sections_count'],
            num_crews=wall_data['num_crews'],
            wall_config_hash=wall_data['wall_config_hash'],
            simulation_type=wall_data['simulation_type']
        )
    except error_utils.WallConstructionError as tech_error:
        error_utils.handle_unknown_error(wall_data, tech_error, 'wall_creation')
        return
    wall_data['wall_construction'] = wall_construction
    wall_data['sim_calc_details'] = wall_construction.sim_calc_details
    store_simulation_result(wall_data)


def store_simulation_result(wall_data):
    """
    Store the simulation results to be used in the responses.
    """
    simulation_result = wall_data['simulation_result'] = {}

    # Used in the costowverview response
    simulation_result['wall_total_cost'] = wall_data['sim_calc_details']['total_cost']

    # Used in the costoverview/profile_id response
    request_profile_id = wall_data['request_profile_id']
    if request_profile_id:
        simulation_result['wall_profile_cost'] = wall_data['sim_calc_details']['profile_costs'][request_profile_id]

    # Used in the daily-ice-usage response
    request_day = wall_data['request_day']
    if request_day:
        profile_daily_progress_data = wall_data['sim_calc_details']['profile_daily_details'][request_profile_id]
        profile_day_data = profile_daily_progress_data.get(wall_data['request_day'], {})
        simulation_result['profile_daily_ice_used'] = profile_day_data.get('ice_used', 0)
