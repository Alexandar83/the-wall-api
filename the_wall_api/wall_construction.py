# This module simulates the construction process of a wall, tracking material usage (ice) and costs.
# It supports both sequential and concurrent simulation modes,and logs progressdata to showcase
# the construction process.

from copy import deepcopy
from multiprocessing import Value, Manager
from threading import Thread
from time import sleep
from typing import Any, Dict

from celery.contrib.abortable import AbortableTask
from django.contrib.auth.models import User
from django.conf import settings

from the_wall_api.utils import error_utils
from the_wall_api.utils.concurrency_utils.multiprocessing_utils import MultiprocessingWallBuilder
from the_wall_api.utils.concurrency_utils.threading_utils import ThreadingWallBuilder
from the_wall_api.utils.wall_config_utils import generate_config_hash_details, CONCURRENT, SEQUENTIAL

CONCURRENT_SIMULATION_MODE = settings.CONCURRENT_SIMULATION_MODE
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

    daily_cost_section = ICE_PER_FOOT * ICE_COST_PER_CUBIC_YARD

    def __init__(
        self, wall_construction_config: list, sections_count: int, num_crews: int,
        wall_config_hash: str, simulation_type: str = SEQUENTIAL, celery_task: AbortableTask | None = None
    ):
        self.wall_construction_config = wall_construction_config
        self.testing_wall_construction_config = deepcopy(wall_construction_config)     # For unit testing purposes
        self.sections_count = sections_count
        self.num_crews = num_crews
        self.wall_config_hash = wall_config_hash
        self.simulation_type = simulation_type

        # Celery task details
        self.celery_task = celery_task
        self.celery_task_id = celery_task.request.id if celery_task else None
        self.celery_task_aborted = False
        self.manage_celery_task_aborted_mprcss()
        self.simulation_finished = False
        self.start_abort_signal_listener_thread()

        # Initialize the wall profile data
        self.wall_profile_data = {}
        self.calc_wall_profile_data()
        self.sim_calc_details = self._calc_sim_details()

    def manage_celery_task_aborted_mprcss(self):
        # Threading
        if 'multiprocessing' not in CONCURRENT_SIMULATION_MODE:
            from types import SimpleNamespace
            self.celery_task_aborted_mprcss = SimpleNamespace(value=False)
        # Multiprocessing
        elif self.is_manager_required():
            self.celery_task_aborted_mprcss = Manager().Value('b', False)
        else:
            self.celery_task_aborted_mprcss = Value('b', False)

    def is_manager_required(self) -> bool:
        return CONCURRENT_SIMULATION_MODE != 'multiprocessing_v1' or bool(self.celery_task)

    def start_abort_signal_listener_thread(self):
        """
        Start a separate thread to periodically check for task revocation.
        """
        if self.celery_task:
            def check_aborted():
                while not self.celery_task_aborted and not self.simulation_finished:
                    if self.celery_task and self.celery_task.is_aborted(task_id=self.celery_task_id):
                        self.celery_task_aborted = True
                        self.celery_task_aborted_mprcss.value = True
                        break
                    sleep(1)

            abort_thread_check = Thread(target=check_aborted)
            abort_thread_check.start()

    def calc_wall_profile_data(self):
        if self.simulation_type == SEQUENTIAL:
            self.calc_wall_profile_data_sequential()
        elif 'threading' in CONCURRENT_SIMULATION_MODE:
            ThreadingWallBuilder(self).calc_wall_profile_data_concurrent()
        else:
            MultiprocessingWallBuilder(self).calc_wall_profile_data_concurrent()
        self.simulation_finished = True

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
                        if self.celery_task_aborted:
                            # Logging to stdout is muted in the workers
                            print('Sequential simulation interrupted by a celery task abort signal!')
                            return

                # Keep track of daily ice usage
                daily_ice_usage[day] = {'ice_used': ice_used}
                day += 1

            # Store the results
            self.wall_profile_data[profile_index + 1] = daily_ice_usage

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
    source: str = 'usage_or_cost_view', profile_id: int | None = None, day: int | None = None,
    request_num_crews: int | None = None, request_type: str | None = None, user: User | None = None,
    wall_config_file_data: list | None = None, config_id: str | None = None

) -> Dict[str, Any]:
    """
    Initialize the wall_data dictionary to hold various control data
    throughout the wall construction simulation or the
    wallconfig file management process.
    """
    if source == 'wallconfig_file_view':
        return {
            'request_type': request_type,
            'user': user,
            'initial_wall_construction_config': wall_config_file_data,
            'config_id': config_id,
            'error_response': None
        }

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
    wall_data['initial_wall_construction_config'] = deepcopy(wall_construction_config)
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
            simulation_type=wall_data['simulation_type'],
            celery_task=wall_data.get('celery_task'),
        )
    except error_utils.WallConstructionError as tech_error:
        error_utils.handle_unknown_error(wall_data, tech_error, 'wall_creation')
        return
    wall_data['wall_construction'] = wall_construction
    wall_data['sim_calc_details'] = wall_construction.sim_calc_details
    store_simulation_result(wall_data)
    if wall_construction.celery_task_aborted:
        wall_data['celery_task_aborted'] = True


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
