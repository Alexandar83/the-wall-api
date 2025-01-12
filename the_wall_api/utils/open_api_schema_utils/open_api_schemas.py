from the_wall_api.models import CONFIG_ID_MAX_LENGTH
from the_wall_api.utils.message_themes import openapi as openapi_messages

wallconfig_file_upload_schema = {
    'multipart/form-data': {
        'type': 'object',
        'properties': {
            'wall_config_file': {
                'type': 'string',
                'format': 'binary',
                'description': openapi_messages.WALLCONFIG_FILE_PARAMETER_DESCRIPTION
            },
            'config_id': {
                'type': 'string',
                'maxLength': CONFIG_ID_MAX_LENGTH,
                'description': openapi_messages.CONFIG_ID_PARAMETER_DESCRIPTION,
                'example': 'test_config_1'
            }
        },
        'required': ['wall_config_file', 'config_id']
    }
}
