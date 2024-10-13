# Management of logs retention policies

from datetime import datetime, timedelta
import gzip
import os
from shutil import copyfileobj

from django.conf import settings

LOGS_DIR = settings.LOGS_DIR
LOGS_ARCHIVE_DIR = str(settings.LOGS_ARCHIVE_DIR)
LOGS_RETENTION_DAYS = settings.LOGS_RETENTION_DAYS
LOGS_ARCHIVE_RETENTION_DAYS = settings.LOGS_ARCHIVE_RETENTION_DAYS


def archive_logs(test_data: dict | None = None) -> None:
    """Move and compress logs older than LOGS_RETENTION_DAYS to the archive directory."""
    log_retention_date, logs_dir, logs_arhive_dir = get_archive_logs_params(test_data)

    os.makedirs(logs_arhive_dir, exist_ok=True)

    for log_file in os.listdir(logs_dir):
        log_path = os.path.join(logs_dir, log_file)

        # Only process files (not directories)
        if os.path.isfile(log_path):
            # Get the file's last modification time
            file_mtime = datetime.fromtimestamp(os.path.getmtime(log_path))

            # Archive the file if it's older than the retention period
            if file_mtime < log_retention_date:
                archive_path = os.path.join(logs_arhive_dir, log_file + '.gzip')

                # Compress the log file and move it to the archive
                with open(log_path, 'rb') as f_in:
                    with gzip.open(archive_path, 'wb', compresslevel=9) as f_out:
                        copyfileobj(f_in, f_out)

                # Delete the original log file after compressing
                os.remove(log_path)


def get_archive_logs_params(test_data: dict | None = None) -> tuple[datetime, str, str]:
    now = datetime.now()
    if not test_data:
        log_retention_date = now - timedelta(days=LOGS_RETENTION_DAYS)
        logs_dir = LOGS_DIR
        logs_archive_dir = LOGS_ARCHIVE_DIR
    else:
        log_retention_date = now
        logs_dir = os.path.join(*test_data['test_logs_dir'])
        logs_archive_dir = os.path.join(*test_data['test_logs_dir_archive'])

    return log_retention_date, logs_dir, logs_archive_dir


def clean_old_archives(test_data: dict | None = None) -> None:
    """Delete archived logs older than LOGS_ARCHIVE_RETENTION_DAYS."""
    archive_retention_date, logs_archive_dir = get_clean_old_archives_params(test_data)

    for archive_file in os.listdir(logs_archive_dir):
        archive_path = os.path.join(logs_archive_dir, archive_file)

        # Only process files (not directories)
        if os.path.isfile(archive_path):
            file_mtime = datetime.fromtimestamp(os.path.getmtime(archive_path))

            if file_mtime < archive_retention_date:
                # Delete the old archive
                os.remove(archive_path)


def get_clean_old_archives_params(test_data: dict | None = None) -> tuple[datetime, str]:
    now = datetime.now()
    if not test_data:
        archive_retention_date = now - timedelta(days=LOGS_ARCHIVE_RETENTION_DAYS)
        logs_archive_dir = LOGS_ARCHIVE_DIR
    else:
        archive_retention_date = now
        logs_archive_dir = os.path.join(*test_data['test_logs_dir_archive'])

    return archive_retention_date, logs_archive_dir
