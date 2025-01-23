from inspect import currentframe
import os
from time import sleep

from config.celery import app as celery_app
from celery.contrib.testing.worker import start_worker
from celery.result import AsyncResult
from django.conf import settings
from django.urls import reverse
from redis import Redis

from the_wall_api.models import (
    Wall, WallConfig, WallConfigReference, WallConfigStatusEnum, WallProgress
)
from the_wall_api.tasks import (
    delete_unused_wall_configs_task_test, orchestrate_wall_config_processing_task_test,
    wall_config_deletion_task_test
)
from the_wall_api.tests.test_utils import BaseTransactionTestcase
from the_wall_api.utils.api_utils import exposed_endpoints
from the_wall_api.utils.message_themes import (
    base as base_messages, errors as error_messages
)
from the_wall_api.utils.storage_utils import manage_wall_config_object
from the_wall_api.utils.wall_config_utils import hash_calc
from the_wall_api.wall_construction import get_sections_count

CONCURRENT_SIMULATION_MODE = settings.CONCURRENT_SIMULATION_MODE
CELERY_TASK_PRIORITY = settings.CELERY_TASK_PRIORITY
MAX_SECTION_HEIGHT = settings.MAX_SECTION_HEIGHT
PROJECT_MODE = settings.PROJECT_MODE


class ConcurrentCeleryTasksTestBase(BaseTransactionTestcase):

    @classmethod
    def setUpClass(cls):
        cls.test_queue_name = 'test_queue'
        cls.orchstrt_wall_config_task_success_msg = 'Wall config processed successfully.'
        cls.deletion_task_success_msg = 'Wall config deleted successfully.'
        cls.deletion_task_fail_msg = 'Wall config deletion failure.'
        if 'multiprocessing' not in CONCURRENT_SIMULATION_MODE:
            cls.concurrency = 8
        else:
            cls.concurrency = 4
        cls.setup_celery_workers()
        super().setUpClass()

    @classmethod
    def setup_celery_workers(cls) -> None:
        # Flush the test queue from any stale tasks
        cls.redis_client = Redis.from_url(settings.CELERY_BROKER_URL)
        cls.redis_client.delete(cls.test_queue_name)
        scheduled_tasks = cls.redis_client.keys(pattern=f'{cls.test_queue_name}*')
        for task in scheduled_tasks:    # type: ignore
            cls.redis_client.delete(task)

        # Start the celery workers and instruct them to listen to 'test_queue'
        if 'multiprocessing' in CONCURRENT_SIMULATION_MODE or PROJECT_MODE == 'dev':
            pool = 'threads'                   # 'prefork' is not supported in dev (on Windows)
            concurrency = cls.concurrency
        else:
            pool = 'prefork'                # 'prefork' is well suited for the containerized app
            concurrency = cls.concurrency

        if os.name == 'nt':
            logfile = 'nul'                 # Discard Celery console logs - Windows
        else:
            logfile = '/dev/null'           # Discard Celery console logs - Unix
        cls.celery_worker = start_worker(
            celery_app, queues=[cls.test_queue_name], concurrency=concurrency,
            pool=pool, perform_ping_check=False, logfile=logfile
        )
        cls.celery_worker.__enter__()

    @classmethod
    def tearDownClass(cls):
        # Flush the test queue
        cls.redis_client.delete(cls.test_queue_name)
        # Grace period to ensure the celery worker finishes
        sleep(3)
        # Stop the celery worker
        cls.celery_worker.__exit__(None, None, None)
        super().tearDownClass()

    def setUp(self):
        # Authorization data
        # Due to TransactionTestCase the test user is destroyed after each test
        # and has to be recreated
        self.test_user = self.create_test_user(username=self.username, password=self.password)
        self.valid_token = self.generate_test_user_token(
            client=self.client, username=self.username, password=self.password
        )
        # Prerequisite test data
        self.init_test_data()
        self.active_testing = True
        self.cncrrncy_test_sleep_period = 0

    def init_test_data(self):
        pass


