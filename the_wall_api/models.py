from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.db.models.signals import post_delete
from django.dispatch import receiver

CONFIG_ID_MAX_LENGTH = 30


class WallConfigStatusEnum(models.TextChoices):
    INITIALIZED = 'initialized', 'Initialized'
    CELERY_CALCULATION = 'celery_calculation', 'Celery calculation'
    ERROR = 'error', 'Error'
    COMPLETED = 'completed', 'Completed'
    READY_FOR_DELETION = 'ready_for_deletion', 'Ready for deletion'


class WallConfig(models.Model):
    """
    wall configuration - source of all possible build simulations
    """
    wall_config_hash = models.CharField(max_length=64, unique=True)
    status = models.CharField(
        max_length=25,
        choices=WallConfigStatusEnum.choices,
        default=WallConfigStatusEnum.INITIALIZED
    )
    deletion_initiated = models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True)


class WallConfigReference(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wall_config_references')
    wall_config = models.ForeignKey(WallConfig, on_delete=models.CASCADE, related_name='wall_config_references')
    config_id = models.CharField(max_length=CONFIG_ID_MAX_LENGTH)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'wall_config', 'config_id')


class Wall(models.Model):
    """
    A single wall build simulation
    """
    # Hash the whole wall config with all profiles
    wall_config = models.ForeignKey(WallConfig, on_delete=models.CASCADE)
    wall_config_hash = models.CharField(max_length=64)
    num_crews = models.IntegerField(validators=[MinValueValidator(0)])
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    construction_days = models.IntegerField()
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('wall_config_hash', 'num_crews')


@receiver(post_delete, sender=Wall)
def delete_wall_cache(sender: models.Model, instance: Wall, **kwargs) -> None:
    from the_wall_api.utils.storage_utils import get_wall_cache_key

    wall_data = {
        'request_type': 'delete_wall',
        'wall_config_hash': instance.wall_config_hash,
    }
    wall_cache_key = get_wall_cache_key(wall_data)
    cache.delete(wall_cache_key)


class WallProfile(models.Model):
    """
    A single profile from the wall with one or multiple sections
    """
    wall = models.ForeignKey(Wall, on_delete=models.CASCADE)
    # Hash the profile with all its sections
    wall_profile_config_hash = models.CharField(max_length=64)
    profile_id = models.IntegerField(validators=[MinValueValidator(1)], null=True, blank=True)
    cost = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # Sufficient for sequential mode
            models.UniqueConstraint(
                fields=['wall', 'wall_profile_config_hash'],
                name='unique_wall_profile_no_profile_id',
                condition=Q(profile_id__isnull=True)
            ),
            # Required for concurrent mode
            models.UniqueConstraint(
                fields=['wall', 'wall_profile_config_hash', 'profile_id'],
                name='unique_wall_profile',
                condition=Q(profile_id__isnull=False)
            ),
        ]


@receiver(post_delete, sender=WallProfile)
def delete_wall_profile_cache(sender: models.Model, instance: WallProfile, **kwargs) -> None:
    from the_wall_api.utils.storage_utils import get_wall_profile_cache_key

    wall_profile_cache_key = get_wall_profile_cache_key(instance.wall_profile_config_hash)
    cache.delete(wall_profile_cache_key)


class WallProfileProgress(models.Model):
    """
    The result for each simulated day of the wall construction
    """
    wall_profile = models.ForeignKey(WallProfile, on_delete=models.CASCADE)
    day = models.IntegerField(validators=[MinValueValidator(1)])
    ice_used = models.IntegerField(validators=[MinValueValidator(0)])
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('wall_profile', 'day')


@receiver(post_delete, sender=WallProfileProgress)
def delete_wall_profile_progress_cache(sender: models.Model, instance: WallProfileProgress, **kwargs) -> None:
    from the_wall_api.utils.storage_utils import get_daily_ice_usage_cache_key
    from the_wall_api.utils.wall_config_utils import SEQUENTIAL

    wall_data = {
        'wall_config_hash': instance.wall_profile.wall.wall_config_hash,
        'num_crews': instance.wall_profile.wall.num_crews,
        'simulation_type': SEQUENTIAL
    }
    wall_profile_progress_cache_key = get_daily_ice_usage_cache_key(
        wall_data, instance.wall_profile.wall_profile_config_hash, instance.day, instance.wall_profile.profile_id
    )
    cache.delete(wall_profile_progress_cache_key)
