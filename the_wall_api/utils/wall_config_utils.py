# Wall configuration loading and config hashing

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
MAX_LENGTH = settings.MAX_LENGTH
MAX_HEIGHT = settings.MAX_HEIGHT


def get_wall_construction_config(wall_data: Dict[str, Any], profile_id: int | None) -> list:
    try:
        wall_construction_config = load_wall_profiles_from_config()
    except (WallConstructionError, FileNotFoundError) as tech_error:
        handle_unknown_error(wall_data, tech_error)
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
    invalid_wall_config_msg = 'Invalid wall configuration file.'
    result = []
    
    try:
        with open(settings.WALL_CONFIG_PATH, 'r') as file:
            result = json.load(file)
    except (json.JSONDecodeError, FileNotFoundError):
        raise WallConstructionError(invalid_wall_config_msg)

    if not isinstance(result, list):
        raise WallConstructionError(invalid_wall_config_msg)

    for profile in result:
        if not isinstance(profile, list) or len(profile) > MAX_LENGTH:
            raise WallConstructionError(invalid_wall_config_msg)

        if not all(isinstance(section_height, int) and 1 <= section_height <= MAX_HEIGHT for section_height in profile):
            raise WallConstructionError(invalid_wall_config_msg)
    
    return result


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
