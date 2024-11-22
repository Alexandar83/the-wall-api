# Externalized parameters for extend_schema

from drf_spectacular.utils import OpenApiParameter

# === Wall app parameters ===

# Optional query parameter for num_crews
num_crews_parameter = OpenApiParameter(
    name='num_crews',
    type=int,
    required=False,
    description=(
        'The number of crews involved in the simulation. '
        'When included: the wall build simulation is concurrent. '
        'When omitted: the simulation defaults to sequential processing.'
    ),
    location=OpenApiParameter.QUERY
)

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
