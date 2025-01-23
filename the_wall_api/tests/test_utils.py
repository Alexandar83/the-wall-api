from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
from typing import Any, Callable

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, TransactionTestCase
from django.test.client import Client
from django.test.runner import DiscoverRunner
from django.urls import reverse
from rest_framework.exceptions import ErrorDetail

from the_wall_api.models import CONFIG_ID_MAX_LENGTH
from the_wall_api.utils.api_utils import exposed_endpoints
from the_wall_api.utils.message_themes import errors as error_messages
from the_wall_api.utils.open_api_schema_utils.djoser_utils import (
    CreateUserExtendSchemaViewSet, DeleteUserExtendSchemaViewSet, SetPasswordExtendSchemaView,
    TokenCreateExtendSchemaView, TokenDestroyExtendSchemaView
)
from the_wall_api.views import (
    ProfilesOverviewView, ProfilesDaysView,
    WallConfigFileDeleteView, WallConfigFileListView, WallConfigFileUploadView
)

# Group all invalid input characters by serializer error message
invalid_input_groups = {
    'profile_id': {
        ErrorDetail(string=error_messages.ensure_value_greater_than_or_equal_to(1), code='min_value'): [
            0, -1, -100, '0', '-1', '-100',
        ],
        ErrorDetail(string=error_messages.VALID_INTEGER_REQUIRED, code='invalid'): [
            3.14, '3.14', 'string', '$', '@', '#', '!', '%', '^', '&', '*', '(', ')', '<', '>', '?', '[]', '{}', '\\', '|', ';', ':', ',', '.', '/', [], {}, '',
        ],
        ErrorDetail(string=error_messages.THIS_FIELD_MAY_NOT_BE_NULL, code='null'): [
            None,
        ],
    },
    'day': {
        ErrorDetail(string=error_messages.ensure_value_greater_than_or_equal_to(1), code='min_value'): [
            0, -1, -100, '0', '-1', '-100',
        ],
        ErrorDetail(string=error_messages.VALID_INTEGER_REQUIRED, code='invalid'): [
            3.14, '3.14', 'string', '$', '@', '#', '!', '%', '^', '&', '*', '(', ')', '<', '>', '?', '[]', '{}', '\\', '|', ';', ':', ',', '.', '/', [], {}, '',
        ],
        ErrorDetail(string=error_messages.THIS_FIELD_MAY_NOT_BE_NULL, code='null'): [
            None,
        ],
    },
    'num_crews': {
        ErrorDetail(string=error_messages.ensure_value_greater_than_or_equal_to(0), code='min_value'): [
            -1, -2, -100, '-1', '-2', '-100',
        ],
        ErrorDetail(string=error_messages.VALID_INTEGER_REQUIRED, code='invalid'): [
            3.14, '3.14', 'string', '$', '@', '#', '!', '%', '^', '&', '*', '(', ')', '<', '>', '?', '[]', '{}', '\\', '|', ';', ':', ',', '.', '/', [], {}, '',
        ],
    },
    'wall_config_file': {
        'invalid_extension': (
            ErrorDetail(string=error_messages.file_extension_not_allowed('txt', 'json'), code='invalid_extension'),
            SimpleUploadedFile('wall_config.txt', b'[]', content_type='application/json'),
        ),
        'non_serializable_data': (
            ErrorDetail(string=error_messages.INVALID_JSON_FILE_FORMAT, code='invalid'),
            SimpleUploadedFile('wall_config.json', b'[[1, 2, 3], [1, 2]', content_type='application/json'),
        ),
        'empty_file': (
            ErrorDetail(string=error_messages.THE_FILE_IS_EMPTY, code='empty'),
            SimpleUploadedFile('wall_config.json', b'', content_type='application/json'),
        ),
        'null_object': (
            ErrorDetail(string=error_messages.THIS_FIELD_MAY_NOT_BE_NULL, code='null'),
            None,
        ),
        'not_a_file_object': (
            ErrorDetail(string=error_messages.DATA_NOT_A_FILE, code='invalid'),
            'not_a_file_object',
        ),
    },
    'config_id': [
        (
            ErrorDetail(string=error_messages.ensure_config_id_valid_length(CONFIG_ID_MAX_LENGTH), code='max_length'),
            'a' * (CONFIG_ID_MAX_LENGTH + 1),
        ),
        (
            ErrorDetail(string=error_messages.THIS_FIELD_MAY_NOT_BE_NULL, code='null'),
            None,
        ),
        (
            ErrorDetail(string=error_messages.THIS_FIELD_MAY_NOT_BE_BLANK, code='blank'),
            '',
        ),
        (
            ErrorDetail(string=error_messages.THIS_FIELD_IS_REQUIRED, code='required'),
            'omit_config_id',
        ),
    ],
    'config_id_list': [
        (
            ErrorDetail(string=error_messages.THIS_FIELD_MAY_NOT_BE_NULL, code='null'),
            None,
        ),
        (
            ErrorDetail(string=error_messages.INVALID_STRING, code='invalid'),
            {'not_a_valid_string': 'not_a_valid_string'},
        ),
    ],
}


