import logging

from django.core.cache import cache
from django.conf import settings
from django.test import TestCase, TransactionTestCase
from django.test.runner import DiscoverRunner
from rest_framework.exceptions import ErrorDetail

# Group all invalid input characters by serializer error message
invalid_input_groups = {
    'profile_id': {
        ErrorDetail(string='Ensure this value is greater than or equal to 1.', code='min_value'): [
            0, -1, -100, '0', '-1', '-100',
        ],
        ErrorDetail(string='A valid integer is required.', code='invalid'): [
            3.14, '3.14', 'string', '$', '@', '#', '!', '%', '^', '&', '*', '(', ')', '<', '>', '?', '[]', '{}', '\\', '|', ';', ':', ',', '.', '/', [], {}, '',
        ],
        ErrorDetail(string='This field may not be null.', code='null'): [
            None,
        ],
    },
    'day': {
        ErrorDetail(string='Ensure this value is greater than or equal to 1.', code='min_value'): [
            0, -1, -100, '0', '-1', '-100',
        ],
        ErrorDetail(string='A valid integer is required.', code='invalid'): [
            3.14, '3.14', 'string', '$', '@', '#', '!', '%', '^', '&', '*', '(', ')', '<', '>', '?', '[]', '{}', '\\', '|', ';', ':', ',', '.', '/', [], {}, '',
        ],
        ErrorDetail(string='This field may not be null.', code='null'): [
            None,
        ],
    },
    'num_crews': {
        ErrorDetail(string='Ensure this value is greater than or equal to 0.', code='min_value'): [
            -1, -2, -100, '-1', '-2', '-100',
        ],
        ErrorDetail(string='A valid integer is required.', code='invalid'): [
            3.14, '3.14', 'string', '$', '@', '#', '!', '%', '^', '&', '*', '(', ')', '<', '>', '?', '[]', '{}', '\\', '|', ';', ':', ',', '.', '/', [], {}, '',
        ],
    }
}


def generate_valid_values() -> list:
    """Generate a range of valid values for profile_id, day, and num_crews."""
    return [
        1, 5, 101, 999999, 2**31,  # Integers
        '1', '5', '101', '999999', str(2**31 - 1)  # String equivalents
    ]


def configure_test_logger():
    """Configure a simple logger for test results."""
    logger = logging.getLogger('test_logger')
    logger.setLevel(logging.DEBUG)

    if not logger.hasHandlers():
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(ch)

    return logger


# Configure the logger with the desired log level
# ERROR - only log errors
# FAILED - only log failed tests
# PASSED - only log passed tests
# ALL - log all tests
# NO-LOGGING - disable logging
# SUMMARY - only log tests summary
TEST_LOGGING_LEVEL: str = settings.TEST_LOGGING_LEVEL
logger = configure_test_logger()


class CustomTestRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        """Called at the start of the entire test suite."""
        cache.clear()   # Ensure cache is cleared at the start of the test suite
        super().setup_test_environment(**kwargs)

    def teardown_test_environment(self, **kwargs):
        """Called at the end of the entire test suite."""
        cache.clear()   # Ensure cache is cleared at the end of the test suite
        super().teardown_test_environment(**kwargs)
        # Log the total PASSED and FAILED across all modules
        logger.info('--------------------------------------------')
        logger.info(f'Total PASSED in all tests: {BaseTestMixin.total_passed}')
        logger.info(f'Total FAILED in all tests: {BaseTestMixin.total_failed}')
        logger.info(f'Total ERRORS in all tests: {BaseTestMixin.total_errors}')


class BaseTestMixin:
    # Class-level counter to track test numbers per test module
    test_counter = 1
    # Class-level counters to track passed/failed/error tests globally
    total_passed = 0
    total_failed = 0
    total_errors = 0
    # Class-level counter to track test groups
    test_group_counter = 0
    # Padding for output messages alignment
    padding = 20
    username = 'testuser'
    password = 'G7m@zK#1qP'

    @classmethod
    def setUpClass(cls):
        # Track passed/failed tests on module level
        cls.module_passed = 0
        cls.module_failed = 0
        cls.module_errors = 0
        if settings.TEST_LOGGING_LEVEL != 'NO-LOGGING':
            logger.info(' ')
            BaseTestMixin.test_group_counter += 1
            cls.test_case_group_description = getattr(cls, 'description', cls.__name__)
            test_module = cls.__module__.upper().rpartition('.')[-1]
            logger.info(f'{"=" * 14} {test_module} -  START OF TEST GROUP #{cls.test_group_counter} {"=" * 14}')
            logger.info(f'{cls.test_case_group_description.upper()}')
            logger.info(' ')

    @classmethod
    def tearDownClass(cls):
        # At the end of each module, log the results for that module
        if settings.TEST_LOGGING_LEVEL != 'NO-LOGGING':
            logger.info(' ')
            logger.info(f'Total PASSED: {cls.module_passed}')
            logger.info(f'Total FAILED: {cls.module_failed}')
            logger.info(f'Total ERRORS: {cls.module_errors}')
            logger.info(f'{"=" * 14} END OF TEST GROUP #{cls.test_group_counter} {"=" * 14}')
            logger.info(' ')

    @classmethod
    def cache_clear(cls, func):
        def wrapper(self, *args, **kwargs):
            cache.clear()
            result = func(self, *args, **kwargs)
            cache.clear()

            return result

        return wrapper

    def _get_test_case_source(self, method_name: str) -> str:
        return f'{self.__module__} -> {method_name}'

    def log_test_result(
        self, passed: bool, input_data, expected_message: str, actual_message: str,
        test_case_source: str, log_level: str = TEST_LOGGING_LEVEL, error_occurred: bool = False
    ) -> None:
        """Helper function to log the test result based on the TEST_LOGGING_LEVEL."""
        if passed:
            status = 'PASSED'
            self.__class__.module_passed += 1
            BaseTestMixin.total_passed += 1
        elif not error_occurred:
            status = 'FAILED'
            self.__class__.module_failed += 1
            BaseTestMixin.total_failed += 1
        else:
            status = 'ERROR'
            self.__class__.module_errors += 1
            BaseTestMixin.total_errors += 1

        if log_level == 'NO-LOGGING':
            return  # Skip logging entirely

        if (
            TEST_LOGGING_LEVEL == 'ALL' or
            (TEST_LOGGING_LEVEL == 'PASSED' and passed) or
            (TEST_LOGGING_LEVEL == 'FAILED' and not passed) or  # Log both FAILED and ERROR
            (TEST_LOGGING_LEVEL == 'ERROR' and error_occurred)  # Log only ERROR
        ):
            logger.info('')
            test_number = BaseTestMixin.test_counter
            logger.info(f'{"TEST #" + str(test_number) + ":":<{self.padding}}{status}')
            logger.info(f'{"Test method:":<{self.padding}}{test_case_source}')
            logger.info(f'{"Input values:":<{self.padding}}{input_data}')
            logger.info(f'{"Expected result:":<{self.padding}}{expected_message}')
            logger.info(f'{"Actual result:":<{self.padding}}{actual_message}')

            BaseTestMixin.test_counter += 1
            for handler in logger.handlers:
                handler.flush()


class BaseTestcase(BaseTestMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        TestCase.setUpClass()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        TestCase.tearDownClass()


class BaseTransactionTestcase(BaseTestMixin, TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        TransactionTestCase.setUpClass()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        TransactionTestCase.tearDownClass()
