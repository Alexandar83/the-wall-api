from django.apps import AppConfig


class TheWallApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'the_wall_api'

    def ready(self):
        # Ensure the Celery tasks are discoverable in celery.py
        import the_wall_api.tasks       # noqa
        # Import the OpenAPI extensions to ensure they are registered
        # with drf-spectacular during application initialization.
        import the_wall_api.utils.open_api_schema_utils.auth_schema_extensions  # noqa
