from inspect import currentframe
from typing import List, Literal

from django.conf import settings
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status

from the_wall_api.tests.test_utils import BaseTestcase, generate_valid_values, invalid_input_groups
from the_wall_api.utils.api_utils import exposed_endpoints
from the_wall_api.utils.wall_config_utils import load_wall_profiles_from_config, CONCURRENT
from the_wall_api.wall_construction import WallConstruction


class ViewTest(BaseTestcase):
    
    url_name = None

    def setUp(self):
        # Load the wall profiles configuration to determine the maximum valid profile_id
        self.wall_construction_config = load_wall_profiles_from_config()
        self.max_profile_id = len(self.wall_construction_config)
        self.max_days_per_profile = {
            index + 1: settings.MAX_HEIGHT - min(profile) for index, profile in enumerate(self.wall_construction_config)
        }

    def get_valid_profile_ids(self) -> List[int]:
        return [int(pid) for pid in generate_valid_values() if int(pid) <= self.max_profile_id]

    def get_invalid_profile_ids(self) -> List[int]:
        return [int(pid) for pid in generate_valid_values() if int(pid) > self.max_profile_id]

    def get_valid_days_for_profile(self, profile_id: int) -> List[int]:
        max_day = self.max_days_per_profile.get(profile_id, 0)
        return [int(day) for day in generate_valid_values() if 1 <= int(day) <= max_day]

    def get_invalid_days_for_profile_sequential(self, profile_id: int) -> List[int]:
        max_day = self.max_days_per_profile.get(profile_id, 0)
        return [day for day in generate_valid_values() if isinstance(day, int) and day > max_day]
    
    def get_invalid_days_for_profile_concurrent(self, valid_profile_id: int, valid_num_crews: int) -> List[int]:
        wall_construction = WallConstruction(
            wall_construction_config=self.wall_construction_config,
            sections_count=sum(len(profile) for profile in self.wall_construction_config),
            num_crews=valid_num_crews,
            simulation_type=CONCURRENT
        )
        profile_days = wall_construction.sim_calc_details['profile_daily_details'][valid_profile_id]
        return [day for day in generate_valid_values() if isinstance(day, int) and day < min(profile_days)]

    def get_valid_num_crews(self) -> range:
        # Add 0 to test sequential mode
        valid_num_crews = range(0, 10, 2)
        return valid_num_crews
    
    def execute_test_case(
        self, expected_status: Literal[200, 400, 404], test_case_source: str, profile_id: int | None = None,
        day: int | None = None, num_crews: int | None = None, consistency_test: bool = False
    ) -> None:
        url = self.prepare_url(profile_id, day)
        params = {'num_crews': num_crews} if num_crews is not None else {}
        input_data = {key: value for key, value in [('profile_id', profile_id), ('day', day), ('num_crews', num_crews)] if value is not None}

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

    def prepare_url(self, profile_id: int | None, day: int | None) -> str:
        if profile_id is not None and day is not None:
            return reverse(self.url_name, kwargs={'profile_id': profile_id, 'day': day})
        elif profile_id is not None:
            return reverse(self.url_name, kwargs={'profile_id': profile_id})
        return reverse(self.url_name)

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


