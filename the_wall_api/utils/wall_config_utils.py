# Wall configuration loading and config hashing
from decimal import Decimal
import hashlib
import json
from typing import Dict, Any

from django.conf import settings
from rest_framework import status

from the_wall_api.models import WallConfigReference
from the_wall_api.utils.error_utils import (
    create_out_of_range_response, handle_not_existing_file_references, handle_known_error,
    WallConstructionError, get_request_params
)

SEQUENTIAL = 'sequential'
CONCURRENT = 'concurrent'
INVALID_WALL_CONFIG_MSG = 'Invalid wall configuration!'
MAX_WALL_PROFILE_SECTIONS = settings.MAX_WALL_PROFILE_SECTIONS
MAX_SECTION_HEIGHT = settings.MAX_SECTION_HEIGHT
MAX_WALL_LENGTH = settings.MAX_WALL_LENGTH
COST_ROUNDING = Decimal('.01')


def get_wall_construction_config(wall_data: Dict[str, Any], profile_id: int | None) -> list:
    try:
        wall_config_reference = WallConfigReference.objects.get(
            user=wall_data['request_user'], config_id=wall_data['request_config_id']
        )
        wall_construction_config = wall_config_reference.wall_config.wall_construction_config
        wall_data['wall_config_object_status'] = wall_config_reference.wall_config.status
        wall_data['wall_construction_config'] = wall_construction_config
        wall_data['wall_config_reference'] = wall_config_reference
    except WallConfigReference.DoesNotExist:
        handle_not_existing_file_references(wall_data)
        return []

    # Validate the profile number if provided
    max_profile_number = len(wall_construction_config)
    if profile_id is not None and profile_id > max_profile_number:
        request_params = get_request_params(wall_data)
        wall_data['error_response'] = create_out_of_range_response(
            'profile number', max_profile_number, request_params, status.HTTP_400_BAD_REQUEST
        )
        return []

    return wall_construction_config


def validate_wall_config_file_data(wall_data: Dict[str, Any]) -> None:
    try:
        validate_wall_config_format(wall_data['initial_wall_construction_config'], INVALID_WALL_CONFIG_MSG)
    except Exception as wall_config_err:
        handle_known_error(wall_data, 'wall_configuration', str(wall_config_err), status.HTTP_400_BAD_REQUEST)


def validate_wall_config_format(wall_config_file_data: list, invalid_wall_config_msg: str) -> None:
    from the_wall_api.wall_construction import get_sections_count

    if not isinstance(wall_config_file_data, list):
        raise WallConstructionError(f'{invalid_wall_config_msg} Must be a nested list of lists of integers.')

    if any(not isinstance(profile, list) for profile in wall_config_file_data):
        raise WallConstructionError(f'{invalid_wall_config_msg} Each profile must be a list of integers.')

    sections_count = get_sections_count(wall_config_file_data)

    if sections_count > MAX_WALL_PROFILE_SECTIONS * MAX_WALL_LENGTH:
        raise WallConstructionError(
            f'{invalid_wall_config_msg} The maximum number of sections '
            f'({MAX_WALL_PROFILE_SECTIONS * MAX_WALL_LENGTH}) has been exceeded.'
        )

    for profile_id, profile in enumerate(wall_config_file_data, start=1):
        for section_number, section_height in enumerate(profile, start=1):
            error_message_suffix = None
            if not isinstance(section_height, int):
                error_message_suffix = 'an integer'

            if not error_message_suffix and section_height > MAX_SECTION_HEIGHT:
                error_message_suffix = f'<= {MAX_SECTION_HEIGHT}'

            if not error_message_suffix and section_height < 0:
                error_message_suffix = '>= 0'

            if error_message_suffix:
                raise WallConstructionError(
                    f"{invalid_wall_config_msg} The section height '{section_height}' of "
                    f'profile {profile_id} - section {section_number} must be {error_message_suffix}.'
                )


def generate_config_hash_details(wall_construction_config: list) -> dict:
    """
    Generates a unique hash for the entire wall configuration,
    taking into account the number of crews.
    """
    result: Dict[str, Any] = {'profile_config_hash_data': {}}

    # Hash of the whole config
    result['wall_config_hash'] = hash_calc(wall_construction_config)

    for profile_id, profile_config in enumerate(wall_construction_config, start=1):
        # Hash each profile config
        result['profile_config_hash_data'][profile_id] = hash_calc(profile_config)

    return result


def hash_calc(data_to_hash: Any) -> str:
    config_str = json.dumps(data_to_hash)
    return hashlib.sha256(config_str.encode('utf-8')).hexdigest()
