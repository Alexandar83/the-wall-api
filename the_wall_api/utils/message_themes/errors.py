from typing import Any

# ====== Serializers ======
DATA_NOT_A_FILE = 'The submitted data was not a file. Check the encoding type on the form.'

NO_FILE_SUBMITTED = 'No file was submitted.'

INVALID_JSON_FILE_FORMAT = 'Invalid JSON file format.'
INVALID_STRING = 'Not a valid string.'

THE_FILE_IS_EMPTY = 'The submitted file is empty.'

THIS_FIELD_IS_REQUIRED = 'This field is required.'
THIS_FIELD_MAY_NOT_BE_BLANK = 'This field may not be blank.'
THIS_FIELD_MAY_NOT_BE_NULL = 'This field may not be null.'

VALID_INTEGER_REQUIRED = 'A valid integer is required.'


def file_limit_per_user_reached(file_limit: int) -> str:
    return f'File limit of {file_limit} per user reached.'


def wall_config_exists(config_id: str, username: str) -> str:
    return f"Wall config '{config_id}' already exists for user '{username}'."


def invalid_config_id_list_format(id_lst_splt_err: Exception | str) -> str:
    return f'Invalid config_id_list format: {id_lst_splt_err}.'


def config_ids_with_invalid_length(invalid_length_list: list[str]) -> str:
    return f"Config IDs with invalid length: {invalid_length_list}."


def ensure_value_greater_than_or_equal_to(limit: int) -> str:
    return f'Ensure this value is greater than or equal to {limit}.'


# ====== Serializers (end) ======
# ====== Views ======
ENDPOINT_NOT_FOUND = 'Endpoint not found.'
ENDPOINT_NOT_FOUND_DETAILS = 'The requested API endpoint does not exist. Please use the available endpoints.'

INVALID_EMAIL = 'Enter a valid email address.'
INVALID_PASSWORD = 'Invalid password.'
INVALID_TOKEN = 'Invalid token.'

NOT_AUTHENTICATED = 'Not authenticated'
NOT_AUTHENTICATED_RESPONSE = 'Authentication credentials were not provided.'

PASSWORD_TOO_SHORT = 'This password is too short. It must contain at least 8 characters.'
PASSWORD_TOO_COMMON = 'This password is too common.'
PASSWORD_NUMERIC = 'This password is entirely numeric.'
PASSWORD_SIMILAR_TO_USERNAME = 'The password is too similar to the username.'

UNABLE_TO_LOG_IN = 'Unable to log in with provided credentials.'
USERNAME_EXISTS = 'A user with that username already exists.'


def no_crew_worked_on_profile(profile_id: int, day: int) -> str:
    return f'No crew has worked on profile {profile_id} on day {day}.'


def ensure_config_id_valid_length(config_id_max_length: int) -> str:
    return f'Ensure this field has no more than {config_id_max_length} characters.'


def request_was_throttled(wait_seconds: int) -> str:
    return f'Request was throttled. Expected available in {wait_seconds} seconds.'


def file_extension_not_allowed(forbidden_extension: str, allowed_extensions: str) -> str:
    return f'File extension “{forbidden_extension}” is not allowed. Allowed extensions are: {allowed_extensions}.'


# ====== Views (end) ======
# ====== Concurrency ======
LOG_STREAM_REQUIRED_WHEN_NO_QUEUE = 'Log stream is required when queue is not provided!'


def multiprocessing_max_allowed_sections(concurrency_mode: str, sections_number: int) -> str:
    return f'Max. allowed number of sections for {concurrency_mode} is {sections_number}.'


# ====== Concurrency (end) ======
# ====== Celery ======
DELETION_ALREADY_STARTED = 'Deletion already initiated by another process.'
INTERRUPTED_BY_DELETION_TASK = 'Interrupted by a deletion task'
INVALID_LOGS_TYPE = 'Invalid or missing logs type.'
WALL_CREATION_TASK_GROUP_INIT_ERROR = 'Task group initialization error.'
WALL_CREATION_TASK_GROUP_FAILED = 'Wall creation task group failed - check error logs.'
WALL_CONFIG_NOT_PROCESSED_DELETION_STARTED = f'Not processed. {DELETION_ALREADY_STARTED}'


def failed_to_delete_file(file_path: str) -> str:
    return f'Failed to delete {file_path} - access denied. Retrying...'


def wall_config_not_processed(status: str) -> str:
    return f'Not processed, current status: {status}.'


def abort_task_group_timeout_error(abort_wait_period: int) -> str:
    return (
        f'Revocation of create wall tasks due to deletion '
        f'initiation takes more than {abort_wait_period} seconds.'
    )


