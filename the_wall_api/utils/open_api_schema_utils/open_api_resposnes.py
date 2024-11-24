# Externalized responses for extend_schema

from drf_spectacular.utils import OpenApiExample, OpenApiResponse

from the_wall_api.utils.open_api_schema_utils import open_api_examples, response_serializers

# == DailyIceUsageView ==
daily_ice_usage_responses = {
    200: OpenApiResponse(
        response=response_serializers.daily_ice_usage_response_serializer,
        examples=[
            OpenApiExample(
                'Example response',
                summary='Profile construction cost',
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
        response=response_serializers.wall_app_error_response_serializer,
        examples=[
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
            ),
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
        ]
    ),
    404: OpenApiResponse(
        response=response_serializers.wall_app_error_response_serializer,
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
        response=response_serializers.wall_app_error_response_serializer,
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
        response=response_serializers.cost_overview_response_serializer,
        examples=[
            OpenApiExample(
                'Example response',
                summary='Total construction cost',
                value={
                    'total_cost': '32233500',
                    'details': 'Total construction cost: 32233500 Gold Dragon coins'
                },
                response_only=True,
            ),
        ]
    ),
    500: OpenApiResponse(
        response=response_serializers.wall_app_error_response_serializer,
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
        response=response_serializers.cost_overview_profile_id_response_serializer,
        examples=[
            OpenApiExample(
                'Example response',
                summary='Profile construction cost',
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
        response=response_serializers.wall_app_error_response_serializer,
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
        response=response_serializers.wall_app_error_response_serializer,
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

# == Djoser ==
# = Create user =
create_user_responses = {
    201: OpenApiResponse(
        response=response_serializers.create_user_response_serializer,
        examples=[
            OpenApiExample(
                'Valid response',
                summary='Create user',
                value={
                    'username': 'testuser',
                    'email': 'testuser@example.com',
                },
                response_only=True,
            ),
        ]
    ),
    400: OpenApiResponse(
        response=response_serializers.create_user_error_response_serializer,
        examples=[
            OpenApiExample(
                name='Invalid email format',
                value={
                    'email': ['Enter a valid email address.']
                },
            ),
            OpenApiExample(
                name='Missing required fields',
                value={
                    'username': ['This field is required.'],
                    'password': ['This field is required.']
                },
            ),
            OpenApiExample(
                name='Username already exists',
                value={
                    'username': ['A user with that username already exists.']
                },
            ),
            OpenApiExample(
                name='Weak password',
                value={
                    'password': open_api_examples.weak_password_msg_list
                },
            ),
        ]
    )
}
# = Create user (end)

# = Delete user =
delete_user_responses = {
    204: '',
    400: OpenApiResponse(
        response=response_serializers.delete_user_error_response_serializer,
        examples=[
            open_api_examples.invalid_password,
        ]
    ),
    401: OpenApiResponse(
        response=response_serializers.delete_user_error_response_serializer,
        examples=[
            OpenApiExample(
                name='Current password required',
                value={
                    'current_password': ['This field is required.']
                },
            ),
            open_api_examples.invalid_token,
            open_api_examples.not_authenticated,
        ]
    ),
}
# = Delete user (end)

# = Change password =
set_password_responses = {
    204: '',
    400: OpenApiResponse(
        response=response_serializers.set_password_error_response_serializer,
        examples=[
            open_api_examples.invalid_password,
            OpenApiExample(
                name='Missing required fields',
                value={
                    'new_password': ['This field is required.'],
                    'current_password': ['This field is required.']
                },
            ),
            open_api_examples.not_authenticated,
            OpenApiExample(
                name='Weak password',
                value={
                    'new_password': open_api_examples.weak_password_msg_list
                },
            ),
        ]
    ),
}
# = Change password (end)

# = Token login =
token_login_responses = {
    200: OpenApiResponse(
        response=response_serializers.token_login_response_serializer,
        examples=[
            OpenApiExample(
                'Valid response',
                summary='Valid token',
                value={
                    'auth_token': '50b3bebe2cb047451c8201e8c3e5b3b950cfec09',
                },
                response_only=True,
            ),
        ]
    ),
    400: OpenApiResponse(
        response=response_serializers.token_login_error_response_serializer,
        examples=[
            OpenApiExample(
                name='Unable to log in',
                value={
                    'non_field_errors': ['Unable to log in with provided credentials.']
                },
            ),
        ]
    ),
}
# = Token login (end)

# = Token logout =
token_logout_responses = {
    204: '',
    401: OpenApiResponse(
        response=response_serializers.token_logout_error_response_serializer,
        examples=[
            open_api_examples.invalid_token,
            open_api_examples.not_authenticated,
        ]
    ),
}
# = Token logout (end)

# == Djoser (end) ==
