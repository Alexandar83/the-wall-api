# Externalized response serializers for extend_schema

from drf_spectacular.utils import inline_serializer
from rest_framework import serializers

# == Wall app serializers ==

# *Common*
wall_app_error_response_serializer = inline_serializer(
    name='WallAppErrorResponse',
    fields={
        'error': serializers.CharField(),
        'error_details': serializers.CharField(required=False),
    }
)

# *DailyIceUsageView*
daily_ice_usage_response_serializer = inline_serializer(
    name='DailyIceUsageResponse',
    fields={
        'profile_id': serializers.IntegerField(),
        'day': serializers.IntegerField(),
        'ice_used': serializers.IntegerField(),
        'details': serializers.CharField(),
    }
)

# *CostOverviewView and CostOverviewProfileidView*
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
delete_user_error_response_serializer = inline_serializer(
    name='DeleteUserErrorResponse',
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
# = Token logout =
token_logout_error_response_serializer = inline_serializer(
    name='TokenLogoutErrorResponse',
    fields={
        'detail': serializers.CharField(),
    }
)
# == Djoser (end) ==
