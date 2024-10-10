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


def archive_logs() -> None:
    """Move and compress logs older than retention_days to the archive directory."""
    os.makedirs(LOGS_ARCHIVE_DIR, exist_ok=True)

    # Calculate the retention period
    now = datetime.now()
    log_retention_date = now - timedelta(days=LOGS_RETENTION_DAYS)

    for log_file in os.listdir(LOGS_DIR):
        log_path = os.path.join(LOGS_DIR, log_file)
        
        # Only process files (not directories)
        if os.path.isfile(log_path):
            # Get the file's last modification time
            file_mtime = datetime.fromtimestamp(os.path.getmtime(log_path))
            
            # Archive the file if it's older than the retention period
            if file_mtime < log_retention_date:
                archive_path = os.path.join(LOGS_ARCHIVE_DIR, log_file + '.gzip')
                
                # Compress the log file and move it to the archive
                with open(log_path, 'rb') as f_in:
                    with gzip.open(archive_path, 'wb', compresslevel=9) as f_out:
                        copyfileobj(f_in, f_out)
                
                # Delete the original log file after compressing
                os.remove(log_path)


def clean_old_archives():
    """Delete archived logs older than max_age_days."""
    now = datetime.now()
    archive_retention_date = now - timedelta(days=LOGS_ARCHIVE_RETENTION_DAYS)

    for archive_file in os.listdir(LOGS_ARCHIVE_DIR):
        archive_path = os.path.join(LOGS_ARCHIVE_DIR, archive_file)
        
        # Only process files (not directories)
        if os.path.isfile(archive_path):
            file_mtime = datetime.fromtimestamp(os.path.getmtime(archive_path))
            
            if file_mtime < archive_retention_date:
                # Delete the old archive
                os.remove(archive_path)
