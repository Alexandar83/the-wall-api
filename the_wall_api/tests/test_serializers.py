from inspect import currentframe

from rest_framework import serializers

from the_wall_api.serializers import CostOverviewSerializer, DailyIceUsageSerializer
from the_wall_api.tests.test_utils import BaseTestcase, generate_valid_values, invalid_input_groups


def extract_error_detail(actual_errors, field_name: str):
    """Helper function to extract error details safely."""
    if isinstance(actual_errors, dict):
        error_detail = actual_errors.get(field_name, None)
        if isinstance(error_detail, list):
            return error_detail[0] if error_detail else None
        return error_detail
    else:
        return str(actual_errors)  # Fallback to string representation if structure is unexpected


class SerializerTest(BaseTestcase):

    def validate_and_log(self, serializer_class, input_data, expected_errors, test_case_source: str) -> None:
        """Handles validation and logging of results."""
        actual_errors = None
        expect_errors = bool(expected_errors)
        serializer = serializer_class(data=input_data)

        try:
            if expect_errors:
                # We expect validation to fail and raise a ValidationError
                validation_error = self.validate_with_errors(serializer, input_data)
                actual_errors = validation_error.exception.detail
            else:
                # We expect no errors, validation should pass
                self.validate_without_errors(serializer)
                actual_errors = None

            self.log_test_serializer_result(True, input_data, expected_errors, actual_errors, test_case_source)

        except AssertionError as e:
            self.log_test_serializer_result(False, input_data, expected_errors, str(e), test_case_source)

    def validate_with_errors(self, serializer, input_data):
        try:
            with self.assertRaises(serializers.ValidationError) as validation_error:
                serializer.is_valid(raise_exception=True)
        except AssertionError:
            self.fail(f'Expected ValidationError was not raised for input data: {input_data}')
        
        return validation_error

    def validate_without_errors(self, serializer):
        is_valid = serializer.is_valid()
        self.assertTrue(is_valid)

    def extract_actual_errors(self, serializer, expected_errors):
        actual_errors = serializer.errors
        for field, expected_error in expected_errors.items():
            actual_error = extract_error_detail(actual_errors, field)
            self.assert_error_matches(field, expected_error, actual_error)
        return actual_errors

    def assert_error_matches(self, field, expected_error, actual_error):
        self.assertIn(field, actual_error)
        if isinstance(expected_error, list):
            for expected_msg in expected_error:
                self.assertIn(expected_msg, actual_error if isinstance(actual_error, list) else [actual_error])
        else:
            self.assertIn(expected_error, actual_error if isinstance(actual_error, list) else [actual_error])

    def log_test_serializer_result(self, passed, input_data, expected_errors, actual_errors, test_case_source):
        expected_message = ', '.join(expected_errors.values()) if expected_errors else 'No errors expected, validation passed'
        actual_message = 'Validation passed' if not actual_errors else ', '.join(
            [str(extract_error_detail(actual_errors, field)) for field in expected_errors.keys()]
        )
        self.log_test_result(passed, input_data, expected_message, actual_message, test_case_source)


class CostOverviewSerializerTest(SerializerTest):
    description = 'Cost overview serializer tests'

    def test_profile_id_valid(self):
        valid_values = generate_valid_values()
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore

        for profile_id in valid_values:
            input_data = {'profile_id': profile_id}
            expected_errors = {}
            self.validate_and_log(CostOverviewSerializer, input_data, expected_errors, test_case_source)

    def test_profile_id_invalid(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore

        for error_message, values in invalid_input_groups['profile_id'].items():
            for value in values:
                # CostOverview: profile_id is optional and None is a properly handled value
                # DailyIceUsage: profile_id is required, but:
                #   -api/v1/daily-ice-usage/null/5/ -> is parsed as a 'null' in the GET method
                #   -api/v1/daily-ice-usage/?day=5&profile_id=None -> leads to Page not found (404)
                if value is None:
                    continue
                input_data = {'profile_id': value}
                expected_errors = {'profile_id': error_message}
                self.validate_and_log(CostOverviewSerializer, input_data, expected_errors, test_case_source)

    def test_num_crews_valid(self):
        valid_values = generate_valid_values()
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore

        for num_crews in valid_values:
            input_data = {'num_crews': num_crews}
            expected_errors = {}
            self.validate_and_log(CostOverviewSerializer, input_data, expected_errors, test_case_source)

    def test_num_crews_invalid(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore

        for error_message, values in invalid_input_groups['num_crews'].items():
            for value in values:
                input_data = {'num_crews': value}
                expected_errors = {'num_crews': error_message}
                self.validate_and_log(CostOverviewSerializer, input_data, expected_errors, test_case_source)


class DailyIceUsageSerializerTest(SerializerTest):
    description = 'Daily ice usage serializer tests'

    def test_both_fields_valid(self):
        valid_values = generate_valid_values()
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore

        for profile_id in valid_values:
            for day in valid_values:
                input_data = {'profile_id': profile_id, 'day': day}
                expected_errors = {}
                self.validate_and_log(DailyIceUsageSerializer, input_data, expected_errors, test_case_source)

    def test_only_day_valid(self):
        valid_values = generate_valid_values()
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore

        for error_message, values in invalid_input_groups['profile_id'].items():
            for value in values:
                for day in valid_values:
                    input_data = {'profile_id': value, 'day': day}
                    expected_errors = {'profile_id': error_message}
                    self.validate_and_log(DailyIceUsageSerializer, input_data, expected_errors, test_case_source)

    def test_only_profile_id_valid(self):
        valid_values = generate_valid_values()
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore

        for error_message, values in invalid_input_groups['day'].items():
            for value in values:
                for profile_id in valid_values:
                    input_data = {'profile_id': profile_id, 'day': value}
                    expected_errors = {'day': error_message}
                    self.validate_and_log(DailyIceUsageSerializer, input_data, expected_errors, test_case_source)

    def test_both_fields_invalid(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore

        for profile_error_message, profile_values in invalid_input_groups['profile_id'].items():
            for day_error_message, day_values in invalid_input_groups['day'].items():
                for profile_value in profile_values:
                    for day_value in day_values:
                        input_data = {'profile_id': profile_value, 'day': day_value}
                        expected_errors = {
                            'profile_id': profile_error_message,
                            'day': day_error_message,
                        }
                        self.validate_and_log(DailyIceUsageSerializer, input_data, expected_errors, test_case_source)

    def test_num_crews_valid(self):
        valid_values = generate_valid_values()
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore

        for profile_id in valid_values:
            for day in valid_values:
                for num_crews in valid_values:
                    input_data = {'profile_id': profile_id, 'day': day, 'num_crews': num_crews}
                    expected_errors = {}
                    self.validate_and_log(DailyIceUsageSerializer, input_data, expected_errors, test_case_source)

    def test_num_crews_invalid(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore

        for profile_id in generate_valid_values():
            for day in generate_valid_values():
                for error_message, values in invalid_input_groups['num_crews'].items():
                    for value in values:
                        input_data = {'profile_id': profile_id, 'day': day, 'num_crews': value}
                        expected_errors = {'num_crews': error_message}
                        self.validate_and_log(DailyIceUsageSerializer, input_data, expected_errors, test_case_source)
