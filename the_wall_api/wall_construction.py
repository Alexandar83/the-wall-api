from concurrent.futures import ThreadPoolExecutor
import copy
import logging
from itertools import count
import os
import re
import uuid
from queue import Queue
from threading import Lock, current_thread
from typing import Dict, Any

from django.conf import settings

from the_wall_api.utils import MULTI_THREADED, SINGLE_THREADED, WallConstructionError

MAX_HEIGHT = settings.MAX_HEIGHT                                        # Maximum height of a wall section
ICE_PER_FOOT = settings.ICE_PER_FOOT                                    # Cubic yards of ice used per 1 foot height increase
ICE_COST_PER_CUBIC_YARD = settings.ICE_COST_PER_CUBIC_YARD              # Gold Dragon coins cost per cubic yard


class WallConstruction:
    """
    A class to simulate the construction of a wall using crews,
    tracking the usage of ice and the associated costs.
    The multi-threaded implementation is done explicitly with a file (and not in the memory)
    to follow the task requirements
    """
    def __init__(self, wall_profiles_config: list, num_crews: int | None, simulation_type: str = SINGLE_THREADED):
        self.wall_profiles_config = wall_profiles_config
        self.testing_wall_profiles_config = copy.deepcopy(wall_profiles_config)
        self.simulation_type = simulation_type
        self.daily_cost_section = ICE_PER_FOOT * ICE_COST_PER_CUBIC_YARD
        sections_count = sum(len(profile) for profile in wall_profiles_config)
        self.max_crews = min(sections_count, num_crews) if num_crews else sections_count
        
        if simulation_type == MULTI_THREADED:
            if num_crews is None:
                raise WallConstructionError('WallConstruction.__init__(): num_crews cannot be None when using MULTI_THREADED simulation type.')
            self.thread_counter = count(1)
            self.counter_lock = Lock()
            self.sections_queue = Queue()
            self.filename = f'logs/wall_construction_{uuid.uuid4().hex}.log'
            self.logger = self._setup_logger()
            self.thread_days = {}

            # Initialize the queue with sections
            for profile_id, profile in enumerate(self.wall_profiles_config):
                for section_id, height in enumerate(profile):
                    self.sections_queue.put((profile_id + 1, section_id + 1, height))
        
        self.wall_profile_data = {}
        self.calc_wall_profile_data()
        self.sim_calc_details = self._calc_sim_details()

    def _setup_logger(self):
        # Ensure the directory exists
        log_dir = os.path.dirname(self.filename)
        os.makedirs(log_dir, exist_ok=True)

        logger = logging.getLogger(self.filename)
        logger.setLevel(logging.INFO)

        # File handler
        file_handler = logging.FileHandler(self.filename, mode='w')
        file_handler.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter('%(asctime)s %(levelname)s [%(threadName)s] %(message)s')
        file_handler.setFormatter(formatter)

        # Handler to the logger
        logger.addHandler(file_handler)

        # Flushing after each log entry
        file_handler.flush = lambda: file_handler.stream.flush()

        return logger

    def calc_wall_profile_data(self):
        if self.simulation_type == MULTI_THREADED:
            self.calc_wall_profile_data_multi_threaded()
        else:
            self.calc_wall_profile_data_single_threaded()
    
    def calc_wall_profile_data_single_threaded(self):
        """
        Sequential construction process simulation.
        All unfinished sections have their designated crew assigned.
        """
        for profile_index, profile in enumerate(self.wall_profiles_config):
            day = 1
            daily_ice_usage = {}
            # Increent the heights of all sections until they reach MAX_HEIGHT
            while any(height < MAX_HEIGHT for height in profile):
                ice_used = 0
                for i, height in enumerate(profile):
                    if height < MAX_HEIGHT:
                        ice_used += ICE_PER_FOOT
                        profile[i] += 1  # Increment the height of the section
                        self.testing_wall_profiles_config[profile_index][i] = profile[i]
                
                # Keep track of daily ice usage
                daily_ice_usage[day] = {'ice_used': ice_used}
                day += 1
            # Store the results
            self.wall_profile_data[profile_index + 1] = daily_ice_usage

    def calc_wall_profile_data_multi_threaded(self):
        """
        Concurrent construction process simulation.
        Using a limited number of crews.
        """
        with ThreadPoolExecutor(max_workers=self.max_crews) as executor:
            while not self.sections_queue.empty():
                profile_id, section_id, height = self.sections_queue.get()
                executor.submit(self.build_section, profile_id, section_id, height)
        executor.shutdown(wait=True)  # Ensure all threads are finished before proceeding

        self.extract_log_data()

    def build_section(self, profile_id: int, section_id: int, initial_height: int):
        """
        Single wall section construction simulation.
        Logs the progress and the completion details in a log file.
        """
        # Shorter thread name to be used in the logs to showcase the concurrent nature of the simulation
        thread = current_thread()
        try:
            with self.counter_lock:
                if not thread.name.startswith('Crew-'):
                    thread.name = f'Crew-{next(self.thread_counter)}'
            
            total_ice_used = 0
            total_cost = 0
            if current_thread().name not in self.thread_days:
                self.thread_days[current_thread().name] = 0
            current_day = self.thread_days[current_thread().name]
            height = initial_height

            while height < MAX_HEIGHT:
                height += 1
                self.thread_days[current_thread().name] += 1
                total_ice_used += ICE_PER_FOOT
                total_cost += self.daily_cost_section

                self.log_section_progress(profile_id, section_id, self.thread_days[current_thread().name], height)
                self.testing_wall_profiles_config[profile_id - 1][section_id - 1] = height
            
            self.log_section_completion(profile_id, section_id, current_day, total_ice_used, total_cost)
        except Exception as e:
            self.logger.error(f'Error in thread {thread.name}: {e}')

    def log_section_progress(self, profile_id: int, section_id: int, day: int, height: int):
        message = (
            f'HGHT_INCRS: Section ID: {profile_id}-{section_id} - DAY_{day} - '
            f'New height: {height} ft - Ice used: {ICE_PER_FOOT} cbc. yrds. - '
            f'Cost: {self.daily_cost_section} gold drgns.'
        )
        self.logger.info(message)

    def log_section_completion(self, profile_id: int, section_id: int, day: int, total_ice_used: int, total_cost: int):
        message = (
            f'FNSH_SCTN: Section ID: {profile_id}-{section_id} - DAY_{day} - finished. '
            f'Ice used: {total_ice_used} cbc. yrds. - Cost: {total_cost} gold drgns.'
        )
        self.logger.info(message)

    def extract_log_data(self):
        try:
            with open(self.filename, 'r') as log_file:
                for line in log_file:
                    try:
                        # Extract profile_id, day, ice used, and cost
                        match = re.search(
                            r'HGHT_INCRS: Section ID: (\d+)-\d+ - DAY_(\d+) - .*Ice used: (\d+) cbc\. yrds\.', line)
                        if match:
                            profile_id, day, ice_used = map(int, match.groups())
                            
                            self.wall_profile_data.setdefault(profile_id, {}).setdefault(day, {'ice_used': 0})
                            self.wall_profile_data[profile_id][day]['ice_used'] += ice_used
                    except Exception as e:
                        self.logger.error(f'Error processing line in log file: {line}. Exception: {e}')
        except IOError as e:
            self.logger.error(f'Failed to open log file {self.filename}. IOError: {e}')
        except Exception as e:
            self.logger.error(f'Unexpected error: {e}')

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
            'max_day': 0
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
                overview['max_day'] = max(overview['max_day'], day)

            # Update the overview dictionary
            overview['total_cost'] += profile_total_cost
            overview['profile_costs'][profile_id] = profile_total_cost
            overview['profile_daily_details'][profile_id] = profile_daily_details

        return overview
