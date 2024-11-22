from django.contrib import admin
from django.urls import include, path

from djoser.views import UserViewSet, TokenCreateView, TokenDestroyView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from the_wall_api.utils.api_utils import exposed_endpoints
from the_wall_api.views import custom_404_view

handler404 = custom_404_view


class CustomUserViewSet(UserViewSet):
    lookup_field = 'username'


# For control of existing and adding of new endpoints -> the_wall_api.utils.api_utils.exposed_endpoints
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('the_wall_api.urls')),
    path(exposed_endpoints['user-create']['path'], UserViewSet.as_view({'post': 'create'}), name=exposed_endpoints['user-create']['name']),
    path(exposed_endpoints['user-delete']['path'], CustomUserViewSet.as_view({'delete': 'destroy'}), name=exposed_endpoints['user-delete']['name']),
    path(exposed_endpoints['user-set-password']['path'], UserViewSet.as_view({'post': 'set_password'}), name=exposed_endpoints['user-set-password']['name']),
    path(exposed_endpoints['token-login']['path'], TokenCreateView.as_view(), name=exposed_endpoints['token-login']['name']),
    path(exposed_endpoints['token-logout']['path'], TokenDestroyView.as_view(), name=exposed_endpoints['token-logout']['name']),
    path(exposed_endpoints['schema']['path'], SpectacularAPIView.as_view(), name=exposed_endpoints['schema']['name']),
    path(exposed_endpoints['swagger-ui']['path'], SpectacularSwaggerView.as_view(url_name=exposed_endpoints['schema']['name']), name=exposed_endpoints['swagger-ui']['name']),
    path(exposed_endpoints['redoc']['path'], SpectacularRedocView.as_view(url_name=exposed_endpoints['schema']['name']), name=exposed_endpoints['redoc']['name']),
]
