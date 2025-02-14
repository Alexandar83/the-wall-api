# Standalone module for wall construction simulation.
# Encapsulates only the core multiprocessing logic of the simulation,
# allowing isolated testing, independent of the broader application context

import os

import django
from django.test.utils import override_settings

os.environ['SECRET_KEY'] = 'django-insecure-*x!p!3#xxluj9i+v6anb!laycbax0rbkefg7$wf06xj2-my63f'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from the_wall_api.utils.wall_config_utils import hash_calc      # noqa: E402
from the_wall_api.wall_construction import (                    # noqa: E402
    get_sections_count, manage_num_crews, WallConstruction
)


# Possible concurrent simulation modes:
# threading_v1 - condition sync.
# threading_v2 - event sync.
# multiprocessing_v1 - multiprocessing Process + Event sync.
# multiprocessing_v2 - multiprocessing ProcessPoolExecutor + Manager().Event sync.
# multiprocessing_v3 - multiprocessing ProcessPoolExecutor + Manager().Condition sync.

@override_settings(CONCURRENT_SIMULATION_MODE='threading_v1')
def construct_wall(wall_construction_config: list[list[int]], num_crews: int) -> None:
    """
    Wall construction simulation, independent of the broader application context.

    Arguments:
    - wall_construction_config: A nested list of lists of integers representing the wall structure.
      The lists of integers represent the profiles of the wall and the integers represent the heights
      of the wall's sections.
      Example: [
          [21, 25, 28],
          [17],
          [17, 22, 17, 19, 17]
      ]

    - num_crews: The number of crews to simulate during the construction process.
      Each crew will be represented by a separate thread (or a process depending on the selected
      CONCURRENT_SIMULATION_MODE). If 0 or >= total number of wall sections is input, a build
      simulation in sequential mode is performed.
    """
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
