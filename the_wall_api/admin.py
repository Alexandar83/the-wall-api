from django.contrib import admin
from the_wall_api.models import Wall, WallProfile, WallProfileProgress


class WallAdmin(admin.ModelAdmin):
    list_filter = ('id', 'wall_config_hash')
    search_fields = ('id', 'wall_config_hash', 'num_crews', 'total_cost', 'construction_days', 'date_created')


class WallProfileAdmin(admin.ModelAdmin):
    list_filter = ('id', 'wall', 'wall_profile_config_hash')
    search_fields = ('id', 'wall_profile_config_hash', 'profile_id', 'cost', 'date_created')


class WallProfileProgressAdmin(admin.ModelAdmin):
    list_filter = ('wall_profile', 'day')
    search_fields = ('id', 'day', 'ice_used', 'date_created')


admin.site.register(Wall, WallAdmin)
admin.site.register(WallProfile, WallProfileAdmin)
admin.site.register(WallProfileProgress, WallProfileProgressAdmin)
