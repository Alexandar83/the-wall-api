from pythonjsonlogger.jsonlogger import JsonFormatter


class CustomJsonFormatter(JsonFormatter):
    """
    Customize the JsonFormatter to rename some of the fields, and ensure the desired field order
    """
    def process_log_record(self, log_record):
        # Rename 'asctime' to 'timestamp'
        if 'asctime' in log_record:
            log_record['timestamp'] = log_record.pop('asctime')
        # Rename 'levelname' to 'level
        if 'levelname' in log_record:
            log_record['level'] = log_record.pop('levelname')

        # Define the custom field order
        field_order = ['error_id', 'levelname', 'timestamp', 'request_info', 'message', 'traceback']

        # Reorder the log_record to have fields in the desired order
        log_record = {key: log_record[key] for key in field_order if key in log_record}

        return super().process_log_record(log_record)
