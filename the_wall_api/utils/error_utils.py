# Error handling utilities

from time import sleep
from traceback import format_exception
from typing import Any, Dict

from rest_framework.response import Response
from rest_framework import status

from the_wall_api.models import Wall, WallProfileProgress
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


def create_technical_error_response(request_params: Dict[str, Any], error_id: str, error_message: str) -> Response:
    error_msg = 'Wall Construction simulation failed. Please contact support.'
    error_response: Dict[str, Any] = {'error': error_msg}

    error_details: Dict[str, Any] = {}

    if request_params:
        error_details['request_params'] = request_params

    error_details['error_id'] = error_id

    error_details['tech_info'] = error_message

    error_response['error_details'] = error_details
    return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def handle_unknown_error(wall_data: Dict[str, Any], unknwn_err: Exception, error_type: str) -> None:
    request_params = get_request_params(wall_data)
    request_info = {
        'request_type': wall_data.get('request_type', 'root'),
        'request_params': request_params
    }

    error_traceback = extract_error_traceback(unknwn_err)
    error_message = f'{unknwn_err.__class__.__name__}: {str(unknwn_err)}'

    task_result = log_error_task.delay(error_type, error_message, error_traceback, request_info=request_info)  # type: ignore
    error_id = get_error_id_from_task_result(task_result)
    wall_data['error_response'] = create_technical_error_response(request_params, error_id, error_message)


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


def check_if_cached_on_another_day(wall_data: Dict[str, Any], profile_id: int) -> None:
    """
    In CONCURRENT mode there are days without profile daily ice usage,
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
        raise WallProfileProgress.DoesNotExist


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

    for param in ['request_profile_id', 'request_day', 'request_num_crews']:
        val = wall_data.get(param)
        if val is not None:
            param = param.replace('request_', '')
            request_params[param] = val

    return request_params
