# Redis caching and database logic

from decimal import Decimal
from typing import Any, Dict, List
import xxhash

from django.conf import settings
from django.core.cache import cache
from django.db import connection, transaction
from django.db.models import Q
from django.db.utils import IntegrityError
from redis.exceptions import ConnectionError, TimeoutError

from the_wall_api.models import (
    Wall, WallConfig, WallConfigReference, WallConfigStatusEnum, WallProfile, WallProfileProgress
)
from the_wall_api.tasks import orchestrate_wall_config_processing_task
from the_wall_api.utils import error_utils, wall_config_utils
from the_wall_api.wall_construction import get_sections_count, run_simulation, set_simulation_params


CELERY_TASK_PRIORITY = settings.CELERY_TASK_PRIORITY
REDIS_CACHE_TRANSIENT_DATA_TIMEOUT = settings.REDIS_CACHE_TRANSIENT_DATA_TIMEOUT


def fetch_wall_data(
    wall_data: Dict[str, Any], num_crews: int, profile_id: int | None = None, request_type: str = ''
):
    wall_construction_config = wall_data.get('wall_construction_config', [])
    if not wall_construction_config:
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
    if wall_data['error_response'] or wall_data.get('celery_task_aborted'):
        return

    # Attempt to get/create the wall config object
    wall_config_object = manage_wall_config_object(wall_data)
    if isinstance(wall_config_object, WallConfig):
        # Successful creation/fetch of the wall config object
        wall_data['wall_config_object'] = wall_config_object
    else:
        # Either being initialized by another process
        # or an error occurred during the creation
        return

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
        if request_type in ['costoverview', 'create_wall_task']:
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


def fetch_wall_cost_from_redis_cache(wall_data: Dict[str, Any]) -> tuple[int | None, str]:
    """
    Fetch a cached Wall from the Redis cache.
    Both simulation types store the same cost.
    """
    wall_redis_key = get_wall_cache_key(wall_data)
    if wall_data['request_type'] != 'create_wall_task':
        cached_wall_cost = cache.get(wall_redis_key)
    else:
        # Call from the Celery computation worker - no Redis cache is used
        cached_wall_cost = None

    return cached_wall_cost, wall_redis_key


def get_wall_cache_key(wall_data: Dict[str, Any]) -> str:
    if wall_data['request_type'] != 'create_wall_task':
        # NOTE-1: App call - optimized query
        return f'wall_cost_{wall_data["wall_config_hash"]}'
    else:
        # NOTE-2: Celery computation task call - full query to check if the wall
        # construction is already cached in the DB with the provided num_crews
        return f'wall_cost_{wall_data["wall_config_hash"]}_{wall_data["num_crews"]}'


def fetch_wall_cost_from_db(wall_data: Dict[str, Any], cached_result: Dict[str, Any], wall_redis_key: str) -> None:
    """
    Fetch a cached Wall from the DB.
    Both simulation types store the same cost.
    """
    request_type = wall_data['request_type']
    if request_type != 'create_wall_task':
        # See NOTE-1
        wall = Wall.objects.filter(wall_config_hash=wall_data['wall_config_hash']).first()
    else:
        # See NOTE-2
        try:
            wall = Wall.objects.get(wall_config_hash=wall_data['wall_config_hash'], num_crews=wall_data['num_crews'])
        except Wall.DoesNotExist:
            wall = None

    if wall:
        cached_result['wall_total_cost'] = wall.total_cost
        if request_type != 'create_wall_task':
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
        wall_data: Dict[str, Any], wall_profile_config_hash: str | None, day: int, profile_id: int | None
) -> str:
    key_data = (
        f'dly_ice_usg_'
        f'{wall_data["wall_config_hash"]}_'
        f'{wall_data["num_crews"]}_'
        f'{wall_profile_config_hash}_'
        f'{day}'
    )
    if wall_data['simulation_type'] == wall_config_utils.CONCURRENT and profile_id is not None:
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


