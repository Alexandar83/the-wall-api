# Exposed endpoint configurations and
# response helper functions

from typing import Any

from django.conf import settings
from rest_framework.response import Response
from rest_framework import status

# API ENDPOINTS SECTION - only for exposed endpoints
# Changes here are reflected automatically throughout the project:
endpoint_prefix = f'api/{settings.API_VERSION}'
exposed_endpoints = {
    'profiles-days': {
        'path': f'{endpoint_prefix}/profiles/<int:profile_id>/days/<int:day>/',
        'name': f'profiles-days-{settings.API_VERSION}',
    },
    'single-profile-overview-day': {
        'path': f'{endpoint_prefix}/profiles/<int:profile_id>/overview/<int:day>/',
        'name': f'single-profile-overview-day-{settings.API_VERSION}',
    },
    'profiles-overview-day': {
        'path': f'{endpoint_prefix}/profiles/overview/<int:day>/',
        'name': f'profiles-overview-day-{settings.API_VERSION}',
    },
    'profiles-overview': {
        'path': f'{endpoint_prefix}/profiles/overview/',
        'name': f'profiles-overview-{settings.API_VERSION}',
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


def handle_being_processed(wall_data: dict[str, Any]) -> None:
    info_message = 'Your request is being calculated. Check back later.'
    wall_data['info_response'] = Response({'info': info_message}, status=status.HTTP_202_ACCEPTED)
