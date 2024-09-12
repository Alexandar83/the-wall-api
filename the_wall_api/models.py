from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator
from django.db.models import Q


class Wall(models.Model):
    """The whole wall"""
    # Hash the whole wall config with all profiles
    wall_config_hash = models.CharField(max_length=64)
    num_crews = models.IntegerField(validators=[MinValueValidator(0)])
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    construction_days = models.IntegerField()
    date_created = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('wall_config_hash', 'num_crews')


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
