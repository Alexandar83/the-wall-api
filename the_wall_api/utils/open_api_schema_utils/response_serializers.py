# Externalized response serializers for extend_schema

from drf_spectacular.utils import inline_serializer
from rest_framework import serializers

# == Wall app serializers ==

# *Common*
error_response_serializer = inline_serializer(
    name='ErrorResponse',
    fields={
        'error': serializers.CharField(),
        'error_details': serializers.CharField(required=False),
    }
)

# *DailyIceUsageView*
daily_ice_usage_response_serializer = inline_serializer(
    name='DailyIceUsageResponse',
    fields={
        'profile_id': serializers.IntegerField(),
        'day': serializers.IntegerField(),
        'ice_used': serializers.IntegerField(),
        'details': serializers.CharField(),
    }
)

# *CostOverviewView and CostOverviewProfileidView*
cost_overview_profile_id_response_serializer = inline_serializer(
    name='CostOverviewProfileIdResponse',
    fields={
        'profile_id': serializers.IntegerField(),
        'profile_cost': serializers.CharField(),
        'details': serializers.CharField(),
    }
)

cost_overview_response_serializer = inline_serializer(
    name='CostOverviewResponse',
    fields={
        'total_cost': serializers.CharField(),
        'details': serializers.CharField(),
    }
)

# == Wall app serializers (end) ==
