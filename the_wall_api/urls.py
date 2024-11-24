from django.urls import path

from the_wall_api.utils.api_utils import exposed_endpoints
from the_wall_api.views import (
    CostOverviewView, CostOverviewProfileidView, DailyIceUsageView, WallConfigFileView
)

# For control of existing and adding of new endpoints -> the_wall_api.utils.api_utils.exposed_endpoints
urlpatterns = [
    path(
        exposed_endpoints['daily-ice-usage']['path'],
        DailyIceUsageView.as_view(),
        name=exposed_endpoints['daily-ice-usage']['name']
    ),
    path(
        exposed_endpoints['cost-overview']['path'],
        CostOverviewView.as_view(),
        name=exposed_endpoints['cost-overview']['name']
    ),
    path(
        exposed_endpoints['cost-overview-profile']['path'],
        CostOverviewProfileidView.as_view(),
        name=exposed_endpoints['cost-overview-profile']['name']
    ),
    path(
        exposed_endpoints['wallconfig-files-upload']['path'],
        WallConfigFileView.as_view(),
        name=exposed_endpoints['wallconfig-files-upload']['name']
    ),
]
