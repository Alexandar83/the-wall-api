# Management of logs retention policies

from datetime import datetime, timedelta
from gzip import open as gzip_open
import logging
import os
from shutil import copyfileobj
from time import sleep

LIGHT_CELERY_CONFIG = os.getenv('LIGHT_CELERY_CONFIG', False) == 'True'

if not LIGHT_CELERY_CONFIG:

    from django.conf import settings

    BUILD_SIM_LOGS_DIR = settings.BUILD_SIM_LOGS_DIR
    BUILD_SIM_LOGS_ARCHIVE_DIR = str(settings.BUILD_SIM_LOGS_ARCHIVE_DIR)
    BUILD_SIM_LOGS_RETENTION_DAYS = settings.BUILD_SIM_LOGS_RETENTION_DAYS
    BUILD_SIM_LOGS_ARCHIVE_RETENTION_DAYS = settings.BUILD_SIM_LOGS_ARCHIVE_RETENTION_DAYS

    CELERY_BROKER_URL = settings.CELERY_BROKER_URL

DELETION_RETRIES = 5


def archive_logs(input_params: dict | None = None, test_input_params: dict | None = None) -> None:
    """Move and compress logs older than the parametrized retention period to the archive directory."""
    log_retention_date, logs_dir, logs_arhive_dir = get_archive_logs_details(input_params, test_input_params)

    os.makedirs(logs_arhive_dir, exist_ok=True)

    for log_file in os.listdir(logs_dir):
        # Skip files in use
        if 'LOCKED' in log_file:
            continue

        log_path = os.path.join(logs_dir, log_file)

        # Only process files (not directories)
        if os.path.isfile(log_path):
            # Get the file's last modification time
            file_mtime = datetime.fromtimestamp(os.path.getmtime(log_path))

            # Archive the file if it's older than the retention period
            if file_mtime < log_retention_date:
                archive_path = os.path.join(logs_arhive_dir, log_file + '.gzip')

                # Compress the log file and copy it to the archive
                with open(log_path, 'rb') as f_in:
                    with gzip_open(archive_path, 'wb', compresslevel=9) as f_out:
                        copyfileobj(f_in, f_out)

                # Delete the original log file after compressing
                remove_file(log_path)


def clean_old_archives(input_params: dict | None = None, test_input_params: dict | None = None) -> None:
    """Delete archived logs older than the parametrized retention period."""
    archive_retention_date, logs_archive_dir = get_clean_old_archives_details(input_params, test_input_params)

    for archive_file in os.listdir(logs_archive_dir):
        archive_path = os.path.join(logs_archive_dir, archive_file)

        # Only process files (not directories)
        if os.path.isfile(archive_path):
            file_mtime = datetime.fromtimestamp(os.path.getmtime(archive_path))

            if file_mtime < archive_retention_date:

                # Delete the old archive
                remove_file(archive_path)


def log_error(error_type: str, error_message: str, error_traceback: str, request_info: dict = {}, error_id_prefix: str = '') -> str:
    from redis import Redis

    # Redis DB2 is used for persistent data
    redis_connection = Redis.from_url(CELERY_BROKER_URL)
    error_id = error_id_prefix + str(redis_connection.incr('unknown_errors_counter'))

    logger = logging.getLogger(error_type)
    logger.error(error_message, extra={'traceback': error_traceback, 'request_info': request_info, 'error_id': error_id})

    return error_id


def get_archive_logs_details(input_params: dict | None = None, test_input_params: dict | None = None) -> tuple[datetime, str, str]:
    now = datetime.now()

    if input_params:
        if input_params['logs_type'] == 'build_sim':
            log_retention_date = now - timedelta(days=BUILD_SIM_LOGS_RETENTION_DAYS)
            return log_retention_date, BUILD_SIM_LOGS_DIR, BUILD_SIM_LOGS_ARCHIVE_DIR

    if test_input_params:
        if test_input_params['logs_type'] == 'build_sim':
            log_retention_date = now
            logs_dir, logs_archive_dir, _ = get_test_log_archive_details(
                BUILD_SIM_LOGS_DIR, test_input_params['test_file_name']
            )
            return log_retention_date, logs_dir, logs_archive_dir

    raise ValueError('Invalid or missing logs type')


def get_clean_old_archives_details(input_params: dict | None = None, test_input_params: dict | None = None) -> tuple[datetime, str]:
    now = datetime.now()

    if input_params:
        if input_params['logs_type'] == 'build_sim':
            archive_retention_date = now - timedelta(days=BUILD_SIM_LOGS_ARCHIVE_RETENTION_DAYS)
            return archive_retention_date, BUILD_SIM_LOGS_ARCHIVE_DIR

    if test_input_params:
        if test_input_params['logs_type'] == 'build_sim':
            archive_retention_date = now
            _, logs_archive_dir, _ = get_test_log_archive_details(
                BUILD_SIM_LOGS_DIR, test_input_params['test_file_name']
            )
            return archive_retention_date, logs_archive_dir

    raise ValueError('Invalid or missing logs type')


def get_test_log_archive_details(root_dir: str, test_file_name: str) -> tuple[str, str, str]:
    testing_dir_name = 'testing'
    test_logs_dir = os.path.join(root_dir, testing_dir_name, 'test_logs')
    test_logs_dir_archive = os.path.join(test_logs_dir, 'archive')
    test_file = os.path.join(test_logs_dir, test_file_name)

    return test_logs_dir, test_logs_dir_archive, test_file


def remove_file(file_path: str) -> None:
    if os.path.exists(file_path):
        retries = 0
        deletion_retry_delay = 0
        while retries < DELETION_RETRIES:
            try:
                os.remove(file_path)
                break
            except PermissionError:
                retries += 1
                deletion_retry_delay += 2
                print(f'Failed to delete {file_path} - access denied. Retrying...')
                sleep(deletion_retry_delay)
