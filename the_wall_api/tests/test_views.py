from django.urls import reverse
from rest_framework import status
from inspect import currentframe

from the_wall_api.tests.test_utils import BaseTestcase, generate_valid_values, invalid_input_groups
from the_wall_api.utils import load_wall_profiles_from_config


class BaseWallProfileTest(BaseTestcase):

    def setUp(self):
        # Load the wall profiles configuration to determine the maximum valid profile_id
        self.wall_construction_config = load_wall_profiles_from_config()
        self.max_profile_id = len(self.wall_construction_config)
        self.max_days_per_profile = {index + 1: len(profile) for index, profile in enumerate(self.wall_construction_config)}

    def get_valid_profile_ids(self):
        return [int(pid) for pid in generate_valid_values() if int(pid) <= self.max_profile_id]

    def get_invalid_profile_ids(self):
        return [int(pid) for pid in generate_valid_values() if int(pid) > self.max_profile_id]

    def get_valid_days_for_profile(self, profile_id):
        max_day = self.max_days_per_profile.get(profile_id, 0)
        return [int(day) for day in generate_valid_values() if 1 <= int(day) <= max_day]

    def get_invalid_days_for_profile(self, profile_id):
        max_day = self.max_days_per_profile.get(profile_id, 0)
        return [int(day) for day in generate_valid_values() if int(day) > max_day]

    def get_valid_num_crews(self):
        """Filter out {} and [] values from valid num_crews."""
        return [value for value in generate_valid_values() if value not in ({}, [])]

    def get_status_name(self, status_code):
        """Helper to convert status code to human-readable name."""
        return {
            200: 'OK',
            400: 'BAD REQUEST',
            500: 'INTERNAL SERVER ERROR',
            # Add more status codes as needed
        }.get(status_code, 'UNKNOWN STATUS')


class DailyIceUsageViewTest(BaseWallProfileTest):

    def test_daily_ice_usage_valid(self):
        valid_profile_ids = self.get_valid_profile_ids()
        valid_num_crews = self.get_valid_num_crews()
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore

        for profile_id in valid_profile_ids:
            valid_days = self.get_valid_days_for_profile(profile_id)
            for day in valid_days:
                for num_crews in valid_num_crews:
                    self._execute_test_case(profile_id, day, num_crews, status.HTTP_200_OK, test_case_source)

    def test_daily_ice_usage_invalid_profile_id(self):
        invalid_profile_ids = self.get_invalid_profile_ids()
        valid_days = generate_valid_values()  # Use general valid day values, since profile_id itself is invalid
        valid_num_crews = self.get_valid_num_crews()
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore

        for profile_id in invalid_profile_ids:
            for day in valid_days:
                for num_crews in valid_num_crews:
                    self._execute_test_case(profile_id, day, num_crews, status.HTTP_400_BAD_REQUEST, test_case_source)

    def _execute_test_case(self, profile_id, day, num_crews, expected_status, test_case_source):
        url = reverse('daily-ice-usage-v1', kwargs={'profile_id': profile_id, 'day': day})
        response = self.client.get(url, {'num_crews': num_crews})
        passed = response.status_code == expected_status
        expected_message = f'HTTP {expected_status} {self.get_status_name(expected_status)}'
        self.log_test_result(
            passed=passed,
            input_data={'profile_id': profile_id, 'day': day, 'num_crews': num_crews},
            expected_message=expected_message,
            actual_message=str(response.status_code),
            test_case_source=test_case_source
        )


class CostOverviewViewTest(BaseWallProfileTest):

    def test_cost_overview_valid(self):
        valid_num_crews = self.get_valid_num_crews()
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore

        for num_crews in valid_num_crews:
            self._execute_test_case(None, num_crews, status.HTTP_200_OK, test_case_source)

    def test_cost_overview_invalid_num_crews(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore

        for error_message, values in invalid_input_groups['num_crews'].items():
            for num_crews in values:
                if num_crews in ({}, []):  # Skip {} and [] in invalid checks - the serializer validates num_crews for them
                    continue
                self._execute_test_case(None, num_crews, status.HTTP_400_BAD_REQUEST, test_case_source)

    def _execute_test_case(self, profile_id, num_crews, expected_status, test_case_source):
        url = reverse('cost-overview-v1')
        response = self.client.get(url, {'num_crews': num_crews})
        passed = response.status_code == expected_status
        expected_message = f'HTTP {expected_status} {self.get_status_name(expected_status)}'
        self.log_test_result(
            passed=passed,
            input_data={'profile_id': profile_id, 'num_crews': num_crews},
            expected_message=expected_message,
            actual_message=str(response.status_code),
            test_case_source=test_case_source
        )


class CostOverviewProfileidViewTest(CostOverviewViewTest):

    def test_cost_overview_profileid_valid(self):
        valid_profile_ids = self.get_valid_profile_ids()
        valid_num_crews = self.get_valid_num_crews()
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore

        for profile_id in valid_profile_ids:
            for num_crews in valid_num_crews:
                self._execute_profileid_test_case(profile_id, num_crews, status.HTTP_200_OK, test_case_source)

    def test_cost_overview_profileid_invalid_profile_id(self):
        invalid_profile_ids = self.get_invalid_profile_ids()
        valid_num_crews = self.get_valid_num_crews()
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore

        for profile_id in invalid_profile_ids:
            for num_crews in valid_num_crews:
                self._execute_profileid_test_case(profile_id, num_crews, status.HTTP_400_BAD_REQUEST, test_case_source)

    def _execute_profileid_test_case(self, profile_id, num_crews, expected_status, test_case_source):
        url = reverse('cost-overview-profile-v1', kwargs={'profile_id': profile_id})
        response = self.client.get(url, {'num_crews': num_crews})
        passed = response.status_code == expected_status
        expected_message = f'HTTP {expected_status} {self.get_status_name(expected_status)}'
        self.log_test_result(
            passed=passed,
            input_data={'profile_id': profile_id, 'num_crews': num_crews},
            expected_message=expected_message,
            actual_message=str(response.status_code),
            test_case_source=test_case_source
        )