def generate_valid_values() -> list:
    """Generate a range of valid values for profile_id, day, and num_crews."""
    return [
        1, 5, 101, 999999, 2**31,  # Integers
        '1', '5', '101', '999999', str(2**31 - 1)  # String equivalents
    ]


def get_test_logger():
    """
    Console logging is always enabled.
    File logging is conditional.
    """
    logger = logging.getLogger('test_suite')

    if (
        settings.TEST_SUITE_FILE_LOGGING_ENABLED and
        not any(isinstance(handler, logging.FileHandler) for handler in logger.handlers)
    ):
        file_handler = RotatingFileHandler(
            filename=settings.TEST_SUITE_LOGS_FILE,
            maxBytes=1024 * 1024 * 5,
            backupCount=1,
            delay=True
        )
        file_handler.setLevel(logging.INFO)
        file_handler_format = settings.LOGGING['formatters']['test_suite']['format']
        file_handler_formatter = logging.Formatter(file_handler_format)
        file_handler.setFormatter(file_handler_formatter)
        logger.addHandler(file_handler)

    return logger


# Configure the logger with the desired log level
# ERROR - only log errors
# FAILED - only log failed tests
# PASSED - only log passed tests
# ALL - log all tests
# NO-LOGGING - disable logging
# SUMMARY - only log tests summary
TEST_LOGGING_LEVEL: str = settings.TEST_LOGGING_LEVEL


view_classes_throttling_details = [
    (ProfilesOverviewView, ProfilesOverviewView.throttle_classes.copy()),
    (ProfilesDaysView, ProfilesDaysView.throttle_classes.copy()),
    (WallConfigFileDeleteView, WallConfigFileDeleteView.throttle_classes.copy()),
    (WallConfigFileListView, WallConfigFileListView.throttle_classes.copy()),
    (WallConfigFileUploadView, WallConfigFileUploadView.throttle_classes.copy()),
    (CreateUserExtendSchemaViewSet, CreateUserExtendSchemaViewSet.throttle_classes.copy()),
    (DeleteUserExtendSchemaViewSet, DeleteUserExtendSchemaViewSet.throttle_classes.copy()),
    (SetPasswordExtendSchemaView, SetPasswordExtendSchemaView.throttle_classes.copy()),
    (TokenCreateExtendSchemaView, TokenCreateExtendSchemaView.throttle_classes.copy()),
    (TokenDestroyExtendSchemaView, TokenDestroyExtendSchemaView.throttle_classes.copy()),
]


