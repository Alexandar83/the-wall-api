# Redis caching and database logic

from time import sleep
from typing import Any, Dict, List
import xxhash

from django.conf import settings
from django.core.cache import cache
from django.db import connection, transaction
from django.db.utils import IntegrityError
from redis.exceptions import ConnectionError, TimeoutError

from the_wall_api.models import (
    Wall, WallConfig, WallConfigReference, WallConfigReferenceStatusEnum, WallConfigStatusEnum,
    WallProgress
)
from the_wall_api.tasks import (
    delete_unused_wall_configs_task, orchestrate_wall_config_processing_task
)
from the_wall_api.utils import error_utils, wall_config_utils
from the_wall_api.utils.api_utils import handle_being_processed
from the_wall_api.wall_construction import (
    get_sections_count, run_simulation, set_simulation_params
)

CELERY_TASK_PRIORITY = settings.CELERY_TASK_PRIORITY
REDIS_CACHE_TRANSIENT_DATA_TIMEOUT = settings.REDIS_CACHE_TRANSIENT_DATA_TIMEOUT


def fetch_user_wall_config_files(wall_data: Dict[str, Any]) -> List[int]:
    config_id_list = list(
        WallConfigReference.objects.filter(user=wall_data['request_user']).values_list('config_id', flat=True)
    )

    return config_id_list


def fetch_wall_data(
    wall_data: Dict[str, Any], num_crews: int = 0, profile_id: int | None = None, request_type: str = ''
):
    # If coming from a Celery create_wall task, the authentication
    # and user file reference filtering are not needed
    wall_construction_config = wall_data.get('wall_construction_config', [])
    if not wall_construction_config:
        # Coming from a profiles endpoint
        wall_construction_config = wall_config_utils.get_wall_construction_config(wall_data, profile_id)
        if wall_data['error_response']:
            return

    set_simulation_params(wall_data, num_crews, wall_construction_config, request_type)

    # Check for other user tasks in progress
    verify_no_other_user_tasks_in_progress(wall_data)
    if wall_data['error_response']:
        return

    get_or_create_cache(wall_data, request_type)


def verify_no_other_user_tasks_in_progress(wall_data) -> None:
    """Ensure a single calculation is in progress per user"""
    if wall_data['request_type'] != 'create_wall_task':
        user_tasks_in_progress = WallConfigReference.objects.filter(
            user=wall_data['request_user'],
            status__in=[
                WallConfigReferenceStatusEnum.CELERY_CALCULATION,
                WallConfigReferenceStatusEnum.SYNC_CALCULATION
            ]
        ).exclude(config_id=wall_data['request_config_id']).values_list('config_id', flat=True)

        if user_tasks_in_progress:
            error_utils.handle_user_task_in_progress_exists(list(user_tasks_in_progress), wall_data)


def get_or_create_cache(wall_data, request_type) -> None:
    # Check for cached data
    collect_cached_data(wall_data, request_type)
    if wall_data.get('cached_result') or wall_data['error_response']:
        return

    if wall_data['request_type'] != 'create_wall_task':
        # Cache not found for profiles endpoints - evaluate the WallConfig status
        error_utils.handle_cache_not_found(wall_data)
        if (
            # Already being processed
            wall_data.get('info_response') or
            # Expected to be found - return 409
            wall_data['error_response']
        ):
            return

    # Attempt to get/create the wall config object
    wall_config_object = manage_wall_config_object(wall_data)

    if (
        # sections_count > MAX_SECTIONS_COUNT_SYNCHRONOUS_RESPONSE
        # -sent for async processing
        wall_data.get('info_response') or
        # Obsolete?
        wall_data['error_response']
    ):
        return

    if isinstance(wall_config_object, WallConfig):
        if wall_config_object.deletion_initiated:
            # Celery task is aborted before the simulation is started
            wall_data['celery_task_aborted'] = 'OK_1'
            return
        # Successful creation/fetch of the wall config object
        wall_data['wall_config_object'] = wall_config_object
        handle_wall_config_status(wall_config_object, wall_data)
    else:
        # Either being initialized by another process
        # or an error occurred during the creation
        return

    run_synchronous_simulation(wall_data, wall_config_object)

    # Validate if the day is correct with data from the simulation
    error_utils.validate_day_within_range(wall_data, post_syncronous_simulation=True)


