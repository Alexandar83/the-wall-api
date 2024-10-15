import os

from celery import shared_task

from the_wall_api.utils.file_utils import archive_logs, clean_old_archives

# Lightweight Celery config without full app loading:
# reduce app dependencies for lightweight worker tasks as much as possible
# to avoid import conflicts
LIGHT_CELERY_CONFIG = os.getenv('LIGHT_CELERY_CONFIG', False) == 'True'
if not LIGHT_CELERY_CONFIG:
    from the_wall_api.utils.error_utils import log_error_to_db


# === Scheduled tasks ===
@shared_task(queue='file_tasks')    # Task sent to 'file_tasks' queue
def archive_logs_task(*args, **kwargs) -> None:
    try:
        archive_logs(*args, **kwargs)
    except Exception as unkwn_err:
        # TODO: add logging
        print(f'ARCHIVE_LOGS_TASK ERROR: {unkwn_err}')


@shared_task(queue='file_tasks')    # Task sent to 'file_tasks' queue
def clean_old_archives_task(*args, **kwargs) -> None:
    try:
        clean_old_archives(*args, **kwargs)
    except Exception as unkwn_err:
        # TODO: add logging
        print(f'CLEAN_OLD_ARCHIVES_TASK ERROR: {unkwn_err}')

# === Scheduled tasks end ===
