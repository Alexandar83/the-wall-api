# This module simulates the construction process of a wall, tracking material usage (ice) and costs.
# It supports both sequential and concurrent simulation modes,and logs progress data to showcase
# the construction process.

from copy import deepcopy
from io import StringIO
import json
from multiprocessing import Value, Manager
from threading import Thread
from time import sleep
from typing import Any, Dict

from celery.contrib.abortable import AbortableTask
from django.contrib.auth.models import AbstractUser
from django.conf import settings

from the_wall_api.utils import error_utils
from the_wall_api.utils.concurrency_utils.base_concurrency_utils import BaseWallBuilder
from the_wall_api.utils.concurrency_utils.multiprocessing_utils import MultiprocessingWallBuilder
from the_wall_api.utils.concurrency_utils.threading_utils import ThreadingWallBuilder
from the_wall_api.utils.wall_config_utils import CONCURRENT, hash_calc, SEQUENTIAL

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
        wall_config_hash: str, simulation_type: str = SEQUENTIAL, celery_task: AbortableTask | None = None,
        proxy_wall_creation_call: bool = False
    ):
        self.CONCURRENT_SIMULATION_MODE = settings.CONCURRENT_SIMULATION_MODE
        self.wall_construction_config = wall_construction_config
        self.testing_wall_construction_config = deepcopy(wall_construction_config)     # For unit testing purposes
        self.sections_count = sections_count
        self.num_crews = num_crews
        self.wall_config_hash = wall_config_hash
        self.simulation_type = simulation_type
        self.log_stream = StringIO()

        # Celery task details
        self.celery_task = celery_task
        self.celery_task_id = celery_task.request.id if celery_task else None
        self.celery_task_aborted = False
        self.manage_celery_task_aborted_mprcss()
        self.simulation_finished = False
        self.start_abort_signal_listener_thread()

        # Initialize the wall profile data
        self.wall_profile_data: dict = {
            'profiles_overview': {
                'total_ice_amount': 0,
                'construction_days': 0,
                'daily_details': {}
            }
        }
        self.proxy_wall_creation_call = proxy_wall_creation_call    # Utilized in proxy_wall_creation
        self.calc_wall_profile_data()

    def manage_celery_task_aborted_mprcss(self):
        # Threading
        if 'multiprocessing' not in self.CONCURRENT_SIMULATION_MODE:
            from types import SimpleNamespace
            self.celery_task_aborted_mprcss = SimpleNamespace(value=False)
        # Multiprocessing
        elif self.is_manager_required():
            self.celery_task_aborted_mprcss = Manager().Value('b', False)
        else:
            self.celery_task_aborted_mprcss = Value('b', False)

    def is_manager_required(self) -> bool:
        return self.CONCURRENT_SIMULATION_MODE != 'multiprocessing_v1' or bool(self.celery_task)

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
        elif 'threading' in self.CONCURRENT_SIMULATION_MODE:
            ThreadingWallBuilder(self).calc_wall_profile_data_concurrent()
        else:
            MultiprocessingWallBuilder(self).calc_wall_profile_data_concurrent()
        self.simulation_finished = True

    def calc_wall_profile_data_sequential(self) -> None:
        """
        Sequential construction process simulation.
        All unfinished sections have a designated crew.
        Increment the heights of all sections, before proceeding to the next day.
        """
        day = 1
        num_available_crews = self.num_crews if self.num_crews else None

        while True:
            num_crews_worked_today = 0 if num_available_crews is not None else None
            all_crews_finished_work_for_the_day = False
            work_done_today = False

            # Increment each profile's unfinished sections
            for profile_index, profile in enumerate(self.wall_construction_config, start=1):
                for i, height in enumerate(profile):
                    if height >= MAX_SECTION_HEIGHT:
                        continue

                    # Perform daily increment
                    profile[i] += 1

                    # Daily progress
                    BaseWallBuilder.update_wall_profile_data(self.wall_profile_data, day, profile_index)

                    # Test data
                    self.testing_wall_construction_config[profile_index - 1][i] = profile[i]

                    # Manage number of crews, if provided
                    work_done_today = True
                    if num_crews_worked_today is not None:
                        num_crews_worked_today += 1
                        if num_crews_worked_today == num_available_crews:
                            all_crews_finished_work_for_the_day = True
                            break

                # All crews are finished - proceed to the next day
                if all_crews_finished_work_for_the_day:
                    break

            if not work_done_today:
                break

            day += 1

        self.wall_profile_data['profiles_overview']['construction_days'] = day - 1


