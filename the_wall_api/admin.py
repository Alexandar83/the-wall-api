from django.contrib import admin
from the_wall_api.models import Wall, WallProfile, WallProfileProgress


class WallAdmin(admin.ModelAdmin):
    list_filter = ('id', 'wall_config_hash', 'total_cost')
    search_fields = ('id', 'wall_config_hash', 'total_cost')


class WallProfileAdmin(admin.ModelAdmin):
    list_filter = ('id', 'wall_profile_config_hash')
    search_fields = ('id', 'wall_profile_config_hash')


class WallProfileProgressAdmin(admin.ModelAdmin):
    list_filter = ('id', 'day')
    search_fields = ('id', 'day')


admin.site.register(Wall, WallAdmin)
admin.site.register(WallProfile, WallProfileAdmin)
admin.site.register(WallProfileProgress, WallProfileProgressAdmin)
