from typing import Callable

from celery import shared_task

from the_wall_api.utils.celery_task_utils import (
    archive_logs, clean_old_archives, log_error,
)


# Helper Functions
def execute_task_with_error_handling(task_func: Callable, *args, **kwargs) -> None:
    from the_wall_api.utils.error_utils import send_log_error_async

    try:
        return task_func(*args, **kwargs)
    except Exception as unknwn_err:
        send_log_error_async('celery_tasks', unknwn_err)


# === Sequential tasks ===

# File Tasks
@shared_task(queue='file_tasks')
def archive_logs_task(*args, **kwargs) -> None:
    execute_task_with_error_handling(archive_logs, *args, **kwargs)


@shared_task(queue='file_tasks')
def clean_old_archives_task(*args, **kwargs) -> None:
    execute_task_with_error_handling(clean_old_archives, *args, **kwargs)


@shared_task(queue='file_tasks')
def log_error_task(*args, **kwargs) -> str:
    from the_wall_api.utils.error_utils import extract_error_traceback

    error_id = ''
    try:
        error_id = log_error(*args, **kwargs)
    except Exception as unknwn_err:
        print(f'LOG_ERROR_TASK ERROR: {unknwn_err}')
        exception_traceback = extract_error_traceback(unknwn_err)
        for line in exception_traceback:
            print(line)

    return error_id


# === Sequential tasks end ===
