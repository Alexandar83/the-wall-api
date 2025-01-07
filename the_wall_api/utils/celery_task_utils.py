# Implementation of the Celery tasks logic - keep only imports of built-ins on top

from datetime import datetime, timedelta
from gzip import open as gzip_open
import logging
import os
from shutil import copyfileobj
from time import sleep, time
from typing import Callable

ABORT_WAIT_PERIOD = int(os.getenv('ABORT_WAIT_PERIOD', 60))
CONCURRENT_SIMULATION_MODE = os.getenv('CONCURRENT_SIMULATION_MODE', 'threading_v1')
if 'multiprocessing' in CONCURRENT_SIMULATION_MODE:
    # Longer finishing times for multiprocessing
    ABORT_WAIT_PERIOD *= 3
DELETION_RETRIES = 5
LIGHT_CELERY_CONFIG = os.getenv('LIGHT_CELERY_CONFIG', False) == 'True'

if not LIGHT_CELERY_CONFIG:
    from django.conf import settings

    BUILD_SIM_LOGS_DIR = settings.BUILD_SIM_LOGS_DIR
    BUILD_SIM_LOGS_ARCHIVE_DIR = str(settings.BUILD_SIM_LOGS_ARCHIVE_DIR)
    BUILD_SIM_LOGS_RETENTION_DAYS = settings.BUILD_SIM_LOGS_RETENTION_DAYS
    BUILD_SIM_LOGS_ARCHIVE_RETENTION_DAYS = settings.BUILD_SIM_LOGS_ARCHIVE_RETENTION_DAYS

    CELERY_BROKER_URL = settings.CELERY_BROKER_URL


def archive_logs(input_params: dict | None = None, test_input_params: dict | None = None) -> None:
    """Move and compress logs older than the parametrized retention period to the archive directory."""
    log_retention_date, logs_dir, logs_archive_dir = get_archive_logs_details(input_params, test_input_params)

    os.makedirs(logs_archive_dir, exist_ok=True)

    for log_file in os.listdir(logs_dir):
        # Skip files in use
        if 'LOCKED' in log_file:
            continue

        log_path = os.path.join(logs_dir, log_file)

        # Only process files (not directories)
        if os.path.isfile(log_path):
            # Get the file's last modification time
            file_mtime = datetime.fromtimestamp(os.path.getmtime(log_path))

            # Archive the file if it's older than the retention period
            if file_mtime < log_retention_date:
                archive_file(logs_archive_dir, log_file, log_path)


def get_archive_logs_details(
    input_params: dict | None = None, test_input_params: dict | None = None
) -> tuple[datetime, str, str]:
    now = datetime.now()

    if input_params and input_params['logs_type'] == 'build_sim':
        log_retention_date = now - timedelta(days=BUILD_SIM_LOGS_RETENTION_DAYS)
        return log_retention_date, BUILD_SIM_LOGS_DIR, BUILD_SIM_LOGS_ARCHIVE_DIR

    if test_input_params and test_input_params['logs_type'] == 'build_sim':
        log_retention_date = now
        logs_dir, logs_archive_dir, _ = get_test_log_archive_details(
            BUILD_SIM_LOGS_DIR, test_input_params['test_file_name']
        )
        return log_retention_date, logs_dir, logs_archive_dir

    raise ValueError('Invalid or missing logs type')


def get_test_log_archive_details(root_dir: str, test_file_name: str) -> tuple[str, str, str]:
    test_logs_dir = os.path.join(root_dir, 'testing', 'test_logs')
    test_logs_dir_archive = os.path.join(test_logs_dir, 'archive')
    test_file = os.path.join(test_logs_dir, test_file_name)

    return test_logs_dir, test_logs_dir_archive, test_file


def archive_file(logs_archive_dir: str, log_file: str, log_path: str,) -> None:
    archive_path = os.path.join(logs_archive_dir, log_file + '.gzip')

    # Compress the log file and copy it to the archive
    with open(log_path, 'rb') as f_in, gzip_open(archive_path, 'wb', compresslevel=9) as f_out:
        copyfileobj(f_in, f_out)

    # Delete the original log file after compressing
    remove_file(log_path)


