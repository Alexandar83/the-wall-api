import os
from celery import Celery
from celery.schedules import crontab


def setup_django_settings():
    """Setup Django settings module and Celery configuration."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

    # 1. Ensures the Celery tasks are discoverable in configure_celery_app
    # 2. Avoids "django.core.exceptions.AppRegistryNotReady: Apps aren't loaded yet."
    # when launching tasks
    import django
    django.setup()


def configure_celery_app(app):
    """Configure Celery app with settings and task discovery."""
    # Seacrh for Celery settings and use them for the internal setup of the Celery service
    app.config_from_object('django.conf:settings', namespace='CELERY')

    # Load task modules (tasks.py) from all registered Django apps
    # django must be fully set up
    app.autodiscover_tasks()


def schedule_periodic_tasks(app):
    app.conf.beat_schedule = {
        'archive-logs': {
            'task': 'the_wall_api.tasks.archive_logs_task',
            'schedule': crontab(hour='0', minute='0', day_of_week='sunday'),
        },
        'clean-old-archives': {
            'task': 'the_wall_api.tasks.clean_old_archives_task',
            'schedule': crontab(hour='0', minute='0', day_of_week='sunday'),
        },
    }


def print_registered_tasks(app: Celery, verbose: bool = False) -> None:
    """Helper function to check if all tasks are discovered."""
    if verbose:
        print('REGISTERED TASKS:')
        for task_name in app.tasks:
            print(task_name)


def create_celery_app() -> Celery:
    """Create and configure the Celery app."""
    app = Celery('the_wall_api')    # Label the app

    # Ensure broker retries on startup for Celery 6.0+
    app.conf.broker_connection_retry_on_startup = True

    setup_django_settings()
    configure_celery_app(app)
    print_registered_tasks(app)
    schedule_periodic_tasks(app)

    return app


app = create_celery_app()
