from copy import copy
from inspect import currentframe
from typing import Callable

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

        # Construction simulation
        run_simulation(self.wall_data)

        # Attempt to get/create the wall config object
        wall_config_object = storage_utils.manage_wall_config_object(self.wall_data)
        if isinstance(wall_config_object, WallConfig):
            # Successful creation/fetch of the wall config object
            self.wall_data['wall_config_object'] = wall_config_object
        else:
            # Either being initialized by another process
            # or an error occurred during the creation
            return

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

    def _assert_wall_cache_consistency(self) -> None:
        """
        Check the consistency of the total wall cost between simulation, Redis, and DB.
        """
        # Wall
        total_cost_sim = self.wall_data['sim_calc_details']['total_cost']

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
        self._assert_profile_cache_consistency()

    def _assert_profile_cache_consistency(self) -> None:
        """
        Check the consistency of profile costs between simulation, Redis, and DB.
        """
        # Profiles
        for profile_id in range(1, len(self.wall_construction_config) + 1):
            profile_cost_sim = self.wall_data['sim_calc_details']['profile_costs'][profile_id]
            wall_profile_config_hash = self.wall_data['profile_config_hash_data'][profile_id]

            # Redis cache value
            cached_wall_profile_cost, wall_profile_redis_cache_key = (
                storage_utils.fetch_wall_profile_cost_from_redis_cache(wall_profile_config_hash)
            )
            if self.redis_cache_status != 'evicted':
                self.assertEqual(profile_cost_sim, cached_wall_profile_cost)

            # DB value
            if self.redis_cache_status != 'restored':
                profile_cost_db = {}
                storage_utils.fetch_wall_profile_cost_from_db(wall_profile_config_hash, profile_cost_db, wall_profile_redis_cache_key)
                self.assertEqual(profile_cost_sim, profile_cost_db['wall_profile_cost'])

            # Daily ice usage
            if not self.concurrency_switched:
                self._assert_daily_ice_usage_cache(profile_id, wall_profile_config_hash)

    def _assert_daily_ice_usage_cache(self, profile_id: int, wall_profile_config_hash: str) -> None:
        """
        Check the consistency of daily ice usage between simulation, Redis, and DB.
        """
        # Daily ice usage
        for day_index, data in self.wall_data['wall_construction'].wall_profile_data[profile_id].items():
            ice_used_sim = data['ice_used']

            # Redis cache value
            wall_data_progress_day = copy(self.wall_data)
            wall_data_progress_day['request_day'] = day_index
            cached_profile_ice_usage, profile_ice_usage_redis_cache_key = (
                storage_utils.fetch_daily_ice_usage_from_redis_cache(wall_data_progress_day, wall_profile_config_hash, profile_id)
            )
            if self.redis_cache_status != 'evicted':
                self.assertEqual(ice_used_sim, cached_profile_ice_usage)

            # DB value
            if self.redis_cache_status != 'restored':
                profile_ice_usage_db = {}
                storage_utils.fetch_daily_ice_usage_from_db(
                    wall_data_progress_day, wall_profile_config_hash, profile_id, profile_ice_usage_db, profile_ice_usage_redis_cache_key
                )
                self.assertEqual(ice_used_sim, profile_ice_usage_db['profile_daily_ice_used'])


class DailyIceUsageCacheTest(CacheTest):
    description = 'Test daily ice usage cache'

    cache_types_msg = 'wall cost and profile cost'

    def setUp(self):
        super().setUp()
        self.request_type = 'daily-ice-usage'
        self.profile_id = 1
        self.day = 2

    def get_expected_message(self, msg_type: str, add_daily_ice_usage: bool = False) -> str:
        if msg_type == 'missing_data':
            if not add_daily_ice_usage:
                msg_out = self.cache_types_msg
            else:
                msg_out = self.cache_types_msg.replace(' and', ', ') + ', and daily ice usage'
            return f'Simulation results for {msg_out} match the cached and DB data'
        elif msg_type == 'cache_eviction_1':
            return 'All data is cached in the DB'
        elif msg_type == 'cache_eviction_2':
            return 'All data is restored in the Redis cache'

        return ''

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
            self.execute_test_case(self._assert_wall_cache_consistency, test_case_source, expected_message)

        # Concurrent second request
        self.setUp()
        self.concurrency_switched = True
        with self.subTest(num_crews=3):
            self.initialize_test_data(num_crews=3, skip_cache_wall=True)
            expected_message = self.get_expected_message('missing_data')
            self.execute_test_case(self._assert_wall_cache_consistency, test_case_source, expected_message)

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
            self.execute_test_case(self._assert_wall_cache_consistency, test_case_source, expected_message)

        # Sequential second request
        self.setUp()
        self.concurrency_switched = True
        with self.subTest(num_crews=0):
            self.initialize_test_data(num_crews=0, skip_cache_wall=True)
            expected_message = self.get_expected_message('missing_data')
            self.execute_test_case(self._assert_wall_cache_consistency, test_case_source, expected_message)

    @BaseTransactionTestcase.cache_clear
    def test_fetch_db_data_evicted_from_cache(self):
        """
        Simulate cache eviction from Redis and refresh from DB.
        """
        num_crews = 0

        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        # Create and commit the test data to the DB and Redis cache
        # and then simulate cache eviction
        self.initialize_test_data(num_crews=num_crews, cache_eviction=True)

        # Fetch the data from the DB to restore it in Redis
        with self.subTest(redis_cache_status='evicted'):
            expected_message = self.get_expected_message('cache_eviction_1')
            self.execute_test_case(self._assert_wall_cache_consistency, test_case_source, expected_message)
            # The Redis cache is restored from the DB
            self.redis_cache_status = 'restored'

        # Check the data is restored in Redis
        with self.subTest(redis_cache_status='restored'):
            expected_message = self.get_expected_message('cache_eviction_2')
            self.execute_test_case(self._assert_wall_cache_consistency, test_case_source, expected_message)


class CostOverviewProfileidCacheTest(DailyIceUsageCacheTest):
    description = 'Test cost overview profile_id cache'

    def setUp(self):
        super().setUp()
        self.request_type = 'costoverview/profile_id'
        self.profile_id = 1
        self.day = None


class CostOverviewCacheTest(DailyIceUsageCacheTest):
    description = 'Test cost overview cache'

    def setUp(self):
        super().setUp()
        self.request_type = 'costoverview'
        self.profile_id = None
        self.day = None