def clean_old_archives(input_params: dict | None = None, test_input_params: dict | None = None) -> None:
    """Delete archived logs older than the parametrized retention period."""
    archive_retention_date, logs_archive_dir = get_clean_old_archives_details(input_params, test_input_params)

    for archive_file in os.listdir(logs_archive_dir):
        archive_path = os.path.join(logs_archive_dir, archive_file)

        # Only process files (not directories)
        if os.path.isfile(archive_path):
            file_mtime = datetime.fromtimestamp(os.path.getmtime(archive_path))

            if file_mtime < archive_retention_date:

                # Delete the old archive
                remove_file(archive_path)


def get_clean_old_archives_details(
    input_params: dict | None = None, test_input_params: dict | None = None
) -> tuple[datetime, str]:
    now = datetime.now()

    if input_params and input_params['logs_type'] == 'build_sim':
        archive_retention_date = now - timedelta(days=BUILD_SIM_LOGS_ARCHIVE_RETENTION_DAYS)
        return archive_retention_date, BUILD_SIM_LOGS_ARCHIVE_DIR

    if test_input_params and test_input_params['logs_type'] == 'build_sim':
        archive_retention_date = now
        _, logs_archive_dir, _ = get_test_log_archive_details(
            BUILD_SIM_LOGS_DIR, test_input_params['test_file_name']
        )
        return archive_retention_date, logs_archive_dir

    raise ValueError('Invalid or missing logs type')


def remove_file(file_path: str) -> None:
    if os.path.exists(file_path):
        retries = 0
        deletion_retry_delay = 0
        while retries < DELETION_RETRIES:
            try:
                os.remove(file_path)
                break
            except PermissionError:
                retries += 1
                deletion_retry_delay += 2
                print(f'Failed to delete {file_path} - access denied. Retrying...')
                sleep(deletion_retry_delay)


def log_error(
    error_type: str, error_message: str, error_traceback: str, request_info: dict = {}, error_id_prefix: str = ''
) -> str:
    """Log unexpected app errors sequentially, avoiding race conditions during log files updates."""
    from redis import Redis

    # Redis DB2 is used for persistent data
    redis_connection = Redis.from_url(CELERY_BROKER_URL)
    error_id = str(redis_connection.incr('unknown_errors_counter'))
    error_id_log = error_id_prefix + error_id

    logger = logging.getLogger(error_type)
    logger.error(
        error_message, extra={'traceback': error_traceback, 'request_info': request_info, 'error_id': error_id_log}
    )

    return error_id


def delete_unused_wall_configs(wall_config_hash_list: list = [], active_testing: bool = False) -> None:
    from celery import chain
    from django.conf import settings
    from django.db.models import Q

    from the_wall_api.models import WallConfig
    wall_config_deletion_task = import_wall_config_deletion_task(active_testing)

    CELERY_TASK_PRIORITY = settings.CELERY_TASK_PRIORITY

    collect_for_delete_query = Q(wall_config_references__isnull=True)
    if wall_config_hash_list:
        collect_for_delete_query &= Q(wall_config_hash__in=wall_config_hash_list)

    wall_config_objects_to_delete = WallConfig.objects.filter(collect_for_delete_query)

    if wall_config_objects_to_delete.count() > 0:
        task_chain = chain(
            wall_config_deletion_task.si(
                wall_config_hash=object_to_delete.wall_config_hash, active_testing=active_testing
            )    # type: ignore
            for object_to_delete in wall_config_objects_to_delete
        )
        # Avoid queue overflow - process the deletion tasks sequentially
        task_chain_result = task_chain.apply_async(priority=CELERY_TASK_PRIORITY['HIGH'])
        if task_chain_result is not None:
            while not task_chain_result.ready():
                sleep(1)


def import_wall_config_deletion_task(active_testing: bool = False):
    if not active_testing:
        from the_wall_api.tasks import wall_config_deletion_task
    else:
        from the_wall_api.tasks import wall_config_deletion_task_test as wall_config_deletion_task

    return wall_config_deletion_task


