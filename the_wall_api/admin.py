from django.contrib import admin

# Register your models here.
from the_wall_api.models import WallProfile, SimulationResult


class WallProfileAdmin(admin.ModelAdmin):
    list_filter = ('id', 'config_hash', 'wall_config_profile_id', 'num_crews')
    search_fields = ('id', 'config_hash', 'wall_config_profile_id', 'num_crews')


class SimulationResultAdmin(admin.ModelAdmin):
    list_filter = ('id', 'day', 'simulation_type')
    search_fields = ('id', 'day', 'simulation_type')


admin.site.register(WallProfile, WallProfileAdmin)
admin.site.register(SimulationResult, SimulationResultAdmin)
