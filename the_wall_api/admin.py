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
            return queryset.filter(wall__wall_config_id=self.value())
        return queryset


class WallConfigReferenceFilter(admin.SimpleListFilter):
    """Custom filter for WallConfigReference."""
    title = 'Wall Config Reference'
    parameter_name = 'wall_config_reference'

    def lookups(self, request, model_admin):
        # Fetch WallConfigReference objects to display as filter options
        references = WallConfigReference.objects.all()
        return [(reference.pk, f"{reference.user.username} - {reference.config_id}") for reference in references]

    def queryset(self, request, queryset):
        # Filter queryset based on selected WallConfigReference
        if self.value():
            if queryset.model == WallProgress:
                return queryset.filter(wall__wall_config__wall_config_references__pk=self.value())
            if queryset.model == Wall:
                return queryset.filter(wall_config__wall_config_references__pk=self.value())
        return queryset


class WallConfigReferenceAdmin(admin.ModelAdmin):
    list_display = ['config_id', 'user', 'status', 'wall_config', 'date_created']
    list_filter = ['config_id', 'user', 'status', 'wall_config']
    search_fields = ['user__username', 'wall_config__wall_config_hash', 'config_id', 'status']


class WallConfigAdmin(admin.ModelAdmin):
    list_display = ['id', 'wall_config_hash', 'status', 'deletion_initiated', 'date_created']
    list_filter = ['id', 'status']
    search_fields = ['id', 'wall_config_hash', 'status']


class WallAdmin(admin.ModelAdmin):
    list_display = ['id', 'wall_config', 'num_crews', 'total_ice_amount', 'construction_days', 'date_created']
    list_filter = [WallConfigReferenceFilter, 'wall_config']
    search_fields = ['id', 'wall_config__wall_config_hash', 'num_crews', 'total_ice_amount']


class WallProgressAdmin(admin.ModelAdmin):
    list_filter = [WallConfigFilter, WallConfigReferenceFilter]
    search_fields = [
        'id', 'day', 'wall__wall_config__wall_config_hash', 'wall__wall_config__wall_config_references__config_id',
        'wall__wall_config__wall_config_references__user__username'
    ]


admin.site.register(WallConfigReference, WallConfigReferenceAdmin)
admin.site.register(WallConfig, WallConfigAdmin)
admin.site.register(Wall, WallAdmin)
admin.site.register(WallProgress, WallProgressAdmin)