def orchestrate_wall_config_processing(
    wall_config_hash: str, wall_construction_config: list, sections_count: int,
    num_crews_range: int | str, username: str, config_id: str,
    active_testing: bool = False
) -> tuple[str, list]:
    """Cache in the DB all possible build simulations for the passed wall configuration."""
    def core_processing() -> tuple[str, list]:
        wall_config_object, task_group_result = create_task_group(
            wall_config_hash, wall_construction_config, sections_count,
            num_crews_range, username, config_id, active_testing
        )
        return monitor_task_group(
            wall_config_object, task_group_result, num_crews_range, username, config_id
        )

    return execute_core_task_logic_with_error_handling(core_processing)


def create_task_group(
    wall_config_hash: str, wall_construction_config: list, sections_count: int,
    num_crews_range: int | str, username: str, reference_config_id: str,
    active_testing: bool
):
    """Start a separate task for wall build simulation for each included number of crews."""
    from celery import group
    from django.conf import settings
    from django.db import transaction

    from the_wall_api.models import (
        WallConfig, WallConfigReference, WallConfigReferenceStatusEnum, WallConfigStatusEnum
    )
    from the_wall_api.tasks import log_error_task
    create_wall_task = import_wall_task(active_testing)

    CELERY_TASK_PRIORITY = settings.CELERY_TASK_PRIORITY

    # Set CELERY_CALCULATION status to indicate the start of the calculation process
    with transaction.atomic():
        wall_config_object = execute_db_query_with_retries(
            lambda: WallConfig.objects.select_for_update().get(wall_config_hash=wall_config_hash)
        )

        wall_config_reference = execute_db_query_with_retries(
            lambda: WallConfigReference.objects.select_for_update().get(
                user__username=username, config_id=reference_config_id
            )
        )

        if wall_config_object.status not in [
            WallConfigStatusEnum.INITIALIZED,
            WallConfigStatusEnum.PARTIALLY_CALCULATED
        ]:
            error_message = f'Not processed, current status: {wall_config_object.status}.'
            log_error_task.delay('celery_tasks', error_message, error_traceback=[])  # type: ignore
            return error_message, []

        if wall_config_object.deletion_initiated:
            return 'Not processed, deletion initiated by another process.', []

        wall_config_object.status = WallConfigStatusEnum.CELERY_CALCULATION
        wall_config_object.save()

        wall_config_reference.status = WallConfigReferenceStatusEnum.CELERY_CALCULATION
        wall_config_reference.save()

    if num_crews_range == 'full-range':
        num_crews_list = [num_crews for num_crews in range(sections_count)]
    else:
        num_crews_list = [num_crews_range]
    task_group = group(
        # num_crews = max sections count is effectively sequential mode (num_crews = 0)
        create_wall_task.s(
            num_crews, wall_config_hash, wall_construction_config, sections_count, active_testing
        ) for num_crews in num_crews_list    # type: ignore
    )
    task_group_result = task_group.apply_async(priority=CELERY_TASK_PRIORITY['LOW'])

    return wall_config_object, task_group_result


def execute_db_query_with_retries(query_callable: Callable):
    """Helper function to avoid DB errors due to DB commit latency."""
    from the_wall_api.models import WallConfig

    retries = 5
    while True:
        try:
            return query_callable()
        except WallConfig.DoesNotExist:
            retries -= 1
            if retries <= 0:
                raise
            else:
                sleep(0.5)


def monitor_task_group(
    wall_config_object, task_group_result, num_crews_range: int | str, username: str, config_id: str
) -> tuple[str, list]:
    """Monitor for task group completion or abort if deletion is initiated."""
    if not task_group_result:
        result = wall_config_object if isinstance(wall_config_object, str) else 'Task group initialization error.'
        return result, []

    while True:
        if task_group_result.ready():
            # All tasks from the group have either finished successfully,
            # have failed or have been aborted
            return finalize_wall_config(
                wall_config_object, task_group_result, num_crews_range, username, config_id
            )

        execute_db_query_with_retries(
            lambda: wall_config_object.refresh_from_db()
        )
        if wall_config_object.deletion_initiated:
            # Deletion initiated
            abort_task_group(task_group_result)

        sleep(1)