def run_synchronous_simulation(wall_data: Dict[str, Any], wall_config_object: WallConfig) -> None:
    """
    If no cached data is found, run the simulation synchronously:
    -Always for Celery create_wall_task
    -Up to a certain limit (MAX_SECTIONS_COUNT_SYNCHRONOUS_RESPONSE) for Cost and Usage requests
    """
    handle_wall_config_reference_status(wall_data, WallConfigReferenceStatusEnum.SYNC_CALCULATION)

    run_simulation(wall_data)
    if wall_data['error_response'] or wall_data.get('celery_task_aborted'):
        return

    # Create the new cache data
    cache_wall(wall_data)

    # Ensure consistent final statuses
    handle_wall_config_reference_status(wall_data, WallConfigReferenceStatusEnum.AVAILABLE)
    handle_wall_config_status_after_synchronous_calculation(wall_config_object, wall_data)


def collect_cached_data(wall_data: Dict[str, Any], request_type: str) -> None:
    """
    Check for different type of cached data, based on the request type.
    """
    cached_result = wall_data['cached_result'] = {}

    request_type = wall_data['request_type']
    try:
        if request_type in ['profiles-overview', 'create_wall_task']:
            fetch_wall_cost(wall_data, cached_result)
        elif request_type == 'profiles-overview-day':
            fetch_profiles_overview_day_cost(wall_data, cached_result)
        elif request_type == 'single-profile-overview-day':
            fetch_profile_day_cost(wall_data, cached_result)
        elif request_type == 'profiles-days':
            fetch_profile_day_ice_amount(wall_data, cached_result)
        else:
            raise Exception(f'Unknown request type: {request_type}')
    except (Wall.DoesNotExist, WallProgress.DoesNotExist):
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
    Redis cache for 'profiles-overview'.
    Both simulation types store the same cost.
    """
    wall_redis_key = get_wall_cache_key(wall_data)
    if wall_data['request_type'] != 'create_wall_task':
        cached_wall_ice_amount = cache.get(wall_redis_key)
        if cached_wall_ice_amount is None:
            cached_wall_cost = None
        else:
            cached_wall_cost = cached_wall_ice_amount * settings.ICE_COST_PER_CUBIC_YARD
    else:
        # Call from the Celery computation worker - no Redis cache is used
        cached_wall_cost = None

    return cached_wall_cost, wall_redis_key


def get_wall_cache_key(wall_data: Dict[str, Any]) -> str:
    if wall_data['request_type'] != 'create_wall_task':
        # NOTE-1: App call - optimized query
        return f'wall_ttl_ice_amnt_{wall_data["wall_config_hash"]}'
    else:
        # NOTE-2: Celery task call - full query to check if the wall
        # construction is already cached in the DB with the provided num_crews
        return f'wall_ttl_ice_amnt_{wall_data["wall_config_hash"]}_{wall_data["num_crews"]}'


def fetch_wall_cost_from_db(wall_data: Dict[str, Any], cached_result: Dict[str, Any], wall_redis_key: str) -> None:
    """
    DB cache for 'profiles-overview'.
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
        cached_result['wall_total_cost'] = wall.total_ice_amount * settings.ICE_COST_PER_CUBIC_YARD
        if request_type != 'create_wall_task':
            # Refresh the Redis cache
            set_redis_cache(wall_redis_key, wall.total_ice_amount)


def fetch_profile_day_cost(wall_data: Dict[str, Any], cached_result: Dict[str, Any]) -> None:
    """
    Cache for 'single-profile-overview-day'.
    Reuse the profiles-days caching logic.
    """
    fetch_profile_day_ice_amount(wall_data, cached_result)
    ice_amount = cached_result.pop('profile_day_ice_amount', None)
    if ice_amount is not None:
        cached_result['profile_day_cost'] = ice_amount * settings.ICE_COST_PER_CUBIC_YARD


def fetch_profiles_overview_day_cost(wall_data: Dict[str, Any], cached_result: Dict[str, Any]) -> None:
    # Redis cache
    cached_cost, redis_cache_key = fetch_profiles_overview_day_cost_from_redis_cache(wall_data)
    if cached_cost is not None:
        cached_result['profiles_overview_day_cost'] = cached_cost
        return

    # DB
    fetch_profiles_overview_day_cost_from_db(wall_data, cached_result, redis_cache_key)


