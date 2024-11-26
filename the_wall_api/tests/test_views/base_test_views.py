from abc import ABC, abstractmethod
from typing import Literal

from django.core.cache import cache

from the_wall_api.tests.test_utils import BaseTestcase


class BaseViewTest(ABC, BaseTestcase):
    url_name = None

    def execute_test_case(
        self, expected_status: Literal[200, 400, 404], test_case_source: str, consistency_test: bool = False,
        *args, **kwargs
    ) -> None:
        url, params, input_data = self.prepare_final_test_data(*args, **kwargs)

        try:
            if not consistency_test:
                self.execute_response_status_test(url, params, expected_status, input_data, test_case_source)
            else:
                self.execute_results_consistency_test(url, params, input_data, test_case_source)
        except Exception as err:
            self.log_test_result(
                passed=False, input_data=input_data, expected_message=str(expected_status),
                actual_message=f'{err.__class__.__name__}: {str(err)}',
                test_case_source=test_case_source, error_occurred=True
            )

        # Clear the cache after each test
        # A DB flush for such tests is automatically performed
        # by the Django test runner
        cache.clear()

    @abstractmethod
    def prepare_final_test_data(self, *args, **kwargs) -> tuple[str, dict, dict]:
        pass

    @abstractmethod
    def prepare_url(self, *args, **kwargs) -> str:
        pass

    def execute_response_status_test(self, url: str, params: dict, expected_status: int, input_data: dict, test_case_source: str) -> None:
        response = self.client.get(url, params)
        passed = response.status_code == expected_status
        self.log_response_status_test_result(
            passed, input_data, expected_status, response.status_code, test_case_source
        )

    def execute_results_consistency_test(self, url: str, params: dict, input_data: dict, test_case_source: str) -> None:
        reference_result = self.client.get(url, params).json()
        passed, result = True, {}

        for _ in range(5):
            result = self.client.get(url, params).json()
            if result != reference_result:
                passed = False
                break

        self.log_results_consistency_test_result(passed, input_data, reference_result, result, test_case_source)

    def log_response_status_test_result(self, passed: bool, input_data: dict, expected_status: int, actual_status: int, test_case_source: str) -> None:
        self.log_test_result(
            passed=passed,
            input_data=input_data,
            expected_message=str(expected_status),
            actual_message=str(actual_status),
            test_case_source=test_case_source
        )

    def log_results_consistency_test_result(self, passed: bool, input_data: dict, reference_result: dict, result: dict, test_case_source: str) -> None:
        self.log_test_result(
            passed=passed,
            input_data=input_data,
            expected_message=str(reference_result),
            actual_message=str(result),
            test_case_source=test_case_source
        )