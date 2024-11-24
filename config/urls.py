from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from the_wall_api.utils.api_utils import exposed_endpoints
from the_wall_api.utils.open_api_schema_utils.djoser_utils import (
    CreateUserExtendSchemaViewSet, DeleteUserExtendSchemaViewSet, SetPasswordExtendSchemaView,
    TokenCreateExtendSchemaView, TokenDestroyExtendSchemaView
)
from the_wall_api.views import custom_404_view

handler404 = custom_404_view

# For control of existing and adding of new endpoints -> the_wall_api.utils.api_utils.exposed_endpoints
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('the_wall_api.urls')),
    path(exposed_endpoints['user-create']['path'], CreateUserExtendSchemaViewSet.as_view({'post': 'create'}), name=exposed_endpoints['user-create']['name']),
    path(exposed_endpoints['user-delete']['path'], DeleteUserExtendSchemaViewSet.as_view({'delete': 'destroy'}), name=exposed_endpoints['user-delete']['name']),
    path(exposed_endpoints['user-set-password']['path'], SetPasswordExtendSchemaView.as_view({'post': 'set_password'}), name=exposed_endpoints['user-set-password']['name']),
    path(exposed_endpoints['token-login']['path'], TokenCreateExtendSchemaView.as_view(), name=exposed_endpoints['token-login']['name']),
    path(exposed_endpoints['token-logout']['path'], TokenDestroyExtendSchemaView.as_view(), name=exposed_endpoints['token-logout']['name']),
    path(exposed_endpoints['schema']['path'], SpectacularAPIView.as_view(), name=exposed_endpoints['schema']['name']),
    path(exposed_endpoints['swagger-ui']['path'], SpectacularSwaggerView.as_view(url_name=exposed_endpoints['schema']['name']), name=exposed_endpoints['swagger-ui']['name']),
    path(exposed_endpoints['redoc']['path'], SpectacularRedocView.as_view(url_name=exposed_endpoints['schema']['name']), name=exposed_endpoints['redoc']['name']),
]