def fetch_profiles_overview_day_cost_from_redis_cache(wall_data: Dict[str, Any]) -> tuple[int | None, str]:
    """Redis cache for 'profiles-overview-day'"""
    redis_cache_key = get_wall_progress_cache_key(wall_data, wall_data['request_day'])
    cached_ice_amount = cache.get(redis_cache_key)
    if cached_ice_amount is not None:
        cached_cost = cached_ice_amount * settings.ICE_COST_PER_CUBIC_YARD
    else:
        cached_cost = None

    return cached_cost, redis_cache_key


def fetch_profiles_overview_day_cost_from_db(
    wall_data: Dict[str, Any], cached_result: Dict[str, Any], redis_cache_key: str
) -> None:
    """DB cache for 'profiles-overview-day'"""
    _wall, wall_progress = fetch_wall_and_wall_progress(wall_data)

    if wall_data['error_response'] or wall_progress is None:
        return

    # Work is done on the provided day
    total_daily_ice_amount = wall_progress.ice_amount_data['dly_ttl']
    cached_result['profiles_overview_day_cost'] = total_daily_ice_amount * settings.ICE_COST_PER_CUBIC_YARD
    # Refresh the Redis cache
    set_redis_cache(redis_cache_key, total_daily_ice_amount)


def fetch_wall_and_wall_progress(
    wall_data: Dict[str, Any]
) -> tuple[Wall | None, WallProgress | None]:
    wall = Wall.objects.filter(
        wall_config_hash=wall_data['wall_config_hash'], num_crews=wall_data['num_crews']
    ).first()

    if wall is None:
        return None, None

    # Wall is cached - validate the day
    error_utils.validate_day_within_range(wall_data, wall)
    if wall_data['error_response']:
        return None, None

    wall_progress = WallProgress.objects.filter(
        wall=wall,
        day=wall_data['request_day'],
    ).first()

    return wall, wall_progress


def fetch_profile_day_ice_amount(wall_data: Dict[str, Any], cached_result: Dict[str, Any]) -> None:
    profile_id = wall_data['request_profile_id']

    # Redis cache
    cached_ice_amount, redis_cache_key = fetch_profile_day_ice_amount_from_redis_cache(
        wall_data, profile_id
    )
    if cached_ice_amount is not None:
        # Return the cached value
        cached_result['profile_day_ice_amount'] = cached_ice_amount
        return
    if wall_data['error_response']:
        # Return if any day errors
        return

    # DB
    fetch_profile_day_ice_amount_from_db(wall_data, profile_id, cached_result, redis_cache_key)


def fetch_profile_day_ice_amount_from_redis_cache(wall_data: Dict[str, Any], profile_id: int) -> tuple[int, str]:
    """Redis cache for 'profiles-days'"""
    redis_cache_key = get_wall_progress_cache_key(
        wall_data, wall_data['request_day'], profile_id
    )
    cached_ice_amount = cache.get(redis_cache_key)

    # No check_wall_construction_days_redis_cache method is implemented:
    # Explanation:
    # Don't mix DB with Redis cache fetches in this case, to avoid theoretical
    # race conditions, where 1 process has already cached the wall
    # and its construction days in the DB, but the Redis cache is still
    # not committed

    return cached_ice_amount, redis_cache_key


def get_wall_progress_cache_key(
    wall_data: Dict[str, Any], day: int, profile_id: int | None = None
) -> str:
    """
    Generate a key for the Redis cache.
    Two types of cache keys are generated:
        - For a specific profile
        - For all profiles
    """
    cache_type = 'prfl_day_ice_amt' if profile_id is not None else 'day_ice_amt'
    key_data = (
        f'{cache_type}_'
        f'{wall_data["wall_config_hash"]}_'
        f'{wall_data["num_crews"]}_'
        f'{day}'
    )
    if profile_id is not None:
        key_data += f'_{profile_id}'

    # key_data = hash_calc(key_data)   # Potential future mem. usage optimisation

    return key_data


