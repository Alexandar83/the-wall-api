# Externalized responses for extend_schema

from django.conf import settings
from drf_spectacular.utils import OpenApiExample, OpenApiResponse

from the_wall_api.utils.message_themes import (
    errors as error_messages, openapi as openapi_messages, success as success_messages
)
from the_wall_api.utils.open_api_schema_utils import open_api_examples, response_serializers
from the_wall_api.serializers import CONFIG_ID_MAX_LENGTH

MAX_USER_WALL_CONFIGS = settings.MAX_USER_WALL_CONFIGS
MAX_SECTION_HEIGHT = settings.MAX_SECTION_HEIGHT
MAX_WALL_PROFILE_SECTIONS = settings.MAX_WALL_PROFILE_SECTIONS
MAX_WALL_LENGTH = settings.MAX_WALL_LENGTH


# == Common ==
unauthorized_401_responses = OpenApiResponse(
    response=response_serializers.unauthorized_401_response_serializer,
    examples=[
        open_api_examples.invalid_token,
        open_api_examples.not_authenticated,
    ]
)
profiles_404_responses = OpenApiResponse(
    response=response_serializers.profiles_404_response_serializer,
    examples=[
        open_api_examples.file_not_existing_for_user,
    ]
)
profiles_409_responses = OpenApiResponse(
    response=response_serializers.profiles_409_response_serializer,
    examples=[
        open_api_examples.wall_config_409_status,
    ]
)
throttled_429_responses = OpenApiResponse(
    response=response_serializers.throttled_429_response_serializer,
    examples=[
        open_api_examples.throttled_error_example
    ]
)

# == Common (end) ==

