from rest_framework import serializers
from django.core.validators import MinValueValidator
from the_wall_api.models import WallProfile, WallProfileProgress


class DailyIceUsageRequestSerializer(serializers.ModelSerializer):
    profile_id = serializers.IntegerField(allow_null=False, validators=[MinValueValidator(1)])
    day = serializers.IntegerField(validators=[MinValueValidator(1)])
    num_crews = serializers.IntegerField(required=False, allow_null=True, validators=[MinValueValidator(0)])

    class Meta:
        model = WallProfile
        fields = ['profile_id', 'day', 'num_crews']


class CostOverviewRequestSerializer(serializers.ModelSerializer):
    profile_id = serializers.IntegerField(required=False, allow_null=True, validators=[MinValueValidator(1)])
    num_crews = serializers.IntegerField(required=False, allow_null=True, validators=[MinValueValidator(0)])

    class Meta:
        model = WallProfile
        fields = ['profile_id', 'num_crews']


class WallProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = WallProfile
        fields = '__all__'

    def validate_wall_profile_config_hash(self, value):
        if len(value) < 64:
            raise serializers.ValidationError('wall_profile_config_hash must be exactly 64 characters long.')
        return value


class WallProfileProgressSerializer(serializers.ModelSerializer):
    wall_profile = serializers.PrimaryKeyRelatedField(queryset=WallProfile.objects.all())

    class Meta:
        model = WallProfileProgress
        fields = ['wall_profile', 'day', 'ice_used', 'cost']
