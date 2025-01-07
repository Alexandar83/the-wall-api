from django.urls import path

from the_wall_api.utils.api_utils import exposed_endpoints
from the_wall_api.views import (
    ProfilesDaysView, ProfilesOverviewView,
    ProfilesOverviewDayView, SingleProfileOverviewDayView,
    WallConfigFileDeleteView, WallConfigFileListView, WallConfigFileUploadView
)

# For control of existing and adding of new endpoints -> the_wall_api.utils.api_utils.exposed_endpoints
urlpatterns = [
    path(
        exposed_endpoints['profiles-days']['path'],
        ProfilesDaysView.as_view(),
        name=exposed_endpoints['profiles-days']['name']
    ),
    path(
        exposed_endpoints['single-profile-overview-day']['path'],
        SingleProfileOverviewDayView.as_view(),
        name=exposed_endpoints['single-profile-overview-day']['name']
    ),
    path(
        exposed_endpoints['profiles-overview-day']['path'],
        ProfilesOverviewDayView.as_view(),
        name=exposed_endpoints['profiles-overview-day']['name']
    ),
    path(
        exposed_endpoints['profiles-overview']['path'],
        ProfilesOverviewView.as_view(),
        name=exposed_endpoints['profiles-overview']['name']
    ),
    path(
        exposed_endpoints['wallconfig-files-upload']['path'],
        WallConfigFileUploadView.as_view(),
        name=exposed_endpoints['wallconfig-files-upload']['name']
    ),
    path(
        exposed_endpoints['wallconfig-files-list']['path'],
        WallConfigFileListView.as_view(),
        name=exposed_endpoints['wallconfig-files-list']['name']
    ),
    path(
        exposed_endpoints['wallconfig-files-delete']['path'],
        WallConfigFileDeleteView.as_view(),
        name=exposed_endpoints['wallconfig-files-delete']['name']
    ),
]
