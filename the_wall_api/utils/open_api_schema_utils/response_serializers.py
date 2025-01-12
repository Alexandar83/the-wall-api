# Externalized response serializers for extend_schema
from django.core.validators import MinValueValidator
from drf_spectacular.utils import inline_serializer
from rest_framework import serializers

from the_wall_api.models import CONFIG_ID_MAX_LENGTH

# == Wall app serializers ==

# *Common*
wall_app_error_response_serializer = inline_serializer(
    name='WallAppErrorResponse',
    fields={
        'error': serializers.CharField(required=False),
        'error_details': serializers.DictField(required=False),
        'config_id': serializers.ListField(child=serializers.CharField(), required=False),
    }
)
profiles_error_and_details_response_serializer_1 = inline_serializer(
    name='ProfilesErrorAndDetailsResponse1',
    fields={
        'error': serializers.CharField(),
        'error_details': serializers.DictField(required=False),
    }
)
profiles_404_response_serializer = inline_serializer(
    name='ProfilesError404Response',
    fields={
        'error': serializers.CharField(),
    }
)
profiles_error_and_details_response_serializer_2 = inline_serializer(
    name='ProfilesErrorAndDetailsResponse2',
    fields={
        'error': serializers.CharField(),
        'error_details': serializers.DictField(),
    }
)
config_id_error_response_serializer = inline_serializer(
    name='ConfigIdErrorResponse',
    fields={
        'config_id': serializers.ListField(child=serializers.CharField(), required=False),
        'error': serializers.CharField(required=False),
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


# = Profiles Views =
# *Base Response Serializer*
class ProfilesResponseSerializerBase(serializers.Serializer):
    num_crews = serializers.IntegerField(validators=[MinValueValidator(0)])
    config_id = serializers.CharField(max_length=CONFIG_ID_MAX_LENGTH)
    details = serializers.CharField()


# *ProfilesDaysView*
class ProfilesDaysResponseSerializer(ProfilesResponseSerializerBase):
    day = serializers.IntegerField(validators=[MinValueValidator(1)])
    ice_amount = serializers.IntegerField(validators=[MinValueValidator(0)])
    profile_id = serializers.IntegerField(validators=[MinValueValidator(1)])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Reorder declared fields
        ordered_fields = ['day', 'ice_amount', 'profile_id', 'num_crews', 'config_id', 'details']
        self._declared_fields = {key: self._declared_fields[key] for key in ordered_fields if key in self._declared_fields}


# *SingleProfileOverviewDayView*
class SingleProfileOverviewDayResponseSerializer(ProfilesResponseSerializerBase):
    day = serializers.IntegerField(validators=[MinValueValidator(1)])
    cost = serializers.IntegerField(validators=[MinValueValidator(0)])
    profile_id = serializers.IntegerField(validators=[MinValueValidator(1)])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Reorder declared fields
        ordered_fields = ['day', 'cost', 'profile_id', 'num_crews', 'config_id', 'details']
        self._declared_fields = {key: self._declared_fields[key] for key in ordered_fields if key in self._declared_fields}


# *ProfilesOverviewDayView*
class ProfilesOverviewDayResponseSerializer(SingleProfileOverviewDayResponseSerializer):
    profile_id = serializers.IntegerField(allow_null=True)


# *ProfilesOverviewView*
class ProfilesOverviewResponseSerializer(ProfilesOverviewDayResponseSerializer):
    day = serializers.IntegerField(allow_null=True)


# = Profiles Views (end) =

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
