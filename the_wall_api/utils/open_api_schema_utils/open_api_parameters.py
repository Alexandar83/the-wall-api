# Externalized parameters for extend_schema

from drf_spectacular.utils import OpenApiParameter

# === Wall app parameters ===

# Optional query parameter for num_crews in the profiles endpoints
num_crews_parameter = OpenApiParameter(
    name='num_crews',
    type=int,
    required=False,
    description=(
        'The number of crews involved in the simulation.'
        '<br><br>'
        '<i><b>When included</b>: the wall build simulation is concurrent.</i>'
        '<br><br>'
        '<i><b>When omitted</b>: the simulation defaults to sequential processing.</i>'
        '<br><br>'
    ),
    location=OpenApiParameter.QUERY
)
# Obligatory query parameter for config_id in the profiles endpoints
config_id_parameter = OpenApiParameter(
    name='config_id',
    type=str,
    required=True,
    description='Wall configuration file ID.',
    location=OpenApiParameter.QUERY
)

# == WallConfigFileDeleteView ==
# QUERY parameters
file_delete_config_id_list_parameter = OpenApiParameter(
    name='config_id_list',
    type=str,
    required=False,
    description=(
        'Comma-separated list of wall configuration file IDs to be deleted, <b><i>(provided as a single string)</i></b>.'
        '<br><br>'
        '<b><i>Example</b>: test_config_1,test_config_2,test_config_3</i>'
        '<br><br>'
        '<b><i>Important: Deletes all user files if omitted!</i></b>'
        '<br><br>'
    ),
    location=OpenApiParameter.QUERY
)
# == WallConfigFileDeleteView (end) ==
