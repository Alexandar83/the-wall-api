# Externalized response serializers for extend_schema

from drf_spectacular.utils import inline_serializer
from rest_framework import serializers

# == Wall app serializers ==

# *Common*
wall_app_error_response_serializer = inline_serializer(
    name='WallAppErrorResponse',
    fields={
        'error': serializers.CharField(required=False),
        'error_details': serializers.DictField(required=False),
        'config_id': serializers.CharField(required=False),
    }
)
profiles_404_response_serializer = inline_serializer(
    name='ProfilesError404Response',
    fields={
        'error': serializers.CharField(),
    }
)
profiles_409_response_serializer = inline_serializer(
    name='ProfilesError409Response',
    fields={
        'error': serializers.CharField(),
        'error_details': serializers.DictField(),
    }
)
config_id_error_response_serializer = inline_serializer(
    name='ConfigIdErrorResponse',
    fields={
        'config_id': serializers.CharField(),
    }
)
unauthorized_401_response_serializer = inline_serializer(
    name='UnauthorizedErrorResponse',
    fields={
        'detail': serializers.CharField(),
    }
)
throttled_429_response_serializer = inline_serializer(
    name='ThrottledErrorResponse',
    fields={
        'detail': serializers.CharField(),
    }
)

# *WallConfigFileUploadView*
wall_config_file_upload_response_serializer = inline_serializer(
    name='WallConfigFileUploadResponse',
    fields={
        'config_id': serializers.CharField(),
        'details': serializers.CharField(),
    }
)
wall_config_file_upload_400_response_serializer = inline_serializer(
    name='WallConfigFileUploadError400Response',
    fields={
        'wall_config_file': serializers.ListField(child=serializers.CharField(), required=False),
        'config_id': serializers.ListField(child=serializers.CharField(), required=False),
        'non_field_errors': serializers.ListField(child=serializers.CharField(), required=False),
        'error': serializers.CharField(required=False),
        'error_details': serializers.DictField(required=False),
    }
)
wall_config_file_upload_503_response_serializer = inline_serializer(
    name='WallConfigFileUploadError503Response',
    fields={
        'error': serializers.CharField(),
    }
)

# *WallConfigFileListView*
wall_config_list_response_serializer = inline_serializer(
    name='WallConfigFileListResponse',
    fields={
        'config_id_list': serializers.ListField(child=serializers.CharField()),
    }
)

# *WallConfigFileDeleteView*
wall_config_delete_400_response_serializer = inline_serializer(
    name='WallConfigFileDeleteError400Response',
    fields={
        'config_id_list': serializers.ListField(child=serializers.CharField()),
    }
)
wall_config_delete_404_response_serializer = inline_serializer(
    name='WallConfigFileDeleteError404Response',
    fields={
        'error': serializers.CharField(),
    }
)

# *ProfilesDaysView*
profiles_days_response_serializer = inline_serializer(
    name='ProfilesDaysResponse',
    fields={
        'profile_id': serializers.IntegerField(),
        'day': serializers.IntegerField(),
        'ice_used': serializers.IntegerField(),
        'details': serializers.CharField(),
    }
)

# *ProfilesOverviewView*
profiles_overview_response_serializer = inline_serializer(
    name='ProfilesOverviewResponse',
    fields={
        'profile_id': serializers.IntegerField(),
        'profile_cost': serializers.CharField(),
        'details': serializers.CharField(),
    }
)

# == Wall app serializers (end) ==

# == Djoser ==
# = Create user =
create_user_response_serializer = inline_serializer(
    name='CreateUserResponse',
    fields={
        'username': serializers.CharField(),
        'email': serializers.EmailField(),
    }
)

create_user_error_response_serializer = inline_serializer(
    name='CreateUserErrorResponse',
    fields={
        'username': serializers.ListField(child=serializers.CharField(), required=False),
        'email': serializers.ListField(child=serializers.CharField(), required=False),
        'password': serializers.ListField(child=serializers.CharField(), required=False),
    }
)
# = Delete user =
delete_user_400_response_serializer = inline_serializer(
    name='DeleteUserError400Response',
    fields={
        'current_password': serializers.ListField(child=serializers.CharField()),
    }
)
delete_user_401_response_serializer = inline_serializer(
    name='DeleteUserError401Response',
    fields={
        'detail': serializers.CharField(required=False),
        'current_password': serializers.ListField(child=serializers.CharField(), required=False),
    }
)
# = Change password =
set_password_error_response_serializer = inline_serializer(
    name='SetPasswordErrorResponse',
    fields={
        'current_password': serializers.CharField(required=False),
        'new_password': serializers.CharField(),
    }
)
# = Token login =
token_login_response_serializer = inline_serializer(
    name='TokenLoginResponse',
    fields={
        'auth_token': serializers.CharField(),
    }
)
token_login_error_response_serializer = inline_serializer(
    name='TokenLoginErrorResponse',
    fields={
        'non_field_errors': serializers.ListField(child=serializers.CharField()),
    }
)
# == Djoser (end) ==
