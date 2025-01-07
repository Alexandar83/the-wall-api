from copy import copy
from inspect import currentframe
from typing import Callable

from django.conf import settings
from django.core.cache import cache

from the_wall_api.models import WallConfig
from the_wall_api.utils import storage_utils
from the_wall_api.tests.test_utils import BaseTransactionTestcase
from the_wall_api.wall_construction import initialize_wall_data, set_simulation_params, run_simulation


class CacheTest(BaseTransactionTestcase):

    def setUp(self):
        self.profile_id = None
        self.day = None
        self.num_crews = None
        self.wall_data = {}
        self.request_type = ''
        self.concurrency_switched = False
        self.redis_cache_status = None

    def initialize_test_data(self, num_crews: int = 0, skip_cache_wall: bool = False, cache_eviction: bool = False) -> None:
        # Request params
        self.num_crews = num_crews

        # Wall params
        self.wall_data = initialize_wall_data(profile_id=self.profile_id, day=self.day, request_num_crews=self.num_crews)
        set_simulation_params(self.wall_data, self.num_crews, self.wall_construction_config, self.request_type)

        # Attempt to get/create the wall config object
        wall_config_object = storage_utils.manage_wall_config_object(self.wall_data)

        if (
            # sections_count > MAX_SECTIONS_COUNT_SYNCHRONOUS_RESPONSE
            # -sent for async processing
            self.wall_data.get('info_response') or
            # Obsolete?
            self.wall_data['error_response']
        ):
            return

        if isinstance(wall_config_object, WallConfig):
            # Successful creation/fetch of the wall config object
            self.wall_data['wall_config_object'] = wall_config_object
        else:
            # Either being initialized by another process
            # or an error occurred during the creation
            return

        # Construction simulation
        run_simulation(self.wall_data)

        if not skip_cache_wall:
            # Commit test data
            storage_utils.cache_wall(self.wall_data)

        # Simulate cache eviction
        if cache_eviction:
            cache.clear()
            self.redis_cache_status = 'evicted'

    def execute_test_case(self, test_func: Callable, test_case_source: str, expected_message: str = '') -> None:
        """
        Centralized error handling for test execution.
        """
        input_data = {
            'profile_id': self.profile_id,
            'day': self.day,
            'num_crews': self.num_crews
        }
        try:
            test_func()
            self.log_test_result(
                passed=True,
                input_data=input_data,
                expected_message=expected_message,
                actual_message=expected_message,
                test_case_source=test_case_source
            )
        except AssertionError as assrtn_err:
            self.log_test_result(
                passed=False,
                input_data=input_data,
                expected_message=expected_message,
                actual_message=f'{assrtn_err.__class__.__name__}: {str(assrtn_err)}',
                test_case_source=test_case_source
            )
        except Exception as unkwn_err:
            self.log_test_result(
                passed=False,
                input_data=input_data,
                expected_message=expected_message,
                actual_message=f'{unkwn_err.__class__.__name__}: {str(unkwn_err)}',
                test_case_source=test_case_source,
                error_occurred=True
            )

    def assert_wall_cache_consistency(self) -> None:
        """
        Check the consistency of the total wall cost between simulation, Redis, and DB.
        """
        # Wall
        total_ice_amount_sim = self.wall_data['wall_construction'].wall_profile_data['profiles_overview']['total_ice_amount']
        total_cost_sim = total_ice_amount_sim * settings.ICE_COST_PER_CUBIC_YARD

        # Redis cache value
        wall_cost_redis_cache, wall_redis_key = storage_utils.fetch_wall_cost_from_redis_cache(self.wall_data)
        if self.redis_cache_status != 'evicted':
            self.assertEqual(total_cost_sim, wall_cost_redis_cache)

        # DB value
        if self.redis_cache_status != 'restored':
            wall_cost_db = {}
            storage_utils.fetch_wall_cost_from_db(self.wall_data, wall_cost_db, wall_redis_key)
            self.assertEqual(total_cost_sim, wall_cost_db['wall_total_cost'])

        # Profiles
        if not self.concurrency_switched:
            self.assert_wall_progress_cache_consistency()

    def assert_wall_progress_cache_consistency(self) -> None:
        """
        Check the consistency of profiles costs between simulation, Redis, and DB.
        """
        daily_details = self.wall_data['wall_construction'].wall_profile_data['profiles_overview']['daily_details']

        for day, ice_amount_data in daily_details.items():
            for profile_key, ice_amount in ice_amount_data.items():
                calculated_cost = ice_amount * settings.ICE_COST_PER_CUBIC_YARD
                redis_cache_key = self.check_redis_cache(day, profile_key, calculated_cost)

                if self.redis_cache_status != 'restored':
                    self.check_db_cache(day, profile_key, calculated_cost, redis_cache_key)

    def check_redis_cache(self, day: int, profile_key: str | int, calculated_cost: int) -> str:
        wall_data_copy = copy(self.wall_data)
        wall_data_copy['request_day'] = day

        if isinstance(profile_key, int):
            # Cache for 'profiles-days'
            cached_ice_amount, redis_cache_key = storage_utils.fetch_profile_day_ice_amount_from_redis_cache(
                wall_data_copy, profile_key
            )
            # Transform into cache for 'single-profile-overview-day'
            if cached_ice_amount is not None:
                cached_cost = cached_ice_amount * settings.ICE_COST_PER_CUBIC_YARD
            else:
                cached_cost = None
        else:
            # Cache for 'profiles-overview-day'
            cached_cost, redis_cache_key = storage_utils.fetch_profiles_overview_day_cost_from_redis_cache(
                wall_data_copy
            )

        if self.redis_cache_status != 'evicted':
            self.assertEqual(calculated_cost, cached_cost)

        return redis_cache_key

    def check_db_cache(self, day: int, profile_key: str | int, calculated_cost: int, redis_cache_key: str) -> None:
        ice_amount_db_dict = {}

        wall_data_copy = copy(self.wall_data)
        wall_data_copy['request_day'] = day
        if isinstance(profile_key, int):
            # DB value for 'profiles-days'
            storage_utils.fetch_profile_day_ice_amount_from_db(
                wall_data_copy, profile_key, ice_amount_db_dict, redis_cache_key
            )
            ice_amount_db = ice_amount_db_dict.get('profile_day_ice_amount')
            cost_db = ice_amount_db * settings.ICE_COST_PER_CUBIC_YARD if ice_amount_db is not None else None
        else:
            # DB value for 'profiles-overview-day'
            storage_utils.fetch_profiles_overview_day_cost_from_db(
                wall_data_copy, ice_amount_db_dict, redis_cache_key
            )
            cost_db = ice_amount_db_dict.get('profiles_overview_day_cost')

        self.assertEqual(calculated_cost, cost_db)