def initialize_wall_data(
    source: str = 'profiles_view', profile_id: int | None = None, day: int | None = None,
    request_num_crews: int | None = None, request_type: str | None = None, user: AbstractUser | None = None,
    wall_config_file_data: list | None = None, config_id: str | None = None,
    request_config_id_list: list | None = None, input_data={}

) -> Dict[str, Any]:
    """
    Initialize the wall_data dictionary to hold various control data
    throughout the wall construction simulation or the
    wallconfig file management process.
    """
    test_data_json = input_data.get('test_data', '{}') if settings.ACTIVE_TESTING else '{}'
    test_data = json.loads(test_data_json)

    if source in ['wallconfig_file_view', 'test_profiles_views']:
        return {
            'request_type': request_type,
            'request_user': user,
            'initial_wall_construction_config': wall_config_file_data,
            'request_config_id': config_id,
            'request_config_id_list': request_config_id_list,
            'error_response': None,
            'test_data': test_data
        }

    return {
        'request_profile_id': profile_id,
        'request_day': day,
        'request_num_crews': request_num_crews,
        'error_response': None,
        'concurrent_not_needed': None,
        'wall_construction': None,
        'request_config_id': config_id,
        'request_user': user,
        'test_data': test_data
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

    simulation_type, num_crews_final = manage_num_crews(num_crews, sections_count)
    wall_data['num_crews'] = num_crews_final
    wall_data['wall_construction_config'] = deepcopy(wall_construction_config)
    wall_data['initial_wall_construction_config'] = deepcopy(wall_construction_config)
    wall_data['simulation_type'] = simulation_type
    wall_config_hash = wall_data.get('wall_config_hash')
    if not wall_config_hash:
        wall_data['wall_config_hash'] = hash_calc(wall_construction_config)
    wall_data['request_type'] = request_type


def get_sections_count(wall_construction_config: list) -> int:
    return sum(len(profile) for profile in wall_construction_config)


def manage_num_crews(num_crews: int, sections_count: int) -> tuple[str, int]:
    if num_crews == 0:
        # No num_crews provided - sequential mode
        simulation_type = SEQUENTIAL
        num_crews_final = 0
    elif num_crews >= sections_count:
        # There's a crew for each section at the beginning
        # which is the same as the sequential mode
        simulation_type = SEQUENTIAL
        num_crews_final = 0
    elif (
        # Fine-tuning of multiprocessing limits
        (
            'threading' in settings.CONCURRENT_SIMULATION_MODE and
            (
                num_crews > settings.MAX_CONCURRENT_NUM_CREWS_THREADING or
                sections_count > settings.MAX_SECTIONS_COUNT_CONCURRENT_THREADING
            )
        ) or
        (
            'multiprocessing' in settings.CONCURRENT_SIMULATION_MODE and
            (
                num_crews > settings.MAX_CONCURRENT_NUM_CREWS_MULTIPROCESSING or
                sections_count > settings.MAX_SECTIONS_COUNT_CONCURRENT_MULTIPROCESSING
            )
        )
    ):
        simulation_type = SEQUENTIAL
        num_crews_final = num_crews
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
    except Exception as tech_error:
        error_utils.handle_unknown_error(wall_data, tech_error, 'wall_creation')
        return
    wall_data['wall_construction'] = wall_construction
    store_simulation_result(wall_data)
    if wall_construction.celery_task_aborted:
        wall_data['celery_task_aborted'] = True


def store_simulation_result(wall_data):
    """
    Store the simulation results to be used in the responses.
    """
    simulation_result = wall_data['simulation_result'] = {}
    profile_overview = wall_data['wall_construction'].wall_profile_data['profiles_overview']
    daily_details = profile_overview['daily_details']
    request_day = wall_data['request_day']
    request_profile_id = wall_data['request_profile_id']

    # Used in the profiles-overview response
    total_ice_amount = profile_overview['total_ice_amount']
    simulation_result['wall_total_cost'] = total_ice_amount * settings.ICE_COST_PER_CUBIC_YARD

    if request_day:
        # Used in the profiles-overview-day response
        daily_total_amount = daily_details[request_day]['dly_ttl']
        simulation_result['profiles_overview_day_cost'] = daily_total_amount * settings.ICE_COST_PER_CUBIC_YARD

        if request_profile_id:
            # Used in the profiles-days response
            profile_day_ice_amount = daily_details[request_day][request_profile_id]
            simulation_result['profile_day_ice_amount'] = profile_day_ice_amount
            # Used in single-profile-overview-day
            simulation_result['profile_day_cost'] = profile_day_ice_amount * settings.ICE_COST_PER_CUBIC_YARD
