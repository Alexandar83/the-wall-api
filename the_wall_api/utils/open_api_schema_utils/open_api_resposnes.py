# Externalized responses for extend_schema

from django.conf import settings
from drf_spectacular.utils import OpenApiExample, OpenApiResponse

from the_wall_api.utils.open_api_schema_utils import open_api_examples, response_serializers
from the_wall_api.serializers import CONFIG_ID_MAX_LENGTH

MAX_USER_WALL_CONFIGS = settings.MAX_USER_WALL_CONFIGS


# == Common ==
unauthorized_responses = OpenApiResponse(
    response=response_serializers.unauthorized_error_response_serializer,
    examples=[
        open_api_examples.invalid_token,
        open_api_examples.not_authenticated,
    ]
)
cost_usage_404_responses = OpenApiResponse(
    response=response_serializers.cost_usage_404_response_serializer,
    examples=[
        open_api_examples.file_not_existing_for_user,
    ]
)
cost_usage_409_responses = OpenApiResponse(
    response=response_serializers.cost_usage_409_response_serializer,
    examples=[
        open_api_examples.wall_config_409_status,
    ]
)

# == Common (end) ==

# == WallConfigFileUploadView ==
wallconfig_file_upload_responses = {
    201: OpenApiResponse(
        response=response_serializers.wall_config_file_upload_response_serializer,
        examples=[
            OpenApiExample(
                name='Valid response',
                summary='Upload success',
                value={
                    'config_id': 'test_config_1',
                    'details': 'Wall config <test_config_1> uploaded successfully.',
                },
                response_only=True,
            ),
        ]
    ),
    400: OpenApiResponse(
        response=response_serializers.wall_config_file_upload_400_response_serializer,
        examples=[
            OpenApiExample(
                name='Already exists',
                value={
                    'non_field_errors': ["Wall config 'test_config_1' already exists for user 'testuser'."],
                },
            ),
            OpenApiExample(
                name='config_id Null object',
                value={
                    'config_id': ['This field may not be null.'],
                },
            ),
            OpenApiExample(
                name='config_id blank string',
                value={
                    'config_id': ['This field may not be blank.'],
                },
            ),
            OpenApiExample(
                name='Empty file',
                value={
                    'wall_config_file': ['The submitted file is empty.'],
                },
            ),
            OpenApiExample(
                name='File Null object',
                value={
                    'wall_config_file': ['This field may not be null.'],
                },
            ),
            OpenApiExample(
                name='Invalid config_id length',
                value={
                    'config_id': [f'Ensure this field has no more than {CONFIG_ID_MAX_LENGTH} characters.'],
                },
            ),
            OpenApiExample(
                name='Invalid file extension',
                value={
                    'wall_config_file': ['File extension “txt” is not allowed. Allowed extensions are: json.'],
                },
            ),
            OpenApiExample(
                name='Invalid file format',
                value={
                    'non_field_errors': ['Invalid JSON file format.'],
                },
            ),
            OpenApiExample(
                name='File limit reached',
                value={
                    'non_field_errors': [f'File limit of {MAX_USER_WALL_CONFIGS} per user reached.'],
                },
            ),
            OpenApiExample(
                name='Missing config_id',
                value={
                    'config_id': ['This field is required.'],
                },
            ),
            OpenApiExample(
                name='Missing file',
                value={
                    'wall_config_file': ['No file was submitted.'],
                },
            ),
            OpenApiExample(
                name='Not a file',
                value={
                    'wall_config_file': ['The submitted data was not a file. Check the encoding type on the form.'],
                },
            ),
        ]
    ),
    401: unauthorized_responses,
    500: OpenApiResponse(
        response=response_serializers.wall_app_error_response_serializer,
        examples=[
            OpenApiExample(
                name='Deletion in progress',
                value={
                    'error': 'Wall config file upload failed. Please contact support.',
                    'error_details': {
                        'request_params': {'config_id': 'valid_config_id'},
                        'error_id': '25',
                        'tech_info': 'Exception: Unknown exception'
                    }
                },
            ),
        ]
    ),
    503: OpenApiResponse(
        response=response_serializers.wall_config_file_upload_503_response_serializer,
        examples=[
            OpenApiExample(
                name='Try again',
                value={
                    'error': 'A deletion of an existing wall config is being processed - please try again later.',
                },
            ),
        ]
    ),
}

# == WallConfigFileUploadView (end) ==

