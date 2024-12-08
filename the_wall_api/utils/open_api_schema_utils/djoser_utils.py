# Subclassed Djoser classes to facilitate OpenAPI schema generation

from djoser.views import TokenCreateView, TokenDestroyView, UserViewSet
from drf_spectacular.utils import extend_schema
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle, ScopedRateThrottle

from the_wall_api.utils.open_api_schema_utils import (
    open_api_examples, open_api_resposnes, request_serializers
)


# User creation
class CreateUserExtendSchemaViewSet(UserViewSet):
    authentication_classes = []
    throttle_classes = [AnonRateThrottle]

    @extend_schema(
        tags=['auth'],
        summary='Create User',
        description='Register a new user with email and password.',
        request=request_serializers.create_user_request_serializer,
        responses=open_api_resposnes.create_user_responses,
        examples=[open_api_examples.create_user_request_example]
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)


# User deletion
class DeleteUserExtendSchemaViewSet(UserViewSet):
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = 'user-management'

    @extend_schema(
        tags=['auth'],
        summary='Delete User',
        description=(
            'This endpoint requires the `current_password` parameter in the request\'s body.\n\n'
            '**Example request body:**\n'
            '```json\n'
            '{\n'
            '  "current_password": "strongpassword#123"\n'
            '}\n'
            '```\n'
            '**Note:** Due to OpenAPI 3.1 limitations, request body schema '
            'and examples cannot be included in the schema documentation for DELETE endpoints.\n\n'
            '*The "Try it out" functionality also doesn\'t work properly in Swagger UI.*" '
        ),
        responses=open_api_resposnes.delete_user_responses,
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


# Change password
class SetPasswordExtendSchemaView(UserViewSet):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'user-management'

    @extend_schema(
        tags=['auth'],
        summary='Update User Password',
        description='Change/reset the user\'s current password.',
        request=request_serializers.set_password_request_serializer,
        responses=open_api_resposnes.set_password_responses,
        examples=[open_api_examples.set_password_request_example]
    )
    def set_password(self, request, *args, **kwargs):
        return super().set_password(request, *args, **kwargs)


# Token login
class TokenCreateExtendSchemaView(TokenCreateView):
    authentication_classes = []
    throttle_classes = [AnonRateThrottle, UserRateThrottle]

    @extend_schema(
        tags=['auth'],
        summary='Obtain Authentication Token',
        description=(
            'Obtain an authentication token by creating a new one or '
            'retrieving an existing valid token.'
        ),
        # Override the default request serializer to indicate the required arguments
        request=request_serializers.token_login_request_serializer,
        responses=open_api_resposnes.token_login_responses,
        examples=[open_api_examples.token_login_request_example]
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


# Token logout
class TokenDestroyExtendSchemaView(TokenDestroyView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'user-management'

    @extend_schema(
        tags=['auth'],
        summary='Revoke Authentication Token',
        description='Revoke an existing authentication token - requires only a valid token.',
        responses=open_api_resposnes.token_logout_responses,
        request=request_serializers.token_logout_request_serializer
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
