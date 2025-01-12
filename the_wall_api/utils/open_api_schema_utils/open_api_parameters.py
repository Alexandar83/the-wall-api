# Externalized parameters for extend_schema

from drf_spectacular.utils import OpenApiParameter

from the_wall_api.utils.message_themes import openapi as openapi_messages


# === Wall app parameters ===

# Optional query parameter for num_crews in the profiles endpoints
num_crews_parameter = OpenApiParameter(
    name='num_crews',
    type=int,
    required=False,
    description=openapi_messages.NUM_CREWS_PARAMETER_DESCRIPTION,
    location=OpenApiParameter.QUERY
)
# Obligatory query parameter for config_id in the profiles endpoints
config_id_parameter = OpenApiParameter(
    name='config_id',
    type=str,
    required=True,
    description=openapi_messages.CONFIG_ID_PARAMETER_DESCRIPTION,
    location=OpenApiParameter.QUERY
)

# == WallConfigFileDeleteView ==
# QUERY parameters
file_delete_config_id_list_parameter = OpenApiParameter(
    name='config_id_list',
    type=str,
    required=False,
    description=openapi_messages.FILE_DELETE_CONFIG_ID_LIST_PARAMETER_DESCRIPTION,
    location=OpenApiParameter.QUERY
)
# == WallConfigFileDeleteView (end) ==
