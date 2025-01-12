# Externalized examples for extend_schema

from drf_spectacular.utils import OpenApiExample

from the_wall_api.models import CONFIG_ID_MAX_LENGTH
from the_wall_api.utils.message_themes import (
    errors as error_messages, openapi as openapi_messages
)

# = Common =
not_authenticated = OpenApiExample(
    name=error_messages.NOT_AUTHENTICATED,
    value={
        'detail': error_messages.NOT_AUTHENTICATED_RESPONSE
    },
)
invalid_password = OpenApiExample(
    name=error_messages.INVALID_PASSWORD.replace('.', ''),
    value={
        'current_password': [error_messages.INVALID_PASSWORD]
    },
)
invalid_token = OpenApiExample(
    name=error_messages.INVALID_TOKEN.replace('.', ''),
    value={
        'detail': error_messages.INVALID_TOKEN
    },
)
weak_password_msg_list = [
    error_messages.PASSWORD_TOO_SHORT,
    error_messages.PASSWORD_TOO_COMMON,
    error_messages.PASSWORD_NUMERIC,
    error_messages.PASSWORD_SIMILAR_TO_USERNAME
]
invalid_config_id_length = OpenApiExample(
    name=openapi_messages.INVALID_CONFIG_ID_LENGTH,
    value={
        'config_id': [
            error_messages.ensure_config_id_valid_length(CONFIG_ID_MAX_LENGTH)
        ]
    },
)
file_not_existing_for_user = OpenApiExample(
    name=openapi_messages.FILE_NOT_EXISTING_FOR_USER,
    value={
        'error': error_messages.file_does_not_exist_for_user('not_existing_config_id', 'testuser')
    },
)
throttled_error_example = OpenApiExample(
    name=openapi_messages.THROTTLED,
    value={
        'detail': error_messages.request_was_throttled(wait_seconds=59)
    },
)
# = Create user =
create_user_request_example = OpenApiExample(
    name=openapi_messages.CREATE_USER_REQUEST,
    summary=openapi_messages.CREATE_USER_REQUEST_SUMMARY,
    value={
        'username': 'testuser',
        'email': 'testuser@example.com',
        'password': 'strongpassword#123'
    },
    request_only=True
)
# = Change password =
set_password_request_example = OpenApiExample(
    name=openapi_messages.CHANGE_PASSWORD_REQUEST,
    summary=openapi_messages.CHANGE_PASSWORD_REQUEST_SUMMARY,
    value={
        'current_password': 'strongpassword#123',
        'new_password': 'stronger_password#123'
    },
    request_only=True
)
# = Token login =
token_login_request_example = OpenApiExample(
    name=openapi_messages.TOKEN_LOGIN_REQUEST,
    summary=openapi_messages.TOKEN_LOGIN_REQUEST_SUMMARY,
    value={
        'username': 'testuser',
        'password': 'strongpassword#123'
    },
    request_only=True
)