# == WallConfigDeleteView ==
wallconfig_file_delete_responses = {
    204: '',
    400: OpenApiResponse(
        response=response_serializers.wall_config_delete_400_response_serializer,
        examples=[
            OpenApiExample(
                name='Invalid length',
                value={
                    'config_id_list': [(
                        "Config IDs with invalid length: ['too_long_config_id_too_long_config_id_1', "
                        "'too_long_config_id_too_long_config_id_2']."
                    )],
                },
            ),
            OpenApiExample(
                name='Invalid string',
                value={
                    'config_id_list': ['Not a valid string.'],
                },
            ),
            OpenApiExample(
                name='Null object',
                value={
                    'config_id_list': ['This field may not be null.'],
                },
            ),
        ]
    ),
    401: unauthorized_responses,
    404: OpenApiResponse(
        response=response_serializers.wall_config_delete_404_response_serializer,
        examples=[
            OpenApiExample(
                name='No matching files',
                value={
                    'error': "No matching files for user 'testuser' exist for the provided config ID list.",
                },
            ),
            OpenApiExample(
                name='No files for the user',
                value={
                    'error': "No files exist for user 'testuser' in the database.",
                },
            ),
            OpenApiExample(
                name='Files not found',
                value={
                    'error': "File(s) with config ID(s) ['test_config_2', 'test_config_3'] not found for user 'testuser'.",
                },
            ),
        ]
    ),
    500: OpenApiResponse(
        response=response_serializers.wall_app_error_response_serializer,
        examples=[
            OpenApiExample(
                name='Deletion in progress',
                value={
                    'error': 'Wall config file delete failed. Please contact support.',
                    'error_details': {
                        'error_id': '25',
                        'tech_info': 'Exception: Unknown exception.'
                    }
                },
            ),
        ]
    ),
}

# == WallConfigDeleteView (end) ==

# == WallConfigListView ==
wallconfig_file_list_responses = {
    200: OpenApiResponse(
        response=response_serializers.wall_config_list_response_serializer,
        examples=[
            OpenApiExample(
                name='Valid response',
                summary='Wall config ID list',
                value={
                    'config_id_list': ['test_config_1', 'test_config_2'],
                },
                response_only=True,
            ),
        ]
    ),
    401: unauthorized_responses,
}

# == WallConfigFileListView (end) ==

# == DailyIceUsageView ==
daily_ice_usage_responses = {
    200: OpenApiResponse(
        response=response_serializers.daily_ice_usage_response_serializer,
        examples=[
            OpenApiExample(
                name='Valid response',
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
            open_api_examples.invalid_config_id_length,
            open_api_examples.file_not_existing_for_user,
        ]
    ),
    401: unauthorized_responses,
    404: OpenApiResponse(
        response=response_serializers.wall_app_error_response_serializer,
        examples=[
            open_api_examples.file_not_existing_for_user,
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
            ),
        ]
    ),
    409: cost_usage_409_responses,
    500: OpenApiResponse(
        response=response_serializers.wall_app_error_response_serializer,
        examples=[
            OpenApiExample(
                name='Simulation Data Inconsistency',
                value={
                    'error': 'Wall construction simulation failed. Please contact support.',
                    'error_details': {
                        'request_params': {
                            'config_id': 'test_config_1',
                            'profile_id': 1,
                            'day': 14,
                            'num_crews': 5
                        },
                        'error_id': '1',
                        'tech_info': 'Exception: Unknown exception.',
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
                name='Valid response',
                summary='Total construction cost',
                value={
                    'total_cost': '32233500',
                    'details': 'Total construction cost: 32233500 Gold Dragon coins'
                },
                response_only=True,
            ),
        ]
    ),
    400: OpenApiResponse(
        response=response_serializers.config_id_error_response_serializer,
        examples=[
            open_api_examples.invalid_config_id_length,
            open_api_examples.file_not_existing_for_user,
        ]
    ),
    401: unauthorized_responses,
    404: cost_usage_404_responses,
    409: cost_usage_409_responses,
    500: OpenApiResponse(
        response=response_serializers.wall_app_error_response_serializer,
        examples=[
            OpenApiExample(
                name='Simulation Data Inconsistency',
                value={
                    'error': 'Wall construction simulation failed. Please contact support.',
                    'error_details': {
                        'request_params': {'config_id': 'test_config_1'},
                        'error_id': '1',
                        'tech_info': 'Exception: Unknown exception.',
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
                name='Valid response',
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
            open_api_examples.invalid_config_id_length,
        ]
    ),
    401: unauthorized_responses,
    404: cost_usage_404_responses,
    409: cost_usage_409_responses,
    500: OpenApiResponse(
        response=response_serializers.wall_app_error_response_serializer,
        examples=[
            OpenApiExample(
                name='Simulation Data Inconsistency',
                value={
                    'error': 'Wall construction simulation failed. Please contact support.',
                    'error_details': {
                        'request_params': {
                            'config_id': 'test_config_1',
                            'profile_id': 5,
                            'num_crews': 1
                        },
                        'error_id': '1',
                        'tech_info': 'WallConstructionError: Invalid wall configuration file.',
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
                name='Valid response',
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
    ),
    404: cost_usage_404_responses,
}
# = Create user (end)

# = Delete user =
delete_user_responses = {
    204: '',
    400: OpenApiResponse(
        response=response_serializers.delete_user_400_response_serializer,
        examples=[
            open_api_examples.invalid_password,
        ]
    ),
    401: OpenApiResponse(
        response=response_serializers.delete_user_401_response_serializer,
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
                name='Valid response',
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
    401: unauthorized_responses,
}
# = Token logout (end)

# == Djoser (end) ==
