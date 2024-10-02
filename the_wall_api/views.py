import copy
from typing import Any, Dict, List
import xxhash

from django.core.cache import cache
from django.db import connection, IntegrityError, transaction
from django.db.models import Q
from django.http import HttpRequest, JsonResponse
from django_redis import get_redis_connection
from django.views.defaults import page_not_found

from drf_spectacular.utils import extend_schema

from redis import Redis
from redis.exceptions import ConnectionError, TimeoutError

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from the_wall_api.models import WallProfileProgress, WallProfile, Wall
from the_wall_api.serializers import CostOverviewSerializer, DailyIceUsageSerializer
from the_wall_api.utils import (
    CONCURRENT, SEQUENTIAL, WallConstructionError,
    cost_overview_examples, cost_overview_parameters,
    cost_overview_profile_id_examples, cost_overview_responses,
    daily_ice_usage_examples, daily_ice_usage_parameters, daily_ice_usage_responses,
    exposed_endpoints, generate_config_hash_details,
    load_wall_profiles_from_config, num_crews_parameter
)
from the_wall_api.wall_construction import WallConstruction


class BaseWallProfileView(APIView):
    
    def initialize_wall_data(self, profile_id: int | None = None, day: int | None = None) -> Dict[str, Any]:
        """
        Initialize the wall_data dictionary to hold various control data
        throughout the wall construction simulation process.
        """
        return {
            'request_profile_id': profile_id,
            'request_day': day,
            'error_response': None,
            'concurrent_not_needed': None,
            'wall_construction': None,
        }

    def fetch_wall_data(
        self, wall_data: Dict[str, Any], num_crews: int, profile_id: int | None = None, request_type: str = ''
    ):
        wall_construction_config = self.get_wall_construction_config(wall_data)
        if wall_data['error_response']:
            return

        if self.is_invalid_profile_number(profile_id, wall_construction_config, wall_data):
            return

        self.set_simulation_params(wall_data, num_crews, wall_construction_config, request_type)
        
        self.get_or_create_cache(wall_data, request_type)

    def get_wall_construction_config(self, wall_data: Dict[str, Any]) -> list:
        try:
            return load_wall_profiles_from_config()
        except (WallConstructionError, FileNotFoundError) as tech_error:
            wall_data['error_response'] = self.create_technical_error_response({}, tech_error)
            return []

    def is_invalid_profile_number(self, profile_id: int | None, wall_construction_config: list, wall_data: Dict[str, Any]) -> bool:
        max_profile_number = len(wall_construction_config)
        if profile_id is not None and profile_id > max_profile_number:
            wall_data['error_response'] = self.create_out_of_range_response('profile number', max_profile_number, status.HTTP_400_BAD_REQUEST)
            return True
        return False

    def set_simulation_params(
            self, wall_data: Dict[str, Any], num_crews: int,
            wall_construction_config: list, request_type: str
    ) -> None:
        """
        Set the simulation parameters for the wall_data dictionary.
        """
        sections_count = sum(len(profile) for profile in wall_construction_config)
        wall_data['sections_count'] = sections_count

        simulation_type, wall_config_hash_details, num_crews_final = self.evaluate_simulation_params(
            num_crews, sections_count, wall_construction_config, wall_data
        )
        wall_data['num_crews'] = num_crews_final
        wall_data['wall_construction_config'] = copy.deepcopy(wall_construction_config)
        wall_data['simulation_type'] = simulation_type
        wall_data['wall_config_hash'] = wall_config_hash_details['wall_config_hash']
        wall_data['profile_config_hash_data'] = wall_config_hash_details['profile_config_hash_data']
        wall_data['request_type'] = request_type

    def evaluate_simulation_params(
            self, num_crews: int, sections_count: int, wall_construction_config: list, wall_data: Dict[str, Any]
    ) -> tuple[str, dict, int]:
        # num_crews
        if num_crews == 0:
            # No num_crews provided - sequential mode
            simulation_type = SEQUENTIAL
            num_crews_final = 0
        elif num_crews >= sections_count:
            # There's a crew for each section at the beginning
            # which is the same as the sequential mode
            simulation_type = SEQUENTIAL
            num_crews_final = 0
            # For eventual future response message
            wall_data['concurrent_not_needed'] = True
        else:
            # The crews are less than the number of sections
            simulation_type = CONCURRENT
            num_crews_final = num_crews

        # configuration hashes
        wall_config_hash_details = generate_config_hash_details(wall_construction_config)

        return simulation_type, wall_config_hash_details, num_crews_final
        
    def get_or_create_cache(self, wall_data, request_type) -> None:
        # Check for cached data
        self.collect_cached_data(wall_data, request_type)
        if wall_data.get('cached_result') or wall_data['error_response']:
            return
        
        # If no cached data is found, run the simulation
        self.run_simulation_and_create_cache(wall_data)

    def validate_day_within_range(self, wall_data: Dict[str, Any]) -> None:
        """
        Compare the day from the request (if provided and the max day in the simulation).
        """
        construction_days = wall_data['sim_calc_details']['construction_days']
        if wall_data['request_day'] is not None and wall_data['request_day'] > construction_days:
            wall_data['error_response'] = self.create_out_of_range_response('day', construction_days, status.HTTP_400_BAD_REQUEST)

    def collect_cached_data(self, wall_data: Dict[str, Any], request_type: str) -> None:
        """
        Check for different type of cached data, based on the request type.
        """
        cached_result = wall_data['cached_result'] = {}

        request_type = wall_data['request_type']
        try:
            if request_type == 'costoverview':
                self.fetch_wall_cost(wall_data, cached_result)
            elif request_type == 'costoverview/profile_id':
                self.fetch_wall_profile_cost(wall_data, cached_result)
            elif request_type == 'daily-ice-usage':
                self.fetch_daily_ice_usage(wall_data, cached_result)
        except (Wall.DoesNotExist, WallProfile.DoesNotExist, WallProfileProgress.DoesNotExist):
            return

    def fetch_wall_cost(self, wall_data: Dict[str, Any], cached_result: Dict[str, Any]) -> None:
        # Redis cache
        cached_wall_cost, wall_redis_key = self.fetch_wall_cost_from_redis_cache(wall_data)
        if cached_wall_cost is not None:
            cached_result['wall_total_cost'] = cached_wall_cost
            return
        
        # DB
        self.fetch_wall_cost_from_db(wall_data, cached_result, wall_redis_key)

    def fetch_wall_cost_from_redis_cache(self, wall_data: Dict[str, Any]) -> tuple[Dict[str, Any], str]:
        """
        Fetch a cached Wall from the Redis cache.
        Both simulation types store the same cost.
        """
        wall_redis_key = self.get_wall_cache_key(wall_data)
        cached_wall_cost = cache.get(wall_redis_key)
        
        return cached_wall_cost, wall_redis_key

    def get_wall_cache_key(self, wall_data: Dict[str, Any]) -> str:
        return f'wall_cost_{wall_data["wall_config_hash"]}'

    def fetch_wall_cost_from_db(self, wall_data: Dict[str, Any], cached_result: Dict[str, Any], wall_redis_key: str) -> None:
        """
        Fetch a cached Wall from the DB.
        Both simulation types store the same cost.
        """
        wall = Wall.objects.filter(wall_config_hash=wall_data['wall_config_hash']).first()
        if wall:
            cached_result['wall_total_cost'] = wall.total_cost
            # Refresh the Redis cache
            self.set_redis_cache(wall_data, wall_redis_key, wall.total_cost)

    def fetch_wall_profile_cost(self, wall_data: Dict[str, Any], cached_result: Dict[str, Any]) -> None:
        profile_id = wall_data['request_profile_id']
        profile_config_hash_data = wall_data['profile_config_hash_data']
        wall_profile_config_hash = profile_config_hash_data[profile_id]

        # Redis cache
        cached_wall_profile_cost, wall_profile_redis_cache_key = self.fetch_wall_profile_cost_from_redis_cache(
            wall_profile_config_hash
        )
        if cached_wall_profile_cost is not None:
            cached_result['wall_profile_cost'] = cached_wall_profile_cost
            return
        
        # DB
        self.fetch_wall_profile_cost_from_db(
            wall_profile_config_hash, cached_result, wall_data, wall_profile_redis_cache_key
        )

    def fetch_wall_profile_cost_from_redis_cache(self, wall_profile_config_hash: str) -> tuple[Dict[str, Any], str]:
        """
        Fetch a cached Wall Profile from the Redis cache.
        Both simulation types store the same cost - attempt to find a cached value for any of them.
        """
        wall_profile_redis_cache_key = self.get_wall_profile_cache_key(wall_profile_config_hash)
        cached_wall_profile_cost = cache.get(wall_profile_redis_cache_key)

        return cached_wall_profile_cost, wall_profile_redis_cache_key

    def get_wall_profile_cache_key(self, wall_profile_config_hash: str) -> str:
        return f'wall_prfl_cost_{wall_profile_config_hash}'

    def fetch_wall_profile_cost_from_db(
            self, wall_profile_config_hash: str | None, cached_result: Dict[str, Any],
            wall_data: Dict[str, Any], wall_profile_redis_cache_key: str
    ) -> None:
        """
        Fetch a cached Wall Profile from the DB.
        Both simulation types store the same cost.
        """
        wall_profile = WallProfile.objects.filter(wall_profile_config_hash=wall_profile_config_hash).first()
        if wall_profile:
            cached_result['wall_profile_cost'] = wall_profile.cost
            # Refresh the Redis cache
            self.set_redis_cache(wall_data, wall_profile_redis_cache_key, wall_profile.cost)

    def fetch_daily_ice_usage(self, wall_data: Dict[str, Any], cached_result: Dict[str, Any]) -> None:
        profile_id = wall_data['request_profile_id']
        profile_config_hash_data = wall_data['profile_config_hash_data']
        wall_profile_config_hash = profile_config_hash_data[profile_id]

        # Redis cache
        cached_profile_ice_usage, profile_ice_usage_redis_cache_key = self.fetch_daily_ice_usage_from_redis_cache(
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
        self.fetch_daily_ice_usage_from_db(
            wall_data, wall_profile_config_hash, profile_id, cached_result, profile_ice_usage_redis_cache_key
        )

    def fetch_daily_ice_usage_from_redis_cache(
            self, wall_data: Dict[str, Any], wall_profile_config_hash: str | None, profile_id: int,
    ) -> tuple[str | None, str]:
        """
        Fetch a cached Wall Profile Progress from the Redis cache.
        Variability depending on the number of crews.
        """
        profile_ice_usage_redis_cache_key = self.get_daily_ice_usage_cache_key(
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
            self, wall_data: Dict[str, Any], wall_profile_config_hash: str | None, day: int, profile_id: int
    ) -> str:
        key_data = (
            f'dly_ice_usg_'
            f'{wall_data["wall_config_hash"]}_'
            f'{wall_data["num_crews"]}_'
            f'{wall_profile_config_hash}_'
            f'{day}'
        )
        if wall_data['simulation_type'] == CONCURRENT:
            key_data += f'_{profile_id}'
        
        # profile_ice_usage_redis_cache_key = hash_calc(key_data)   # Potential future mem. usage optimisation
        
        return key_data

    def fetch_daily_ice_usage_from_db(
            self, wall_data: Dict[str, Any], wall_profile_config_hash: str | None,
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

        if wall_data['simulation_type'] == CONCURRENT:
            wall_progress_query &= Q(wall_profile__profile_id=profile_id)

        try:
            wall_profile_progress = WallProfileProgress.objects.get(wall_progress_query)
            cached_result['profile_daily_ice_used'] = wall_profile_progress.ice_used
            # Refresh the Redis cache
            self.set_redis_cache(wall_data, profile_ice_usage_redis_cache_key, wall_profile_progress.ice_used)
        except WallProfileProgress.DoesNotExist:
            self.check_if_cached_on_another_day(wall_data, profile_id)

    def check_if_cached_on_another_day(self, wall_data: Dict[str, Any], profile_id: int) -> None:
        """
        In CONCURRENT mode there are days without profile daily ice usage,
        because there was no crew assigned on the profile.
        Check for other cached daily progress to avoid processing of
        an already cached simulation.
        """
        try:
            wall = Wall.objects.get(
                wall_config_hash=wall_data['wall_config_hash'],
                num_crews=wall_data['num_crews'],
            )
            wall_construction_days = wall.construction_days
            self.check_wall_construction_days(wall_construction_days, wall_data, profile_id)
        except Wall.DoesNotExist:
            raise WallProfileProgress.DoesNotExist
    
    def check_wall_construction_days(self, wall_construction_days: int, wall_data: Dict[str, Any], profile_id):
        """
        Handle erroneous construction days related responses.
        """
        if wall_data['request_day'] <= wall_construction_days:
            response_details = f'No crew has worked on profile {profile_id} on day {wall_data["request_day"]}.'
            wall_data['error_response'] = Response(response_details, status=status.HTTP_404_NOT_FOUND)
        else:
            wall_data['error_response'] = self.create_out_of_range_response('day', wall_construction_days, status.HTTP_400_BAD_REQUEST)

    def run_simulation_and_create_cache(self, wall_data: Dict[str, Any]) -> None:
        """
        Run the simulation, create and save the wall and its elements.
        """
        try:
            wall_construction = WallConstruction(
                wall_construction_config=wall_data['wall_construction_config'],
                sections_count=wall_data['sections_count'],
                num_crews=wall_data['num_crews'],
                simulation_type=wall_data['simulation_type']
            )
        except WallConstructionError as tech_error:
            wall_data['error_response'] = self.create_technical_error_response({}, tech_error)
            return
        wall_data['wall_construction'] = wall_construction
        wall_data['sim_calc_details'] = wall_construction.sim_calc_details
        self.store_simulation_result(wall_data)

        # Create the new cache data
        self.cache_wall(wall_data)
        if wall_data['error_response']:
            return

        # Validate if the day is correct with data from the simulation
        self.validate_day_within_range(wall_data)

    def store_simulation_result(self, wall_data):
        """
        Store the simulation results to be used in the responses.
        """
        simulation_result = wall_data['simulation_result'] = {}

        # Used in the costowverview response
        simulation_result['wall_total_cost'] = wall_data['sim_calc_details']['total_cost']

        # Used in the costoverview/profile_id response
        request_profile_id = wall_data['request_profile_id']
        if request_profile_id:
            simulation_result['wall_profile_cost'] = wall_data['sim_calc_details']['profile_costs'][request_profile_id]

        # Used in the daily-ice-usage response
        request_day = wall_data['request_day']
        if request_day:
            profile_daily_progress_data = wall_data['sim_calc_details']['profile_daily_details'][request_profile_id]
            profile_day_data = profile_daily_progress_data.get(wall_data['request_day'], {})
            simulation_result['profile_daily_ice_used'] = profile_day_data.get('ice_used', 0)

    def cache_wall(self, wall_data: Dict[str, Any]) -> None:
        """
        Creates a new Wall object.
        Start a cascade cache creation of all wall elements.
        """
        wall_cache_key = self.get_wall_cache_key(wall_data)
        wall_db_lock_key = self.generate_db_lock_key(wall_cache_key)
        db_lock_acquired = None
        total_cost = wall_data['sim_calc_details']['total_cost']
        wall_redis_data = []
        
        try:
            db_lock_acquired = self.acquire_db_lock(wall_db_lock_key)
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
                wall_redis_data.append((wall_cache_key, total_cost))
                self.process_wall_profiles(wall_data, wall, wall_data['simulation_type'], wall_redis_data)

                # Commit deferred Redis cache after a successful DB transaction
                transaction.on_commit(lambda: self.commit_deferred_redis_cache(wall_data, wall_redis_data))
        
        except IntegrityError as wall_crtn_intgrty_err:
            self.handle_wall_crtn_integrity_error(wall_data, wall_crtn_intgrty_err)
        except Exception as wall_crtn_unkwn_err:
            self.handle_wall_crtn_unknown_error(wall_data, wall_crtn_unkwn_err)
        finally:
            if db_lock_acquired:
                self.release_db_lock(wall_db_lock_key)

    def generate_db_lock_key(self, cache_lock_key: str) -> List[int]:
        """Generate two unique integers from a string key for PostgreSQL advisory locks."""
        xxhash_64bit = xxhash.xxh64(cache_lock_key).intdigest()
        lock_id1 = xxhash_64bit & 0xFFFFFFFF  # Lower 32 bits
        lock_id2 = (xxhash_64bit >> 32) & 0xFFFFFFFF  # Upper 32 bits
        return [lock_id1, lock_id2]

    def acquire_db_lock(self, wall_db_lock_key: List[int]) -> bool:
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_try_advisory_lock(%s, %s);', wall_db_lock_key)
            db_lock_acquired = cursor.fetchone()
            return bool(db_lock_acquired and db_lock_acquired[0])

    def release_db_lock(self, wall_db_lock_key: List[int]) -> None:
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_unlock(%s, %s);', wall_db_lock_key)

    def handle_wall_crtn_integrity_error(self, wall_data: Dict[str, Any], wall_crtn_intgrty_err: IntegrityError) -> None:
        """Handle known integrity errors, such as hash collisions."""
        if (
            wall_data['num_crews'] == 0 and
            'unique constraint' in str(wall_crtn_intgrty_err) and
            'wall_config_hash' in str(wall_crtn_intgrty_err)
        ):
            # Hash collision - should be a very rare case
            wall_data['error_response'] = self.create_technical_error_response({}, wall_crtn_intgrty_err)
        else:
            self.log_error_to_db(wall_crtn_intgrty_err)

    def handle_wall_crtn_unknown_error(self, wall_data: Dict[str, Any], wall_crtn_unkwn_err: Exception) -> None:
        self.log_error_to_db(wall_crtn_unkwn_err)
        wall_data['error_response'] = self.create_technical_error_response({}, wall_crtn_unkwn_err)

    def process_wall_profiles(
            self, wall_data: Dict[str, Any], wall: Wall, simulation_type: str,
            wall_redis_data: list[tuple[str, int]]
    ) -> None:
        """
        Manage the different behaviors for wall profiles caching in SEQUENTIAL and CONCURRENT modes.
        """
        cached_wall_profile_hashes = []

        for profile_id, profile_data in wall_data['wall_construction'].wall_profile_data.items():
            wall_profile_config_hash = wall_data['profile_config_hash_data'][profile_id]

            if simulation_type == SEQUENTIAL:
                # Only cache the unique wall profile configs in sequential mode.
                # The build progress of the wall profiles with duplicate configs is
                # always the same.
                if wall_profile_config_hash in cached_wall_profile_hashes:
                    continue
                cached_wall_profile_hashes.append(wall_profile_config_hash)

            # Proceed to create the wall profile
            self.cache_wall_profile(
                wall, wall_data, profile_id, profile_data,
                wall_profile_config_hash, simulation_type, wall_redis_data
            )

    def cache_wall_profile(
            self, wall: Wall, wall_data: Dict[str, Any], profile_id: int, profile_data: Any,
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
        if simulation_type == CONCURRENT:
            wall_profile_creation_kwargs['profile_id'] = profile_id

        # Create the wall profile object
        wall_profile = WallProfile.objects.create(**wall_profile_creation_kwargs)

        # Deferred Redis cache
        wall_redis_data.append(
            (
                self.get_wall_profile_cache_key(wall_profile_config_hash),
                wall_profile_cost
            )
        )

        # Proceed to create the wall profile progress
        self.cache_wall_profile_progress(
            wall_data, wall_profile, wall_profile_config_hash, profile_id, profile_data, wall_redis_data
        )

    def cache_wall_profile_progress(
            self, wall_data: Dict[str, Any], wall_profile: WallProfile, wall_profile_config_hash: str, profile_id: int,
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
                    self.get_daily_ice_usage_cache_key(wall_data, wall_profile_config_hash, day_index, profile_id),
                    data['ice_used']
                )
            )

    def commit_deferred_redis_cache(self, wall_data: Dict[str, Any], wall_redis_data: list[tuple[str, Any]]) -> None:
        for redis_cache_key, redis_cache_value in wall_redis_data:
            self.set_redis_cache(wall_data, redis_cache_key, redis_cache_value)

    def set_redis_cache(self, wall_data: Dict[str, Any], redis_cache_key: str, redis_cache_value: Any) -> None:
        """
        Thread-Safe and Distributed Locking, ensuring safety across processes and servers.
        """
        # Establish a Redis connection only once per view
        redis_connection = self.fetch_redis_connection(wall_data)
        
        lock_key = f'lock_{redis_cache_key}'

        try:
            lock = redis_connection.lock(lock_key, blocking=False)
            # If no lock - skip
            # The cache is being created in another process
            if not lock.acquire(blocking=False):
                return

            # Create the cache if the lock is acquired
            cache.set(redis_cache_key, redis_cache_value)
        except (ConnectionError, TimeoutError):
            # The Redis server is down
            # TODO: Add logging?
            pass
    
    def fetch_redis_connection(self, wall_data: Dict[str, Any]) -> Redis:
        if not wall_data.get('redis_connection'):
            redis_connection = get_redis_connection('default')
            wall_data['redis_connection'] = redis_connection
        
        return wall_data['redis_connection']
        
    def create_out_of_range_response(self, out_of_range_type: str, max_value: int | Any, status_code: int) -> Response:
        if out_of_range_type == 'day':
            finishing_msg = f'The wall has been finished for {max_value} days.'
        else:
            finishing_msg = f'The wall has {max_value} profiles.'
        response_details = {'error': f'The {out_of_range_type} is out of range. {finishing_msg}'}
        return Response(response_details, status=status_code)

    def create_technical_error_response(self, request_data, tech_error: Exception | None = None) -> Response:
        error_details = None
        if tech_error:
            error_details = {'tech_info': f'{tech_error.__class__.__name__}: {str(tech_error)}'}
            if request_data:
                error_details['request_data'] = request_data
        error_msg = 'Wall Construction simulation failed. Please contact support.'
        error_response: Dict[str, Any] = {'error': error_msg}
        if error_details:
            error_response['error_details'] = error_details
        return Response(error_response, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def log_error_to_db(self, error: Exception) -> None:
        pass


class DailyIceUsageView(BaseWallProfileView):

    @extend_schema(
        tags=['daily-ice-usage'],
        summary='Get daily ice usage',
        description='Retrieve the amount of ice used on a specific day for a given wall profile.',
        parameters=daily_ice_usage_parameters + [num_crews_parameter],
        examples=daily_ice_usage_examples,
        responses=daily_ice_usage_responses
    )
    def get(self, request: HttpRequest, profile_id: int, day: int) -> Response:
        num_crews = request.GET.get('num_crews', 0)
        serializer = DailyIceUsageSerializer(data={'profile_id': profile_id, 'day': day, 'num_crews': num_crews})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        profile_id = serializer.validated_data['profile_id']    # type: ignore
        day = serializer.validated_data['day']                  # type: ignore
        num_crews = serializer.validated_data['num_crews']      # type: ignore

        wall_data = self.initialize_wall_data(profile_id, day)
        self.fetch_wall_data(wall_data, num_crews, profile_id, request_type='daily-ice-usage')
        if wall_data['error_response']:
            return wall_data['error_response']

        return self.build_daily_usage_response(wall_data, profile_id, day)

    def build_daily_usage_response(self, wall_data: Dict[str, Any], profile_id: int, day: int) -> Response:
        result_data = wall_data['cached_result']
        if not result_data:
            result_data = wall_data['simulation_result']
        profile_daily_ice_used = result_data['profile_daily_ice_used']
        response_data: Dict[str, Any] = {
            'profile_id': profile_id,
            'day': day,
        }
        if profile_daily_ice_used and isinstance(profile_daily_ice_used, int) and profile_daily_ice_used > 0:
            response_data['ice_used'] = profile_daily_ice_used
            response_data['details'] = f'Volume of ice used for profile {profile_id} on day {day}: {profile_daily_ice_used} cubic yards.'
            return Response(response_data, status=status.HTTP_200_OK)
        
        response_data['details'] = f'No crew has worked on profile {profile_id} on day {day}.'
        return Response(response_data, status=status.HTTP_404_NOT_FOUND)
    

class CostOverviewView(BaseWallProfileView):

    @extend_schema(
        tags=['cost-overview'],
        operation_id='get_cost_overview',
        summary='Get cost overview',
        description='Retrieve the total wall construction cost.',
        parameters=[num_crews_parameter],
        examples=cost_overview_examples,
        responses=cost_overview_responses
    )
    def get(self, request: HttpRequest, profile_id: int | None = None) -> Response:
        num_crews = request.GET.get('num_crews', 0)
        request_data = {'profile_id': profile_id, 'num_crews': num_crews}
        cost_serializer = CostOverviewSerializer(data=request_data)
        if not cost_serializer.is_valid():
            return Response(cost_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        profile_id = cost_serializer.validated_data['profile_id']  # type: ignore
        num_crews = cost_serializer.validated_data['num_crews']  # type: ignore

        request_type = 'costoverview' if not profile_id else 'costoverview/profile_id'

        wall_data = self.initialize_wall_data(profile_id, None)
        self.fetch_wall_data(wall_data, num_crews, profile_id, request_type)
        if wall_data['error_response']:
            return wall_data['error_response']
        
        return self.build_cost_overview_response(wall_data, profile_id)

    def build_cost_overview_response(self, wall_data: Dict[str, Any], profile_id: int | None) -> Response:
        result_data = wall_data['cached_result']
        if not result_data:
            result_data = wall_data['simulation_result']
        if profile_id is None:
            wall_total_cost = result_data['wall_total_cost']
            response_data = {
                'total_cost': f'{wall_total_cost:.0f}',
                'details': f'Total construction cost: {wall_total_cost:.0f} Gold Dragon coins',
            }
        else:
            wall_profile_cost = result_data['wall_profile_cost']
            response_data = {
                'profile_id': profile_id,
                'profile_cost': f'{wall_profile_cost:.0f}',
                'details': f'Profile {profile_id} construction cost: {wall_profile_cost:.0f} Gold Dragon coins',
            }
        return Response(response_data, status=status.HTTP_200_OK)


class CostOverviewProfileidView(CostOverviewView):

    @extend_schema(
        tags=['cost-overview'],
        operation_id='get_cost_overview_profile_id',
        summary='Get cost overview for a profile',
        description='Retrieve the total cost for a specific wall profile.',
        parameters=cost_overview_parameters + [num_crews_parameter],
        examples=cost_overview_profile_id_examples,
        responses=cost_overview_responses
    )
    def get(self, request: HttpRequest, profile_id: int | None = None) -> Response:
        return super().get(request, profile_id)


def custom_404_view(request, exception=None):
    """
    Custom 404 view for the API. Returns a JSON response with an error message
    and a list of available endpoints.
    """
    if request.path.startswith('/api'):
        available_endpoints = [
            endpoint['path'].replace('<', '{').replace('>', '}')
            for endpoint in exposed_endpoints.values()
        ]

        response_data = {
            'error': 'Endpoint not found',
            'error_details': 'The requested API endpoint does not exist. Please use the available endpoints.',
            'available_endpoints': available_endpoints,
        }
        return JsonResponse(response_data, status=404)
    else:
        return page_not_found(request, exception, template_name='404.html')
