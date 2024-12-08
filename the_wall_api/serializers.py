import json

from django.core.validators import MinValueValidator, FileExtensionValidator
from rest_framework import serializers

from the_wall_api.models import CONFIG_ID_MAX_LENGTH, WallConfigReference


class DailyIceUsageSerializer(serializers.Serializer):
    profile_id = serializers.IntegerField(allow_null=False, validators=[MinValueValidator(1)])
    day = serializers.IntegerField(validators=[MinValueValidator(1)])
    num_crews = serializers.IntegerField(required=False, allow_null=True, validators=[MinValueValidator(0)])
    config_id = serializers.CharField(required=True, allow_blank=False, max_length=CONFIG_ID_MAX_LENGTH)


class CostOverviewSerializer(serializers.Serializer):
    profile_id = serializers.IntegerField(required=False, allow_null=True, validators=[MinValueValidator(1)])
    num_crews = serializers.IntegerField(required=False, allow_null=True, validators=[MinValueValidator(0)])
    config_id = serializers.CharField(required=True, allow_blank=False, max_length=CONFIG_ID_MAX_LENGTH)


class WallConfigFileUploadSerializer(serializers.Serializer):
    wall_config_file = serializers.FileField(
        required=True,
        validators=[FileExtensionValidator(allowed_extensions=['json'])]
    )
    config_id = serializers.CharField(required=True, allow_blank=False, max_length=CONFIG_ID_MAX_LENGTH)

    class Meta:
        fields = ['wall_config_file', 'config_id']

    def validate(self, attrs: dict):
        from django.conf import settings

        MAX_USER_WALL_CONFIGS = settings.MAX_USER_WALL_CONFIGS

        user = self.context['request'].user
        user_configs_count = WallConfigReference.objects.filter(user=user).count()

        if user_configs_count >= MAX_USER_WALL_CONFIGS:
            raise serializers.ValidationError(
                f'File limit of {MAX_USER_WALL_CONFIGS} per user reached.'
            )

        if WallConfigReference.objects.filter(config_id=attrs['config_id'], user=user).exists():
            raise serializers.ValidationError(
                f"Wall config '{attrs['config_id']}' already exists for user '{user.username}'."
            )

        try:
            uploaded_file = attrs['wall_config_file']
            file_content = uploaded_file.read().decode('utf-8')
            wall_config_file_data = json.loads(file_content)
            self.context['wall_config_file_data'] = wall_config_file_data
        except json.JSONDecodeError:
            raise serializers.ValidationError('Invalid JSON file format.')

        return attrs


class WallConfigFileDeleteSerializer(serializers.Serializer):
    config_id_list = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        fields = ['config_id_list']

    def validate_config_id_list(self, config_id_list_str: str) -> list[str]:
        try:
            config_id_list = [config_id.strip() for config_id in config_id_list_str.split(',')] if config_id_list_str else []
        except Exception as id_lst_splt_err:
            raise serializers.ValidationError(f'Invalid config_id_list format: {id_lst_splt_err}.')

        invalid_length_list = [config_id for config_id in config_id_list if len(config_id) > CONFIG_ID_MAX_LENGTH]
        if invalid_length_list:
            raise serializers.ValidationError(f'Config IDs with invalid length: {str(invalid_length_list)}.')

        return config_id_list
