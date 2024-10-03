from django.contrib import admin
from django.urls import include, path

from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from the_wall_api.utils.api_utils import exposed_endpoints
from the_wall_api.views import custom_404_view

handler404 = custom_404_view

# For control of existing and adding of new endpoints -> the_wall_api.utils.api_utils.exposed_endpoints
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('the_wall_api.urls')),
    path(exposed_endpoints['schema']['path'], SpectacularAPIView.as_view(), name=exposed_endpoints['schema']['name']),
    path(exposed_endpoints['swagger-ui']['path'], SpectacularSwaggerView.as_view(url_name=exposed_endpoints['schema']['name']), name=exposed_endpoints['swagger-ui']['name']),
    path(exposed_endpoints['redoc']['path'], SpectacularRedocView.as_view(url_name=exposed_endpoints['schema']['name']), name=exposed_endpoints['redoc']['name']),
    # You can add more paths here if needed, for other endpoints
]

SPECTACULAR_SETTINGS = {
    'SERVE_INCLUDE_SCHEMA': False,
}
