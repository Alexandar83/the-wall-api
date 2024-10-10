# Redis caching and database logic

from decimal import Decimal
from typing import Any, Dict, List
import xxhash

from django.conf import settings
from django.core.cache import cache
from django.db import connection, IntegrityError, transaction
from django.db.models import Q
from redis.exceptions import ConnectionError, TimeoutError

from the_wall_api.models import WallProfileProgress, WallProfile, Wall
from the_wall_api.utils import wall_config_utils, error_utils
from the_wall_api.wall_construction import run_simulation, set_simulation_params


REDIS_CACHE_TRANSIENT_DATA_TIMEOUT = settings.REDIS_CACHE_TRANSIENT_DATA_TIMEOUT


def fetch_wall_data(
    wall_data: Dict[str, Any], num_crews: int, profile_id: int | None = None, request_type: str = ''
):
    wall_construction_config = wall_config_utils.get_wall_construction_config(wall_data, profile_id)
    if wall_data['error_response']:
        return

    set_simulation_params(wall_data, num_crews, wall_construction_config, request_type)
    
    get_or_create_cache(wall_data, request_type)


def get_or_create_cache(wall_data, request_type) -> None:
    # Check for cached data
    collect_cached_data(wall_data, request_type)
    if wall_data.get('cached_result') or wall_data['error_response']:
        return
    
    # If no cached data is found, run the simulation
    run_simulation(wall_data)

    # Create the new cache data
    cache_wall(wall_data)
    if wall_data['error_response']:
        return

    # Validate if the day is correct with data from the simulation
    error_utils.validate_day_within_range(wall_data)


def collect_cached_data(wall_data: Dict[str, Any], request_type: str) -> None:
    """
    Check for different type of cached data, based on the request type.
    """
    cached_result = wall_data['cached_result'] = {}

    request_type = wall_data['request_type']
    try:
        if request_type == 'costoverview':
            fetch_wall_cost(wall_data, cached_result)
        elif request_type == 'costoverview/profile_id':
            fetch_wall_profile_cost(wall_data, cached_result)
        elif request_type == 'daily-ice-usage':
            fetch_daily_ice_usage(wall_data, cached_result)
    except (Wall.DoesNotExist, WallProfile.DoesNotExist, WallProfileProgress.DoesNotExist):
        return


def fetch_wall_cost(wall_data: Dict[str, Any], cached_result: Dict[str, Any]) -> None:
    # Redis cache
    cached_wall_cost, wall_redis_key = fetch_wall_cost_from_redis_cache(wall_data)
    if cached_wall_cost is not None:
        cached_result['wall_total_cost'] = cached_wall_cost
        return
    
    # DB
    fetch_wall_cost_from_db(wall_data, cached_result, wall_redis_key)


def fetch_wall_cost_from_redis_cache(wall_data: Dict[str, Any]) -> tuple[int, str]:
    """
    Fetch a cached Wall from the Redis cache.
    Both simulation types store the same cost.
    """
    wall_redis_key = get_wall_cache_key(wall_data)
    cached_wall_cost = cache.get(wall_redis_key)
    
    return cached_wall_cost, wall_redis_key


def get_wall_cache_key(wall_data: Dict[str, Any]) -> str:
    return f'wall_cost_{wall_data["wall_config_hash"]}'


def fetch_wall_cost_from_db(wall_data: Dict[str, Any], cached_result: Dict[str, Any], wall_redis_key: str) -> None:
    """
    Fetch a cached Wall from the DB.
    Both simulation types store the same cost.
    """
    wall = Wall.objects.filter(wall_config_hash=wall_data['wall_config_hash']).first()
    if wall:
        cached_result['wall_total_cost'] = wall.total_cost
        # Refresh the Redis cache
        set_redis_cache(wall_redis_key, wall.total_cost)