class CustomTestRunner(DiscoverRunner):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = get_test_logger()

    def setup_test_environment(self, **kwargs):
        """Called at the start of the entire test suite."""
        self.logger.info(f'\n{settings.CONCURRENT_SIMULATION_MODE}')
        cache.clear()   # Ensure cache is cleared at the start of the test suite
        super().setup_test_environment(**kwargs)

    def teardown_test_environment(self, **kwargs):
        """Called at the end of the entire test suite."""
        cache.clear()   # Ensure cache is cleared at the end of the test suite
        super().teardown_test_environment(**kwargs)
        # Log the total PASSED and FAILED across all modules
        self.logger.info('--------------------------------------------')
        self.logger.info(f'Total PASSED in all tests: {BaseTestMixin.total_passed}')
        self.logger.info(f'Total FAILED in all tests: {BaseTestMixin.total_failed}')
        self.logger.info(f'Total ERRORS in all tests: {BaseTestMixin.total_errors}')


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
    wall_construction_config = [
        [21, 25, 28],
        [17],
        [17, 22, 17, 19, 17]
    ]

    @classmethod
    def setUpClass(cls, bypass_throttling: bool = True):
        cls.logger = get_test_logger()
        # Track passed/failed tests on module level
        cls.module_passed = 0
        cls.module_failed = 0
        cls.module_errors = 0
        if settings.TEST_LOGGING_LEVEL not in ['NO-LOGGING', 'SUMMARY']:
            cls.logger.info(' ')
            BaseTestMixin.test_group_counter += 1
            cls.test_case_group_description = getattr(cls, 'description', cls.__name__)
            test_module = cls.__module__.upper().rpartition('.')[-1]
            cls.logger.info(f'{"=" * 14} {test_module} -  START OF TEST GROUP #{cls.test_group_counter} {"=" * 14}')
            cls.logger.info(f'{cls.test_case_group_description.upper()}')
            cls.logger.info(' ')

        if bypass_throttling:
            cls.bypass_throttling()

    @classmethod
    def bypass_throttling(cls) -> None:
        for view_class, _ in view_classes_throttling_details:
            if view_class.throttle_classes:
                view_class.throttle_classes = []

    @classmethod
    def tearDownClass(cls):
        # At the end of each module, log the results for that module
        if settings.TEST_LOGGING_LEVEL not in ['NO-LOGGING', 'SUMMARY']:
            cls.logger.info(' ')
            cls.logger.info(f'Total PASSED: {cls.module_passed}')
            cls.logger.info(f'Total FAILED: {cls.module_failed}')
            cls.logger.info(f'Total ERRORS: {cls.module_errors}')
            cls.logger.info(f'{"=" * 14} END OF TEST GROUP #{cls.test_group_counter} {"=" * 14}')
            cls.logger.info(' ')

        cls.revert_throttling_bypass()

    @classmethod
    def revert_throttling_bypass(cls):
        for view_class, stored_throttle_classes in view_classes_throttling_details:
            if view_class.throttle_classes == []:
                view_class.throttle_classes = stored_throttle_classes

    @classmethod
    def cache_clear(cls, func):
        def wrapper(self, *args, **kwargs):
            cache.clear()
            result = func(self, *args, **kwargs)
            cache.clear()

            return result

        return wrapper

    @classmethod
    def create_test_user(cls, username: str, password: str) -> AbstractUser:
        User = get_user_model()
        test_user = User.objects.create_user(username=username, password=password)

        return test_user

    @classmethod
    def generate_test_user_token(cls, client: Client, username: str, password: str) -> str:
        response = client.post(
            path=reverse(exposed_endpoints['token-login']['name']),
            data={'username': username, 'password': password}
        )
        response_data = response.json()

        return response_data['auth_token']

    def _get_test_case_source(self, method_name: str, class_name: str) -> str:
        return f'{self.__module__}.{class_name}.{method_name}'

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
            (TEST_LOGGING_LEVEL in ['FAILED', 'SUMMARY'] and not passed) or  # Log both FAILED and ERROR
            (TEST_LOGGING_LEVEL in ['ERROR', 'SUMMARY'] and error_occurred)  # Log only ERROR
        ):
            self.logger.info('')
            test_number = BaseTestMixin.test_counter
            self.logger.info(f'{"TEST #" + str(test_number) + ":":<{self.padding}}{status}')
            self.logger.info(f'{"Timestamp:":<{self.padding}}{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
            self.logger.info(f'{"Test method:":<{self.padding}}{test_case_source}')
            self.logger.info(f'{"Input values:":<{self.padding}}{input_data}')
            self.logger.info(f'{"Expected result:":<{self.padding}}{expected_message}')
            self.logger.info(f'{"Actual result:":<{self.padding}}{actual_message}')

            BaseTestMixin.test_counter += 1
            for handler in self.logger.handlers:
                handler.flush()

    def pre_request_hook(self, *args, **kwargs) -> None:
        pass

    def post_request_hook(self, *args, **kwargs) -> None:
        pass


class BaseTestcase(BaseTestMixin, TestCase):
    @classmethod
    def setUpClass(cls, *args, **kwargs):
        TestCase.setUpClass()
        super().setUpClass(*args, **kwargs)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        TestCase.tearDownClass()

    def setUp(self, generate_token=False):
        self.client_get_method = getattr(self.client, 'get')
        self.client_post_method = getattr(self.client, 'post')
        self.client_delete_method = getattr(self.client, 'delete')

        if generate_token:
            self.valid_token = self.generate_test_user_token(
                client=self.client, username=self.username, password=self.password
            )

    def execute_throttling_test(
        self, rest_method: Callable, url: str, request_params: dict[str, Any], throttle_scope: str,
        input_data: dict[str, Any], test_case_source: str
    ) -> None:
        rate_limit = int(settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'][throttle_scope].split('/')[0])

        expected_message = actual_message = 'Correct throttle rate applied'
        response = None
        requests_count = 0
        error_occured = False

        for requests_count in range(1, rate_limit + 2):
            self.pre_request_hook(request_params)
            response = rest_method(url, **request_params)
            self.post_request_hook(request_params)
            if response.status_code == 429:
                break

        try:
            if response is None:
                raise ValueError('No requests were processed!')
            self.assertEqual(response.status_code, 429, f'Incorrect status code: {response.status_code}!')
            self.assertEqual(
                requests_count,
                rate_limit + 1,
                f'Incorrect rate limit: {requests_count} - expected: {rate_limit + 1}!'
            )
        except (AssertionError, ValueError) as assrtn_err:
            actual_message = f'{assrtn_err.__class__.__name__}: {str(assrtn_err)}'
        except Exception as unknwn_err:
            actual_message = f'{unknwn_err.__class__.__name__}: {str(unknwn_err)}'
            error_occured = True

        passed = expected_message == actual_message

        self.log_test_result(
            passed=passed, input_data=input_data, expected_message=expected_message,
            actual_message=actual_message, test_case_source=test_case_source, error_occurred=error_occured
        )


class BaseTransactionTestcase(BaseTestMixin, TransactionTestCase):
    @classmethod
    def setUpClass(cls, *args, **kwargs):
        TransactionTestCase.setUpClass()
        super().setUpClass(*args, **kwargs)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        TransactionTestCase.tearDownClass()
