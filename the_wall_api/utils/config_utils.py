# Wall configuration loading and config hashing

import hashlib
import json
from typing import Dict, Any

from django.conf import settings

SEQUENTIAL = 'sequential'
CONCURRENT = 'concurrent'
MAX_LENGTH = settings.MAX_LENGTH
MAX_HEIGHT = settings.MAX_HEIGHT


class WallConstructionError(ValueError):
    pass


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
