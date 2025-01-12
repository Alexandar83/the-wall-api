# ====== Views ======
# == User Management ==
USER_MANAGEMENT_TAG = 'User Management'
USER_MANAGEMENT_TAG_DESCRIPTION = 'Manage users, authentication, and passwords'

CREATE_USER_SUMMARY = 'Create User'
CREATE_USER_DESCRIPTION = 'Register a new user with email and password.'

DELETE_USER_SUMMARY = 'Delete User'
DELETE_USER_DESCRIPTION = (
    'This endpoint requires the `current_password` parameter in the request\'s body.\n\n'
    '<b>Example request body:</b>\n'
    '```json\n'
    '{\n'
    '  "current_password": "strongpassword#123"\n'
    '}\n'
    '```\n'
    '<b>Note:</b> Due to OpenAPI 3.1 limitations, request body schema '
    'and examples cannot be included in the schema documentation for DELETE endpoints.\n\n'
    '<i>*The "Try it out" functionality also doesn\'t work properly in Swagger UI.</i>'
)

SET_PASSWORD_SUMMARY = 'Update User Password'
SET_PASSWORD_DESCRIPTION = 'Change/reset the user\'s current password.'

TOKEN_LOGIN_SUMMARY = 'Obtain Authentication Token'
TOKEN_LOGIN_DESCRIPTION = (
    'Obtain an authentication token by creating a new one or '
    'retrieving an existing valid token.'
)

TOKEN_LOGOUT_SUMMARY = 'Revoke Authentication Token'
TOKEN_LOGOUT_DESCRIPTION = 'Revoke an existing authentication token - requires only a valid token.'

# == User Management (end) ==
# == File Management ==
FILE_MANAGEMENT_TAG = 'File Management'
FILE_MANAGEMENT_TAG_DESCRIPTION = 'Upload, list, and delete wall configuration files'

FILE_UPLOAD_SUMMARY = 'Upload Wall Configuration File'
FILE_UPLOAD_DESCRIPTION = (
    'Allows users to upload wall configuration files, which are '
    'parsed and stored as structured data in the database. \n\nThe processed data can be '
    'accessed through the `profiles-days` and `profiles-overview` endpoints.'
    '<br><br>'
    '*<b><i>Swagger UI-only:</i></b> \n\n'
    '<i>If a file upload fails due to validation errors,</i> \n\n'
    '<i>and the file is subsequently modified to meet the validation requirements,</i> \n\n'
    '<i>the "Try it out" functionality must be reset before attempting a second upload.</i>'
)

FILES_LIST_SUMMARY = 'List Wall Configuration Files'
FILES_LIST_DESCRIPTION = 'Retrieve a list of wall configuration files uploaded by the user.'

FILES_DELETE_SUMMARY = 'Delete Wall Configuration File'
FILES_DELETE_DESCRIPTION = 'Delete a wall configuration file uploaded by the user.'

# == File Management (end) ==
# == Profiles ==
COST_AND_DAILY_ICE_AMOUNTS_TAG = 'Costs and Daily Ice Amounts'
COST_AND_DAILY_ICE_AMOUNTS_TAG_DESCRIPTION = 'Analyze construction costs and daily ice usage'

PROFILES_DAYS_SUMMARY = 'Daily Profile Construction Ice Amount'
PROFILES_DAYS_DESCRIPTION = 'Retrieve the amount of ice used on a specific day for a given wall profile.'

PROFILES_OVERVIEW_SUMMARY = 'Total Wall Construction Cost'
PROFILES_OVERVIEW_DESCRIPTION = 'Retrieve the total wall construction cost.'

PROFILES_OVERVIEW_DAY_SUMMARY = 'Daily Wall Construction Cost'
PROFILES_OVERVIEW_DAY_DESCRIPTION = 'Retrieve the total construction cost for a specific day.'

SINGLE_PROFILE_OVERVIEW_DAY_SUMMARY = 'Daily Profile Construction Cost'
SINGLE_PROFILE_OVERVIEW_DAY_DESCRIPTION = 'Retrieve the cost on a specific day for a given wall profile.'

# == Profiles (end) ==
# ====== Views (end) ======

# ====== Schema ======
# === Common ===
TOKEN_AUTH_SCHEME_DESCRIPTION = (
    # Use &lt; to represent a literal < and &gt; to represent a literal >
    # in the description, ensuring proper rendering in Markdown viewers like Redoc.
    'Enter your token in the format: <b>Token &lt;your_token&gt;</b>\n\n'
    'Example header:\n'
    '{"Authorization": "Token abcdef1234567890"}'
)
# === Common (end) ===
# === Examples ===
CHANGE_PASSWORD_REQUEST = 'Change password request'
CHANGE_PASSWORD_REQUEST_SUMMARY = 'Valid request to change a user\'s password'

CREATE_USER_REQUEST = 'Create user request'
CREATE_USER_REQUEST_SUMMARY = 'Valid request to create a new user'

FILE_NOT_EXISTING_FOR_USER = 'File not existing for user'

