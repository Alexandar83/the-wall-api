# Externalized examples for extend_schema

from drf_spectacular.utils import OpenApiExample

# = Common =
not_authenticated = OpenApiExample(
    name='Not authenticated',
    value={
        'detail': 'Authentication credentials were not provided.'
    },
)
invalid_password = OpenApiExample(
    name='Invalid password',
    value={
        'current_password': ['Invalid password.']
    },
)
invalid_token = OpenApiExample(
    name='Invalid token',
    value={
        'detail': 'Invalid token.'
    },
)
weak_password_msg_list = [
    'This password is too short. It must contain at least 8 characters.',
    'This password is too common.',
    'This password is entirely numeric.',
    'The password is too similar to the username.'
]
invalid_config_id_length = OpenApiExample(
    name='Invalid config ID length',
    value={
        'config_id': [
            'Ensure this field has no more than 30 characters.'
        ]
    },
)
file_not_existing_for_user = OpenApiExample(
    name='File not existing for user',
    value={
        'error': "File with config ID 'not_existing_config_id' does not exist for user 'testuser'."
    },
)
wall_config_409_status = OpenApiExample(
    name='Invalid wall config status',
    value={
        'error': "The resource is not found. Wall configuration status = 'Error'",
        'error_details': {
            'request_params': {
                'profile_id': 1,
                'day': 1,
                'config_id': 'test_config_1'
            },
            'error_id': '1',
        }
    },
)
throttled_error_example = OpenApiExample(
    name='Throttled',
    value={
        'detail': 'Request was throttled. Expected available in 59 seconds.'
    },
)
# = Create user =
create_user_request_example = OpenApiExample(
    name='Create ser request',
    summary='Valid request to create a new user',
    value={
        'username': 'testuser',
        'email': 'testuser@example.com',
        'password': 'strongpassword#123'
    },
    request_only=True
)
# = Change password =
set_password_request_example = OpenApiExample(
    name='Change password request',
    summary='Valid request to change a user\'s password',
    value={
        'current_password': 'strongpassword#123',
        'new_password': 'stronger_password#123'
    },
    request_only=True
)
# = Token login =
token_login_request_example = OpenApiExample(
    name='Token login request',
    summary='Valid request to generate a token for a user',
    value={
        'username': 'testuser',
        'password': 'strongpassword#123'
    },
    request_only=True
)