def fetch_wall_profile_cost(wall_data: Dict[str, Any], cached_result: Dict[str, Any]) -> None:
    profile_id = wall_data['request_profile_id']
    profile_config_hash_data = wall_data['profile_config_hash_data']
    wall_profile_config_hash = profile_config_hash_data[profile_id]

    # Redis cache
    cached_wall_profile_cost, wall_profile_redis_cache_key = fetch_wall_profile_cost_from_redis_cache(
        wall_profile_config_hash
    )
    if cached_wall_profile_cost is not None:
        cached_result['wall_profile_cost'] = cached_wall_profile_cost
        return
    
    # DB
    fetch_wall_profile_cost_from_db(
        wall_profile_config_hash, cached_result, wall_profile_redis_cache_key
    )


def fetch_wall_profile_cost_from_redis_cache(wall_profile_config_hash: str) -> tuple[int, str]:
    """
    Fetch a cached Wall Profile from the Redis cache.
    Both simulation types store the same cost - attempt to find a cached value for any of them.
    """
    wall_profile_redis_cache_key = get_wall_profile_cache_key(wall_profile_config_hash)
    cached_wall_profile_cost = cache.get(wall_profile_redis_cache_key)

    return cached_wall_profile_cost, wall_profile_redis_cache_key


def get_wall_profile_cache_key(wall_profile_config_hash: str) -> str:
    return f'wall_prfl_cost_{wall_profile_config_hash}'


def fetch_wall_profile_cost_from_db(
        wall_profile_config_hash: str | None, cached_result: Dict[str, Any],
        wall_profile_redis_cache_key: str
) -> None:
    """
    Fetch a cached Wall Profile from the DB.
    Both simulation types store the same cost.
    """
    wall_profile = WallProfile.objects.filter(wall_profile_config_hash=wall_profile_config_hash).first()
    if wall_profile:
        cached_result['wall_profile_cost'] = wall_profile.cost
        # Refresh the Redis cache
        set_redis_cache(wall_profile_redis_cache_key, wall_profile.cost)


def fetch_daily_ice_usage(wall_data: Dict[str, Any], cached_result: Dict[str, Any]) -> None:
    profile_id = wall_data['request_profile_id']
    profile_config_hash_data = wall_data['profile_config_hash_data']
    wall_profile_config_hash = profile_config_hash_data[profile_id]

    # Redis cache
    cached_profile_ice_usage, profile_ice_usage_redis_cache_key = fetch_daily_ice_usage_from_redis_cache(
        wall_data, wall_profile_config_hash, profile_id
    )
    if cached_profile_ice_usage is not None:
        # Return the cached value
        cached_result['profile_daily_ice_used'] = cached_profile_ice_usage
        return
    if wall_data['error_response']:
        # Return if any day errors
        return
    
    # DB
    fetch_daily_ice_usage_from_db(
        wall_data, wall_profile_config_hash, profile_id, cached_result, profile_ice_usage_redis_cache_key
    )


def fetch_daily_ice_usage_from_redis_cache(
        wall_data: Dict[str, Any], wall_profile_config_hash: str | None, profile_id: int,
) -> tuple[int, str]:
    """
    Fetch a cached Wall Profile Progress from the Redis cache.
    Variability depending on the number of crews.
    """
    profile_ice_usage_redis_cache_key = get_daily_ice_usage_cache_key(
        wall_data, wall_profile_config_hash, wall_data['request_day'], profile_id
    )
    cached_profile_ice_usage = cache.get(profile_ice_usage_redis_cache_key)
    if cached_profile_ice_usage:
        return cached_profile_ice_usage, profile_ice_usage_redis_cache_key
    
    # No check_if_cached_on_another_day_redis_cache method is implemented:
    # Explanation:
    # Don't mix DB with Redis cache fethes in this case, to avoid theoretical
    # race conditions, where 1 process has already cached the wall
    # and its construction days in the DB, but the Redis cache is still
    # not committed

    return cached_profile_ice_usage, profile_ice_usage_redis_cache_key


