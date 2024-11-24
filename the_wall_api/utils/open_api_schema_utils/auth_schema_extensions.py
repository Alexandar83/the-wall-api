from drf_spectacular.extensions import OpenApiAuthenticationExtension


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
            'description': (
                # Use &lt; to represent a literal < and &gt; to represent a literal >
                # in the description, ensuring proper rendering in Markdown viewers like Redoc.
                'Enter your token in the format: **Token &lt;your_token&gt;**\n\n'
                'Example header:\n'
                '{"Authorization": "Token abcdef1234567890"}'
            )
        }