class DailyIceUsageViewTest(ViewTest):
    description = 'Daily Ice Usage View Tests'
    
    url_name = exposed_endpoints['daily-ice-usage']['name']

    def test_daily_ice_usage_valid(self, test_case_source=None, consistency_test=False):
        if test_case_source is None:
            test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore
        valid_profile_ids = self.get_valid_profile_ids()
        valid_num_crews = self.get_valid_num_crews()

        for profile_id in valid_profile_ids:
            valid_days = self.get_valid_days_for_profile(profile_id)
            for day in valid_days:
                for num_crews in valid_num_crews:
                    with self.subTest(profile_id=profile_id, day=day, num_crews=num_crews):
                        self.execute_test_case(
                            status.HTTP_200_OK, test_case_source, profile_id, day, num_crews,
                            consistency_test=consistency_test
                        )

    def test_daily_ice_usage_results_consistency(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore
        self.test_daily_ice_usage_valid(test_case_source=test_case_source, consistency_test=True)
    
    def test_daily_ice_usage_invalid_profile_id(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore
        invalid_profile_ids = self.get_invalid_profile_ids()
        day = generate_valid_values()[0]
        num_crews = self.get_valid_num_crews()[0]

        for invalid_profile_id in invalid_profile_ids:
            with self.subTest(invalid_profile_id=invalid_profile_id):
                self.execute_test_case(status.HTTP_400_BAD_REQUEST, test_case_source, invalid_profile_id, day, num_crews)
    
    def test_daily_ice_usage_invalid_day_sequential(self):
        """Test with days after the construction's completion day."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore
        profile_id = self.get_valid_profile_ids()[0]
        invalid_days = self.get_invalid_days_for_profile_sequential(profile_id)
        num_crews = 0

        for invalid_day in invalid_days:
            with self.subTest(invalid_day=invalid_day):
                self.execute_test_case(status.HTTP_400_BAD_REQUEST, test_case_source, profile_id, invalid_day, num_crews)
    
    def test_daily_ice_usage_invalid_day_concurrent(self):
        """Test with days on which the profile was not worked on."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore
        profile_id = 2
        num_crews = 1
        invalid_days = self.get_invalid_days_for_profile_concurrent(profile_id, num_crews)

        for invalid_day in invalid_days:
            with self.subTest(invalid_day=invalid_day):
                self.execute_test_case(status.HTTP_404_NOT_FOUND, test_case_source, profile_id, invalid_day, num_crews)
    
    def test_daily_ice_usage_invalid_num_crews(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore
        profile_id = self.get_valid_profile_ids()[0]
        day = self.get_valid_days_for_profile(profile_id)[0]

        for invalid_num_crews_group in invalid_input_groups['num_crews'].values():
            invalid_num_crews = invalid_num_crews_group[0]
            with self.subTest(invalid_num_crews=invalid_num_crews):
                self.execute_test_case(status.HTTP_400_BAD_REQUEST, test_case_source, profile_id, day, invalid_num_crews)


class CostOverviewViewTest(ViewTest):
    description = 'Cost Overview View Tests'
    
    url_name = exposed_endpoints['cost-overview']['name']

    def test_cost_overview_valid(self, test_case_source=None, consistency_test=False):
        if test_case_source is None:
            test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore
        valid_num_crews = self.get_valid_num_crews()

        for num_crews in valid_num_crews:
            with self.subTest(num_crews=num_crews):
                self.execute_test_case(
                    status.HTTP_200_OK, test_case_source, num_crews=num_crews,
                    consistency_test=consistency_test
                )

    def test_cost_overview_results_consistency(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore
        self.test_cost_overview_valid(test_case_source=test_case_source, consistency_test=True)

    def test_cost_overview_invalid_num_crews(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore

        for invalid_num_crews_group in invalid_input_groups['num_crews'].values():
            invalid_num_crews = invalid_num_crews_group[0]
            with self.subTest(invalid_num_crews=invalid_num_crews):
                self.execute_test_case(status.HTTP_400_BAD_REQUEST, test_case_source, num_crews=invalid_num_crews)


class CostOverviewProfileidViewTest(ViewTest):
    description = 'Cost Overview Profileid View Tests'
    
    url_name = exposed_endpoints['cost-overview-profile']['name']

    def test_cost_overview_profileid_valid(self, test_case_source=None, consistency_test=False):
        if test_case_source is None:
            test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore
        valid_profile_ids = self.get_valid_profile_ids()
        valid_num_crews = self.get_valid_num_crews()

        for profile_id in valid_profile_ids:
            for num_crews in valid_num_crews:
                with self.subTest(profile_id=profile_id, num_crews=num_crews):
                    self.execute_test_case(
                        status.HTTP_200_OK, test_case_source, profile_id=profile_id, num_crews=num_crews,
                        consistency_test=consistency_test
                    )

    def test_cost_overview_profileid_results_consistency(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore
        self.test_cost_overview_profileid_valid(test_case_source=test_case_source, consistency_test=True)

    def test_cost_overview_profileid_invalid_profile_id(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore
        invalid_profile_ids = self.get_invalid_profile_ids()
        valid_num_crews = self.get_valid_num_crews()

        for invalid_profile_id in invalid_profile_ids:
            for num_crews in valid_num_crews:
                with self.subTest(invalid_profile_id=invalid_profile_id, num_crews=num_crews):
                    self.execute_test_case(status.HTTP_400_BAD_REQUEST, test_case_source, profile_id=invalid_profile_id, num_crews=num_crews)
    
    def test_cost_overview_profileid_invalid_num_crews(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore
        profile_id = self.get_valid_profile_ids()[0]

        for invalid_num_crews_group in invalid_input_groups['num_crews'].values():
            invalid_num_crews = invalid_num_crews_group[0]
            with self.subTest(invalid_num_crews=invalid_num_crews):
                self.execute_test_case(status.HTTP_400_BAD_REQUEST, test_case_source, profile_id=profile_id, num_crews=invalid_num_crews)