def get_daily_ice_usage_cache_key(
        wall_data: Dict[str, Any], wall_profile_config_hash: str | None, day: int, profile_id: int
) -> str:
    key_data = (
        f'dly_ice_usg_'
        f'{wall_data["wall_config_hash"]}_'
        f'{wall_data["num_crews"]}_'
        f'{wall_profile_config_hash}_'
        f'{day}'
    )
    if wall_data['simulation_type'] == wall_config_utils.CONCURRENT:
        key_data += f'_{profile_id}'
    
    # profile_ice_usage_redis_cache_key = hash_calc(key_data)   # Potential future mem. usage optimisation
    
    return key_data


def fetch_daily_ice_usage_from_db(
        wall_data: Dict[str, Any], wall_profile_config_hash: str | None,
        profile_id: int, cached_result: Dict[str, Any], profile_ice_usage_redis_cache_key: str
) -> None:
    """
    Fetch a cached Wall Profile Progress from the DB.
    Variability based on the number of crews.
    """
    wall_progress_query = Q(
        wall_profile__wall__wall_config_hash=wall_data['wall_config_hash'],
        wall_profile__wall__num_crews=wall_data['num_crews'],
        wall_profile__wall_profile_config_hash=wall_profile_config_hash,
        day=wall_data['request_day'],
    )

    if wall_data['simulation_type'] == wall_config_utils.CONCURRENT:
        wall_progress_query &= Q(wall_profile__profile_id=profile_id)

    try:
        wall_profile_progress = WallProfileProgress.objects.get(wall_progress_query)
        cached_result['profile_daily_ice_used'] = wall_profile_progress.ice_used
        # Refresh the Redis cache
        set_redis_cache(profile_ice_usage_redis_cache_key, wall_profile_progress.ice_used)
    except WallProfileProgress.DoesNotExist:
        error_utils.check_if_cached_on_another_day(wall_data, profile_id)


def cache_wall(wall_data: Dict[str, Any]) -> None:
    """
    Creates a new Wall object.
    Start a cascade cache creation of all wall elements.
    """
    wall_cache_key = get_wall_cache_key(wall_data)
    wall_db_lock_key = generate_db_lock_key(wall_cache_key)
    db_lock_acquired = None
    total_cost = wall_data['sim_calc_details']['total_cost']
    wall_redis_data = []
    
    try:
        db_lock_acquired = acquire_db_lock(wall_db_lock_key)
        if not db_lock_acquired:
            # Skip cache creation if lock is not acquired -
            # another process is creating the cache
            return
        
        with transaction.atomic():
            # Create the wall object in the DB
            wall = Wall.objects.create(
                wall_config_hash=wall_data['wall_config_hash'],
                num_crews=wall_data['num_crews'],
                total_cost=total_cost,
                construction_days=wall_data['sim_calc_details']['construction_days'],
            )

            # Deferred Redis cache
            wall_redis_data.append((
                wall_cache_key,
                format_value_for_redis('cost', total_cost)
            ))
            process_wall_profiles(wall_data, wall, wall_data['simulation_type'], wall_redis_data)

            # Commit deferred Redis cache after a successful DB transaction
            transaction.on_commit(lambda: commit_deferred_redis_cache(wall_redis_data))
    
    except IntegrityError as wall_crtn_intgrty_err:
        error_utils.handle_wall_crtn_integrity_error(wall_data, wall_crtn_intgrty_err)
    except Exception as wall_crtn_unkwn_err:
        error_utils.handle_unknown_error(wall_data, wall_crtn_unkwn_err)
    finally:
        if db_lock_acquired:
            release_db_lock(wall_db_lock_key)


def generate_db_lock_key(cache_lock_key: str) -> List[int]:
    """Generate two unique integers from a string key for PostgreSQL advisory locks."""
    xxhash_64bit = xxhash.xxh64(cache_lock_key).intdigest()
    lock_id1 = xxhash_64bit & 0xFFFFFFFF  # Lower 32 bits
    lock_id2 = (xxhash_64bit >> 32) & 0xFFFFFFFF  # Upper 32 bits
    return [lock_id1, lock_id2]


def acquire_db_lock(wall_db_lock_key: List[int]) -> bool:
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_lock(%s, %s);', wall_db_lock_key)
        db_lock_acquired = cursor.fetchone()
        return bool(db_lock_acquired and db_lock_acquired[0])