INVALID_WALL_CONFIG_STATUS = 'Invalid wall config status'

THROTTLED = 'Throttled'

TOKEN_LOGIN_REQUEST = 'Token login request'
TOKEN_LOGIN_REQUEST_SUMMARY = 'Valid request to generate a token for a user'

# === Examples (end) ===
# === Parameters ===
NUM_CREWS_PARAMETER_DESCRIPTION = (
    'The number of crews involved in the simulation.'
    '<br><br>'
    '<i><b>When included</b>: the wall build simulation is concurrent.</i>'
    '<br><br>'
    '<i><b>When omitted</b>: the simulation defaults to sequential processing.</i>'
    '<br><br>'
)
CONFIG_ID_PARAMETER_DESCRIPTION = 'Wall configuration file ID.'
FILE_DELETE_CONFIG_ID_LIST_PARAMETER_DESCRIPTION = (
    'Comma-separated list of wall configuration file IDs to be deleted, <b><i>(provided as a single string)</i></b>.'
    '<br><br>'
    '<b><i>Example</b>: test_config_1,test_config_2,test_config_3</i>'
    '<br><br>'
    '<b><i>Important: Deletes all user files if omitted!</i></b>'
    '<br><br>'
)
WALLCONFIG_FILE_PARAMETER_DESCRIPTION = (
    'A JSON file containing Wall configuration data.\n\n'
    'Should contain a nested list of lists of integers.\n\n'
    '**Example**:\n'
    '[[1, 5, 10], [5, 7, 16, 23]]'
)

# === Parameters (end) ===
# === Responses ===
CONFIG_ID_ALREADY_EXISTS = 'config_id already exists'
CONFIG_ID_BLANK_STRING = 'config_id blank string'
CONFIG_ID_NULL_OBJECT = 'config_id Null object'
CREATE_USER_SUMMARY = 'Create user'
CURRENT_PASSWORD_REQUIRED = 'Current password required'

EMPTY_FILE = 'Empty file'

FILE_LIMIT_REACHED = 'File limit reached'
FILE_NULL_OBJECT = 'File Null object'
FILES_NOT_FOUND = 'Files not found'
FILE_UPLOAD_TECHNICAL_ERROR = 'File upload technical error'

INVALID_CONFIG_ID_LENGTH = 'Invalid config_id length'
INVALID_CONFIG_ID_LIST_FORMAT = 'Invalid config_id_list format'
INVALID_EMAIL_FORMAT = 'Invalid email format'
INVALID_FILE_EXTENSION = 'Invalid file extension'
INVALID_FILE_FORMAT = 'Invalid file format'
INVALID_LENGTH = 'Invalid length'
INVALID_PROFILE_SECTIONS_COUNT = 'Invalid profile sections count'
INVALID_SECTIONS_COUNT = 'Invalid sections count'
INVALID_SECTION_TYPE = 'Invalid section type'
INVALID_STRING = 'Invalid string'
INVALID_WALL_LENGTH = 'Invalid wall length'

MISSING_CONFIG_ID = 'Missing config_id'
MISSING_FILE = 'Missing file'
MISSING_REQUIRED_FIELDS = 'Missing required fields'

NO_FILES_FOR_USER = 'No files for the user'
NO_MATCHING_FILES = 'No matching files'
NO_WORK_ON_PROFILE = 'No work on profile'
NOT_A_FILE = 'Not a file'
NULL_OBJECT = 'Null object'

OUT_OF_RANGE_DAY = 'Day Out of Range'
OUT_OF_RANGE_PROFILE_ID = 'Profile ID Out of Range'

PROFILE_NOT_A_LIST = 'Profile not a list'

SIMULATION_DATA_INCONSISTENCY = 'Simulation Data Inconsistency'
SUMMARY_FILES_LIST_RESPONSE = 'Wall config ID list'
SUMMARY_PROFILES_DAYS_RESPONSE = 'Profile construction cost'
SUMMARY_TOKEN_LOGIN = 'Valid token'

TECHNICAL_ERROR_DELETION = 'Deletion technical error'
TOTAL_CONSTRUCTION_COST = 'Total construction cost'
TRY_AGAIN = 'Try again'

UNABLE_TO_LOG_IN = 'Unable to log in'
UNKNOWN_EXCEPTION = 'Exception: Unknown exception'
USERNAME_ALREADY_EXISTS = 'Username already exists'
USERNAME_PARAMETER_HELP_TEXT = "150 characters or fewer. Letters, digits and @/./+/-/_ only."

VALID_RESPONSE = 'Valid response'
VALID_RESPONSE_SUMMARY = 'Upload success'

WALL_CONFIG_ALREADY_EXISTS = 'Wall config already exists'
WALL_CONFIG_NOT_A_LIST = 'Wall config not a list'
WEAK_PASSWORD = 'Weak password'


def invalid_section_height_label(counter: int) -> str:
    return f'Invalid section height {counter}'


# === Responses (end) ===
# ====== Schema (end) ======
