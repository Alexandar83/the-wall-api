# Externalized request serializers for extend_schema

from drf_spectacular.utils import inline_serializer
from rest_framework import serializers


# = Create user =
create_user_request_serializer = inline_serializer(
    name='CreateUserRequestBody',
    fields={
        'username': serializers.RegexField(
            regex=r'^[\w.@+-]+$',
            max_length=150,
            required=True,
            help_text="150 characters or fewer. Letters, digits and @/./+/-/_ only."
        ),
        'password': serializers.CharField(min_length=8, write_only=True, required=True),
        'email': serializers.EmailField(max_length=254, required=False),
    }
)
# = Change password =
set_password_request_serializer = inline_serializer(
    name='SetPasswordRequestBody',
    fields={
        'current_password': serializers.CharField(write_only=True, required=True),
        'new_password': serializers.CharField(write_only=True, required=True),
    }
)
# = Token login =
token_login_request_serializer = inline_serializer(
    name='TokenLoginRequestBody',
    fields={
        'username': serializers.CharField(required=True),
        'password': serializers.CharField(write_only=True, required=True),
    }
)
# = Token logout =
# Needed to avoid "Warning [TokenDestroyExtendSchemaView > Serializer]:
# Component name "" contains illegal characters.""
token_logout_request_serializer = inline_serializer(
    name='TokenLogoutRequestBody',
    fields={}
)
