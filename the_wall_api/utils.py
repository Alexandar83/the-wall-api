import hashlib
import json
from typing import Iterable, NamedTuple

from django.conf import settings
from drf_spectacular.utils import OpenApiParameter, OpenApiExample, inline_serializer, OpenApiResponse
from rest_framework import serializers
from rest_framework.response import Response

from the_wall_api.models import WallProfile
from the_wall_api.serializers import DailyIceUsageRequestSerializer, CostOverviewRequestSerializer

SINGLE_THREADED = 'single_threaded'
MULTI_THREADED = 'multi_threaded'
MAX_LENGTH = settings.MAX_LENGTH
MAX_HEIGHT = settings.MAX_HEIGHT

# API ENPOINTS SECTION - only for exposed endpoints
# Changes here are reflected automatically throughout the project:
endpoint_prefix = f'api/{settings.API_VERSION}'
exposed_endpoints = {
    'daily-ice-usage': {
        'path': f'{endpoint_prefix}/daily-ice-usage/<profile_id>/<day>/',
        'name': f'daily-ice-usage-{settings.API_VERSION}',
    },
    'cost-overview': {
        'path': f'{endpoint_prefix}/cost-overview/',
        'name': f'cost-overview-{settings.API_VERSION}',
    },
    'cost-overview-profile': {
        'path': f'{endpoint_prefix}/cost-overview/<profile_id>/',
        'name': f'cost-overview-profile-{settings.API_VERSION}',
    },
    'schema': {
        'path': f'{endpoint_prefix}/schema/',
        'name': 'schema',
    },
    'swagger-ui': {
        'path': f'{endpoint_prefix}/swagger-ui/',
        'name': 'swagger-ui',
    },
    'redoc': {
        'path': f'{endpoint_prefix}/redoc/',
        'name': 'redoc',
    },

}


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


def generate_config_hash(wall_profiles: list, num_crews: int | None = None) -> str:
    """
    Generates a unique hash for the entire wall configuration,
    taking into account the number of crews.
    """
    data_to_hash = {
        'wall_profiles': wall_profiles,
        'num_crews': num_crews
    }
    config_str = json.dumps(data_to_hash, sort_keys=True)
    return hashlib.sha256(config_str.encode('utf-8')).hexdigest()


class WallProfileResponse(NamedTuple):
    """
    NamedTuple for easier maintenance of the typed annotation of the get_wall_profiles method
    """
    error_response: Response | None
    wall_profiles: Iterable[WallProfile]
    simulation_type: str | None


# **Externalized parameters for extend_schema**

# DailyIceUsageView
error_response_serializer = inline_serializer(
    name='ErrorResponse',
    fields={
        'error': serializers.CharField(),
        'details': serializers.CharField(required=False),
    }
)

# Optional query parameter for num_crews
num_crews_parameter = OpenApiParameter(
    name='num_crews',
    type=int,
    required=False,
    description=(
        'The number of crews involved in the simulation. '
        'When included: the wall build simulation is concurrent. '
        'When omitted: the simulation defaults to sequential processing.'
    ),
    location=OpenApiParameter.QUERY
)

# Daily usage parameters
daily_ice_usage_parameters = [
    OpenApiParameter(
        name='profile_id',
        type=int,
        required=True,
        description='Wall profile number (required).',
        location=OpenApiParameter.PATH
    ),
    OpenApiParameter(
        name='day',
        type=int,
        required=True,
        description='Construction day number (required).',
        location=OpenApiParameter.PATH
    ),
]

daily_ice_usage_examples = [
    OpenApiExample(
        'Example response',
        summary='Profile construction cost (Response)',
        value={
            'profile_id': 1,
            'day': 2,
            'ice_amount': 585,
            'details': 'Volume of ice used for profile 1 on day 2: 585 cubic yards.'
        },
        description='Response example when retrieving a profile cost overview.',
        response_only=True,
    ),
]

daily_ice_usage_responses = {
    200: DailyIceUsageRequestSerializer,
    400: OpenApiResponse(
        response=error_response_serializer,
        examples=[
            OpenApiExample(
                name='Profile ID Out of Range',
                value={
                    'error': 'The profile number is out of range. The maximum value is 10.',
                },
            ),
            OpenApiExample(
                name='Day Out of Range',
                value={
                    'error': 'The day is out of range. The maximum value is 30.',
                },
            )
        ]
    ),
    404: OpenApiResponse(
        response=error_response_serializer,
        examples=[
            OpenApiExample(
                name='No work on profile',
                value={
                    "profile_id": 2,
                    "day": 14,
                    "details": "No crew has worked on profile 2 on day 14."
                },
            )
        ]
    ),
    500: OpenApiResponse(
        response=error_response_serializer,
        examples=[
            OpenApiExample(
                name='Simulation Data Inconsistency 1',
                value={
                    'error': 'Wall Construction simulation failed. Please contact support.',
                    'error_details': {
                        'request_data': {
                            'profile_id': 1,
                            'day': 14,
                            'num_crews': 5
                        },
                        'error_msg': 'FileNotFoundError'
                    }
                },
            ),
            OpenApiExample(
                name='Simulation Data Inconsistency 2',
                value={
                    'error': 'Wall Construction simulation failed. Please contact support.',
                    'error_details': 'Invalid wall configuration file.'
                },
            ),
        ]
    ),
}

# CostOverviewView and CostOverviewProfileidView
cost_overview_examples = [
    OpenApiExample(
        'Example response',
        summary='Total construction cost (Response)',
        value={
            'total_cost': '32233500',
            'details': 'Total construction cost: 32233500 Gold Dragon coins'
        },
        description='Response example when retrieving wall construction total cost overview.',
        response_only=True,
    ),
]

cost_overview_parameters = [
    OpenApiParameter(
        name='profile_id',
        type=int,
        required=False,
        description='Wall profile number (optional).',
        location=OpenApiParameter.PATH
    ),
]

cost_overview_responses = {
    200: CostOverviewRequestSerializer,
    400: OpenApiResponse(
        response=error_response_serializer,
        examples=[
            OpenApiExample(
                name='Profile ID Out of Range',
                value={
                    'error': 'The profile number is out of range. The maximum value is 10.',
                },
            ),
        ]
    ),
    500: OpenApiResponse(
        response=error_response_serializer,
        examples=[
            OpenApiExample(
                name='Simulation Data Inconsistency 1',
                value={
                    'error': 'Simulation data inconsistency detected.',
                    'error_details': 'Please contact support.'
                },
                
            ),
            OpenApiExample(
                name='Simulation Data Inconsistency 2',
                value={
                    'error': 'Wall Construction simulation failed. Please contact support.',
                    'error_details': 'Invalid wall configuration file.'
                },
            ),
        ]
    ),
}
# **Externalized parameters for extend_schema - end**
