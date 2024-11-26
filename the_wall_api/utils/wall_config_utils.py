# Wall configuration loading and config hashing
from decimal import Decimal
import hashlib
import json
from typing import Dict, Any

from django.conf import settings
from rest_framework import status

from the_wall_api.utils.error_utils import (
    create_out_of_range_response, handle_unknown_error, WallConstructionError, get_request_params
)

SEQUENTIAL = 'sequential'
CONCURRENT = 'concurrent'
INVALID_WALL_CONFIG_MSG = 'Invalid wall configuration file!'
MAX_WALL_PROFILE_SECTIONS = settings.MAX_WALL_PROFILE_SECTIONS
MAX_SECTION_HEIGHT = settings.MAX_SECTION_HEIGHT
MAX_WALL_LENGTH = settings.MAX_WALL_LENGTH
COST_ROUNDING = Decimal('.01')


def get_wall_construction_config(wall_data: Dict[str, Any], profile_id: int | None) -> list:
    try:
        wall_construction_config = load_wall_profiles_from_config()
    except (WallConstructionError, FileNotFoundError) as tech_error:
        handle_unknown_error(wall_data, tech_error, 'wall_configuration')
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


def load_wall_profiles_from_config() -> list:
    result = []

    try:
        with open(settings.WALL_CONFIG_PATH, 'r') as file:
            result = json.load(file)
    except (json.JSONDecodeError, FileNotFoundError):
        raise WallConstructionError(INVALID_WALL_CONFIG_MSG)

    validate_wall_config_format(result, INVALID_WALL_CONFIG_MSG)

    return result


def validate_wall_config_file_data(wall_data: Dict[str, Any]) -> None:
    try:
        validate_wall_config_format(wall_data['initial_wall_construction_config'], INVALID_WALL_CONFIG_MSG)
    except Exception as wall_config_err:
        handle_unknown_error(wall_data, wall_config_err, 'wall_configuration')


def validate_wall_config_format(wall_config_file_data: list, invalid_wall_config_msg: str) -> None:
    if not isinstance(wall_config_file_data, list):
        raise WallConstructionError(f'{invalid_wall_config_msg} Must be a list of nested lists of integers.')

    if len(wall_config_file_data) > MAX_WALL_LENGTH:
        raise WallConstructionError(f'The loaded wall config exceeds the maximum wall length of {MAX_WALL_LENGTH}.')

    for profile in wall_config_file_data:
        if not isinstance(profile, list):
            raise WallConstructionError(f'{invalid_wall_config_msg} The data in each profile must be a list of integers.')

        if len(profile) > MAX_WALL_PROFILE_SECTIONS:
            raise WallConstructionError(
                f'Wall config profile({profile}) exceeds the maximum number of sections of {MAX_WALL_PROFILE_SECTIONS}.'
            )

        for section_number, section_height in enumerate(profile, start=1):
            if not isinstance(section_height, int):
                raise WallConstructionError(f'{invalid_wall_config_msg} The data in each profile must be a list of integers.')

            if section_height > MAX_SECTION_HEIGHT:
                raise WallConstructionError(
                    f'Wall config profile({profile}) section({section_number}) '
                    f'height exceeds the maximum section height of {MAX_SECTION_HEIGHT}.'
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
