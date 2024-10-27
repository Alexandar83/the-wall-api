from inspect import currentframe

from config.celery import app as celery_app
from celery.contrib.testing.worker import start_worker
from django.conf import settings
from django.db.models import Q
from redis import Redis

from the_wall_api.models import WallConfig, Wall, WallConfigStatusEnum, WallProfile, WallProfileProgress
from the_wall_api.tasks import orchestrate_wall_config_processing_task_test
from the_wall_api.tests.test_utils import BaseTransactionTestcase
from the_wall_api.utils.storage_utils import manage_wall_config_object
from the_wall_api.utils.wall_config_utils import CONCURRENT, hash_calc, load_wall_profiles_from_config
from the_wall_api.wall_construction import get_sections_count, manage_num_crews

MAX_WALL_PROFILE_SECTIONS = settings.MAX_WALL_PROFILE_SECTIONS
MAX_SECTION_HEIGHT = settings.MAX_SECTION_HEIGHT


class OrchestrateWallConfigTaskTest(BaseTransactionTestcase):
    description = 'Orchestrate Wall Config Processing Task Tests'

    @classmethod
    def setUpClass(cls):
        cls.test_queue_name = 'test_queue'
        cls.worker_count = 8
        cls.setup_celery_worker()
        super().setUpClass()

    @classmethod
    def setup_celery_worker(cls) -> None:
        # Flush the test queue from any stale tasks
        cls.redis_client = Redis.from_url(settings.CELERY_BROKER_URL)
        cls.redis_client.ltrim(cls.test_queue_name, 1, 0)

        # Start the celery worker and instruct it to listen to 'test_queue'
        if settings.PROJECT_MODE == 'dev':
            # 'prefork' is not supported in dev (on Windows)
            # Avoid 'gevent' dependency - not justified
            pool = 'solo'
            for i in range(1, cls.worker_count + 1):
                worker_name = f'test_celery_worker_{i}'
                worker = start_worker(
                    celery_app,
                    queues=[cls.test_queue_name],
                    perform_ping_check=False,
                    concurrency=1,
                    pool=pool,
                    logfile='nul'    # Discard Celery console logs - Windows
                )
                setattr(cls, worker_name, worker)
                getattr(cls, worker_name).__enter__()
        else:
            # 'prefork' is well suited for the containerized app
            pool = 'prefork'
            cls.test_celery_worker = start_worker(
                celery_app,
                queues=[cls.test_queue_name],
                perform_ping_check=False,
                concurrency=cls.worker_count,
                pool=pool,
                logfile='dev/null'  # Discard Celery console logs - Unix
            )
            cls.test_celery_worker.__enter__()

    @classmethod
    def tearDownClass(cls):
        # Flush the test queue
        cls.redis_client.ltrim(cls.test_queue_name, 1, 0)

        # Stop the celery workers
        if settings.PROJECT_MODE == 'dev':
            for i in range(1, cls.worker_count + 1):
                worker_name = f'test_celery_worker_{i}'
                getattr(cls, worker_name).__exit__(None, None, None)
        else:
            cls.test_celery_worker.__exit__(None, None, None)

        super().tearDownClass()

    def setUp(self):
        self.wall_construction_config = load_wall_profiles_from_config()
        # self.wall_construction_config = [
        #     [[0] * 10] * 2000,
        # ]
        self.wall_config_hash = hash_calc(self.wall_construction_config)
        self.sections_count = get_sections_count(self.wall_construction_config)
        self.input_data = {
            'wall_config_hash': self.wall_config_hash,
            'sections_count': self.sections_count
        }
        self.wall_data = {
            'wall_config_hash': self.wall_config_hash,
            'wall_construction_config': self.wall_construction_config
        }
        self.wall_config_object = manage_wall_config_object(self.wall_data)
        self.active_testing = True

    def process_orchestrate_task(self, test_case_source: str) -> tuple[str, list]:
        actual_result = []
        if isinstance(self.wall_config_object, WallConfig):
            result = orchestrate_wall_config_processing_task_test.delay(
                wall_config_hash=self.wall_config_hash,
                wall_construction_config=self.wall_construction_config,
                sections_count=self.sections_count,
                active_testing=self.active_testing
            )    # type: ignore
            try:
                result.get()
            except TimeoutError:
                actual_message = f'{test_case_source} timed out'
            else:
                actual_message, actual_result = result.result
        else:
            actual_message = self.wall_config_object

        return actual_message, actual_result

    def evaluate_orchestration_result(self, task_results: list) -> str:
        # Check if the processing of the wall config was successful
        if not isinstance(self.wall_config_object, WallConfig):
            return self.wall_config_object
        self.wall_config_object.refresh_from_db()
        if self.wall_config_object.status != WallConfigStatusEnum.COMPLETED:
            return 'Wall config processing failed'

        for task_result in task_results:
            # Check if the wall is in the DB
            wall = self.evaluate_wall_result(task_result)
            if not isinstance(wall, Wall):
                return 'Wall not found'

            # Check if all profiles are in the DB
            wall_profiles_evaluation_message = self.evaluate_wall_profiles(task_result, wall)
            if wall_profiles_evaluation_message != 'OK':
                return wall_profiles_evaluation_message

        return 'Wall config processed successfully'

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
                return f'Wall profile progress for profile id({wall_profile.profile_id}) - \
                        day({day_index}) - num_crews={num_crews} not found.'
        return 'OK'

    def test_orchestrate_wall_config_processing_task(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore
        expected_message = 'Wall config processed successfully'

        actual_message, task_results = self.process_orchestrate_task(test_case_source)

        if actual_message != 'OK':
            self.log_test_result(
                passed=False,
                input_data=self.input_data,
                expected_message=expected_message,
                actual_message=actual_message,
                test_case_source=test_case_source
            )
            return

        actual_message = self.evaluate_orchestration_result(task_results)

        passed = actual_message == expected_message
        self.log_test_result(
            passed=passed,
            input_data=self.input_data,
            expected_message=expected_message,
            actual_message=actual_message,
            test_case_source=test_case_source
        )

    def test_to_delete(self):
        pass