from drf_spectacular.extensions import OpenApiAuthenticationExtension

from the_wall_api.utils.message_themes import openapi as openapi_messages


class TokenAuthScheme(OpenApiAuthenticationExtension):
    """
    Custom OpenAPI extension for DRF Spectacular to override
    the TokenAuthentication security definition
    with more detailed Token usage instructions in the description.
    """
    target_class = 'rest_framework.authentication.TokenAuthentication'  # Link to DRF's TokenAuthentication
    name = 'tokenAuth'  # Security scheme name used in your schema

    def get_security_definition(self, auto_schema):
        return {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Authorization',
            'description': openapi_messages.TOKEN_AUTH_SCHEME_DESCRIPTION
        }
