from rest_framework import serializers
from django.core.validators import MinValueValidator
from the_wall_api.models import WallProfile


class DailyIceUsageSerializer(serializers.ModelSerializer):
    profile_id = serializers.IntegerField(allow_null=False, validators=[MinValueValidator(1)])
    day = serializers.IntegerField(validators=[MinValueValidator(1)])
    num_crews = serializers.IntegerField(required=False, allow_null=True, validators=[MinValueValidator(0)])

    class Meta:
        model = WallProfile
        fields = ['profile_id', 'day', 'num_crews']


class CostOverviewSerializer(serializers.ModelSerializer):
    profile_id = serializers.IntegerField(required=False, allow_null=True, validators=[MinValueValidator(1)])
    num_crews = serializers.IntegerField(required=False, allow_null=True, validators=[MinValueValidator(0)])

    class Meta:
        model = WallProfile
        fields = ['profile_id', 'num_crews']