# == WallConfigFileUploadView ==
wallconfig_file_upload_responses = {
    201: OpenApiResponse(
        response=response_serializers.wall_config_file_upload_response_serializer,
        examples=[
            OpenApiExample(
                name=openapi_messages.VALID_RESPONSE,
                summary=openapi_messages.VALID_RESPONSE_SUMMARY,
                value={
                    'config_id': 'test_config_1',
                    'details': success_messages.file_upload_details('test_config_1'),
                },
                response_only=True,
            ),
        ]
    ),
    400: OpenApiResponse(
        response=response_serializers.wall_config_file_upload_400_response_serializer,
        examples=[
            OpenApiExample(
                name=openapi_messages.CONFIG_ID_ALREADY_EXISTS,
                value={
                    'non_field_errors': [error_messages.wall_config_exists('test_config_1', 'testuser')],
                },
            ),
            OpenApiExample(
                name=openapi_messages.CONFIG_ID_BLANK_STRING,
                value={
                    'config_id': [error_messages.THIS_FIELD_MAY_NOT_BE_BLANK],
                },
            ),
            OpenApiExample(
                name=openapi_messages.CONFIG_ID_NULL_OBJECT,
                value={
                    'config_id': [error_messages.THIS_FIELD_MAY_NOT_BE_NULL],
                },
            ),
            OpenApiExample(
                name=openapi_messages.EMPTY_FILE,
                value={
                    'wall_config_file': [error_messages.THE_FILE_IS_EMPTY],
                },
            ),
            OpenApiExample(
                name=openapi_messages.FILE_LIMIT_REACHED,
                value={
                    'non_field_errors': [error_messages.file_limit_per_user_reached(MAX_USER_WALL_CONFIGS)],
                },
            ),
            OpenApiExample(
                name=openapi_messages.FILE_NULL_OBJECT,
                value={
                    'wall_config_file': [error_messages.THIS_FIELD_MAY_NOT_BE_NULL],
                },
            ),
            OpenApiExample(
                name=openapi_messages.INVALID_CONFIG_ID_LENGTH,
                value={
                    'config_id': [error_messages.ensure_config_id_valid_length(CONFIG_ID_MAX_LENGTH)],
                },
            ),
            OpenApiExample(
                name=openapi_messages.INVALID_FILE_EXTENSION,
                value={
                    'wall_config_file': [error_messages.file_extension_not_allowed('txt', 'json')],
                },
            ),
            OpenApiExample(
                name=openapi_messages.INVALID_FILE_FORMAT,
                value={
                    'non_field_errors': [error_messages.INVALID_JSON_FILE_FORMAT],
                },
            ),
            OpenApiExample(
                name=openapi_messages.INVALID_PROFILE_SECTIONS_COUNT,
                value={
                    'error': (error_messages.maximum_profile_sections_exceeded(MAX_WALL_PROFILE_SECTIONS)),
                    'error_details': {
                        'request_params': {
                            'config_id': 'test_config_1'
                        },
                        'error_id': '20'
                    }
                },
            ),
            OpenApiExample(
                name=openapi_messages.INVALID_SECTIONS_COUNT,
                value={
                    'error': (error_messages.maximum_number_of_sections_exceeded(MAX_WALL_LENGTH * MAX_WALL_PROFILE_SECTIONS)),
                    'error_details': {
                        'request_params': {
                            'config_id': 'test_config_1'
                        },
                        'error_id': '21'
                    }
                },
            ),
            OpenApiExample(
                name=openapi_messages.invalid_section_height_label(counter=1),
                value={
                    'error': error_messages.invalid_section_height(
                        section_height=31, profile_id=1, section_number=1,
                        error_message_suffix=error_messages.section_height_must_be_less_than_limit(MAX_SECTION_HEIGHT)
                    ),
                    'error_details': {
                        'request_params': {
                            'config_id': 'test_config_1'
                        },
                        'error_id': '23'
                    }
                },
            ),
            OpenApiExample(
                name=openapi_messages.invalid_section_height_label(counter=2),
                value={
                    'error': error_messages.invalid_section_height(
                        section_height=-1, profile_id=1, section_number=1,
                        error_message_suffix=error_messages.SECTION_HEIGHT_MUST_BE_GREATER_THAN_ZERO
                    ),
                    'error_details': {
                        'request_params': {
                            'config_id': 'test_config_1'
                        },
                        'error_id': '11'
                    }
                },
            ),
            OpenApiExample(
                name=openapi_messages.INVALID_SECTION_TYPE,
                value={
                    'error': error_messages.invalid_section_height(
                        section_height='text', profile_id=1, section_number=1,
                        error_message_suffix=error_messages.SECTION_HEIGHT_MUST_BE_INTEGER
                    ),
                    'error_details': {
                        'request_params': {
                            'config_id': 'test_config_1'
                        },
                        'error_id': '22'
                    }
                },
            ),
            OpenApiExample(
                name=openapi_messages.INVALID_WALL_LENGTH,
                value={
                    'error': error_messages.maximum_wall_length_exceeded(MAX_WALL_LENGTH),
                    'error_details': {
                        'request_params': {
                            'config_id': 'test_config_1'
                        },
                        'error_id': '19'
                    }
                },
            ),
            OpenApiExample(
                name=openapi_messages.MISSING_CONFIG_ID,
                value={
                    'config_id': [error_messages.THIS_FIELD_IS_REQUIRED],
                },
            ),
            OpenApiExample(
                name=openapi_messages.MISSING_FILE,
                value={
                    'wall_config_file': [error_messages.NO_FILE_SUBMITTED],
                },
            ),
            OpenApiExample(
                name=openapi_messages.NOT_A_FILE,
                value={
                    'wall_config_file': [error_messages.DATA_NOT_A_FILE],
                },
            ),
            OpenApiExample(
                name=openapi_messages.PROFILE_NOT_A_LIST,
                value={
                    'error': error_messages.profile_must_be_list_of_integers(),
                    'error_details': {
                        'request_params': {
                            'config_id': 'test_config_1'
                        },
                        'error_id': '20'
                    }
                },
            ),
            OpenApiExample(
                name=openapi_messages.WALL_CONFIG_ALREADY_EXISTS,
                value={
                    'error': error_messages.wall_config_already_uploaded('test_config_1'),
                    'error_details': {
                        'request_params': {
                            'config_id': 'test_config_1'
                        },
                        'error_id': '18'
                    }
                },
            ),
            OpenApiExample(
                name=openapi_messages.WALL_CONFIG_NOT_A_LIST,
                value={
                    'error': error_messages.must_be_nested_list_of_lists_of_integers(),
                    'error_details': {
                        'request_params': {
                            'config_id': 'test_config_1'
                        },
                        'error_id': '18'
                    }
                },
            ),
        ]
    ),
    401: unauthorized_401_responses,
    429: throttled_429_responses,
    500: OpenApiResponse(
        response=response_serializers.wall_app_error_response_serializer,
        examples=[
            OpenApiExample(
                name=openapi_messages.FILE_UPLOAD_TECHNICAL_ERROR,
                value={
                    'error': error_messages.wall_operation_failed(error_messages.CONSTRUCTION_ERROR_SOURCE_UPLOAD),
                    'error_details': {
                        'request_params': {'config_id': 'valid_config_id'},
                        'error_id': '25',
                        'tech_info': openapi_messages.UNKNOWN_EXCEPTION
                    }
                },
            ),
        ]
    ),
    503: OpenApiResponse(
        response=response_serializers.wall_config_file_upload_503_response_serializer,
        examples=[
            OpenApiExample(
                name=openapi_messages.TRY_AGAIN,
                value={
                    'error': error_messages.WALL_CONFIG_DELETION_BEING_PROCESSED,
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
                name=openapi_messages.INVALID_LENGTH,
                value={
                    'config_id_list': [error_messages.config_ids_with_invalid_length(
                        ['too_long_config_id_too_long_config_id_1', 'too_long_config_id_too_long_config_id_2']
                    )],
                },
            ),
            OpenApiExample(
                name=openapi_messages.INVALID_CONFIG_ID_LIST_FORMAT,
                value={
                    'config_id_list': [error_messages.invalid_config_id_list_format('Exception text')],
                }
            ),
            OpenApiExample(
                name=openapi_messages.INVALID_STRING,
                value={
                    'config_id_list': [error_messages.INVALID_STRING],
                },
            ),
            OpenApiExample(
                name=openapi_messages.NULL_OBJECT,
                value={
                    'config_id_list': [error_messages.THIS_FIELD_MAY_NOT_BE_NULL],
                },
            ),
        ]
    ),
    401: unauthorized_401_responses,
    404: OpenApiResponse(
        response=response_serializers.wall_config_delete_404_response_serializer,
        examples=[
            OpenApiExample(
                name=openapi_messages.NO_MATCHING_FILES,
                value={
                    'error': error_messages.no_matching_files_for_user('testuser'),
                },
            ),
            OpenApiExample(
                name=openapi_messages.NO_FILES_FOR_USER,
                value={
                    'error': error_messages.no_files_exist_for_user('testuser'),
                },
            ),
            OpenApiExample(
                name=openapi_messages.FILES_NOT_FOUND,
                value={
                    'error': error_messages.files_with_config_id_not_found_for_user(
                        ['test_config_2', 'test_config_3'], 'testuser'
                    )
                },
            ),
        ]
    ),
    429: throttled_429_responses,
    500: OpenApiResponse(
        response=response_serializers.wall_app_error_response_serializer,
        examples=[
            OpenApiExample(
                name=openapi_messages.TECHNICAL_ERROR_DELETION,
                value={
                    'error': error_messages.wall_operation_failed(error_messages.CONSTRUCTION_ERROR_SOURCE_DELETE),
                    'error_details': {
                        'error_id': '25',
                        'tech_info': openapi_messages.UNKNOWN_EXCEPTION
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
                name=openapi_messages.VALID_RESPONSE,
                summary=openapi_messages.SUMMARY_FILES_LIST_RESPONSE,
                value={
                    'config_id_list': ['test_config_1', 'test_config_2'],
                },
                response_only=True,
            ),
        ]
    ),
    401: unauthorized_401_responses,
    429: throttled_429_responses,
}

# == WallConfigFileListView (end) ==

# == ProfilesDaysView ==
profiles_days_responses = {
    200: OpenApiResponse(
        response=response_serializers.profiles_days_response_serializer,
        examples=[
            OpenApiExample(
                name=openapi_messages.VALID_RESPONSE,
                summary=openapi_messages.SUMMARY_PROFILES_DAYS_RESPONSE,
                value={
                    'profile_id': 1,
                    'day': 2,
                    'ice_used': 585,
                    'details': success_messages.profiles_days_details(1, 2, 585),
                },
                response_only=True,
            ),
        ]
    ),
    400: OpenApiResponse(
        response=response_serializers.wall_app_error_response_serializer,
        examples=[
            OpenApiExample(
                name=openapi_messages.OUT_OF_RANGE_DAY,
                value={
                    'error': error_messages.out_of_range(
                        'day', error_messages.out_of_range_finishing_message_1(13)
                    ),
                    'error_details': {
                        'request_params': {
                            'profile_id': 1,
                            'day': 15
                        },
                    },
                },
            ),
            OpenApiExample(
                name=openapi_messages.OUT_OF_RANGE_PROFILE_ID,
                value={
                    'error': error_messages.out_of_range(
                        'profile number', error_messages.out_of_range_finishing_message_2(3)
                    ),
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
    401: unauthorized_401_responses,
    404: OpenApiResponse(
        response=response_serializers.wall_app_error_response_serializer,
        examples=[
            open_api_examples.file_not_existing_for_user,
            OpenApiExample(
                name=openapi_messages.NO_WORK_ON_PROFILE,
                value={
                    'error': error_messages.no_crew_worked_on_profile(2, 1),
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
    409: profiles_409_responses,
    429: throttled_429_responses,
    500: OpenApiResponse(
        response=response_serializers.wall_app_error_response_serializer,
        examples=[
            OpenApiExample(
                name=openapi_messages.SIMULATION_DATA_INCONSISTENCY,
                value={
                    'error': error_messages.wall_operation_failed(error_messages.CONSTRUCTION_ERROR_SOURCE_SIMULATION),
                    'error_details': {
                        'request_params': {
                            'config_id': 'test_config_1',
                            'profile_id': 1,
                            'day': 14,
                            'num_crews': 5
                        },
                        'error_id': '1',
                        'tech_info': openapi_messages.UNKNOWN_EXCEPTION,
                    }
                },
            ),
        ]
    ),
}
# == ProfilesDaysView (end) ==

# == ProfilesOverviewView ==
profiles_overview_responses = {
    200: OpenApiResponse(
        response=response_serializers.profiles_overview_response_serializer,
        examples=[
            OpenApiExample(
                name=openapi_messages.VALID_RESPONSE,
                summary=openapi_messages.TOTAL_CONSTRUCTION_COST,
                value={
                    'cost': '32233500',
                    'details': success_messages.profiles_overview_details(
                        success_messages.WALL_TOTAL_COST_RESPONSE, 32233500
                    ),
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
    401: unauthorized_401_responses,
    404: profiles_404_responses,
    409: profiles_409_responses,
    429: throttled_429_responses,
    500: OpenApiResponse(
        response=response_serializers.wall_app_error_response_serializer,
        examples=[
            OpenApiExample(
                name=openapi_messages.SIMULATION_DATA_INCONSISTENCY,
                value={
                    'error': error_messages.wall_operation_failed(error_messages.CONSTRUCTION_ERROR_SOURCE_SIMULATION),
                    'error_details': {
                        'request_params': {'config_id': 'test_config_1'},
                        'error_id': '1',
                        'tech_info': openapi_messages.UNKNOWN_EXCEPTION,
                    }
                },
            ),
        ]
    ),
}

#TODO: to merge with ProfilesOverview responses
profiles_overview_profile_id_responses = {
    200: OpenApiResponse(
        response=response_serializers.profiles_overview_response_serializer,
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
                    'error': error_messages.out_of_range(
                        'profile number', error_messages.out_of_range_finishing_message_2(3)
                    ),
                    'error_details': {
                        'request_params': {
                            'profile_id': 5
                        },
                    },
                },
            ),
            open_api_examples.invalid_config_id_length,
        ]
    ),
    401: unauthorized_401_responses,
    404: profiles_404_responses,
    409: profiles_409_responses,
    429: throttled_429_responses,
    500: OpenApiResponse(
        response=response_serializers.wall_app_error_response_serializer,
        examples=[
            OpenApiExample(
                name=openapi_messages.SIMULATION_DATA_INCONSISTENCY,
                value={
                    'error': error_messages.wall_operation_failed(error_messages.CONSTRUCTION_ERROR_SOURCE_SIMULATION),
                    'error_details': {
                        'request_params': {
                            'config_id': 'test_config_1',
                            'profile_id': 5
                        },
                        'error_id': '1',
                        'tech_info': 'WallConstructionError: Invalid wall configuration.',
                    }
                },
            ),
        ]
    ),
}

# == ProfilesOverviewView(end) ==

# == Djoser ==
# = Create user =
create_user_responses = {
    201: OpenApiResponse(
        response=response_serializers.create_user_response_serializer,
        examples=[
            OpenApiExample(
                name=openapi_messages.VALID_RESPONSE,
                summary=openapi_messages.CREATE_USER_SUMMARY,
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
                name=openapi_messages.INVALID_EMAIL_FORMAT,
                value={
                    'email': [error_messages.INVALID_EMAIL]
                },
            ),
            OpenApiExample(
                name=openapi_messages.MISSING_REQUIRED_FIELDS,
                value={
                    'username': [error_messages.THIS_FIELD_IS_REQUIRED],
                    'password': [error_messages.THIS_FIELD_IS_REQUIRED]
                },
            ),
            OpenApiExample(
                name=openapi_messages.USERNAME_ALREADY_EXISTS,
                value={
                    'username': [error_messages.USERNAME_EXISTS]
                },
            ),
            OpenApiExample(
                name=openapi_messages.WEAK_PASSWORD,
                value={
                    'password': open_api_examples.weak_password_msg_list
                },
            ),
        ]
    ),
    404: profiles_404_responses,
    429: throttled_429_responses,
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
                name=openapi_messages.CURRENT_PASSWORD_REQUIRED,
                value={
                    'current_password': [error_messages.THIS_FIELD_IS_REQUIRED]
                },
            ),
            open_api_examples.invalid_token,
            open_api_examples.not_authenticated,
        ]
    ),
    429: throttled_429_responses,
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
                name=openapi_messages.MISSING_REQUIRED_FIELDS,
                value={
                    'new_password': [error_messages.THIS_FIELD_IS_REQUIRED],
                    'current_password': [error_messages.THIS_FIELD_IS_REQUIRED]
                },
            ),
            open_api_examples.not_authenticated,
            OpenApiExample(
                name=openapi_messages.WEAK_PASSWORD,
                value={
                    'new_password': open_api_examples.weak_password_msg_list
                },
            ),
        ]
    ),
    429: throttled_429_responses,
}
# = Change password (end)

# = Token login =
token_login_responses = {
    200: OpenApiResponse(
        response=response_serializers.token_login_response_serializer,
        examples=[
            OpenApiExample(
                name=openapi_messages.VALID_RESPONSE,
                summary=openapi_messages.SUMMARY_TOKEN_LOGIN,
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
                name=openapi_messages.UNABLE_TO_LOG_IN,
                value={
                    'non_field_errors': [error_messages.UNABLE_TO_LOG_IN]
                },
            ),
        ]
    ),
    429: throttled_429_responses,
}
# = Token login (end)

# = Token logout =
token_logout_responses = {
    204: '',
    401: unauthorized_401_responses,
    429: throttled_429_responses,
}
# = Token logout (end)

# == Djoser (end) ==