class OrchestrateWallConfigTaskTest(ConcurrentCeleryTasksTestBase):
    description = 'Wall Config Processing and Deletion Tasks Tests'

    def setUp(self):
        self.wall_config_hash = hash_calc(self.wall_construction_config)
        self.sections_count = get_sections_count(self.wall_construction_config)
        super().setUp()

    def init_test_data(self):
        self.input_data = {
            'wall_config_hash': self.wall_config_hash,
            'sections_count': self.sections_count
        }
        self.wall_config_object = manage_wall_config_object({
            'wall_config_hash': self.wall_config_hash,
            'initial_wall_construction_config': self.wall_construction_config,
            'error_response': None
        })
        self.valid_config_id = 'test_config_id_1'
        self.wall_config_reference_1 = WallConfigReference.objects.create(
            user=self.test_user,
            wall_config=self.wall_config_object,
            config_id=self.valid_config_id,
        )
        sleep(1)    # Grace period to ensure objects are properly created in postgres

    def process_tasks(
        self, test_case_source: str, deletion: str | None = None
    ) -> tuple[str, list]:
        """
        Send the wall config processing task to the celery worker alone or
        along with the deletion task.
        """
        actual_result = []
        if isinstance(self.wall_config_object, WallConfig):
            wall_config_orchestration_result, deletion_result = self.send_celery_tasks(deletion)
            actual_message, actual_result = self.get_results(
                wall_config_orchestration_result, deletion, deletion_result, test_case_source
            )
        else:
            actual_message = self.wall_config_object

        return actual_message, actual_result

    def send_celery_tasks(
        self, deletion: str | None, num_crews_range: str | int = 'full-range'
    ) -> tuple[AsyncResult, AsyncResult | None]:
        task_kwargs = {
            'wall_config_hash': self.wall_config_hash,
            'wall_construction_config': self.wall_construction_config,
            'sections_count': self.sections_count,
            'active_testing': self.active_testing,
            'username': self.username,
            'config_id': self.valid_config_id,
            'num_crews_range': num_crews_range,
            'cncrrncy_test_sleep_period': self.cncrrncy_test_sleep_period,
        }

        wall_config_orchestration_result = orchestrate_wall_config_processing_task_test.apply_async(
            kwargs=task_kwargs, priority=CELERY_TASK_PRIORITY['MEDIUM']
        )   # type: ignore

        deletion_result = None
        if deletion:
            if deletion == 'sequential':
                # Simulate that the deletion occurs after the whole wall config is processed
                wall_config_orchestration_result.get()
            if deletion == 'concurrent':
                # Ensure the orchestration task has time to start
                # -If too long - the orchestration task finishes and the interruption is
                # not properly simulated
                # - If too short - the orchestration task has no time to start
                sleep(5)
            deletion_result = wall_config_deletion_task_test.apply_async(
                kwargs={'wall_config_hash': self.wall_config_hash}, priority=CELERY_TASK_PRIORITY['HIGH']
            )    # type: ignore

        return wall_config_orchestration_result, deletion_result

    def get_results(
        self, wall_config_orchestration_result: AsyncResult, deletion: str | None,
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
        if actual_deletion_message != base_messages.OK:
            return actual_deletion_message

        actual_message, actual_result = wall_config_orchestration_result.result
        if deletion == 'sequential' and actual_message != base_messages.OK:
            return actual_message
        if deletion == 'concurrent':
            if (
                actual_message != error_messages.INTERRUPTED_BY_DELETION_TASK and
                self._testMethodName != 'test_wall_config_deletion_task_concurrent'
            ):
                return actual_message
            if {} not in actual_result:
                return 'Abort signal not processed!'

        return base_messages.OK

    def evaluate_tasks_result(self, task_results: list, deletion: str | None = None) -> str:
        if deletion:
            return self.evaluate_deletion()

        # Check if the processing of the wall config was successful
        if not isinstance(self.wall_config_object, WallConfig):
            return self.wall_config_object
        self.wall_config_object.refresh_from_db()
        if self.wall_config_object.status != WallConfigStatusEnum.CALCULATED:
            return 'Wall config processing failed.'

        for task_result in task_results:
            # Check if the wall is in the DB
            wall = self.evaluate_wall_result(task_result)
            if not isinstance(wall, Wall):
                return 'Wall not found.'
            # Check if all profiles are in the DB
            wall_profiles_evaluation_message = self.evaluate_wall_progress(task_result, wall)
            if wall_profiles_evaluation_message != base_messages.OK:
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
                total_ice_amount=task_result['celery_sim_calc_details']['total_ice_amount'],
                construction_days=task_result['celery_sim_calc_details']['construction_days'],
            )
            return wall
        except Wall.DoesNotExist:
            return None

    def evaluate_wall_progress(self, task_result: dict, wall: Wall) -> str:
        daily_details = task_result['celery_sim_calc_details']['daily_details']

        for day, ice_amount_data in daily_details.items():
            try:
                wall_progress = WallProgress.objects.get(
                    wall=wall,
                    day=day,
                )
            except WallProgress.DoesNotExist:
                return f'Wall progress for day({day}) not found: num_crews={task_result["num_crews"]}'

            for profile_key, ice_amount in ice_amount_data.items():
                cached_ice_amount = wall_progress.ice_amount_data.get(profile_key)
                if cached_ice_amount != ice_amount:
                    result_message = (
                        f'Day({day}) profile({profile_key}) calculated amount '
                        f'({ice_amount}) does not match the cached value ({cached_ice_amount}).'
                    )
                    return result_message

        return base_messages.OK

    def send_multiple_deletion_tasks(self, test_case_source) -> tuple[str, str]:
        deletion_task_1_kwargs = {
            'wall_config_hash': self.wall_config_hash,
            'active_testing': self.active_testing
        }
        deletion_result_1 = wall_config_deletion_task_test.apply_async(
            kwargs=deletion_task_1_kwargs, priority=CELERY_TASK_PRIORITY['HIGH']
        )    # type: ignore

        deletion_task_2_kwargs = {
            'wall_config_hash': self.wall_config_hash,
            'active_testing': self.active_testing
        }
        deletion_result_2 = wall_config_deletion_task_test.apply_async(
            kwargs=deletion_task_2_kwargs, priority=CELERY_TASK_PRIORITY['HIGH']
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
        """One of the tasks should return a 'Deletion already initiated' result"""
        expected_condition_met = (
            (actual_message_1 == base_messages.OK and actual_message_2 == expected_message) or
            (actual_message_2 == base_messages.OK and actual_message_1 == expected_message)
        )
        wall_config_absent = not WallConfig.objects.filter(wall_config_hash=self.wall_config_hash).exists()

        # Condition passes if expected condition is met and wall config does not exist
        if expected_condition_met and wall_config_absent:
            return True, expected_message

        # Condition failed, determine the appropriate failure message
        if actual_message_1 != base_messages.OK:
            return False, actual_message_1
        elif actual_message_2 != base_messages.OK:
            return False, actual_message_2

        # Default failure message
        return False, self.deletion_task_fail_msg

    def test_orchestrate_wall_config_processing_task(self, deletion: str | None = None, test_case_source: str = ''):
        if not deletion:
            test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
            expected_message = self.orchstrt_wall_config_task_success_msg
        else:
            expected_message = self.deletion_task_success_msg

        task_result_message, task_results = self.process_tasks(test_case_source, deletion=deletion)
        common_result_kwargs = {
            'input_data': self.input_data,
            'expected_message': expected_message,
            'test_case_source': test_case_source
        }

        if task_result_message != base_messages.OK:
            self.log_test_result(passed=False, actual_message=task_result_message, **common_result_kwargs)
            return

        actual_message = self.evaluate_tasks_result(task_results, deletion)

        passed = actual_message == expected_message
        self.log_test_result(passed=passed, actual_message=actual_message, **common_result_kwargs)

    def test_wall_config_deletion_task_concurrent(self):
        """
        Start the deletion task during the orchestration task processing.
        The expected result is that the orchestration is gracefully aborted.
        *On a faster machine this test may fail due to one of the tasks not starting at the correct time or
        finishing prematurely. To avoid this:
        -Decrease the wait period between the tasks in send_celery_tasks (for deletion == 'concurrent')
        -Increase the size of wall_construction_config in ConcurrentCeleryTasksTestBase.setUpClass
        -Both of the above together
        """
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        # Used to ensure proper testing conditions for mid-calculation abort signal
        if 'multiprocessing' in CONCURRENT_SIMULATION_MODE:
            self.cncrrncy_test_sleep_period = 0.05
        else:
            self.cncrrncy_test_sleep_period = 0.2
        self.test_orchestrate_wall_config_processing_task(deletion='concurrent', test_case_source=test_case_source)

    def test_wall_config_deletion_task_sequential(self):
        """Start the deletion task after the orchestration task is finished."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        self.test_orchestrate_wall_config_processing_task(deletion='sequential', test_case_source=test_case_source)

    def test_simultaneous_wall_config_deletion_tasks(self):
        """Start two deletion tasks at the same time - one of them should skip the deletion processing."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        expected_message = error_messages.DELETION_ALREADY_STARTED
        actual_message_1, actual_message_2 = self.send_multiple_deletion_tasks(test_case_source)
        passed, actual_message_final = self.check_deletion_tasks_results(actual_message_1, actual_message_2, expected_message)
        self.log_test_result(
            passed=passed,
            input_data=self.input_data,
            expected_message=expected_message,
            actual_message=actual_message_final,
            test_case_source=test_case_source
        )


class DeleteUnusedWallConfigsTaskTest(ConcurrentCeleryTasksTestBase):
    description = 'Delete unused wall configs task test'

    def init_test_data(self):
        self.wall_config_hash_1 = 'test_wall_config_hash_1'
        self.wall_config_object_1 = WallConfig.objects.create(
            wall_config_hash=self.wall_config_hash_1,
            wall_construction_config=[]
        )
        self.wall_config_reference_1 = WallConfigReference.objects.create(
            user=self.test_user,
            wall_config=self.wall_config_object_1,
            config_id='test_config_id_1',
        )
        self.wall_config_hash_2 = 'test_wall_config_hash_2'
        self.wall_config_object_2 = WallConfig.objects.create(
            wall_config_hash=self.wall_config_hash_2,
            wall_construction_config=[]
        )
        self.wall_config_reference_2 = WallConfigReference.objects.create(
            user=self.test_user,
            wall_config=self.wall_config_object_2,
            config_id='test_config_id_2',
        )
        self.input_data = {
            'wall_config_object_1': self.wall_config_object_1,
            'wall_config_object_2': self.wall_config_object_2,
            'wall_config_reference_1': self.wall_config_reference_1,
            'wall_config_reference_2': self.wall_config_reference_2,
        }
        sleep(1)    # Grace period to ensure objects are properly created in postgres

    def delete_user(self) -> None:
        self.client.delete(
            path=reverse(
                exposed_endpoints['user-delete']['name'], kwargs={'username': self.username}
            ),
            data={'current_password': self.password},
            HTTP_AUTHORIZATION=f'Token {self.valid_token}',
            content_type='application/json'
        )
        # Grace period cascade deletion
        sleep(1)

    def process_deletion_attempt(
        self, attempt_number: int, fail_message: str, expected_message: str, test_case_source: str
    ) -> str:
        delete_attempt_result = delete_unused_wall_configs_task_test.apply_async(
            kwargs={'active_testing': self.active_testing}, priority=CELERY_TASK_PRIORITY['HIGH']
        )    # type: ignore
        delete_attempt_result.get()

        if attempt_number == 1:
            deletion_check = not WallConfig.objects.filter(
                wall_config_hash__in=[self.wall_config_hash_1, self.wall_config_hash_2]
            ).exists()
        else:
            deletion_check = WallConfig.objects.filter(
                wall_config_hash__in=[self.wall_config_hash_1, self.wall_config_hash_2]
            ).exists()

        if deletion_check:
            self.log_test_result(
                passed=False, input_data=self.input_data, expected_message=expected_message,
                actual_message=fail_message, test_case_source=test_case_source
            )
            return base_messages.NOK

        return base_messages.OK

    def test_delete_task_success(self):
        """
        The test checks if:
        1. A wall config is retained for an existing user after a delete_unused_wall_configs_task.
        2. A wall config is deleted for a deleted user.
        """
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        actual_message = expected_message = 'Wall config deleted after task execution.'

        fail_message_1 = 'Wall config not deleted after task execution.'
        if self.process_deletion_attempt(
            1, fail_message_1, expected_message, test_case_source,
        ) != base_messages.OK:
            return

        self.delete_user()
        fail_message_2 = 'Wall config not deleted after reference deletion.'
        if self.process_deletion_attempt(
            2, fail_message_2, expected_message, test_case_source
        ) != base_messages.OK:
            return

        self.log_test_result(
            passed=True, input_data=self.input_data, expected_message=expected_message,
            actual_message=actual_message, test_case_source=test_case_source
        )
