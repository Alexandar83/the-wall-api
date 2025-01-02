from django.contrib import admin
from the_wall_api.models import (
    Wall, WallConfig, WallConfigReference, WallProgress
)


class WallConfigFilter(admin.SimpleListFilter):
    """Custom filter for WallConfig."""
    title = 'Wall Config'
    parameter_name = 'wall_config'

    def lookups(self, request, model_admin):
        # Fetch WallConfig objects to display as filter options
        wall_configs = WallConfig.objects.all()
        return [(config.pk, str(config)) for config in wall_configs]

    def queryset(self, request, queryset):
        # Filter queryset based on selected WallConfig
        if self.value():
            return queryset.filter(wall_profile__wall__wall_config_id=self.value())
        return queryset


class WallConfigReferenceAdmin(admin.ModelAdmin):
    list_filter = ['user', 'wall_config', 'config_id']
    search_fields = ['user', 'wall_config', 'config_id', 'date_created']


class WallConfigAdmin(admin.ModelAdmin):
    list_filter = ['id', 'status']
    search_fields = ['id', 'wall_config_hash', 'status', 'date_created']


class WallAdmin(admin.ModelAdmin):
    list_filter = ['wall_config']
    search_fields = ['id', 'wall_config_hash', 'num_crews', 'total_cost', 'construction_days', 'date_created']


class WallProgressAdmin(admin.ModelAdmin):
    list_filter = [WallConfigFilter]
    search_fields = ['id', 'day', 'date_created']


admin.site.register(WallConfigReference, WallConfigReferenceAdmin)
admin.site.register(WallConfig, WallConfigAdmin)
admin.site.register(Wall, WallAdmin)
admin.site.register(WallProgress, WallProgressAdmin)