def finalize_wall_config(
    wall_config_object, task_group_result, num_crews_range: int | str, username: str, config_id: str
) -> tuple[str, list]:
    """Evaluate and set the final status for the wall config object, based on the task group results."""
    from the_wall_api.models import WallConfigStatusEnum
    from the_wall_api.utils.error_utils import send_log_error_async

    task_group_result_value_list = []
    try:
        task_group_result_message_list = collect_task_group_results(
            task_group_result, task_group_result_value_list
        )

        wall_config_object_status = process_wall_config_object_status(
            wall_config_object, task_group_result, task_group_result_message_list, num_crews_range,
            username, config_id
        )

        if wall_config_object_status == WallConfigStatusEnum.ERROR:
            error_result = send_log_error_async(
                'celery_tasks', error_message='Wall creation task group failed - check error logs.'
            )
            return error_result, task_group_result_value_list

        if wall_config_object_status == WallConfigStatusEnum.READY_FOR_DELETION:
            return 'Interrupted by a deletion task', task_group_result_value_list

    except Exception as unknwn_err:
        error_result = send_log_error_async('celery_tasks', error=unknwn_err)
        return error_result, task_group_result_value_list

    return 'OK', task_group_result_value_list


def collect_task_group_results(task_group_result, task_group_result_value_list) -> list:
    task_group_result_message_list = []
    for task_result in task_group_result.results:
        if task_result.result is not None:
            task_group_result_message_list.append(task_result.result[0])
            task_group_result_value_list.append(task_result.result[1])
        else:
            task_group_result_message_list.append('TASK_ABORTED_BEFORE_START')

    return task_group_result_message_list


def process_wall_config_object_status(
    wall_config_object, task_group_result, task_group_result_message_list: list, num_crews_range: int | str,
    username: str, config_id: str
) -> str:
    """
    Set the final statuses for the wall config object and the source wall config reference,
    based on the task group results.
    """
    from django.db import transaction
    from the_wall_api.models import (
        WallConfig, WallConfigReference, WallConfigReferenceStatusEnum, WallConfigStatusEnum
    )

    with transaction.atomic():
        # Lock the wall config object for a final status set
        wall_config_object = WallConfig.objects.select_for_update().get(wall_config_hash=wall_config_object.wall_config_hash)
        if wall_config_object.deletion_initiated:
            wall_config_object.status = WallConfigStatusEnum.READY_FOR_DELETION

        else:
            final_status = WallConfigStatusEnum.ERROR
            if wall_config_object.status == WallConfigStatusEnum.CELERY_CALCULATION and task_group_result.successful():
                # All wall creation task results are consistent
                if all(result_message == 'OK' for result_message in task_group_result_message_list):
                    if num_crews_range == 'full-range':
                        final_status = WallConfigStatusEnum.CALCULATED
                    else:
                        final_status = WallConfigStatusEnum.PARTIALLY_CALCULATED

            if wall_config_object.status != final_status:
                wall_config_object.status = final_status

        wall_config_object.save()

        wall_config_reference = WallConfigReference.objects.select_for_update().get(
            user__username=username, config_id=config_id
        )

        wall_config_reference.status = WallConfigReferenceStatusEnum.AVAILABLE
        wall_config_reference.save()

    return wall_config_object.status


def abort_task_group(task_group_result) -> None:
    for abortable_task_result in task_group_result.results:
        abortable_task_result.abort()
    abort_started_time = time()
    while not task_group_result.ready():
        if time() - abort_started_time > ABORT_WAIT_PERIOD:
            raise_timeout_error()
        sleep(1)


def raise_timeout_error() -> None:
    error_message = (
        f'Revocation of create wall tasks due to deletion '
        f'initiation takes more than {ABORT_WAIT_PERIOD} seconds.'
    )
    raise TimeoutError(error_message)


def import_wall_task(active_testing: bool):
    if not active_testing:
        from the_wall_api.tasks import create_wall_task
    else:
        from the_wall_api.tasks import create_wall_task_test as create_wall_task
    return create_wall_task


def execute_core_task_logic_with_error_handling(func: Callable, *args, **kwargs) -> tuple[str, list]:
    """Executes a function with standardized error handling."""
    from django.db.utils import OperationalError
    from the_wall_api.models import WallConfig
    from the_wall_api.utils.error_utils import send_log_error_async

    try:
        return func(*args, **kwargs)
    except OperationalError as oprtnl_err:
        return send_log_error_async('celery_tasks', error=oprtnl_err), []
    except WallConfig.DoesNotExist as not_exst_err:
        return send_log_error_async('celery_tasks', error=not_exst_err), []
    except Exception as unknwn_err:
        return send_log_error_async('celery_tasks', error=unknwn_err), []


