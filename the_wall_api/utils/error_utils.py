# Error handling utilities

from typing import Any, Dict

from django.db import IntegrityError
from rest_framework.response import Response
from rest_framework import status

from the_wall_api.models import Wall, WallProfileProgress


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


def create_technical_error_response(request_params: Dict[str, Any], tech_error: Exception | None = None) -> Response:
    error_msg = 'Wall Construction simulation failed. Please contact support.'
    error_response: Dict[str, Any] = {'error': error_msg}

    error_details: Dict[str, Any] = {}

    if request_params:
        error_details['request_params'] = request_params
    if tech_error:
        error_details['tech_info'] = f'{tech_error.__class__.__name__}: {str(tech_error)}'

    error_response['error_details'] = error_details
    return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def handle_wall_crtn_integrity_error(wall_data: Dict[str, Any], wall_crtn_intgrty_err: IntegrityError) -> None:
    """Handle known integrity errors, such as hash collisions."""
    request_params = get_request_params(wall_data)
    if (
        wall_data['num_crews'] == 0 and
        'unique constraint' in str(wall_crtn_intgrty_err) and
        'wall_config_hash' in str(wall_crtn_intgrty_err)
    ):
        # Hash collision - should be a very rare case
        wall_data['error_response'] = create_technical_error_response(request_params, wall_crtn_intgrty_err)
    else:
        log_error_to_db(wall_crtn_intgrty_err)


def handle_unknown_error(wall_data: Dict[str, Any], wall_crtn_unkwn_err: Exception) -> None:
    request_params = get_request_params(wall_data)
    log_error_to_db(wall_crtn_unkwn_err)
    wall_data['error_response'] = create_technical_error_response(request_params, wall_crtn_unkwn_err)


def log_error_to_db(error: Exception) -> None:
    pass


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
