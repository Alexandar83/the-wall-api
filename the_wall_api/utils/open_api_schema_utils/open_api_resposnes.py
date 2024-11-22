# Externalized responses for extend_schema

from drf_spectacular.utils import OpenApiExample, OpenApiResponse

from the_wall_api.utils.open_api_schema_utils.response_serializers import (
    cost_overview_response_serializer, cost_overview_profile_id_response_serializer,
    daily_ice_usage_response_serializer, error_response_serializer
)

# == DailyIceUsageView ==
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
            ),
        ]
    ),
}
# == DailyIceUsageView (end) ==

# == CostOverviewView and CostOverviewProfileidView ==
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

# == CostOverviewView and CostOverviewProfileidView (end) ==
