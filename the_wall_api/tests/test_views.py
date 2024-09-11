from django.conf import settings
from django.urls import reverse
from rest_framework import status
from inspect import currentframe

from the_wall_api.tests.test_utils import BaseTestcase, generate_valid_values, invalid_input_groups
from the_wall_api.utils import load_wall_profiles_from_config, MULTI_THREADED
from the_wall_api.wall_construction import WallConstruction


class BaseWallProfileTest(BaseTestcase):

    def setUp(self):
        # Load the wall profiles configuration to determine the maximum valid profile_id
        self.wall_construction_config = load_wall_profiles_from_config()
        self.max_profile_id = len(self.wall_construction_config)
        self.max_days_per_profile = {
            index + 1: settings.MAX_HEIGHT - min(profile) for index, profile in enumerate(self.wall_construction_config)
        }
        pass

    def get_valid_profile_ids(self):
        return [int(pid) for pid in generate_valid_values() if int(pid) <= self.max_profile_id]

    def get_invalid_profile_ids(self):
        return [int(pid) for pid in generate_valid_values() if int(pid) > self.max_profile_id]

    def get_valid_days_for_profile(self, profile_id):
        max_day = self.max_days_per_profile.get(profile_id, 0)
        return [int(day) for day in generate_valid_values() if 1 <= int(day) <= max_day]

    def get_invalid_days_for_profile_single_threaded(self, profile_id):
        max_day = self.max_days_per_profile.get(profile_id, 0)
        return [day for day in generate_valid_values() if isinstance(day, int) and day > max_day]
    
    def get_invalid_days_for_profile_multi_threaded(self, valid_profile_id, valid_num_crews):
        wall_construction = WallConstruction(
            wall_construction_config=self.wall_construction_config,
            sections_count=sum(len(profile) for profile in self.wall_construction_config),
            num_crews=valid_num_crews,
            simulation_type=MULTI_THREADED
        )
        profile_days = wall_construction.sim_calc_details['profile_daily_details'][valid_profile_id]
        return [day for day in generate_valid_values() if isinstance(day, int) and day < min(profile_days)]

    def get_valid_num_crews(self):
        return [value for value in generate_valid_values()]


class DailyIceUsageViewTest(BaseWallProfileTest):
    description = 'Daily Ice Usage View Tests'

    def test_daily_ice_usage_valid(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore
        valid_profile_ids = self.get_valid_profile_ids()
        valid_num_crews = self.get_valid_num_crews()

        for profile_id in valid_profile_ids:
            valid_days = self.get_valid_days_for_profile(profile_id)
            for day in valid_days:
                for num_crews in valid_num_crews:
                    self._execute_test_case(profile_id, day, num_crews, status.HTTP_200_OK, test_case_source)

    def test_daily_ice_usage_invalid_profile_id(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore
        invalid_profile_ids = self.get_invalid_profile_ids()
        valid_days = generate_valid_values()
        valid_num_crews = self.get_valid_num_crews()

        for profile_id in invalid_profile_ids:
            self._execute_test_case(profile_id, valid_days[0], valid_num_crews[0], status.HTTP_400_BAD_REQUEST, test_case_source)
    
    def test_daily_ice_usage_invalid_day_single_threaded(self):
        """Test with days after the construction's completion day."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore
        valid_profile_id = self.get_valid_profile_ids()[0]
        invalid_days = self.get_invalid_days_for_profile_single_threaded(valid_profile_id)
        num_crews = 0

        for day in invalid_days:
            self._execute_test_case(valid_profile_id, day, num_crews, status.HTTP_400_BAD_REQUEST, test_case_source)
    
    def test_daily_ice_usage_invalid_day_multi_threaded(self):
        """Test with days on which the profile was not worked on."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore
        valid_profile_id = 2
        valid_num_crews = self.get_valid_num_crews()[0]
        invalid_days = self.get_invalid_days_for_profile_multi_threaded(valid_profile_id, valid_num_crews)

        for day in invalid_days:
            self._execute_test_case(valid_profile_id, day, valid_num_crews, status.HTTP_404_NOT_FOUND, test_case_source)

    def _execute_test_case(self, profile_id, day, num_crews, expected_status, test_case_source):
        url = reverse('daily-ice-usage-v1', kwargs={'profile_id': profile_id, 'day': day})
        response = self.client.get(url, {'num_crews': num_crews})
        passed = response.status_code == expected_status
        self.log_test_result(
            passed=passed,
            input_data={'profile_id': profile_id, 'day': day, 'num_crews': num_crews},
            expected_message=expected_status,
            actual_message=str(response.status_code),
            test_case_source=test_case_source
        )


class CostOverviewViewTest(BaseWallProfileTest):
    description = 'Cost Overview View Tests'

    def test_cost_overview_valid(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore
        valid_num_crews = self.get_valid_num_crews()

        for num_crews in valid_num_crews:
            self._execute_test_case(None, num_crews, status.HTTP_200_OK, test_case_source)

    def test_cost_overview_invalid_num_crews(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore

        for _, invalid_num_crews in invalid_input_groups['num_crews'].items():
            for num_crews in invalid_num_crews:
                if num_crews in ({}, []):  # Skip {} and [] in invalid checks - the serializer validates num_crews for them
                    continue
                self._execute_test_case(None, num_crews, status.HTTP_400_BAD_REQUEST, test_case_source)

    def _execute_test_case(self, profile_id, num_crews, expected_status, test_case_source):
        url = reverse('cost-overview-v1')
        response = self.client.get(url, {'num_crews': num_crews})
        passed = response.status_code == expected_status
        self.log_test_result(
            passed=passed,
            input_data={'profile_id': profile_id, 'num_crews': num_crews},
            expected_message=expected_status,
            actual_message=str(response.status_code),
            test_case_source=test_case_source
        )


class CostOverviewProfileidViewTest(CostOverviewViewTest):
    description = 'Cost Overview Profileid View Tests'

    def test_cost_overview_profileid_valid(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore
        valid_profile_ids = self.get_valid_profile_ids()
        valid_num_crews = self.get_valid_num_crews()

        for profile_id in valid_profile_ids:
            for num_crews in valid_num_crews:
                self._execute_profileid_test_case(profile_id, num_crews, status.HTTP_200_OK, test_case_source)

    def test_cost_overview_profileid_invalid_profile_id(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore
        invalid_profile_ids = self.get_invalid_profile_ids()
        valid_num_crews = self.get_valid_num_crews()

        for profile_id in invalid_profile_ids:
            for num_crews in valid_num_crews:
                self._execute_profileid_test_case(profile_id, num_crews, status.HTTP_400_BAD_REQUEST, test_case_source)

    def _execute_profileid_test_case(self, profile_id, num_crews, expected_status, test_case_source):
        url = reverse('cost-overview-profile-v1', kwargs={'profile_id': profile_id})
        response = self.client.get(url, {'num_crews': num_crews})
        passed = response.status_code == expected_status
        self.log_test_result(
            passed=passed,
            input_data={'profile_id': profile_id, 'num_crews': num_crews},
            expected_message=expected_status,
            actual_message=str(response.status_code),
            test_case_source=test_case_source
        )
