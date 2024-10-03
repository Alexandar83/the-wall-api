from typing import Any, Dict

from django.db import IntegrityError
from rest_framework.response import Response
from rest_framework import status

from the_wall_api.models import Wall, WallProfileProgress


class WallConstructionError(ValueError):
    pass


def create_out_of_range_response(out_of_range_type: str, max_value: int | Any, status_code: int) -> Response:
    if out_of_range_type == 'day':
        finishing_msg = f'The wall has been finished for {max_value} days.'
    else:
        finishing_msg = f'The wall has {max_value} profiles.'
    response_details = {'error': f'The {out_of_range_type} is out of range. {finishing_msg}'}
    return Response(response_details, status=status_code)


def create_technical_error_response(tech_error: Exception | None = None, request_data: Dict[str, Any] = {}) -> Response:
    error_details: Dict[str, Any] = {}
    if tech_error:
        error_details = {'tech_info': f'{tech_error.__class__.__name__}: {str(tech_error)}'}
        if request_data:
            error_details['request_data'] = request_data
    error_msg = 'Wall Construction simulation failed. Please contact support.'
    error_response: Dict[str, Any] = {'error': error_msg}
    if error_details:
        error_response['error_details'] = error_details
    return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def handle_wall_crtn_integrity_error(wall_data: Dict[str, Any], wall_crtn_intgrty_err: IntegrityError) -> None:
    """Handle known integrity errors, such as hash collisions."""
    if (
        wall_data['num_crews'] == 0 and
        'unique constraint' in str(wall_crtn_intgrty_err) and
        'wall_config_hash' in str(wall_crtn_intgrty_err)
    ):
        # Hash collision - should be a very rare case
        wall_data['error_response'] = create_technical_error_response(wall_crtn_intgrty_err)
    else:
        log_error_to_db(wall_crtn_intgrty_err)


def handle_unknown_error(wall_data: Dict[str, Any], wall_crtn_unkwn_err: Exception) -> None:
    log_error_to_db(wall_crtn_unkwn_err)
    wall_data['error_response'] = create_technical_error_response(wall_crtn_unkwn_err)


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
    if wall_data['request_day'] <= wall_construction_days:
        response_details = f'No crew has worked on profile {profile_id} on day {wall_data["request_day"]}.'
        wall_data['error_response'] = Response(response_details, status=status.HTTP_404_NOT_FOUND)
    else:
        wall_data['error_response'] = create_out_of_range_response(
            'day', wall_construction_days, status.HTTP_400_BAD_REQUEST
        )
