from inspect import currentframe
from the_wall_api.serializers import CostOverviewRequestSerializer, DailyIceUsageRequestSerializer
from the_wall_api.tests.test_utils import BaseTestcase, generate_valid_values, invalid_input_groups


class CostOverviewRequestSerializerTest(BaseTestcase):

    def test_profile_id_valid(self):
        valid_values = generate_valid_values()
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore

        for profile_id in valid_values:
            input_data = {'profile_id': profile_id}
            expected_errors = {}
            self.validate_and_log(CostOverviewRequestSerializer, input_data, expected_errors, test_case_source)

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
                self.validate_and_log(CostOverviewRequestSerializer, input_data, expected_errors, test_case_source)

    def test_num_crews_valid(self):
        valid_values = generate_valid_values()
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore

        for num_crews in valid_values:
            input_data = {'num_crews': num_crews}
            expected_errors = {}
            self.validate_and_log(CostOverviewRequestSerializer, input_data, expected_errors, test_case_source)

    def test_num_crews_invalid(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore

        for error_message, values in invalid_input_groups['num_crews'].items():
            for value in values:
                input_data = {'num_crews': value}
                expected_errors = {'num_crews': error_message}
                self.validate_and_log(CostOverviewRequestSerializer, input_data, expected_errors, test_case_source)


class DailyIceUsageRequestSerializerTest(BaseTestcase):

    def test_both_fields_valid(self):
        valid_values = generate_valid_values()
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore

        for profile_id in valid_values:
            for day in valid_values:
                input_data = {'profile_id': profile_id, 'day': day}
                expected_errors = {}
                self.validate_and_log(DailyIceUsageRequestSerializer, input_data, expected_errors, test_case_source)

    def test_only_day_valid(self):
        valid_values = generate_valid_values()
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore

        for error_message, values in invalid_input_groups['profile_id'].items():
            for value in values:
                for day in valid_values:
                    input_data = {'profile_id': value, 'day': day}
                    expected_errors = {'profile_id': error_message}
                    self.validate_and_log(DailyIceUsageRequestSerializer, input_data, expected_errors, test_case_source)

    def test_only_profile_id_valid(self):
        valid_values = generate_valid_values()
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore

        for error_message, values in invalid_input_groups['day'].items():
            for value in values:
                for profile_id in valid_values:
                    input_data = {'profile_id': profile_id, 'day': value}
                    expected_errors = {'day': error_message}
                    self.validate_and_log(DailyIceUsageRequestSerializer, input_data, expected_errors, test_case_source)

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
                        self.validate_and_log(DailyIceUsageRequestSerializer, input_data, expected_errors, test_case_source)

    def test_num_crews_valid(self):
        valid_values = generate_valid_values()
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore

        for profile_id in valid_values:
            for day in valid_values:
                for num_crews in valid_values:
                    input_data = {'profile_id': profile_id, 'day': day, 'num_crews': num_crews}
                    expected_errors = {}
                    self.validate_and_log(DailyIceUsageRequestSerializer, input_data, expected_errors, test_case_source)

    def test_num_crews_invalid(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore

        for profile_id in generate_valid_values():
            for day in generate_valid_values():
                for error_message, values in invalid_input_groups['num_crews'].items():
                    for value in values:
                        input_data = {'profile_id': profile_id, 'day': day, 'num_crews': value}
                        expected_errors = {'num_crews': error_message}
                        self.validate_and_log(DailyIceUsageRequestSerializer, input_data, expected_errors, test_case_source)
