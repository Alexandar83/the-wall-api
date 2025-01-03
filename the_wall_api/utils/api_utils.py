# Exposed endpoint configurations and schema helpers

from django.conf import settings

# API ENDPOINTS SECTION - only for exposed endpoints
# Changes here are reflected automatically throughout the project:
endpoint_prefix = f'api/{settings.API_VERSION}'
exposed_endpoints = {
    'daily-ice-usage': {
        'path': f'{endpoint_prefix}/daily-ice-usage/<profile_id>/<day>/',
        'name': f'daily-ice-usage-{settings.API_VERSION}',
    },
    'cost-overview': {
        'path': f'{endpoint_prefix}/cost-overview/',
        'name': f'cost-overview-{settings.API_VERSION}',
    },
    'cost-overview-profile': {
        'path': f'{endpoint_prefix}/cost-overview/<profile_id>/',
        'name': f'cost-overview-profile-{settings.API_VERSION}',
    },
    'wallconfig-files-upload': {
        'path': f'{endpoint_prefix}/wallconfig-files/upload/',
        'name': f'wallconfig-files-upload-{settings.API_VERSION}',
    },
    'wallconfig-files-list': {
        'path': f'{endpoint_prefix}/wallconfig-files/list/',
        'name': f'wallconfig-files-list-{settings.API_VERSION}',
    },
    'wallconfig-files-delete': {
        'path': f'{endpoint_prefix}/wallconfig-files/delete/',
        'name': f'wallconfig-files-delete-{settings.API_VERSION}',
    },
    'schema': {
        'path': f'{endpoint_prefix}/schema/',
        'name': 'schema',
    },
    'swagger-ui': {
        'path': f'{endpoint_prefix}/swagger-ui/',
        'name': 'swagger-ui',
    },
    'redoc': {
        'path': f'{endpoint_prefix}/redoc/',
        'name': 'redoc',
    },
    'user-create': {
        'path': f'{endpoint_prefix}/auth/users/',
        'name': 'user-create',
    },
    'user-delete': {
        'path': f'{endpoint_prefix}/auth/users/me/<username>/',
        'name': 'user-delete',
    },
    'user-set-password': {
        'path': f'{endpoint_prefix}/auth/users/set_password/',
        'name': 'user-set-password',
    },
    'token-login': {
        'path': f'{endpoint_prefix}/auth/token/login/',
        'name': 'token-login',
    },
    'token-logout': {
        'path': f'{endpoint_prefix}/auth/token/logout/',
        'name': 'token-logout',
    },
}


def get_request_num_crews(request):
    request_num_crews = request.query_params.get('num_crews')

    if request_num_crews is not None:
        try:
            return int(request_num_crews)
        except ValueError:
            return None

    return None
