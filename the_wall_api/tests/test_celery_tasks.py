from inspect import currentframe
import os
from shutil import rmtree

from the_wall_api.utils.file_utils import BUILD_SIM_LOGS_DIR, get_test_log_archive_details
from the_wall_api.tasks import archive_logs_task, clean_old_archives_task
from the_wall_api.tests.test_utils import BaseTestcase


class CeleryTaskTest(BaseTestcase):
    description = 'Test celery tasks'

    def setUp(self):
        self.root_dir = BUILD_SIM_LOGS_DIR
        self.logs_type = 'build_sim'
        self.test_file_name = 'test_build_simulation_log.txt'

        self.root_testing_dir = os.path.join(self.root_dir, 'testing')
        test_logs_dir, test_logs_dir_archive, test_file = get_test_log_archive_details(self.root_dir, self.test_file_name)
        self.test_logs_dir = test_logs_dir
        self.test_logs_dir_archive = test_logs_dir_archive
        self.test_file = test_file

        os.makedirs(self.test_logs_dir, exist_ok=True)
        with open(self.test_file, 'a') as test_file:
            test_file.write('This is a test log.')

    def get_file_retention_tasks_result(self, test_input_params: dict, expected_message: str) -> str:
        # Ensure the test file is existing
        if not os.path.exists(self.test_file):
            return f'Test file: {self.test_file} does not exist!'

        # Archive the test file
        archive_task_result = archive_logs_task.delay(test_input_params=test_input_params)
        archive_task_result.get(timeout=10)

        # Check archive task success
        if not archive_task_result.successful():
            return f'Archive_logs_task failed: {archive_task_result.result}!'

        # Ensure the test file is moved and archived
        archived_file_path = os.path.join(self.test_logs_dir_archive, f'{self.test_file_name}.gzip')
        if not os.path.exists(archived_file_path):
            return f'Archived file: {archived_file_path} does not exist!'

        # Remove the archived test file
        clean_old_archives_task_result = clean_old_archives_task.delay(test_input_params=test_input_params)
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
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore

        test_input_params = {
            'logs_type': self.logs_type,
            'test_file_name': self.test_file_name
        }

        error_occurred = False
        expected_message = 'File retention tasks successful.'

        try:
            actual_mesasge = self.get_file_retention_tasks_result(test_input_params, expected_message)
        except Exception as task_err:
            passed = False
            actual_mesasge = f'{task_err.__class__.__name__}: {str(task_err)}'
            error_occurred = True

        passed = expected_message == actual_mesasge

        self.log_test_result(
            passed=passed,
            input_data=test_input_params,
            expected_message=expected_message,
            actual_message=actual_mesasge,
            test_case_source=test_case_source,
            error_occurred=error_occurred
        )

        rmtree(self.root_testing_dir)
