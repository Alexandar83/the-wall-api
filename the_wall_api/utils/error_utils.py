# Error handling utilities

from time import sleep
from traceback import format_exception
from typing import Any, Dict

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Q, QuerySet
from rest_framework.response import Response
from rest_framework import status

from the_wall_api.utils.api_utils import handle_being_processed
from the_wall_api.models import (
    Wall, WallConfig, WallProgress, WallConfigReference, WallConfigStatusEnum
)
from the_wall_api.tasks import log_error_task

TASK_RESULT_RETRIES = 3
TASK_RESULT_RETRY_DELAY = 1


class WallConstructionError(ValueError):
    pass


def create_out_of_range_response(
    out_of_range_type: str, max_value: int | Any, request_params: Dict[str, Any], status_code: int
) -> Response:
    if out_of_range_type == 'day':
        finishing_msg = f'The wall has been finished for {max_value} days.'
    else:
        finishing_msg = f'The wall has {max_value} profiles.'
    response_details = {
        'error': f'The {out_of_range_type} is out of range. {finishing_msg}',
        'error_details': {
            'request_params': request_params
        }
    }
    return Response(response_details, status=status_code)


def create_technical_error_response(
    wall_data: Dict[str, Any], request_params: Dict[str, Any], error_id: str, error_message: str
) -> Response:
    if wall_data.get('request_type') == 'wallconfig-files/upload':
        error_msg_source = 'config file upload'
    elif wall_data.get('request_type') == 'wallconfig-files/delete':
        error_msg_source = 'config file delete'
    else:
        error_msg_source = 'construction simulation'
    error_msg = f'Wall {error_msg_source} failed. Please contact support.'

    error_response: Dict[str, Any] = {'error': error_msg}

    error_details: Dict[str, Any] = {}

    if request_params:
        error_details['request_params'] = request_params

    error_details['error_id'] = error_id

    error_details['tech_info'] = error_message

    error_response['error_details'] = error_details
    return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def handle_unknown_error(wall_data: Dict[str, Any], unknwn_err: Exception | str, error_type: str) -> None:
    """Unknown exception - handle logging and response."""
    request_params, request_info, error_message, error_traceback = get_log_error_task_params(wall_data, unknwn_err)

    task_result = log_error_task.delay(error_type, error_message, error_traceback, request_info=request_info)  # type: ignore
    error_id = get_error_id_from_task_result(task_result)
    wall_data['error_response'] = create_technical_error_response(
        wall_data, request_params, error_id, error_message
    )


def get_log_error_task_params(
    wall_data: Dict[str, Any], unknwn_err: Exception | str
) -> tuple[Dict[str, Any], Dict[str, Any], str, list[str]]:
    request_params = get_request_params(wall_data)
    request_info = get_request_info(wall_data, request_params)

    if isinstance(unknwn_err, Exception):
        error_traceback = extract_error_traceback(unknwn_err)
        error_message = f'{unknwn_err.__class__.__name__}: {str(unknwn_err)}'
    else:
        error_traceback = []
        error_message = unknwn_err

    return request_params, request_info, error_message, error_traceback


def get_request_info(wall_data, request_params) -> Dict[str, Any]:
    user = wall_data.get('request_user')
    username = user.username if user else None
    request_type = wall_data.get('request_type', 'root')
    if settings.ACTIVE_TESTING:
        request_type = f'test_suite_{request_type}'
    request_info = {
        'request_type': request_type,
        'request_params': request_params
    }
    if username:
        request_info['request_user'] = username

    return request_info


def extract_error_traceback(error: Exception) -> list[str]:
    """Transform the error traceback in a list of strings."""
    formatted_err_traceback = format_exception(error.__class__, error, error.__traceback__)

    cleaned_traceback = []

    for line in formatted_err_traceback:
        line = line.strip(' \n')

        split_strings = line.split('\n')

        for sub_string in split_strings:
            sub_str = sub_string.strip()
            cleaned_traceback.append(sub_str)

    return cleaned_traceback


def get_error_id_from_task_result(task_result) -> str:
    error_id = 'N/A'

    retries = 0
    while retries < TASK_RESULT_RETRIES:
        if task_result.ready():
            error_id = task_result.result
            break
        else:
            retries += 1
            sleep(TASK_RESULT_RETRY_DELAY)

    return error_id