def manage_wall_config_file_upload(wall_data: Dict[str, Any]) -> None:
    # Uploaded config data validation
    wall_config_utils.validate_wall_config_file_data(wall_data)
    if wall_data['error_response']:
        return

    # Prepare final data
    wall_data['wall_config_hash'] = wall_config_utils.hash_calc(wall_data['initial_wall_construction_config'])
    wall_data['sections_count'] = get_sections_count(wall_data['initial_wall_construction_config'])
    wall_data['num_crews'] = None

    # Fetch or create the WallConfig object
    wall_config_object = manage_wall_config_object(wall_data)
    if wall_data['error_response']:
        return

    if isinstance(wall_config_object, WallConfig) and not wall_config_object.deletion_initiated:
        create_new_wall_config_file(wall_data, wall_config_object)
    else:
        error_utils.manage_wall_config_deletion_in_progress(wall_data)


def create_new_wall_config_file(wall_data, wall_config_object) -> None:
    wall_config_file_cache_key = get_wall_config_file_cache_key(wall_data['wall_config_hash'])
    wall_config_file_db_lock_key = generate_db_lock_key(wall_config_file_cache_key)
    db_lock_acquired = None
    try:
        db_lock_acquired = acquire_db_lock(wall_config_file_db_lock_key)
        if not db_lock_acquired:
            # Being created in another process
            return

        with transaction.atomic():
            WallConfigReference.objects.create(
                user=wall_data['user'],
                wall_config=wall_config_object,
                config_id=wall_data['config_id'],
            )
    except Exception as wall_config_file_crtn_unkwn_err:
        error_utils.handle_unknown_error(wall_data, wall_config_file_crtn_unkwn_err, 'caching')
    finally:
        if db_lock_acquired:
            release_db_lock(wall_config_file_db_lock_key)


def get_wall_config_file_cache_key(wall_config_hash: str) -> str:
    return f'wall_config_file_{wall_config_hash}'


def manage_wall_config_object(wall_data: Dict[str, Any]) -> WallConfig | str:
    """WallConfig object management corresponding to its state."""
    wall_config_hash = wall_data['wall_config_hash']
    try:
        # Already created
        wall_config_object = WallConfig.objects.get(wall_config_hash=wall_config_hash)
    except WallConfig.DoesNotExist:
        # First request for this config - create it in the DB
        wall_config_object = create_new_wall_config(wall_data, wall_config_hash)

    if isinstance(wall_config_object, WallConfig) and not wall_config_object.deletion_initiated:
        handle_wall_config_status(wall_config_object, wall_data)

    return wall_config_object


def create_new_wall_config(wall_data, wall_config_hash) -> WallConfig | str:
    wall_config_cache_key = get_wall_config_cache_key(wall_config_hash)
    wall_config_db_lock_key = generate_db_lock_key(wall_config_cache_key)
    db_lock_acquired = None
    try:
        db_lock_acquired = acquire_db_lock(wall_config_db_lock_key)
        if not db_lock_acquired:
            return 'Being initialized in another process'

        with transaction.atomic():
            # Create a new object with status INITIALIZED (default value)
            wall_config_object = WallConfig.objects.create(wall_config_hash=wall_config_hash)
    except Exception as wall_config_crtn_unkwn_err:
        wall_config_object = f'{wall_config_crtn_unkwn_err.__class__.__name__}: {str(wall_config_crtn_unkwn_err)}'
        error_utils.handle_unknown_error(wall_data, wall_config_crtn_unkwn_err, 'caching')
    finally:
        if db_lock_acquired:
            release_db_lock(wall_config_db_lock_key)

    return wall_config_object


def handle_wall_config_status(wall_config_object: WallConfig, wall_data: Dict[str, Any]) -> None:
    if wall_config_object.status == WallConfigStatusEnum.INITIALIZED:
        # Skip during testing
        if not settings.ACTIVE_TESTING:
            task_kwargs = {
                'wall_config_hash': wall_config_object.wall_config_hash,
                'wall_construction_config': wall_data['initial_wall_construction_config'],
                'sections_count': wall_data['sections_count'],
                'num_crews_source': wall_data['num_crews'],
            }
            orchestrate_wall_config_processing_task.apply_async(
                kwargs=task_kwargs, priority=CELERY_TASK_PRIORITY['MEDIUM']
            )    # type: ignore
    elif wall_config_object.status == WallConfigStatusEnum.ERROR:
        # Error from past processing attempt
        unknwn_err = (
            f'WallConfig object {wall_config_object.wall_config_hash} '
            f'is with {WallConfigStatusEnum.ERROR} status.'
        )
        error_utils.handle_unknown_error(wall_data, unknwn_err, 'caching')