def fetch_profile_day_ice_amount_from_db(
    wall_data: Dict[str, Any], profile_id: int, cached_result: Dict[str, Any], redis_cache_key: str
) -> None:
    """
    Fetch a cached Wall Profile Progress from the DB.
    Variability based on the number of crews.
    """
    wall, wall_progress = fetch_wall_and_wall_progress(wall_data)

    if wall_data['error_response'] or wall_progress is None:
        return

    # Work is done on the provided day
    profile_day_ice_amount = wall_progress.ice_amount_data.get(str(profile_id))
    if profile_day_ice_amount is not None:
        # There's work done on this day on the provided profile
        cached_result['profile_day_ice_amount'] = profile_day_ice_amount
        # Refresh the Redis cache
        set_redis_cache(redis_cache_key, profile_day_ice_amount)
    elif wall is not None:
        # No work done on this day on the provided profile,
        # verify the wall construction days
        error_utils.check_wall_construction_days(
            wall.construction_days, wall_data, profile_id
        )


def manage_wall_config_file_upload(wall_data: Dict[str, Any]) -> None:
    # Check for other user tasks in progress
    verify_no_other_user_tasks_in_progress(wall_data)

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
        create_new_wall_config_reference(wall_data, wall_config_object)
        if wall_data['error_response']:
            return
        handle_wall_config_status(wall_config_object, wall_data)
    else:
        error_utils.handle_wall_config_deletion_in_progress(wall_data)


def create_new_wall_config_reference(wall_data: Dict[str, Any], wall_config_object: WallConfig) -> None:
    wall_config_reference_cache_key = get_wall_config_reference_cache_key(
        wall_data['wall_config_hash'], wall_data['request_config_id']
    )
    wall_config_reference_db_lock_key = generate_db_lock_key(wall_config_reference_cache_key)
    db_lock_acquired = None
    try:
        db_lock_acquired = acquire_db_lock(wall_config_reference_db_lock_key)
        if not db_lock_acquired:
            # Being created in another process
            return

        with transaction.atomic():
            wall_config_reference = WallConfigReference.objects.create(
                user=wall_data['request_user'],
                wall_config=wall_config_object,
                config_id=wall_data['request_config_id'],
            )
            wall_data['wall_config_reference'] = wall_config_reference
    except Exception as wall_config_reference_crtn_unkwn_err:
        error_utils.handle_unknown_error(wall_data, wall_config_reference_crtn_unkwn_err, 'caching')
    finally:
        if db_lock_acquired:
            release_db_lock(wall_config_reference_db_lock_key)


def get_wall_config_reference_cache_key(wall_config_hash: str, config_id: str) -> str:
    return f'wall_config_reference_{wall_config_hash}_{config_id}'


def manage_wall_config_file_delete(wall_data: Dict[str, Any]) -> None:
    error_utils.handle_not_existing_file_references(wall_data)
    if wall_data['error_response']:
        return

    wall_config_hash_list = delete_wall_config_references(wall_data)

    if wall_data['error_response'] or not wall_config_hash_list:
        return

    if not settings.ACTIVE_TESTING:
        delete_unused_wall_configs_task.apply_async(
            kwargs={'wall_config_hash_list': wall_config_hash_list},
            priority=CELERY_TASK_PRIORITY['HIGH'],
        )   # type: ignore


def delete_wall_config_references(wall_data: Dict[str, Any]) -> list[str]:
    wall_config_hash_list = []

    for wall_config_reference in wall_data['deletion_queryset']:
        wall_config_reference_cache_key = get_wall_config_reference_cache_key(
            wall_config_reference.wall_config.wall_config_hash, wall_config_reference.config_id
        )
        wall_config_reference_db_lock_key = generate_db_lock_key(wall_config_reference_cache_key)
        db_lock_acquired = None
        try:
            db_lock_acquired = acquire_db_lock(wall_config_reference_db_lock_key)
            if not db_lock_acquired:
                # Being deleted in another process
                return []

            with transaction.atomic():
                wall_config_reference.delete()
                if wall_config_reference.wall_config.wall_config_hash not in wall_config_hash_list:
                    wall_config_hash_list.append(wall_config_reference.wall_config.wall_config_hash)
        except Exception as del_unkwn_err:
            error_utils.handle_unknown_error(wall_data, del_unkwn_err, 'caching')
        finally:
            if db_lock_acquired:
                release_db_lock(wall_config_reference_db_lock_key)

    return wall_config_hash_list