def handle_known_error(wall_data: Dict[str, Any], error_type: str, error_message: str, http_status: int) -> None:
    """Known inconsistencies - handle logging and response."""
    request_params = get_request_params(wall_data)
    request_info = get_request_info(wall_data, request_params)
    error_id_prefix = wall_data.get('test_data', {}).get('error_id_prefix', '')
    task_result = log_error_task.delay(
        error_type, error_message, error_traceback=[], request_info=request_info, error_id_prefix=error_id_prefix
    )  # type: ignore
    error_id = get_error_id_from_task_result(task_result)

    error_response_data = {
        'error': error_message,
        'error_details': {
            'request_params': request_params,
            'error_id': error_id
        }
    }

    wall_data['error_response'] = Response(error_response_data, status=http_status)


def send_log_error_async(
    error_type: str, error: Exception | None = None, error_message: str = '', request_info: dict = {}
) -> str:
    """Log error details asynchronously."""
    if error is not None:
        error_message_out = f'{error.__class__.__name__}: {str(error)}'
        error_traceback = extract_error_traceback(error)
    else:
        error_message_out = ''
        error_traceback = []

    if error_message:
        error_message_out = error_message

    log_error_task.delay(error_type, error_message_out, error_traceback, request_info)    # type: ignore

    return error_message_out


def check_if_cached_on_another_day(wall_data: Dict[str, Any], profile_id: int) -> None:
    """
    In CONCURRENT mode there are days without wall progress,
    because there was no crew assigned on the profile.
    Check for other cached daily progress to avoid processing of
    an already cached simulation.
    """
    try:
        wall = Wall.objects.get(
            wall_config_hash=wall_data['wall_config_hash'],
            num_crews=wall_data['num_crews'],
        )
        wall_construction_days = wall.construction_days
        check_wall_construction_days(wall_construction_days, wall_data, profile_id)
    except Wall.DoesNotExist:
        raise WallProgress.DoesNotExist


def check_wall_construction_days(wall_construction_days: int, wall_data: Dict[str, Any], profile_id):
    """
    Handle erroneous construction days related responses.
    """
    request_params = get_request_params(wall_data)
    if wall_data['request_day'] <= wall_construction_days:
        response_details = {
            'error': f'No crew has worked on profile {profile_id} on day {wall_data["request_day"]}.',
            'error_details': {
                'request_params': request_params
            }
        }
        wall_data['error_response'] = Response(response_details, status=status.HTTP_404_NOT_FOUND)
    else:
        wall_data['error_response'] = create_out_of_range_response(
            'day', wall_construction_days, request_params, status.HTTP_400_BAD_REQUEST
        )


def validate_day_within_range(wall_data: Dict[str, Any]) -> None:
    """
    Compare the day from the request (if provided and the max day in the simulation).
    """
    request_params = get_request_params(wall_data)
    construction_days = wall_data['sim_calc_details']['construction_days']
    if wall_data['request_day'] is not None and wall_data['request_day'] > construction_days:
        wall_data['error_response'] = create_out_of_range_response(
            'day', construction_days, request_params, status.HTTP_400_BAD_REQUEST
        )


def get_request_params(wall_data: Dict[str, Any]) -> Dict[str, Any]:
    request_params = {}

    if wall_data.get('request_type') == 'wallconfig-files/upload':
        param_list = ['request_config_id']
    else:
        param_list = ['request_profile_id', 'request_day', 'request_num_crews', 'request_config_id']

    for param in param_list:
        val = wall_data.get(param)
        if val is not None:
            param = param.replace('request_', '')
            request_params[param] = val

    return request_params


def handle_wall_config_deletion_in_progress(wall_data: Dict[str, Any]) -> None:
    error_response_data = {
        'error': 'A deletion of an existing wall config is being processed - please try again later.'
    }
    wall_data['error_response'] = Response(
        error_response_data,
        status=status.HTTP_503_SERVICE_UNAVAILABLE
    )