def get_wall_config_cache_key(wall_config_hash: str) -> str:
    return f'wall_config_{wall_config_hash}'


def generate_db_lock_key(cache_lock_key: str) -> List[int]:
    """Generate two unique integers from a string key for PostgreSQL advisory locks."""
    xxhash_64bit = xxhash.xxh64(cache_lock_key).intdigest()
    # Use 31 bits (0x7FFFFFFF) to keep values within PostgreSQL's signed 32-bit integer limit range
    lock_id1 = (xxhash_64bit & 0x7FFFFFFF)
    lock_id2 = ((xxhash_64bit >> 32) & 0x7FFFFFFF)
    return [lock_id1, lock_id2]


def acquire_db_lock(wall_db_lock_key: List[int]) -> bool:
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_lock(%s, %s);', wall_db_lock_key)
        db_lock_acquired = cursor.fetchone()
        return bool(db_lock_acquired and db_lock_acquired[0])


def release_db_lock(wall_db_lock_key: List[int]) -> None:
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_unlock(%s, %s);', wall_db_lock_key)


def cache_wall(wall_data: Dict[str, Any]) -> None:
    """
    Creates a new Wall object.
    Start a cascade cache creation of all wall elements.
    """
    wall_cache_key = get_wall_cache_key(wall_data)
    wall_db_lock_key = generate_db_lock_key(wall_cache_key)
    db_lock_acquired = False

    try:
        db_lock_acquired = acquire_db_lock(wall_db_lock_key)
        if not db_lock_acquired:
            # Skip cache creation if lock is not acquired -
            # another process is creating the cache
            return

        perform_wall_transaction(wall_data, wall_cache_key)

    except Exception as wall_crtn_unkwn_err:
        error_utils.handle_unknown_error(wall_data, wall_crtn_unkwn_err, 'caching')
    finally:
        if db_lock_acquired:
            release_db_lock(wall_db_lock_key)


def perform_wall_transaction(wall_data: Dict[str, Any], wall_cache_key: str) -> None:
    total_cost = wall_data['sim_calc_details']['total_cost']
    wall_redis_data = []

    with transaction.atomic():
        try:
            # Create the wall object in the DB
            wall = Wall.objects.create(
                wall_config=wall_data['wall_config_object'],
                wall_config_hash=wall_data['wall_config_hash'],
                num_crews=wall_data['num_crews'],
                total_cost=total_cost,
                construction_days=wall_data['sim_calc_details']['construction_days'],
            )
        except IntegrityError as intgrty_err:
            # Rare case - log it to keep track of ocurence frequency
            error_type = 'caching' if wall_data['request_type'] != 'create_wall_task' else 'celery_tasks'
            error_utils.send_log_error_async(error_type, error=intgrty_err)
            return

        if wall_data['request_type'] != 'create_wall_task':
            # Deferred Redis cache
            wall_redis_data.append((
                wall_cache_key,
                format_value_for_redis('cost', total_cost)
            ))
        process_wall_profiles(wall_data, wall, wall_data['simulation_type'], wall_redis_data)

        if wall_data['request_type'] != 'create_wall_task':
            # Commit deferred Redis cache after a successful DB transaction
            # Redis cache not managed for Celery computation config tasks
            transaction.on_commit(lambda: commit_deferred_redis_cache(wall_redis_data))


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

    for profile_id, profile_data in wall_data['sim_calc_details']['profile_daily_details'].items():
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
            wall, wall_data, profile_id, profile_data, wall_profile_config_hash,
            simulation_type, wall_redis_data
        )


def cache_wall_profile_to_db(
        wall: Wall, wall_data: Dict[str, Any], profile_id: int, profile_data: Any, wall_profile_config_hash: str,
        simulation_type: str, wall_redis_data: list[tuple[str, int]]
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

    if wall_data['request_type'] != 'create_wall_task':
        # Deferred Redis cache
        wall_redis_data.append(
            (
                get_wall_profile_cache_key(wall_profile_config_hash),
                format_value_for_redis('cost', wall_profile_cost)
            )
        )

    # Proceed to create the wall profile progress
    cache_wall_profile_progress_to_db(
        wall_data, wall_profile, wall_profile_config_hash, profile_id,
        profile_data, wall_redis_data
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

        if wall_data['request_type'] != 'create_wall_task':
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