def manage_wall_config_object(wall_data: Dict[str, Any]) -> WallConfig | str:
    """WallConfig object management corresponding to its state."""
    wall_config_hash = wall_data['wall_config_hash']
    try:
        # Already created
        wall_config_object = WallConfig.objects.get(wall_config_hash=wall_config_hash)
        error_utils.handle_wall_config_object_already_exists(wall_data, wall_config_object)
        if wall_data['error_response']:
            return 'Already uploaded for this user.'
    except WallConfig.DoesNotExist:
        # Only possible for wallconfig-files/upload.
        # The other endpoints must be blocked at the wall config reference fetch
        # in case of a missing wall config.
        wall_config_object = create_new_wall_config(wall_data, wall_config_hash)

    return wall_config_object


def create_new_wall_config(wall_data: Dict[str, Any], wall_config_hash: str) -> WallConfig | str:
    wall_config_cache_key = get_wall_config_cache_key(wall_config_hash)
    wall_config_db_lock_key = generate_db_lock_key(wall_config_cache_key)
    db_lock_acquired = None
    try:
        db_lock_acquired = acquire_db_lock(wall_config_db_lock_key)
        if not db_lock_acquired:
            return 'Being initialized in another process'

        with transaction.atomic():
            # Create a new object with status INITIALIZED (default value)
            wall_config_object = WallConfig.objects.create(
                wall_config_hash=wall_config_hash,
                wall_construction_config=wall_data['initial_wall_construction_config']
            )
    except Exception as wall_config_crtn_unkwn_err:
        wall_config_object = f'{wall_config_crtn_unkwn_err.__class__.__name__}: {str(wall_config_crtn_unkwn_err)}'
        error_utils.handle_unknown_error(wall_data, wall_config_crtn_unkwn_err, 'caching')
    finally:
        if db_lock_acquired:
            release_db_lock(wall_config_db_lock_key)

    return wall_config_object


def handle_wall_config_status(wall_config_object: WallConfig, wall_data: Dict[str, Any]) -> None:
    if wall_data['request_type'] == 'create_wall_task' or settings.ACTIVE_TESTING:
        # Skip during Celery task creation and testing
        return

    sections_count = wall_data['sections_count']

    task_kwargs = {
        'wall_config_hash': wall_config_object.wall_config_hash,
        'wall_construction_config': wall_data['initial_wall_construction_config'],
        'sections_count': sections_count,
        'username': wall_data['request_user'].username,
        'config_id': wall_data['wall_config_reference'].config_id,
    }

    if wall_data['request_type'] == 'wallconfig-files/upload':
        # File upload
        handle_file_upload_request(wall_config_object, task_kwargs, sections_count)

    elif sections_count > settings.MAX_SECTIONS_COUNT_SYNCHRONOUS_RESPONSE:
        # Cost and usage API requests - Send to Celery only if not in the synchronous processing case
        # WallConfig.status in [INITIALIZED, PARTIALLY_CALCULATED]
        handle_async_single_num_crews_request(task_kwargs, wall_data)


def handle_file_upload_request(
    wall_config_object: WallConfig, task_kwargs: Dict[str, Any], sections_count: int
) -> None:
    """
    Handle only WallConfig.status == INITIALIZED.
    Send to Celery for full-range processing only if up to a certain number of sections
    """
    if (
        wall_config_object.status == WallConfigStatusEnum.INITIALIZED and
        sections_count <= settings.MAX_SECTIONS_COUNT_FULL_RANGE_CACHING
    ):
        task_kwargs['num_crews_range'] = 'full-range'
        orchestrate_wall_config_processing_task.apply_async(
            kwargs=task_kwargs, priority=CELERY_TASK_PRIORITY['MEDIUM']
        )  # type: ignore


