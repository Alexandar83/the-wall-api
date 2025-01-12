# == Views ==
WALL_TOTAL_COST_RESPONSE = 'Total wall construction cost.'


# = File Upload =
def file_upload_details(config_id: str) -> str:
    return f'Wall config <{config_id}> uploaded successfully.'


# = Profiles =
def profile_day_cost(profile_id: int, day: int) -> str:
    return f'Construction cost for profile {profile_id} on day {day}.'


def profiles_overview_day_cost(day: int) -> str:
    return f'Construction cost for day {day}.'


def format_cost(cost: int) -> str:
    return f'{cost:,}'


def profiles_overview_details(response_message: str, cost: int) -> str:
    return f'{response_message}: {format_cost(cost)} Gold Dragon coins'


def profiles_days_details(profile_id: int, day: int, profile_day_ice_amount: int) -> str:
    return f'Volume of ice used for profile {profile_id} on day {day}: {profile_day_ice_amount} cubic yards.'

# == Views (end) ==
