# Exposed endpoint configurations and schema helpers

from django.conf import settings
from drf_spectacular.utils import OpenApiParameter, OpenApiExample, inline_serializer, OpenApiResponse
from rest_framework import serializers


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

# **Externalized parameters for extend_schema**

# *COMMON elements*
error_response_serializer = inline_serializer(
    name='ErrorResponse',
    fields={
        'error': serializers.CharField(),
        'error_details': serializers.CharField(required=False),
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
# *COMMON elements -end-*

# *DailyIceUsageView*

# Response serializers
daily_ice_usage_response_serializer = inline_serializer(
    name='DailyIceUsageResponse',
    fields={
        'profile_id': serializers.IntegerField(),
        'day': serializers.IntegerField(),
        'ice_used': serializers.IntegerField(),
        'details': serializers.CharField(),
    }
)

# PATH parameters
daily_ice_usage_parameters = [
    OpenApiParameter(
        name='profile_id',
        type=int,
        # required=True,    # Omitted for PATH parameters -> always required
        description='Wall profile number.',
        location=OpenApiParameter.PATH
    ),
    OpenApiParameter(
        name='day',
        type=int,
        # required=True,    # Omitted for PATH parameters -> always required
        description='Construction day number.',
        location=OpenApiParameter.PATH
    ),
]

# Responses
daily_ice_usage_responses = {
    200: OpenApiResponse(
        response=daily_ice_usage_response_serializer,
        examples=[
            OpenApiExample(
                'Example response',
                summary='Profile construction cost (Response)',
                value={
                    'profile_id': 1,
                    'day': 2,
                    'ice_used': 585,
                    'details': 'Volume of ice used for profile 1 on day 2: 585 cubic yards.'
                },
                response_only=True,
            ),
        ]
    ),
    400: OpenApiResponse(
        response=error_response_serializer,
        examples=[
            OpenApiExample(
                name='Profile ID Out of Range',
                value={
                    'error': 'The profile number is out of range. The wall has 3 profiles.',
                    'error_details': {
                        'request_params': {
                            'profile_id': 5,
                            'day': 1
                        },
                    },
                },
            ),
            OpenApiExample(
                name='Day Out of Range',
                value={
                    'error': 'The day is out of range. The wall has been finished for 13 days.',
                    'error_details': {
                        'request_params': {
                            'profile_id': 1,
                            'day': 15
                        },
                    },
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
                    'error': 'No crew has worked on profile 2 on day 1.',
                    'error_details': {
                        'request_params': {
                            'profile_id': 2,
                            'day': 1,
                            'num_crews': 1
                        }
                    }
                },
            )
        ]
    ),
    500: OpenApiResponse(
        response=error_response_serializer,
        examples=[
            OpenApiExample(
                name='Simulation Data Inconsistency',
                value={
                    'error': 'Wall Construction simulation failed. Please contact support.',
                    'error_details': {
                        'request_params': {
                            'profile_id': 1,
                            'day': 14,
                            'num_crews': 5
                        },
                        'tech_info': 'WallConstructionError: Invalid wall configuration file.',
                        'error_id': '1',
                    }
                },
            )
        ]
    ),
}
# *DailyIceUsageView -end-*

# *CostOverviewView and CostOverviewProfileidView*

# Response serializers
cost_overview_profile_id_response_serializer = inline_serializer(
    name='CostOverviewProfileIdResponse',
    fields={
        'profile_id': serializers.IntegerField(),
        'profile_cost': serializers.CharField(),
        'details': serializers.CharField(),
    }
)

cost_overview_response_serializer = inline_serializer(
    name='CostOverviewResponse',
    fields={
        'total_cost': serializers.CharField(),
        'details': serializers.CharField(),
    }
)

# PATH parameters
cost_overview_profile_id_parameters = [
    OpenApiParameter(
        name='profile_id',
        type=int,
        # required=True,    # Omitted for PATH parameters -> always required
        description='Wall profile number.',
        location=OpenApiParameter.PATH
    ),
]

# Responses
cost_overview_responses = {
    200: OpenApiResponse(
        response=cost_overview_response_serializer,
        examples=[
            OpenApiExample(
                'Example response',
                summary='Total construction cost (Response)',
                value={
                    'total_cost': '32233500',
                    'details': 'Total construction cost: 32233500 Gold Dragon coins'
                },
                response_only=True,
            ),
        ]
    ),
    500: OpenApiResponse(
        response=error_response_serializer,
        examples=[
            OpenApiExample(
                name='Simulation Data Inconsistency',
                value={
                    'error': 'Wall Construction simulation failed. Please contact support.',
                    'error_details': {
                        'tech_info': 'WallConstructionError: Invalid wall configuration file.',
                        'error_id': '1',
                    }
                },
            ),
        ]
    ),
}

cost_overview_profile_id_responses = {
    200: OpenApiResponse(
        response=cost_overview_profile_id_response_serializer,
        examples=[
            OpenApiExample(
                'Example response',
                summary='Profile construction cost (Response)',
                value={
                    'profile_id': 2,
                    'profile_cost': '8058375',
                    'details': 'Profile 2 construction cost: 8058375 Gold Dragon coins'
                },
                response_only=True,
            ),
        ]
    ),
    400: OpenApiResponse(
        response=error_response_serializer,
        examples=[
            OpenApiExample(
                name='Profile ID Out of Range',
                value={
                    'error': 'The profile number is out of range. The wall has 3 profiles.',
                    'error_details': {
                        'request_params': {
                            'profile_id': 5,
                            'num_crews': 1
                        },
                    },
                },
            ),
        ]
    ),
    500: OpenApiResponse(
        response=error_response_serializer,
        examples=[
            OpenApiExample(
                name='Simulation Data Inconsistency',
                value={
                    'error': 'Wall Construction simulation failed. Please contact support.',
                    'error_details': {
                        'request_params': {
                            'profile_id': 5,
                            'num_crews': 1
                        },
                        'tech_info': 'WallConstructionError: Invalid wall configuration file.',
                        'error_id': '1',
                    }
                },
            ),
        ]
    ),
}
# *CostOverviewView and CostOverviewProfileidView -end-*

# **Externalized parameters for extend_schema -end-**


def get_request_num_crews(request):
    request_num_crews = request.GET.get('num_crews')

    if request_num_crews is not None:
        try:
            return int(request_num_crews)
        except ValueError:
            return None

    return None
