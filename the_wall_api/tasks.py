from celery import shared_task

from the_wall_api.utils.file_utils import archive_logs, clean_old_archives, log_error


# === Scheduled tasks ===
@shared_task(queue='file_tasks')    # Task sent to 'file_tasks' queue
def archive_logs_task(*args, **kwargs) -> None:
    from the_wall_api.utils.error_utils import extract_error_traceback

    try:
        archive_logs(*args, **kwargs)
    except Exception as unknwn_err:
        error_message = f'{unknwn_err.__class__.__name__}: {str(unknwn_err)}'
        error_traceback = extract_error_traceback(unknwn_err)
        log_error_task.delay('celery_tasks', error_message, error_traceback)    # type: ignore


@shared_task(queue='file_tasks')    # Task sent to 'file_tasks' queue
def clean_old_archives_task(*args, **kwargs) -> None:
    from the_wall_api.utils.error_utils import extract_error_traceback

    try:
        clean_old_archives(*args, **kwargs)
    except Exception as unknwn_err:
        error_message = f'{unknwn_err.__class__.__name__}: {str(unknwn_err)}'
        error_traceback = extract_error_traceback(unknwn_err)
        log_error_task.delay('celery_tasks', error_message, error_traceback)    # type: ignore

# === Scheduled tasks end ===


@shared_task(queue='file_tasks')    # Task sent to 'file_tasks' queue
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