def handle_not_existing_file_references(wall_data: Dict[str, Any]) -> None:
    user = wall_data['request_user']

    if wall_data.get('request_type') == 'wallconfig-files/delete':
        config_id_list = wall_data['request_config_id_list']

        wall_config_ref_query = Q(user=user)
        if config_id_list:
            wall_config_ref_query &= Q(config_id__in=config_id_list)
        references_queryset = WallConfigReference.objects.filter(wall_config_ref_query)

        handle_not_existing_file_references_delete(wall_data, references_queryset, user, config_id_list)

    else:
        # Profiles endpoints
        config_id = wall_data['request_config_id']
        error_message = f"File with config ID '{config_id}' does not exist for user '{user.username}'."
        wall_data['error_response'] = Response({'error': error_message}, status=status.HTTP_404_NOT_FOUND)


def handle_not_existing_file_references_delete(
    wall_data: Dict[str, Any], references_queryset: QuerySet, user: User,
    config_id_list: list | None
) -> None:
    """Manages the response for the wallconfig-files/delete endpoint."""
    wall_data['deletion_queryset'] = references_queryset
    validated_ids = set(references_queryset.values_list('config_id', flat=True))

    if not validated_ids:
        # No wall config references exist for the user
        error_message = (
            f"No files exist for user '{user.username}' in the database."
            if not config_id_list
            else f"No matching files for user '{user.username}' exist for the provided config ID list."
        )
        wall_data['error_response'] = Response({'error': error_message}, status=status.HTTP_404_NOT_FOUND)
        return

    if config_id_list:
        not_found_ids = [
            config_id for config_id in config_id_list if config_id not in validated_ids
        ]
        if not_found_ids:
            # Some of the provided config IDs do not exist
            plrl_suffix = 's' if len(not_found_ids) > 1 else ''
            error_message = f"File{plrl_suffix} with config ID{plrl_suffix} {str(not_found_ids)} not found for user '{user.username}'."
            wall_data['error_response'] = Response({'error': error_message}, status=status.HTTP_404_NOT_FOUND)


def handle_cache_not_found(wall_data: Dict[str, Any]) -> None:
    if wall_data['wall_config_object_status'] in [
        WallConfigStatusEnum.INITIALIZED,
        WallConfigStatusEnum.PARTIALLY_CALCULATED
    ]:
        # Non-full-range case - proceed with single num_crews calculation
        return

    if wall_data['wall_config_object_status'] == WallConfigStatusEnum.CELERY_CALCULATION:
        # The calculation is being processed
        handle_being_processed(wall_data)
        return

    # Statuses: CALCULATED, ERROR, READY_FOR_DELETION
    # Conflicting case
    status_label = WallConfigStatusEnum(wall_data['wall_config_object_status']).label
    error_message = f"The resource is not found. Wall configuration status = '{status_label}'"
    handle_known_error(wall_data, 'caching', error_message, status.HTTP_409_CONFLICT)


def handle_wall_config_object_already_exists(wall_data: Dict[str, Any], wall_config_object: WallConfig) -> None:
    """Return an error if already uploaded by the current user"""
    if wall_data.get('request_type') == 'wallconfig-files/upload':

        error_message_suffix = ''
        if wall_config_object.status in [
            WallConfigStatusEnum.ERROR, WallConfigStatusEnum.READY_FOR_DELETION
        ]:
            status_label = WallConfigStatusEnum(wall_data['wall_config_object_status']).label
            error_message_suffix = f" Wall configuration status = '{status_label}'"

        reference = WallConfigReference.objects.filter(
            user=wall_data['request_user'], wall_config=wall_config_object
        ).first()
        if reference is not None:
            error_message = f"This wall configuration is already uploaded with config_id = '{reference.config_id}'.{error_message_suffix}"
            handle_known_error(
                wall_data, 'caching', error_message, status.HTTP_400_BAD_REQUEST
            )


def handle_user_task_in_progress_exists(user_tasks_in_progress: list[str], wall_data: Dict[str, Any]) -> None:
    error_message = (
        'The following config IDs have calculations in progress for this user: '
        f'{user_tasks_in_progress}. Please wait until they are completed.'
    )
    handle_known_error(wall_data, 'caching', error_message, status.HTTP_409_CONFLICT)