# ====== Celery (end) ======
# ====== API Requests Flow ======
CONSTRUCTION_ERROR_SOURCE_UPLOAD = 'config file upload'
CONSTRUCTION_ERROR_SOURCE_DELETE = 'config file delete'
CONSTRUCTION_ERROR_SOURCE_SIMULATION = 'construction simulation'
CREATE_NEW_WALL_CONFIG_ERROR_RESULT = 'Being initialized in another process'
MANAGE_WALL_CONFIG_OBJECT_ERROR_RESULT = 'Already uploaded for this user.'
USER_TASKS_IN_PROGRESS = 'The following config IDs have calculations in progress for this user'
WALL_CONFIG_DELETION_BEING_PROCESSED = (
    'A deletion of an existing wall config is being processed - please try again later.'
)


def out_of_range_finishing_message_1(max_value: int) -> str:
    return f'The wall has been finished for {max_value} days.'


def out_of_range_finishing_message_2(max_value: int) -> str:
    return f'The wall has {max_value} profiles.'


def out_of_range(out_of_range_type: str, finishing_msg: str) -> str:
    return f'The {out_of_range_type} is out of range. {finishing_msg}'


def file_does_not_exist_for_user(config_id: str, username: str) -> str:
    return f"File with config ID '{config_id}' does not exist for user '{username}'."


def no_files_exist_for_user(username: str) -> str:
    return f"No files exist for user '{username}' in the database."


def no_matching_files_for_user(username: str) -> str:
    return f"No matching files for user '{username}' exist for the provided config ID list."


def files_with_config_id_not_found_for_user(not_found_ids: list[str], username: str) -> str:
    plrl_suffix = 's' if len(not_found_ids) > 1 else ''

    return f"File{plrl_suffix} with config ID{plrl_suffix} {not_found_ids} not found for user '{username}'."


def must_be_handled_in(method_name: str) -> str:
    return f'Must be handled in {method_name}!'


def resource_not_found_status(status_label: str) -> str:
    return f"The resource is not found. Wall configuration status = '{status_label}'."


def wall_config_already_uploaded_suffix(status_label: str) -> str:
    return f" Wall configuration status = '{status_label}'."


def wall_config_already_uploaded(config_id: str, error_message_suffix: str = '') -> str:
    return f"This wall configuration is already uploaded with config_id = '{config_id}'.{error_message_suffix}"


def user_tasks_in_progress(user_tasks_in_progress: list[str]) -> str:
    return (
        f'{USER_TASKS_IN_PROGRESS}'
        f': {user_tasks_in_progress}. Please wait until they are completed.'
    )


def wall_operation_failed(error_msg_source: str) -> str:
    return f'Wall {error_msg_source} failed. Please contact support.'


def unknown_request_type(request_type: str) -> str:
    return f'Unknown request type: {request_type}'


# == API Requests Flow (end) ======
# == Wall Construction Validation ==
INVALID_WALL_CONFIG = 'Invalid wall configuration!'
MAXIMUM_NUMBER_OF_SECTIONS = 'The maximum number of sections'
MAXIMUM_NUMBER_OF_PROFILE_SECTIONS = 'Each profile must have a maximum of'
MAXIMUM_WALL_LENGTH = 'The maximum wall length'
MUST_BE_NESTED_LIST = 'Must be a nested list of lists of integers.'
PROFILE_MUST_BE_LIST_OF_INTEGERS = 'Each profile must be a list of integers.'
SECTION_HEIGHT_MUST_BE_INTEGER = 'must be an integer'
SECTION_HEIGHT_MUST_BE_GREATER_THAN_ZERO = 'must be >= 0'


def must_be_nested_list_of_lists_of_integers() -> str:
    return f'{INVALID_WALL_CONFIG} {MUST_BE_NESTED_LIST}'


def profile_must_be_list_of_integers() -> str:
    return f'{INVALID_WALL_CONFIG} {PROFILE_MUST_BE_LIST_OF_INTEGERS}'


def maximum_number_of_sections_exceeded(sections_count: int) -> str:
    return (
        f'{INVALID_WALL_CONFIG} {MAXIMUM_NUMBER_OF_SECTIONS} '
        f'({sections_count}) has been exceeded.'
    )


def maximum_wall_length_exceeded(max_wall_length: int) -> str:
    return f'{INVALID_WALL_CONFIG} {MAXIMUM_WALL_LENGTH} ({max_wall_length}) has been exceeded.'


def maximum_profile_sections_exceeded(max_profile_sections: int) -> str:
    return (
        f'{INVALID_WALL_CONFIG} {MAXIMUM_NUMBER_OF_PROFILE_SECTIONS} '
        f'{max_profile_sections} sections.'
    )


def invalid_section_height(
    section_height: Any, profile_id: int, section_number: int, error_message_suffix: str
) -> str:
    return (
        f"{INVALID_WALL_CONFIG} The section height ({section_height}) of "
        f'profile {profile_id} - section {section_number} {error_message_suffix}.'
    )


def section_height_must_be_less_than_limit(max_section_height: int) -> str:
    return f'must be <= {max_section_height}'

# ====== Wall Construction Validation (end) ======
