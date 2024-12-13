import os

import django
from django.test.utils import override_settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from the_wall_api.utils.wall_config_utils import hash_calc      # noqa: E402
from the_wall_api.wall_construction import (                    # noqa: E402
    get_sections_count, manage_num_crews, WallConstruction
)


# Possible concurrent simulation modes:
# threading_v1 - condition sync.
# threading_v2 - even sync.
# multiprocessing_v1 - multiprocessing Process + Event sync.
# multiprocessing_v2 - multiprocessing ProcessPoolExecutor + Manager().Event sync.
# multiprocessing_v3 - multiprocessing ProcessPoolExecutor + Manager().Condition sync.

@override_settings(CONCURRENT_SIMULATION_MODE='threading_v1')
def construct_wall(wall_construction_config: list[list[int]], num_crews: int) -> None:
    sections_count = get_sections_count(wall_construction_config)
    simulation_type, num_crews_final = manage_num_crews(num_crews, sections_count)
    wall_config_hash = hash_calc(wall_construction_config)

    WallConstruction(
        wall_construction_config=wall_construction_config,
        sections_count=sections_count,
        num_crews=num_crews_final,
        wall_config_hash=wall_config_hash,
        simulation_type=simulation_type,
        proxy_wall_creation_call=True
    )


if __name__ == '__main__':
    num_crews = 5
    wall_construction_config = [
        [21, 25, 28],
        [17],
        [17, 22, 17, 19, 17]
    ]

    construct_wall(wall_construction_config, num_crews)
