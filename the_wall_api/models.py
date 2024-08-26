from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator


class WallProfile(models.Model):
    id = models.AutoField(primary_key=True)
    wall_config_profile_id = models.IntegerField(validators=[MinValueValidator(1)])
    config_hash = models.CharField(max_length=64)
    num_crews = models.IntegerField(null=True, validators=[MinValueValidator(0)])
    date_created = models.DateTimeField(auto_now_add=True)
    max_day = models.IntegerField()

    class Meta:
        unique_together = ('config_hash', 'wall_config_profile_id', 'num_crews')


class SimulationResult(models.Model):
    wall_profile = models.ForeignKey(WallProfile, related_name='simulation_results', on_delete=models.CASCADE)
    day = models.IntegerField(validators=[MinValueValidator(1)])
    ice_used = models.IntegerField(validators=[MinValueValidator(0)])
    # Allows flexibility for cost value format
    cost = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    # 'single_threaded' or 'multi_threaded'
    simulation_type = models.CharField(max_length=20)
    date_simulated = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('wall_profile', 'day', 'simulation_type')
