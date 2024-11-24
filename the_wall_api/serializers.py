from django.conf import settings
from django.core.validators import MinValueValidator, FileExtensionValidator
from rest_framework import serializers

from the_wall_api.models import CONFIG_ID_MAX_LENGTH, WallProfile, WallConfigFile

MAX_USER_WALL_CONFIGS = settings.MAX_USER_WALL_CONFIGS


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


class WallConfigFileUploadSerializer(serializers.Serializer):
    wall_config_file = serializers.FileField(
        required=True,
        validators=[FileExtensionValidator(allowed_extensions=['json'])]
    )
    config_id = serializers.CharField(required=True, max_length=CONFIG_ID_MAX_LENGTH)

    class Meta:
        fields = ['wall_config_file', 'config_id']

    def validate(self, attrs):
        user = self.context['request'].user
        user_configs_count = WallConfigFile.objects.filter(user=user).count()

        if user_configs_count >= MAX_USER_WALL_CONFIGS:
            raise serializers.ValidationError(
                f'It is not possible to have more than {MAX_USER_WALL_CONFIGS} wall configs per user.'
            )

        if WallConfigFile.objects.filter(config_id=attrs['config_id'], user=user).exists():
            raise serializers.ValidationError(
                f'Wall config "{attrs["config_id"]}" already exists for user "{user.username}"'
            )

        return attrs
