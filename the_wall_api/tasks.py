from typing import Callable

from celery import shared_task, Task
from celery.contrib.abortable import AbortableTask

from the_wall_api.utils.celery_task_utils import (
    archive_logs, clean_old_archives, create_wall, log_error, delete_unused_wall_configs,
    orchestrate_wall_config_processing, wall_config_deletion
)


# Helper Functions
def execute_task_with_error_handling(task_func: Callable, *args, **kwargs) -> tuple[str, list]:
    from the_wall_api.utils.error_utils import send_log_error_async

    try:
        return task_func(*args, **kwargs)
    except Exception as unknwn_err:
        error_message = send_log_error_async('celery_tasks', unknwn_err)
        return error_message, []


# === Sequential tasks ===

# File Tasks
@shared_task(queue='sequential_tasks')
def archive_logs_task(*args, **kwargs) -> None:
    execute_task_with_error_handling(archive_logs, *args, **kwargs)


@shared_task(queue='sequential_tasks')
def clean_old_archives_task(*args, **kwargs) -> None:
    execute_task_with_error_handling(clean_old_archives, *args, **kwargs)


@shared_task(queue='sequential_tasks')
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

# === Concurrent tasks ===

# Computation Tasks
@shared_task(queue='concurrent_tasks')
def orchestrate_wall_config_processing_task(*args, **kwargs) -> tuple[str, list]:
    return execute_task_with_error_handling(orchestrate_wall_config_processing, *args, **kwargs)


@shared_task(bind=True, base=AbortableTask, queue='concurrent_tasks')
def create_wall_task(self, *args, test_task: Task | None = None, **kwargs) -> tuple[str, list]:
    if not test_task:
        task = self
    else:
        task = test_task
    return execute_task_with_error_handling(create_wall, task, *args, **kwargs)


@shared_task(queue='concurrent_tasks')
def wall_config_deletion_task(*args, **kwargs) -> tuple[str, list]:
    return execute_task_with_error_handling(wall_config_deletion, *args, **kwargs)


@shared_task(queue='concurrent_tasks')
def delete_unused_wall_configs_task(*args, **kwargs) -> None:
    execute_task_with_error_handling(delete_unused_wall_configs, *args, **kwargs)


# Test Tasks
@shared_task(queue='test_queue')
def orchestrate_wall_config_processing_task_test(*args, **kwargs) -> tuple[str, list]:
    return orchestrate_wall_config_processing_task(*args, **kwargs)


@shared_task(bind=True, base=AbortableTask, queue='test_queue')
def create_wall_task_test(self, *args, **kwargs) -> tuple[str, list]:
    return create_wall_task(*args, test_task=self, **kwargs)


@shared_task(queue='test_queue')
def wall_config_deletion_task_test(*args, **kwargs) -> tuple[str, list]:
    return wall_config_deletion_task(*args, **kwargs)
# === Concurrent tasks end ===