def create_wall(
    celery_task, num_crews: int, wall_config_hash: str, wall_construction_config: list,
    sections_count: int, active_testing: bool = False
) -> tuple[str, dict]:
    from the_wall_api.utils.error_utils import send_log_error_async
    from the_wall_api.utils.storage_utils import fetch_wall_data
    from the_wall_api.wall_construction import initialize_wall_data

    wall_data = initialize_wall_data(profile_id=None, day=None, request_num_crews=num_crews)

    # Add the precalculated wall details, to avoid double calculations
    wall_data['celery_task'] = celery_task
    wall_data['wall_config_hash'] = wall_config_hash
    wall_data['wall_construction_config'] = wall_construction_config
    wall_data['sections_count'] = sections_count

    result_wall_data = {}
    try:
        fetch_wall_data(wall_data, num_crews, profile_id=None, request_type='create_wall_task')
        if wall_data['error_response']:
            raise Exception(wall_data['error_response'].data.get('error'))
    except Exception as cmpttn_err:
        return send_log_error_async('celery_tasks', cmpttn_err), result_wall_data
    else:
        celery_task_aborted = wall_data.get('celery_task_aborted')
        if celery_task_aborted is not None:
            return celery_task_aborted, result_wall_data

        if active_testing:
            if wall_data.get('wall_construction'):
                celery_sim_calc_details = wall_data['wall_construction'].wall_profile_data['profiles_overview']
            elif wall_data.get('cached_result'):
                celery_sim_calc_details = 'cached_result'
            else:
                celery_sim_calc_details = None
            result_wall_data = {
                'num_crews': num_crews,
                'celery_sim_calc_details': celery_sim_calc_details,
            }

    return 'OK', result_wall_data


def wall_config_deletion(wall_config_hash: str, active_testing: bool = False) -> tuple[str, list]:
    from the_wall_api.models import WallConfig

    def core_deletion() -> tuple[str, list]:
        wall_config_object = init_wall_config_deletion(wall_config_hash, active_testing)
        if not isinstance(wall_config_object, WallConfig):
            return wall_config_object, []
        return wall_config_delete(wall_config_object)

    return execute_core_task_logic_with_error_handling(core_deletion)


def init_wall_config_deletion(wall_config_hash: str, active_testing: bool):
    """Set the flag initiating the deletion of the wall config object."""
    from time import sleep
    from django.db import transaction
    from the_wall_api.models import WallConfig

    with transaction.atomic():
        wall_config_object = WallConfig.objects.select_for_update().get(wall_config_hash=wall_config_hash)
        if wall_config_object.deletion_initiated:
            return 'Deletion already initiated by another process.'
        wall_config_object.deletion_initiated = True
        wall_config_object.save()
        if active_testing:
            # Ensure proper simulation of race conditions
            sleep(1)

    return wall_config_object


def wall_config_delete(wall_config_object) -> tuple[str, list]:
    """After confirming that the wall config object is not used by any other process, delete it."""
    from django.db import transaction
    from the_wall_api.models import WallConfig, WallConfigStatusEnum
    from the_wall_api.utils.error_utils import send_log_error_async

    abort_started_time = time()
    while True:
        if time() - abort_started_time > ABORT_WAIT_PERIOD:
            raise_timeout_error()

        # This could theoretically be blocked but only for a short time -
        # - in orchestrate_wall_config_processing_task during finalize_wall_config
        wall_config_object.refresh_from_db()
        try:
            with transaction.atomic():
                wall_config_object = WallConfig.objects.select_for_update().get(wall_config_hash=wall_config_object.wall_config_hash)
                if wall_config_object.status in [
                    WallConfigStatusEnum.INITIALIZED,
                    WallConfigStatusEnum.READY_FOR_DELETION,
                    WallConfigStatusEnum.PARTIALLY_CALCULATED,
                    WallConfigStatusEnum.CALCULATED
                ]:
                    wall_config_object.delete()
                    break
        except Exception as unknwn_err:
            return send_log_error_async('celery_tasks', error=unknwn_err), []

        sleep(1)

    return 'OK', []
