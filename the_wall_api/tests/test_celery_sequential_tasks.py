from inspect import currentframe
import json
import os
from shutil import rmtree

from django.conf import settings

from the_wall_api.utils.celery_task_utils import BUILD_SIM_LOGS_DIR, get_test_log_archive_details
from the_wall_api.utils.error_utils import get_error_id_from_task_result, extract_error_traceback
from the_wall_api.utils.message_themes import base as base_messages
from the_wall_api.tasks import archive_logs_task, clean_old_archives_task, log_error_task
from the_wall_api.tests.test_utils import BaseTestcase

CELERY_BROKER_URL = settings.CELERY_BROKER_URL
ERROR_LOGS_DIR = settings.ERROR_LOGS_DIR
ERROR_LOG_FILES_CONFIG = settings.ERROR_LOG_FILES_CONFIG


class FileRetentionCeleryTaskTest(BaseTestcase):
    description = 'File Retention Celery Task Tests'

    def setUp(self, *args, **kwargs):
        self.root_dir = BUILD_SIM_LOGS_DIR
        self.logs_type = 'build_sim'
        self.test_file_name = 'test_build_simulation_log.txt'

        self.root_testing_dir = os.path.join(self.root_dir, 'testing')
        test_logs_dir, test_logs_dir_archive, test_file = get_test_log_archive_details(self.root_dir, self.test_file_name)
        self.test_logs_dir = test_logs_dir
        self.test_logs_dir_archive = test_logs_dir_archive
        self.test_file = test_file

        if os.name == 'nt' or settings.PROJECT_MODE != 'dev':
            os.makedirs(self.test_logs_dir, exist_ok=True)
        else:
            self.manage_test_logs_dir_permissions()
        with open(self.test_file, 'a') as test_file:
            test_file.write('This is a test log.')

    def manage_test_logs_dir_permissions(self):
        """
        On Linux override the default 2755 permissions for newly created folders to 2775.
        This ensures the app group and the assigned to it non-root appuser in celery_worker_2_dev
        has permissions to write to the new folder.
        """
        os.makedirs(self.test_logs_dir, exist_ok=True)
        target_permissions = 0o2775
        os.chmod(self.test_logs_dir, target_permissions)

    def get_file_retention_tasks_result(self, test_input_params: dict, expected_message: str) -> str:
        # Check if the test file is existing
        if not os.path.exists(self.test_file):
            return f'Test file: {self.test_file} does not exist!'

        # Archive the test file
        archive_task_result = archive_logs_task.delay(test_input_params=test_input_params)  # type: ignore
        archive_task_result.get(timeout=5)  # Blocks until the task is done

        # Check archive task success
        if not archive_task_result.successful():
            return f'Archive_logs_task failed: {archive_task_result.result}!'

        # Ensure the test file is moved and archived
        archived_file_path = os.path.join(self.test_logs_dir_archive, f'{self.test_file_name}.gzip')
        if not os.path.exists(archived_file_path):
            return f'Archived file: {archived_file_path} does not exist!'

        # Remove the archived test file
        clean_old_archives_task_result = clean_old_archives_task.delay(test_input_params=test_input_params)     # type: ignore
        clean_old_archives_task_result.get(timeout=10)

        # Check clean task success
        if not clean_old_archives_task_result.successful():
            return f'clean_old_archives_task failed: {clean_old_archives_task_result.result}!'

        # Ensure the archived test file is deleted
        if os.path.exists(archived_file_path):
            return f'Archived file: {archived_file_path} is not deleted!'

        return expected_message

    def test_file_retention_tasks(self):
        """Test that the archive logs and clean old archives tasks are properly executed by the Celery worker."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        test_input_params = {
            'logs_type': self.logs_type,
            'test_file_name': self.test_file_name
        }

        error_occurred = False
        expected_message = 'File retention tasks successful.'

        try:
            actual_message = self.get_file_retention_tasks_result(test_input_params, expected_message)
        except Exception as task_err:
            passed = False
            actual_message = f'{task_err.__class__.__name__}: {str(task_err)}'
            error_occurred = True

        passed = expected_message == actual_message

        self.log_test_result(
            passed=passed,
            input_data=test_input_params,
            expected_message=expected_message,
            actual_message=actual_message,
            test_case_source=test_case_source,
            error_occurred=error_occurred
        )

        rmtree(self.root_testing_dir)


class LogErrorTaskTest(BaseTestcase):
    description = 'Log Error Celery Task Tests'

    def get_log_error_task_result(
        self, unknwn_err: Exception, error_type: str, input_data: dict, expected_message: str, test_case_source: str
    ) -> str:
        # Extract error details
        error_message = f'{unknwn_err.__class__.__name__}: {str(unknwn_err)}'
        error_traceback = extract_error_traceback(unknwn_err)
        input_data['error_type'] = error_type
        input_data['error_message'] = error_message

        # Log the error
        task_result = log_error_task.delay(error_type, error_message, error_traceback, error_id_prefix=f'{test_case_source}_')      # type: ignore
        task_result.get(timeout=5)  # Blocks until the task is done

        # Check log error task success
        if not task_result.successful():
            return f'Log error task failed: {task_result.result}!'

        # Retrieve the global error counter value, returned from the log error task
        error_id = get_error_id_from_task_result(task_result)
        if error_id == base_messages.N_A:
            actual_message = f'Global error counter not incremented successfully: {task_result.result}!'
            return actual_message

        # Check if the error log file is existing
        error_log_file = ERROR_LOG_FILES_CONFIG[error_type]
        if not os.path.exists(error_log_file):
            actual_message = f'Error log file does not exist: {error_log_file}'
            return actual_message

        # Check logged error details
        check_log_file_result = self.check_logged_error_details(error_log_file, error_id, error_message)
        if check_log_file_result != base_messages.OK:
            actual_message = f'Logged error details inconsistency: {check_log_file_result}!'
            return actual_message

        return expected_message

    def check_logged_error_details(self, error_log_file: str, error_id: str, error_message: str) -> str:
        with open(error_log_file, 'r') as error_log:
            for logged_error in error_log:
                logged_error_json = json.loads(logged_error)

                logged_error_id = logged_error_json.get('error_id')
                if logged_error_id.rpartition('_')[2] != error_id:
                    continue

                # If the log is found, check its error message
                logged_error_message = logged_error_json.get('message')
                if logged_error_message != error_message:
                    return (
                        f'Logged error message: {logged_error_message}\n'
                        f'does not match expected error message: {error_message}'
                    )

                return base_messages.OK

        return f'Test error log not found in file {error_log_file}!'

    def send_log_error_task(self, error_type: str, test_case_source: str):
        input_data = {}
        expected_message = actual_message = 'Log error task successful.'
        error_occurred = False
        passed = False

        try:
            raise Exception(f'Test exception for log_error_task of type \'{error_type}\'.')
        except Exception as unknwn_err:
            try:
                actual_message = self.get_log_error_task_result(
                    unknwn_err, error_type, input_data, expected_message, test_case_source
                )
            except Exception as task_err:
                error_message = f'{task_err.__class__.__name__}: {str(task_err)}'
                actual_message = f'Log error task failed: {error_message}'
                error_occurred = True

        passed = expected_message == actual_message

        self.log_test_result(
            passed=passed,
            input_data=input_data,
            expected_message=expected_message,
            actual_message=actual_message,
            test_case_source=test_case_source,
            error_occurred=error_occurred
        )

    def test_log_error_task_caching(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore
        self.send_log_error_task('caching', test_case_source)

    def test_log_error_task_celery_tasks(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore
        self.send_log_error_task('celery_tasks', test_case_source)

    def test_log_error_task_wall_configuration(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore
        self.send_log_error_task('wall_configuration', test_case_source)

    def test_log_error_task_wall_creation(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore
        self.send_log_error_task('wall_creation', test_case_source)
