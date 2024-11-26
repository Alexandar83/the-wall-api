from the_wall_api.models import CONFIG_ID_MAX_LENGTH

wallconfig_file_upload_schema = {
    'multipart/form-data': {
        'type': 'object',
        'properties': {
            'wall_config_file': {
                'type': 'string',
                'format': 'binary',
                'description': (
                    'A JSON file containing Wall configuration data.\n\n'
                    'Should contain a list of nested lists of integers.\n\n'
                    '**Example**:\n'
                    '[[1, 5, 10], [5, 7, 16, 23]]'
                )
            },
            'config_id': {
                'type': 'string',
                'maxLength': CONFIG_ID_MAX_LENGTH,
                'description': 'A unique identifier for the Wall configuration.',
                'example': 'test_config_1'
            }
        },
        'required': ['wall_config_file', 'config_id']
    }
}
