from inspect import currentframe
from time import sleep

from config.celery import app as celery_app
from celery.contrib.testing.worker import start_worker
from celery.result import AsyncResult
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.http import HttpResponse
from django.urls import reverse
from redis import Redis
from rest_framework import status

from the_wall_api.models import WallConfig, Wall, WallConfigStatusEnum, WallProfile, WallProfileProgress
from the_wall_api.tasks import orchestrate_wall_config_processing_task_test, wall_config_deletion_task_test
from the_wall_api.tests.test_utils import BaseTransactionTestcase
from the_wall_api.utils.api_utils import exposed_endpoints
from the_wall_api.utils.storage_utils import get_daily_ice_usage_cache_key, manage_wall_config_object
from the_wall_api.utils.wall_config_utils import CONCURRENT, hash_calc, load_wall_profiles_from_config
from the_wall_api.wall_construction import get_sections_count, manage_num_crews

MAX_WALL_PROFILE_SECTIONS = settings.MAX_WALL_PROFILE_SECTIONS
MAX_SECTION_HEIGHT = settings.MAX_SECTION_HEIGHT


class OrchestrateWallConfigTaskTest(BaseTransactionTestcase):
    description = 'Wall Config Processing and Deletion Tasks Tests'

    @classmethod
    def setUpClass(cls):
        cls.test_queue_name = 'test_queue'
        cls.orchstrt_wall_config_task_success_msg = 'Wall config processed successfully.'
        cls.deletion_task_success_msg = 'Wall config deleted successfully.'
        cls.deletion_task_fail_msg = 'Wall config deletion failure.'
        cls.worker_count = 8
        cls.setup_celery_worker()
        super().setUpClass()

    @classmethod
    def setup_celery_worker(cls) -> None:
        # Flush the test queue from any stale tasks
        cls.redis_client = Redis.from_url(settings.CELERY_BROKER_URL)
        cls.redis_client.ltrim(cls.test_queue_name, 1, 0)

        # Start the celery workers and instruct them to listen to 'test_queue'
        if settings.PROJECT_MODE == 'dev':
            pool = 'solo'                   # 'prefork' is not supported in dev (on Windows); Avoid 'gevent' dependency - not justified
            concurrency = 1
            logfile = 'nul'                 # Discard Celery console logs - Windows
            worker_count = cls.worker_count
        else:
            pool = 'prefork'                # 'prefork' is well suited for the containerized app
            concurrency = cls.worker_count
            logfile = '/dev/null'           # Discard Celery console logs - Unix
            worker_count = 1
        cls.workers = [
            start_worker(
                celery_app, queues=[cls.test_queue_name], concurrency=concurrency,
                pool=pool, perform_ping_check=False, logfile=logfile
            ) for _ in range(worker_count)
        ]
        for worker in cls.workers:
            worker.__enter__()

    @classmethod
    def tearDownClass(cls):
        # Flush the test queue
        cls.redis_client.ltrim(cls.test_queue_name, 1, 0)
        # Stop the celery workers
        for worker in cls.workers:
            worker.__exit__(None, None, None)
        super().tearDownClass()

    def setUp(self):
        self.wall_construction_config = load_wall_profiles_from_config()
        self.wall_config_hash = hash_calc(self.wall_construction_config)
        self.wall_profile_config_hash_data = {
            i: hash_calc(profile) for i, profile in enumerate(self.wall_construction_config, start=1)
        }
        self.sections_count = get_sections_count(self.wall_construction_config)
        self.input_data = {
            'wall_config_hash': self.wall_config_hash,
            'sections_count': self.sections_count
        }
        self.wall_config_object = manage_wall_config_object({
            'wall_config_hash': self.wall_config_hash,
            'wall_construction_config': self.wall_construction_config
        })
        self.active_testing = True

    def process_tasks(
            self, test_case_source: str, deletion: str | None = None,
            normal_request_num_crews: int | None = None
    ) -> tuple[str, list]:
        """
        Send the wall config processing task to the celery worker alone or
        along with the deletion task.
        """
        actual_result = []
        if isinstance(self.wall_config_object, WallConfig):
            wall_config_orchestration_result, deletion_result = self.send_celery_tasks(deletion)
            normal_request_result = self.process_normal_request(normal_request_num_crews)
            actual_message, actual_result = self.get_results(
                wall_config_orchestration_result, normal_request_result, deletion, deletion_result, test_case_source
            )
        else:
            actual_message = self.wall_config_object

        return actual_message, actual_result

    def send_celery_tasks(self, deletion: str | None) -> tuple[AsyncResult, AsyncResult | None]:
        wall_config_orchestration_result = orchestrate_wall_config_processing_task_test.delay(
            wall_config_hash=self.wall_config_hash,
            wall_construction_config=self.wall_construction_config,
            sections_count=self.sections_count,
            active_testing=self.active_testing
        )    # type: ignore

        deletion_result = None
        if deletion:
            if deletion == 'sequential':
                # Simulate that the deletion occurs after the whole wall config is processed
                wall_config_orchestration_result.get()
            if deletion == 'concurrent':
                # Ensure the orchestration task has time to start
                sleep(0.01)
            deletion_result = wall_config_deletion_task_test.delay(
                wall_config_hash=self.wall_config_hash
            )    # type: ignore

        return wall_config_orchestration_result, deletion_result

    def process_normal_request(self, normal_request_num_crews: int | None) -> str | None:
        if not normal_request_num_crews:
            return None

        day = 1
        profile_id = 1

        if normal_request_num_crews == 1:
            sleep(5)

        wall_exists = Wall.objects.filter(wall_config_hash=self.wall_config_hash, num_crews=normal_request_num_crews).exists()

        if normal_request_num_crews == 1 and not wall_exists:
            return 'Wall not created from the orchestration task yet!'

        if normal_request_num_crews > 1 and wall_exists:
            return 'Wall should not be created from the orchestration task befre the normal GET request!'

        redis_daily_ice_usage_cache, daily_ice_usage_cache_key = self.get_redis_cache_details(normal_request_num_crews, profile_id, day)
        if redis_daily_ice_usage_cache:
            return 'Wall Redis cache should not exist before the normal GET request!'

        response = self.fetch_response(profile_id, day, normal_request_num_crews)
        if response.status_code != status.HTTP_200_OK:
            return f'Unexpected normal GET request response code: {response.status_code}!'

        redis_daily_ice_usage_cache = cache.get(daily_ice_usage_cache_key)
        if redis_daily_ice_usage_cache is None:
            return 'Wall Redis cache should exist after the normal GET request!'

        return 'OK'

    def get_redis_cache_details(self, normal_request_num_crews: int, profile_id: int, day: int) -> tuple[str, str]:
        wall_data = {
            'wall_config_hash': self.wall_config_hash,
            'num_crews': normal_request_num_crews,
            'request_type': 'create_wall_task',
            'simulation_type': CONCURRENT
        }
        daily_ice_usage_cache_key = get_daily_ice_usage_cache_key(
            wall_data, self.wall_profile_config_hash_data[profile_id], day, profile_id
        )
        redis_daily_ice_usage_cache = cache.get(daily_ice_usage_cache_key)

        return redis_daily_ice_usage_cache, daily_ice_usage_cache_key

    def fetch_response(self, profile_id: int, day: int, normal_request_num_crews: int) -> HttpResponse:
        url_name = exposed_endpoints['daily-ice-usage']['name']
        url = reverse(url_name, kwargs={'profile_id': profile_id, 'day': day})
        params = {'num_crews': normal_request_num_crews}
        response = self.client.get(url, params)

        return response

    def get_results(
        self, wall_config_orchestration_result: AsyncResult, normal_request_result: str | None, deletion: str | None,
        deletion_result: AsyncResult | None, test_case_source: str
    ) -> tuple[str, list]:
        """Extract the results from the celery tasks, according to the test case"""
        actual_result = []
        try:
            wall_config_orchestration_result.get()
            if deletion_result:
                deletion_result.get()
        except TimeoutError:
            return f'{test_case_source} timed out', actual_result

        if not deletion:
            if normal_request_result and normal_request_result != 'OK':
                return normal_request_result, []
            actual_message, actual_result = wall_config_orchestration_result.result
        elif deletion_result:
            actual_deletion_message, actual_result = deletion_result.result
            actual_message = self.check_abort_signal_processed(actual_deletion_message, wall_config_orchestration_result, deletion)
        else:
            actual_message = self.deletion_task_fail_msg

        return actual_message, actual_result

    def check_abort_signal_processed(
        self, actual_deletion_message: str, wall_config_orchestration_result: AsyncResult, deletion: str
    ) -> str:
        if actual_deletion_message != 'OK':
            return actual_deletion_message

        actual_message, actual_result = wall_config_orchestration_result.result
        if deletion == 'sequential' and actual_message != 'OK':
            return actual_message
        if deletion == 'concurrent':
            if actual_message != 'Interrupted by a deletion task':
                return actual_message
            if {} not in actual_result:
                return 'Abort signal not processed!'

        return 'OK'

    def evaluate_tasks_result(self, task_results: list, deletion: str | None = None) -> str:
        if deletion:
            return self.evaluate_deletion()

        # Check if the processing of the wall config was successful
        if not isinstance(self.wall_config_object, WallConfig):
            return self.wall_config_object
        self.wall_config_object.refresh_from_db()
        if self.wall_config_object.status != WallConfigStatusEnum.COMPLETED:
            return 'Wall config processing failed.'

        for task_result in task_results:
            if task_result['sim_calc_details'] == 'cached_result':
                # A simultaneous normal API request has created the cache
                continue
            # Check if the wall is in the DB
            wall = self.evaluate_wall_result(task_result)
            if not isinstance(wall, Wall):
                return 'Wall not found.'
            # Check if all profiles are in the DB
            wall_profiles_evaluation_message = self.evaluate_wall_profiles(task_result, wall)
            if wall_profiles_evaluation_message != 'OK':
                return wall_profiles_evaluation_message

        return self.orchstrt_wall_config_task_success_msg

    def evaluate_deletion(self) -> str:
        if not WallConfig.objects.filter(wall_config_hash=self.wall_config_hash).exists():
            return self.deletion_task_success_msg
        else:
            return self.deletion_task_fail_msg

    def evaluate_wall_result(self, task_result: dict) -> Wall | None:
        try:
            wall = Wall.objects.get(
                wall_config=self.wall_config_object,
                wall_config_hash=self.wall_config_hash,
                num_crews=task_result['num_crews'],
                total_cost=task_result['sim_calc_details']['total_cost'],
                construction_days=task_result['sim_calc_details']['construction_days'],
            )
            return wall
        except Wall.DoesNotExist:
            return None

    def evaluate_wall_profiles(self, task_result: dict, wall: Wall) -> str:
        for profile_id, profile_data in task_result['sim_calc_details']['profile_daily_details'].items():
            wall_profile_config_hash = task_result['profile_config_hash_data'][profile_id]
            wall_profile_cost = task_result['sim_calc_details']['profile_costs'][profile_id]
            simulation_type, _ = manage_num_crews(task_result['num_crews'], self.sections_count)

            wall_profile_query = Q(
                wall=wall,
                wall_profile_config_hash=wall_profile_config_hash,
                cost=wall_profile_cost,
            )
            if simulation_type == CONCURRENT:
                wall_profile_query &= Q(profile_id=profile_id)

            try:
                wall_profile = WallProfile.objects.get(wall_profile_query)
            except WallProfile.DoesNotExist:
                return f'Wall profile id({profile_id}) not found: num_crews={task_result["num_crews"]}'
            else:
                progress_evaluation_result = self.evaluate_wall_profile_progress(
                    profile_data, wall_profile, task_result['num_crews']
                )
                if progress_evaluation_result != 'OK':
                    return progress_evaluation_result

        return 'OK'

    def evaluate_wall_profile_progress(
        self, profile_data: dict, wall_profile: WallProfile, num_crews: int
    ) -> str:
        for day_index, data in profile_data.items():
            try:
                WallProfileProgress.objects.get(
                    wall_profile=wall_profile,
                    day=day_index,
                    ice_used=data['ice_used'],
                )
            except WallProfileProgress.DoesNotExist:
                return (
                    f'Wall profile progress for profile id({wall_profile.profile_id}) - '
                    f'day({day_index}) - num_crews={num_crews} not found.'
                )
        return 'OK'

    def send_multiple_deletion_tasks(self, test_case_source) -> tuple[str, str]:
        deletion_result_1 = wall_config_deletion_task_test.delay(
            wall_config_hash=self.wall_config_hash,
            active_testing=self.active_testing
        )    # type: ignore

        deletion_result_2 = wall_config_deletion_task_test.delay(
            wall_config_hash=self.wall_config_hash,
            active_testing=self.active_testing
        )    # type: ignore

        try:
            deletion_result_1.get()
            deletion_result_2.get()
        except TimeoutError:
            actual_message_1 = actual_message_2 = f'{test_case_source} timed out'
        else:
            actual_message_1, _ = deletion_result_1.result
            actual_message_2, _ = deletion_result_2.result

        return actual_message_1, actual_message_2

    def check_deletion_tasks_results(
        self, actual_message_1: str, actual_message_2: str, expected_message: str
    ) -> tuple[bool, str]:
        """One of the task should return a 'Deletion already initaiated' result"""
        expected_condition_met = (
            (actual_message_1 == 'OK' and actual_message_2 == expected_message) or
            (actual_message_2 == 'OK' and actual_message_1 == expected_message)
        )
        wall_config_absent = not WallConfig.objects.filter(wall_config_hash=self.wall_config_hash).exists()

        # Condition passes if expected condition is met and wall config does not exist
        if expected_condition_met and wall_config_absent:
            return True, expected_message

        # Condition failed, determine the appropriate failure message
        if actual_message_1 != 'OK':
            return False, actual_message_1
        elif actual_message_2 != 'OK':
            return False, actual_message_2

        # Default failure message
        return False, self.deletion_task_fail_msg

    def test_orchestrate_wall_config_processing_task(self, deletion: str | None = None, test_case_source: str = ''):
        if not deletion:
            test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore
            expected_message = self.orchstrt_wall_config_task_success_msg
        else:
            expected_message = self.deletion_task_success_msg

        task_result_message, task_results = self.process_tasks(test_case_source, deletion=deletion)
        common_result_kwargs = {
            'input_data': self.input_data,
            'expected_message': expected_message,
            'test_case_source': test_case_source
        }

        if task_result_message != 'OK':
            self.log_test_result(passed=False, actual_message=task_result_message, **common_result_kwargs)
            return

        actual_message = self.evaluate_tasks_result(task_results, deletion)

        passed = actual_message == expected_message
        self.log_test_result(passed=passed, actual_message=actual_message, **common_result_kwargs)

    def test_wall_config_deletion_task_concurrent(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore
        self.test_orchestrate_wall_config_processing_task(deletion='concurrent', test_case_source=test_case_source)

    def test_wall_config_deletion_task_sequential(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore
        self.test_orchestrate_wall_config_processing_task(deletion='sequential', test_case_source=test_case_source)

    def test_simultaneous_wall_config_deletion_tasks(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore
        expected_message = 'Deletion already initiated by another process.'
        actual_message_1, actual_message_2 = self.send_multiple_deletion_tasks(test_case_source)
        passed, actual_message_final = self.check_deletion_tasks_results(actual_message_1, actual_message_2, expected_message)
        self.log_test_result(
            passed=passed,
            input_data=self.input_data,
            expected_message=expected_message,
            actual_message=actual_message_final,
            test_case_source=test_case_source
        )

    def test_simultaneous_orchestration_task_and_normal_request(
        self, normal_request_num_crews: int | None = None, test_case_source: str = ''
    ):
        if not normal_request_num_crews:
            normal_request_num_crews = 1
        if not test_case_source:
            test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore
        task_result_message, task_results = self.process_tasks(
            test_case_source, normal_request_num_crews=normal_request_num_crews
        )
        expected_message = self.orchstrt_wall_config_task_success_msg
        common_result_kwargs = {
            'input_data': self.input_data,
            'expected_message': expected_message,
            'test_case_source': test_case_source
        }

        if task_result_message != 'OK':
            self.log_test_result(passed=False, actual_message=task_result_message, **common_result_kwargs)
            return

        actual_message = self.evaluate_tasks_result(task_results, deletion=None)

        passed = actual_message == expected_message
        self.log_test_result(passed=passed, actual_message=actual_message, **common_result_kwargs)

    def test_simultaneous_orchestration_task_and_late_normal_request(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore
        normal_request_num_crews = self.sections_count - 1
        self.test_simultaneous_orchestration_task_and_normal_request(normal_request_num_crews, test_case_source)
