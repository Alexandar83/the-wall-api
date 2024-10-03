from inspect import currentframe
from queue import Queue
import threading
from time import sleep

from django.db import connection
from django_redis import get_redis_connection

from the_wall_api.tests.test_utils import BaseTestcase
from the_wall_api.utils.wall_config_utils import (
    generate_config_hash_details, hash_calc, load_wall_profiles_from_config, CONCURRENT
)
from the_wall_api.utils.storage_utils import (
    acquire_db_lock, generate_db_lock_key, get_wall_cache_key, release_db_lock
)


class LockTestBase(BaseTestcase):
    def setUp(self):
        wall_config = load_wall_profiles_from_config()
        wall_config_hash = hash_calc(wall_config)
        wall_config_hash_details = generate_config_hash_details(wall_config)
        self.wall_data = {
            'wall_config_hash': wall_config_hash,
            'num_crews': 2,
            'profile_config_hash_data': wall_config_hash_details.get('profile_config_hash_data', ''),
            'profile_id': 1,
            'day': 2,
            'sim_calc_details': {'total_cost': 10000, 'construction_days': 10},
            'simulation_type': CONCURRENT,
        }
        self.sleep_time = 3

    def put_lock_acquired_in_result_queue(self, result_queue: Queue | None, lock_acquired: bool) -> None:
        if result_queue is not None:
            result_queue.put(lock_acquired)

    def run_lock_test(self, try_to_acquire_lock_func, lock_key):
        """Run concurrent locking tests."""
        result_queue = Queue()
        t1 = threading.Thread(target=try_to_acquire_lock_func, args=(lock_key, result_queue))
        t1.start()
        sleep(2)  # Ensure the first thread acquires the lock

        # Try to acquire lock in the main thread (should fail)
        main_thread_lock_acquired = try_to_acquire_lock_func(lock_key)
        t1.join()

        return result_queue.get(), main_thread_lock_acquired


class AdvisoryLockTest(LockTestBase):
    description = 'Advisory Lock Test'

    def try_to_acquire_advisory_lock(self, wall_db_lock_key: list[int], result_queue: Queue | None = None) -> bool:
        db_lock_acquired = None
        try:
            db_lock_acquired = acquire_db_lock(wall_db_lock_key)
            if not db_lock_acquired:
                self.put_lock_acquired_in_result_queue(result_queue, bool(db_lock_acquired))
                return db_lock_acquired
            
            sleep(self.sleep_time)  # Simulate a long operation
        
        finally:
            if db_lock_acquired:
                release_db_lock(wall_db_lock_key)
            # Ensure the connection is closed in the thread,
            # to avoid lingering connections during test DB teardown
            connection.close()

        self.put_lock_acquired_in_result_queue(result_queue, bool(db_lock_acquired))
        return bool(db_lock_acquired)

    def test_db_advisory_lock(self):
        """Test concurrent acquisition of PostgreSQL advisory lock."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore
        wall_db_lock_key = generate_db_lock_key(get_wall_cache_key(self.wall_data))

        thread_1_lock_acquired, main_thread_lock_acquired = self.run_lock_test(self.try_to_acquire_advisory_lock, wall_db_lock_key)

        expected_message = 'Advisory lock is not acquired by a concurrent second request'
        actual_message = expected_message if thread_1_lock_acquired and not main_thread_lock_acquired else 'Advisory lock acquisition error'

        self.log_test_result(
            passed=thread_1_lock_acquired and not main_thread_lock_acquired,
            input_data={'wall_config_hash': self.wall_data['wall_config_hash'], 'num_crews': self.wall_data['num_crews']},
            expected_message=expected_message,
            actual_message=actual_message,
            test_case_source=test_case_source
        )


class RedisLockTest(LockTestBase):
    description = 'Redis Locks Tests'

    def try_to_acquire_redis_lock(self, redis_cache_key: str, result_queue: Queue | None = None) -> bool:
        redis_connection = get_redis_connection('default')
        lock_key = f'lock_{redis_cache_key}'
        lock = redis_connection.lock(lock_key, blocking=False)

        if not lock.acquire(blocking=False):
            self.put_lock_acquired_in_result_queue(result_queue, False)
            return False
        
        sleep(self.sleep_time)  # Simulate a long operation
        
        lock.release()
        
        self.put_lock_acquired_in_result_queue(result_queue, True)
        return True

    def test_redis_cache_lock(self):
        """Test concurrent acquisition of Redis cache lock."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore
        cache_lock_key = get_wall_cache_key(self.wall_data)

        thread_1_lock_acquired, main_thread_lock_acquired = self.run_lock_test(self.try_to_acquire_redis_lock, cache_lock_key)

        expected_message = 'Redis cache lock is not acquired by a concurrent second request'
        actual_message = expected_message if thread_1_lock_acquired and not main_thread_lock_acquired else 'Redis cache lock acquisition error'

        self.log_test_result(
            passed=thread_1_lock_acquired and not main_thread_lock_acquired,
            input_data={'wall_config_hash': self.wall_data['wall_config_hash'], 'num_crews': self.wall_data['num_crews']},
            expected_message=expected_message,
            actual_message=actual_message,
            test_case_source=test_case_source
        )
