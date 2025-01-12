# Subclassed Djoser classes to facilitate OpenAPI schema generation

from djoser.views import TokenCreateView, TokenDestroyView, UserViewSet
from drf_spectacular.utils import extend_schema
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle, ScopedRateThrottle

from the_wall_api.utils.message_themes import openapi as openapi_messages
from the_wall_api.utils.open_api_schema_utils import (
    open_api_examples, open_api_responses, request_serializers
)


# User creation
class CreateUserExtendSchemaViewSet(UserViewSet):
    authentication_classes = []
    throttle_classes = [AnonRateThrottle]

    @extend_schema(
        tags=[openapi_messages.USER_MANAGEMENT_TAG],
        summary=openapi_messages.CREATE_USER_SUMMARY,
        description=openapi_messages.CREATE_USER_DESCRIPTION,
        request=request_serializers.create_user_request_serializer,
        responses=open_api_responses.create_user_responses,
        examples=[open_api_examples.create_user_request_example]
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)


# User deletion
class DeleteUserExtendSchemaViewSet(UserViewSet):
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = 'user-management'

    @extend_schema(
        tags=[openapi_messages.USER_MANAGEMENT_TAG],
        summary=openapi_messages.DELETE_USER_SUMMARY,
        description=openapi_messages.DELETE_USER_DESCRIPTION,
        responses=open_api_responses.delete_user_responses,
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


# Change password
class SetPasswordExtendSchemaView(UserViewSet):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'user-management'

    @extend_schema(
        tags=[openapi_messages.USER_MANAGEMENT_TAG],
        summary=openapi_messages.SET_PASSWORD_SUMMARY,
        description=openapi_messages.SET_PASSWORD_DESCRIPTION,
        request=request_serializers.set_password_request_serializer,
        responses=open_api_responses.set_password_responses,
        examples=[open_api_examples.set_password_request_example]
    )
    def set_password(self, request, *args, **kwargs):
        return super().set_password(request, *args, **kwargs)


# Token login
class TokenCreateExtendSchemaView(TokenCreateView):
    authentication_classes = []
    throttle_classes = [AnonRateThrottle, UserRateThrottle]

    @extend_schema(
        tags=[openapi_messages.USER_MANAGEMENT_TAG],
        summary=openapi_messages.TOKEN_LOGIN_SUMMARY,
        description=openapi_messages.TOKEN_LOGIN_DESCRIPTION,
        # Override the default request serializer to indicate the required arguments
        request=request_serializers.token_login_request_serializer,
        responses=open_api_responses.token_login_responses,
        examples=[open_api_examples.token_login_request_example]
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


# Token logout
class TokenDestroyExtendSchemaView(TokenDestroyView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'user-management'

    @extend_schema(
        tags=[openapi_messages.USER_MANAGEMENT_TAG],
        summary=openapi_messages.TOKEN_LOGOUT_SUMMARY,
        description=openapi_messages.TOKEN_LOGOUT_DESCRIPTION,
        responses=open_api_responses.token_logout_responses,
        request=request_serializers.token_logout_request_serializer
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
