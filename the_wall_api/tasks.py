from celery import shared_task

from the_wall_api.utils.file_utils import archive_logs, clean_old_archives
from the_wall_api.utils.error_utils import log_error_to_db


# === Scheduled tasks ===
@shared_task(queue='file_tasks')    # Task sent to 'file_tasks' queue
def archive_logs_task() -> None:
    try:
        archive_logs()
    except Exception as unkwn_err:
        log_error_to_db(unkwn_err)


@shared_task(queue='file_tasks')    # Task sent to 'file_tasks' queue
def clean_old_archives_task() -> None:
    try:
        clean_old_archives()
    except Exception as unkwn_err:
        log_error_to_db(unkwn_err)

# === Scheduled tasks end ===
