# Externalized parameters for extend_schema

from drf_spectacular.utils import OpenApiParameter

# === Wall app parameters ===

# Optional query parameter for num_crews in the usage and cost endpoints
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
# Obligatory query parameter for config_id in the usage and cost endpoints
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

# == DailyIceUsageView ==
# PATH parameters
daily_ice_usage_parameters = [
    OpenApiParameter(
        name='profile_id',
        type=int,
        # required=True,    # Omitted for PATH parameters -> always required
        description='Wall profile number.',
        location=OpenApiParameter.PATH
    ),
    OpenApiParameter(
        name='day',
        type=int,
        # required=True,    # Omitted for PATH parameters -> always required
        description='Construction day number.',
        location=OpenApiParameter.PATH
    ),
]
# == DailyIceUsageView (end) ==

# *CostOverviewView and CostOverviewProfileidView*
# PATH parameters
cost_overview_profile_id_parameters = [
    OpenApiParameter(
        name='profile_id',
        type=int,
        # required=True,    # Omitted for PATH parameters -> always required
        description='Wall profile number.',
        location=OpenApiParameter.PATH
    ),
]

# === Wall app parameters (end) ===