class ProfilesCacheTestBase(CacheTest):
    cache_types_msg = 'profiles overview'

    def setUp(self):
        super().setUp()
        self.request_type = 'profiles-days'
        self.profile_id = 1
        self.day = 2

    def get_expected_message(self, msg_type: str, add_daily_ice_usage: bool = False) -> str:
        if msg_type == 'missing_data':
            if not add_daily_ice_usage:
                msg_out = self.cache_types_msg
            else:
                msg_out = self.cache_types_msg.replace(' and', ', ') + ' and profiles days'
            return f'Simulation results for {msg_out} match the cached and DB data'
        elif msg_type == 'cache_eviction_1':
            return 'All data is cached in the DB'
        elif msg_type == 'cache_eviction_2':
            return 'All data is restored in the Redis cache'

        return ''

    @BaseTransactionTestcase.cache_clear
    def process_fetch_db_data_evicted_from_cache(self, test_case_source: str) -> None:
        """
        Simulate cache eviction from Redis and refresh from DB.
        """
        # Create and commit the test data to the DB and Redis cache
        # and then simulate cache eviction
        self.initialize_test_data(num_crews=0, cache_eviction=True)

        # Fetch the data from the DB to restore it in Redis
        with self.subTest(redis_cache_status='evicted'):
            expected_message = self.get_expected_message('cache_eviction_1')
            self.execute_test_case(self.assert_wall_cache_consistency, test_case_source, expected_message)
            # The Redis cache is restored from the DB
            self.redis_cache_status = 'restored'

        # Check the data is restored in Redis
        with self.subTest(redis_cache_status='restored'):
            expected_message = self.get_expected_message('cache_eviction_2')
            self.execute_test_case(self.assert_wall_cache_consistency, test_case_source, expected_message)


class ProfilesDaysCacheTest(ProfilesCacheTestBase):
    description = 'Test Profiles Days Cache'

    def test_fetch_db_data_evicted_from_cache(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        self.process_fetch_db_data_evicted_from_cache(test_case_source)

    @BaseTransactionTestcase.cache_clear
    def test_fetch_missing_data_sequential(self):
        """
        Sequential first request - assert all types of cache.
        Concurrent second request - skip wall cache creation.
        Check only wall and profile cache, because they store the same
        data for SEQUENTIAL and CONCURRENT requests.
        """
        num_crews = 0

        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        # Sequential first request
        with self.subTest(num_crews=num_crews):
            self.initialize_test_data(num_crews=num_crews)
            expected_message = self.get_expected_message('missing_data', add_daily_ice_usage=True)
            self.execute_test_case(self.assert_wall_cache_consistency, test_case_source, expected_message)

        # Concurrent second request
        self.setUp()
        self.concurrency_switched = True
        with self.subTest(num_crews=3):
            self.initialize_test_data(num_crews=3, skip_cache_wall=True)
            expected_message = self.get_expected_message('missing_data')
            self.execute_test_case(self.assert_wall_cache_consistency, test_case_source, expected_message)

    @BaseTransactionTestcase.cache_clear
    def test_fetch_missing_data_concurrent(self):
        """
        Concurrent first request - assert all types of cache.
        Sequential second request - skip wall cache creation.
        Check only wall and profile cache, because they store the same
        data for SEQUENTIAL and CONCURRENT requests.
        """
        num_crews = 3

        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        # Concurrent first request
        with self.subTest(num_crews=num_crews):
            self.initialize_test_data(num_crews=num_crews)
            expected_message = self.get_expected_message('missing_data', add_daily_ice_usage=True)
            self.execute_test_case(self.assert_wall_cache_consistency, test_case_source, expected_message)

        # Sequential second request
        self.setUp()
        self.concurrency_switched = True
        with self.subTest(num_crews=0):
            self.initialize_test_data(num_crews=0, skip_cache_wall=True)
            expected_message = self.get_expected_message('missing_data')
            self.execute_test_case(self.assert_wall_cache_consistency, test_case_source, expected_message)


class ProfilesOverviewCacheTest(ProfilesCacheTestBase):
    description = 'Test profiles overview cache'

    def setUp(self):
        super().setUp()
        self.request_type = 'profiles-overview'
        self.profile_id = None
        self.day = None

    def test_fetch_db_data_evicted_from_cache(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        self.process_fetch_db_data_evicted_from_cache(test_case_source)

    def test_fetch_db_data_evicted_from_cache_day(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        self.request_type = 'profiles-overview-day'
        self.day = 1

        self.process_fetch_db_data_evicted_from_cache(test_case_source)

    def test_fetch_db_data_evicted_from_cache_single_profile_day(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        self.request_type = 'single-profile-overview-day'
        self.day = 1

        self.process_fetch_db_data_evicted_from_cache(test_case_source)
