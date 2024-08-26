import logging
from django.conf import settings
from django.test import TestCase
from rest_framework import serializers
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
        ErrorDetail(string='Ensure this value is greater than or equal to 1.', code='min_value'): [
            0, -1, -100, '0', '-1', '-100',
        ],
        ErrorDetail(string='A valid integer is required.', code='invalid'): [
            3.14, '3.14', 'string', '$', '@', '#', '!', '%', '^', '&', '*', '(', ')', '<', '>', '?', '[]', '{}', '\\', '|', ';', ':', ',', '.', '/', [], {}, '',
        ],
    }
}


def generate_valid_values() -> list:
    """Generate a range of valid values for both profile_id and day."""
    return [
        1, 5, 101, 999999, 2**31,  # Integers
        '1', '5', '101', '999999', str(2**31 - 1)  # String equivalents
    ]


def extract_error_detail(actual_errors, field_name: str):
    """Helper function to extract error details safely."""
    if isinstance(actual_errors, dict):
        error_detail = actual_errors.get(field_name, None)
        if isinstance(error_detail, list):
            return error_detail[0] if error_detail else None
        return error_detail
    else:
        return str(actual_errors)  # Fallback to string representation if structure is unexpected


def configure_test_logger():
    """Configure a simple logger for test results."""
    logger = logging.getLogger('test_logger')
    logger.setLevel(logging.DEBUG)

    if not logger.hasHandlers():
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        logger.addHandler(ch)

    return logger


# Configure the logger with the desired log level
# FAILED - only log failed tests
# PASSED - only log passed tests
# ALL - log all tests
# NO-LOGGING - disable logging
TEST_LOGGING_LEVEL: str = settings.TEST_LOGGING_LEVEL
logger = configure_test_logger()


class BaseTestcase(TestCase):
    test_counter: int = 1  # Class-level counter to track test numbers

    def _get_test_case_source(self, method_name: str) -> str:
        return f'{self.__class__.__name__} -> {method_name}'

    def log_test_result(self, passed: bool, input_data, expected_message: str, actual_message: str,
                        test_case_source: str, verbose_message: str = '', log_level: str = TEST_LOGGING_LEVEL):
        """Helper function to log the test result based on the TEST_LOGGING_LEVEL."""
        status = 'PASSED' if passed else 'FAILED'

        if log_level == 'NO-LOGGING':
            return  # Skip logging entirely

        if log_level == 'ALL' or (log_level == 'FAILED' and not passed) or (log_level == 'PASSED' and passed):
            test_number = BaseTestcase.test_counter
            logger.info(f'Test #{test_number}: {test_case_source}')
            logger.info(f'[{status}]')
            logger.info(f'Input values: {input_data}')
            logger.info(f'Expected result: {expected_message}')
            logger.info(f'Actual result: {actual_message}')
            if verbose_message:
                logger.info(f'Details: {verbose_message}')

            BaseTestcase.test_counter += 1
            logger.info('')  # Divider
            for handler in logger.handlers:
                handler.flush()

    def validate_and_log(self, serializer_class, input_data, expected_errors, test_case_source: str):
        """Handles validation and logging of results."""
        actual_errors = None
        expect_errors = bool(expected_errors)

        try:
            if expect_errors:
                # We expect validation to fail and raise a ValidationError
                try:
                    with self.assertRaises(serializers.ValidationError) as validation_error:
                        serializer = serializer_class(data=input_data)
                        serializer.is_valid(raise_exception=True)

                    actual_errors = validation_error.exception.detail
                except AssertionError:
                    self.fail(f'Expected ValidationError was not raised for input data: {input_data}')

                for field, expected_error in expected_errors.items():
                    actual_error = extract_error_detail(actual_errors, field)
                    
                    # Check if the error details match the expected errors
                    self.assertIn(field, actual_errors)
                    if isinstance(expected_error, list):
                        for expected_msg in expected_error:
                            self.assertIn(expected_msg, actual_error if isinstance(actual_error, list) else [actual_error])
                    else:
                        self.assertIn(expected_error, actual_error if isinstance(actual_error, list) else [actual_error])
            else:
                # We expect no errors, validation should pass
                serializer = serializer_class(data=input_data)
                is_valid = serializer.is_valid()
                self.assertTrue(is_valid)
                actual_errors = None  # Explicitly setting actual_errors to None when valid

            self.log_test_result(
                passed=True,
                input_data=input_data,
                expected_message=', '.join(expected_errors.values()) if expected_errors else 'No errors expected, validation passed',
                actual_message='Validation passed' if not expect_errors else ', '.join([str(extract_error_detail(actual_errors, field)) for field in expected_errors.keys()]),
                test_case_source=test_case_source
            )
        except AssertionError as e:
            self.log_test_result(
                passed=False,
                input_data=input_data,
                expected_message=', '.join(expected_errors.values()) if expected_errors else 'No errors expected, validation passed',
                actual_message=str(e),
                verbose_message=str(e),
                test_case_source=test_case_source
            )
