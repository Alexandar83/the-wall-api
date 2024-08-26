from rest_framework import serializers
from django.core.validators import MinValueValidator
from the_wall_api.models import WallProfile, SimulationResult


class DailyIceUsageRequestSerializer(serializers.ModelSerializer):
    profile_id = serializers.IntegerField(allow_null=False, validators=[MinValueValidator(1)])
    day = serializers.IntegerField(validators=[MinValueValidator(1)])
    num_crews = serializers.IntegerField(required=False, allow_null=True, validators=[MinValueValidator(1)])

    class Meta:
        model = WallProfile
        fields = ['profile_id', 'day', 'num_crews']


class CostOverviewRequestSerializer(serializers.ModelSerializer):
    profile_id = serializers.IntegerField(required=False, allow_null=True, validators=[MinValueValidator(1)])
    num_crews = serializers.IntegerField(required=False, allow_null=True, validators=[MinValueValidator(1)])

    class Meta:
        model = WallProfile
        fields = ['profile_id', 'num_crews']


class WallProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = WallProfile
        fields = ['wall_config_profile_id', 'config_hash', 'num_crews', 'max_day']


class SimulationResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = SimulationResult
        fields = ['wall_profile', 'day', 'ice_used', 'cost', 'simulation_type']