def handle_async_single_num_crews_request(task_kwargs: Dict[str, Any], wall_data: Dict[str, Any]) -> None:
    """Send to Celery for single num_crews processing"""
    task_kwargs['num_crews_range'] = wall_data['num_crews']
    orchestrate_wall_config_processing_task.apply_async(
        kwargs=task_kwargs, priority=CELERY_TASK_PRIORITY['MEDIUM']
    )  # type: ignore
    handle_being_processed(wall_data)


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
    total_ice_amount = wall_data['wall_construction'].wall_profile_data['profiles_overview']['total_ice_amount']
    construction_days = wall_data['wall_construction'].wall_profile_data['profiles_overview']['construction_days']
    wall_redis_data = []

    with transaction.atomic():
        try:
            # Create the wall object in the DB
            wall = Wall.objects.create(
                wall_config=wall_data['wall_config_object'],
                wall_config_hash=wall_data['wall_config_hash'],
                num_crews=wall_data['num_crews'],
                total_ice_amount=total_ice_amount,
                construction_days=construction_days,
            )
        except IntegrityError as intgrty_err:
            # Rare case - log it to keep track of ocurence frequency
            error_type = 'caching' if wall_data['request_type'] != 'create_wall_task' else 'celery_tasks'
            error_utils.send_log_error_async(error_type, error=intgrty_err)
            return

        if wall_data['request_type'] != 'create_wall_task':
            # Deferred Redis cache for 'profiles-overview'
            wall_redis_data.append((
                wall_cache_key,
                total_ice_amount
            ))
        process_wall_progress(wall_data, wall, wall_redis_data)

        if wall_data['request_type'] != 'create_wall_task':
            # Commit deferred Redis cache after a successful DB transaction
            # Redis cache not managed for Celery computation config tasks
            transaction.on_commit(lambda: commit_deferred_redis_cache(wall_redis_data))


def process_wall_progress(wall_data: Dict[str, Any], wall: Wall, wall_redis_data: list[tuple[str, int]]) -> None:
    """Create DB and Redis caches."""
    daily_details = wall_data['wall_construction'].wall_profile_data['profiles_overview']['daily_details']

    for day, ice_amount_data in daily_details.items():

        # Create the wall profile progress object
        WallProgress.objects.create(
            wall=wall,
            day=day,
            ice_amount_data=ice_amount_data
        )

        if wall_data['request_type'] != 'create_wall_task':
            # Deferred Redis cache - only for non full-range cases - for 'profiles' endpoints requests
            for profile_key, ice_amount in ice_amount_data.items():
                if profile_key != 'dly_ttl':
                    # Cache for 'profiles-days' and 'single-profile-overview-day'
                    cache_key = get_wall_progress_cache_key(wall_data, day, profile_key)
                else:
                    # Cache for 'profiles-overview-day'
                    cache_key = get_wall_progress_cache_key(wall_data, day)

                wall_redis_data.append((cache_key, ice_amount))


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


def handle_wall_config_reference_status(wall_data, new_reference_status: WallConfigReferenceStatusEnum) -> None:
    if wall_data.get('request_type') == 'create_wall_task':
        return

    wall_config_reference = wall_data['wall_config_reference']
    if wall_config_reference.status != new_reference_status:
        try:
            with transaction.atomic():
                WallConfigReference.objects.select_for_update().get(
                    id=wall_data['wall_config_reference'].id
                )
                wall_config_reference.status = new_reference_status
                wall_config_reference.save()
        except Exception as unknwn_err:
            error_utils.handle_unknown_error(wall_data, unknwn_err, 'caching')


def handle_wall_config_status_after_synchronous_calculation(wall_config_object: WallConfig, wall_data: Dict[str, Any]) -> None:
    if wall_data['request_type'] == 'create_wall_task':
        # Handled in the celery task
        return

    max_retries = 3
    retry_delay = 1

    for attempt in range(max_retries):
        try:
            with transaction.atomic():
                # Lock the wall config object for a final status set
                wall_config_object = WallConfig.objects.select_for_update().get(
                    wall_config_hash=wall_config_object.wall_config_hash
                )

                if not wall_data['error_response']:
                    if wall_config_object.status != WallConfigStatusEnum.PARTIALLY_CALCULATED:
                        wall_config_object.status = WallConfigStatusEnum.PARTIALLY_CALCULATED
                else:
                    wall_config_object.status = WallConfigStatusEnum.ERROR

                wall_config_object.save()
            return
        except Exception as unknwn_err:
            if attempt < max_retries - 1:
                sleep(retry_delay)
                continue
            else:
                error_utils.handle_unknown_error(wall_data, unknwn_err, 'caching')