def release_db_lock(wall_db_lock_key: List[int]) -> None:
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_unlock(%s, %s);', wall_db_lock_key)


def format_value_for_redis(type: str, value_in: Any) -> Any:
    """Format a value before storing it in Redis to correspond to the ORM model."""
    if type == 'cost':
        return Decimal(value_in).quantize(wall_config_utils.COST_ROUNDING)


def process_wall_profiles(
        wall_data: Dict[str, Any], wall: Wall, simulation_type: str,
        wall_redis_data: list[tuple[str, int]]
) -> None:
    """
    Manage the different behaviors for wall profiles caching in SEQUENTIAL and CONCURRENT modes.
    """
    cached_wall_profile_hashes = []

    for profile_id, profile_data in wall_data['wall_construction'].wall_profile_data.items():
        wall_profile_config_hash = wall_data['profile_config_hash_data'][profile_id]

        if simulation_type == wall_config_utils.SEQUENTIAL:
            # Only cache the unique wall profile configs in sequential mode.
            # The build progress of the wall profiles with duplicate configs is
            # always the same.
            if wall_profile_config_hash in cached_wall_profile_hashes:
                continue
            cached_wall_profile_hashes.append(wall_profile_config_hash)

        # Proceed to create the wall profile
        cache_wall_profile_to_db(
            wall, wall_data, profile_id, profile_data,
            wall_profile_config_hash, simulation_type, wall_redis_data
        )


def cache_wall_profile_to_db(
        wall: Wall, wall_data: Dict[str, Any], profile_id: int, profile_data: Any,
        wall_profile_config_hash: str, simulation_type: str, wall_redis_data: list[tuple[str, int]]
) -> None:
    """
    Create a new WallProfile object and save it to the database.
    Starting point for the wall profile progress caching..
    """
    wall_profile_cost = wall_data['sim_calc_details']['profile_costs'][profile_id]
    wall_profile_creation_kwargs = {
        'wall': wall,
        'wall_profile_config_hash': wall_profile_config_hash,
        'cost': wall_profile_cost,
    }

    # Set profile_id only for concurrent cases
    if simulation_type == wall_config_utils.CONCURRENT:
        wall_profile_creation_kwargs['profile_id'] = profile_id

    # Create the wall profile object
    wall_profile = WallProfile.objects.create(**wall_profile_creation_kwargs)

    # Deferred Redis cache
    wall_redis_data.append(
        (
            get_wall_profile_cache_key(wall_profile_config_hash),
            format_value_for_redis('cost', wall_profile_cost)
        )
    )

    # Proceed to create the wall profile progress
    cache_wall_profile_progress_to_db(
        wall_data, wall_profile, wall_profile_config_hash, profile_id, profile_data, wall_redis_data
    )


def cache_wall_profile_progress_to_db(
        wall_data: Dict[str, Any], wall_profile: WallProfile, wall_profile_config_hash: str, profile_id: int,
        profile_data: dict, wall_redis_data: list[tuple[str, int]]
) -> None:
    """
    Create a new WallProfileProgress object and save it to the database.
    """
    for day_index, data in profile_data.items():
        # Create the wall profile progress object
        WallProfileProgress.objects.create(
            wall_profile=wall_profile,
            day=day_index,
            ice_used=data['ice_used']
        )
        
        # Deferred Redis cache
        wall_redis_data.append(
            (
                get_daily_ice_usage_cache_key(wall_data, wall_profile_config_hash, day_index, profile_id),
                data['ice_used']
            )
        )


def commit_deferred_redis_cache(wall_redis_data: list[tuple[str, Any]]) -> None:
    for redis_cache_key, redis_cache_value in wall_redis_data:
        set_redis_cache(redis_cache_key, redis_cache_value)


def set_redis_cache(redis_cache_key: str, redis_cache_value: Any) -> None:
    try:
        cache.set(redis_cache_key, redis_cache_value, timeout=REDIS_CACHE_TRANSIENT_DATA_TIMEOUT)
    except (ConnectionError, TimeoutError):
        # The Redis server is down
        # TODO: Add logging?
        pass
