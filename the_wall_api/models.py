from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator


class SimulationType(models.TextChoices):
    SINGLE_THREADED = 'single-threaded', 'Single-Threaded'
    MULTI_THREADED = 'multi-threaded', 'Multi-Threaded'


class YourModel(models.Model):
    simulation_type = models.CharField(
        max_length=20,
        choices=SimulationType.choices,
        default=SimulationType.SINGLE_THREADED
    )


class Wall(models.Model):
    """The whole wall"""
    # Hash the whole wall config with all profiles
    wall_config_hash = models.CharField(max_length=64, unique=True)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    

class WallProfile(models.Model):
    """
    A single profile from the wall with (possible) multiple sections
    Only useful for single-threaded mode
    """
    # Hash only the profile with all its sections
    wall_profile_config_hash = models.CharField(max_length=64, unique=True)
    cost = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    # num_crews = models.IntegerField(null=True, validators=[MinValueValidator(0)])
    date_created = models.DateTimeField(auto_now_add=True)
    max_day = models.IntegerField()


class WallProfileProgress(models.Model):
    """
    The result for each simulated day of the wall construction
    Only useful for single-threaded mode
    """
    wall_profile = models.ForeignKey(WallProfile, related_name='wall_profile', on_delete=models.CASCADE)
    day = models.IntegerField(validators=[MinValueValidator(1)])
    ice_used = models.IntegerField(validators=[MinValueValidator(0)])
    # Allows flexibility for cost value format
    cost = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    date_simulated = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('wall_profile', 'day')
