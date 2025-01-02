from copy import deepcopy
from inspect import currentframe
import json
from typing import Any, Dict, List

from django.conf import settings
from django.urls import reverse
from rest_framework import status

from the_wall_api.models import WallConfig, WallConfigReference, WallConfigStatusEnum
from the_wall_api.tests.test_views.base_test_views import BaseViewTest
from the_wall_api.tests.test_utils import generate_valid_values, invalid_input_groups
from the_wall_api.utils.api_utils import exposed_endpoints
from the_wall_api.utils.storage_utils import fetch_wall_data, manage_wall_config_file_upload
from the_wall_api.utils.wall_config_utils import CONCURRENT, hash_calc
from the_wall_api.wall_construction import get_sections_count, initialize_wall_data, WallConstruction


class CostAndUsageViewTestBase(BaseViewTest):

    @classmethod
    def setUpClass(cls, skip_test_data_creation: bool = False, *args, **kwargs):
        super().setUpClass(*args, **kwargs)
        if not skip_test_data_creation:
            cls.prepare_initial_usage_view_test_data()

    @classmethod
    def prepare_initial_usage_view_test_data(cls, init_wall_config_network: bool = True) -> None:
        """Ensure a proper test wall config object with all its network is created."""
        source = 'test_cost_and_usage_views'
        wall_config_file_upload_wall_data = initialize_wall_data(
            source=source, request_type='wallconfig-files/upload', user=cls.test_user,
            wall_config_file_data=cls.wall_construction_config, config_id=cls.valid_config_id
        )
        manage_wall_config_file_upload(wall_config_file_upload_wall_data)

        if init_wall_config_network:
            # Avoid usage of the wall config orchestration task, because it requires
            # a heavy initial setup. Instead, create only the test data synchronously.
            for num_crews in cls.get_valid_num_crews():
                num_crews_wall_data = initialize_wall_data(profile_id=None, day=None, request_num_crews=num_crews)
                num_crews_wall_data['wall_config_hash'] = wall_config_file_upload_wall_data['wall_config_hash']
                num_crews_wall_data['wall_construction_config'] = deepcopy(wall_config_file_upload_wall_data['initial_wall_construction_config'])
                num_crews_wall_data['sections_count'] = wall_config_file_upload_wall_data['sections_count']
                fetch_wall_data(num_crews_wall_data, num_crews, profile_id=None, request_type='create_wall_task')

    def setUp(self, *args, **kwargs):
        super().setUp(*args, **kwargs)
        # Load the wall profiles configuration to determine the maximum valid profile_id
        self.wall_config_hash = hash_calc(self.wall_construction_config)
        self.max_profile_id = len(self.wall_construction_config)
        self.max_days_per_profile = {
            index: settings.MAX_SECTION_HEIGHT - min(profile) for index, profile in enumerate(self.wall_construction_config, 1)
        }

    def get_valid_profile_ids(self) -> List[int]:
        return [int(pid) for pid in generate_valid_values() if int(pid) <= self.max_profile_id]

    def get_invalid_profile_ids(self) -> List[int]:
        return [int(pid) for pid in generate_valid_values() if int(pid) > self.max_profile_id]

    def get_valid_days_for_profile_sequential(self, profile_id: int) -> List[int]:
        max_day = self.max_days_per_profile.get(profile_id, 0)
        return [int(day) for day in generate_valid_values() if 1 <= int(day) <= max_day]

    def get_valid_days_for_profile_concurrent(self, valid_profile_id: int, valid_num_crews: int) -> List[int]:
        wall_construction = WallConstruction(
            wall_construction_config=self.wall_construction_config,
            sections_count=get_sections_count(self.wall_construction_config),
            num_crews=valid_num_crews,
            wall_config_hash=self.wall_config_hash,
            simulation_type=CONCURRENT
        )
        profile_days = wall_construction.sim_calc_details['profile_daily_details'][valid_profile_id]
        max_day = self.max_days_per_profile.get(valid_profile_id, 0)
        return [day for day in generate_valid_values() if isinstance(day, int) and min(profile_days) <= int(day) <= max_day]

    def get_invalid_days_for_profile_sequential(self, profile_id: int) -> List[int]:
        max_day = self.max_days_per_profile.get(profile_id, 0)
        return [day for day in generate_valid_values() if isinstance(day, int) and day > max_day]

    def get_invalid_days_for_profile_concurrent(self, valid_profile_id: int, valid_num_crews: int) -> List[int]:
        wall_construction = WallConstruction(
            wall_construction_config=self.wall_construction_config,
            sections_count=get_sections_count(self.wall_construction_config),
            num_crews=valid_num_crews,
            wall_config_hash=self.wall_config_hash,
            simulation_type=CONCURRENT
        )
        profile_days = wall_construction.sim_calc_details['profile_daily_details'][valid_profile_id]
        return [day for day in generate_valid_values() if isinstance(day, int) and day < min(profile_days)]

    @staticmethod
    def get_valid_num_crews() -> range:
        # Add 0 to test sequential mode
        valid_num_crews = range(0, 10, 2)
        return valid_num_crews

    def prepare_final_test_data(
        self, profile_id: int | None = None, day: int | None = None, num_crews: int | None = None,
        token: str | None = None, error_id_prefix: str = ''
    ) -> tuple[str, dict, dict]:
        url = self.prepare_url(profile_id, day)
        if token is None:
            token = self.valid_token

        query_params: Dict[str, Any] = {'config_id': self.valid_config_id}
        if num_crews is not None:
            query_params['num_crews'] = num_crews
        request_params = {
            'query_params': query_params,
            'headers': {
                'Authorization': f'Token {token}'
            }
        }
        if error_id_prefix:
            request_params['query_params']['test_data'] = json.dumps({'error_id_prefix': error_id_prefix})

        input_data = {
            key: value for key, value in [
                ('profile_id', profile_id), ('day', day), ('num_crews', num_crews), ('config_id', self.valid_config_id)
            ] if value is not None
        }

        return url, request_params, input_data

    def prepare_url(self, profile_id: int | None, day: int | None) -> str:
        if profile_id is not None and day is not None:
            return reverse(self.url_name, kwargs={'profile_id': profile_id, 'day': day})
        elif profile_id is not None:
            return reverse(self.url_name, kwargs={'profile_id': profile_id})
        return reverse(self.url_name)


class ProfilesDaysViewTest(CostAndUsageViewTestBase):
    description = 'Profiles Days View Tests'

    url_name = exposed_endpoints['profiles-days']['name']

    def test_profiles_days_valid(self, test_case_source=None, consistency_test=False):
        if test_case_source is None:
            test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        valid_profile_ids = self.get_valid_profile_ids()
        valid_num_crews = self.get_valid_num_crews()

        for profile_id in valid_profile_ids:
            for num_crews in valid_num_crews:
                if num_crews == 0:
                    valid_days = self.get_valid_days_for_profile_sequential(profile_id)
                else:
                    valid_days = self.get_valid_days_for_profile_concurrent(profile_id, num_crews)
                for day in valid_days:
                    with self.subTest(profile_id=profile_id, day=day, num_crews=num_crews):
                        self.execute_test_case(
                            self.client_get_method, status.HTTP_200_OK, test_case_source, consistency_test,
                            profile_id, day, num_crews,
                        )

    def test_profiles_days_results_consistency(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        self.test_profiles_days_valid(test_case_source=test_case_source, consistency_test=True)

    def test_profiles_days_invalid_profile_id(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        invalid_profile_ids = self.get_invalid_profile_ids()
        day = generate_valid_values()[0]
        num_crews = self.get_valid_num_crews()[0]

        for invalid_profile_id in invalid_profile_ids:
            with self.subTest(invalid_profile_id=invalid_profile_id):
                self.execute_test_case(
                    self.client_get_method, status.HTTP_400_BAD_REQUEST, test_case_source,
                    profile_id=invalid_profile_id, day=day, num_crews=num_crews
                )

    def test_profiles_days_invalid_day_sequential(self):
        """Test with days after the construction's completion day."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        profile_id = self.get_valid_profile_ids()[0]
        invalid_days = self.get_invalid_days_for_profile_sequential(profile_id)
        num_crews = 0

        for invalid_day in invalid_days:
            with self.subTest(invalid_day=invalid_day):
                self.execute_test_case(
                    self.client_get_method, status.HTTP_400_BAD_REQUEST, test_case_source,
                    profile_id=profile_id, day=invalid_day, num_crews=num_crews
                )

    def test_profiles_days_invalid_day_concurrent(self):
        """Test with days on which the profile was not worked on."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        profile_id = 2
        num_crews = 2
        invalid_days = self.get_invalid_days_for_profile_concurrent(profile_id, num_crews)

        for invalid_day in invalid_days:
            with self.subTest(invalid_day=invalid_day):
                self.execute_test_case(
                    self.client_get_method, status.HTTP_404_NOT_FOUND, test_case_source,
                    profile_id=profile_id, day=invalid_day, num_crews=num_crews
                )

    def test_profiles_days_invalid_num_crews(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        profile_id = self.get_valid_profile_ids()[0]
        day = self.get_valid_days_for_profile_sequential(profile_id)[0]

        for invalid_num_crews_group in invalid_input_groups['num_crews'].values():
            invalid_num_crews = invalid_num_crews_group[0]
            with self.subTest(invalid_num_crews=invalid_num_crews):
                self.execute_test_case(
                    self.client_get_method, status.HTTP_400_BAD_REQUEST, test_case_source,
                    profile_id=profile_id, day=day, num_crews=invalid_num_crews
                )


class CostOverviewViewTest(CostAndUsageViewTestBase):
    description = 'Cost Overview View Tests'

    url_name = exposed_endpoints['cost-overview']['name']

    def test_cost_overview_valid(self, test_case_source=None, consistency_test=False):
        if test_case_source is None:
            test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        num_crews = 0

        self.execute_test_case(
            self.client_get_method, status.HTTP_200_OK, test_case_source, num_crews=num_crews,
            consistency_test=consistency_test
        )

    def test_cost_overview_results_consistency(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        self.test_cost_overview_valid(test_case_source=test_case_source, consistency_test=True)


class CostOverviewProfileidViewTest(CostAndUsageViewTestBase):
    description = 'Cost Overview Profileid View Tests'

    url_name = exposed_endpoints['cost-overview-profile']['name']

    def test_cost_overview_profileid_valid(self, test_case_source=None, consistency_test=False):
        if test_case_source is None:
            test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        valid_profile_ids = self.get_valid_profile_ids()
        num_crews = 0

        for profile_id in valid_profile_ids:
            with self.subTest(profile_id=profile_id, num_crews=num_crews):
                self.execute_test_case(
                    self.client_get_method, status.HTTP_200_OK, test_case_source, profile_id=profile_id,
                    num_crews=num_crews, consistency_test=consistency_test
                )

    def test_cost_overview_profileid_results_consistency(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        self.test_cost_overview_profileid_valid(test_case_source=test_case_source, consistency_test=True)

    def test_cost_overview_profileid_invalid_profile_id(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        invalid_profile_ids = self.get_invalid_profile_ids()
        num_crews = 0

        for invalid_profile_id in invalid_profile_ids:
            with self.subTest(invalid_profile_id=invalid_profile_id, num_crews=num_crews):
                self.execute_test_case(
                    self.client_get_method, status.HTTP_400_BAD_REQUEST, test_case_source,
                    profile_id=invalid_profile_id, num_crews=num_crews
                )


class AbnormalCasesProfilesDaysViewTest(CostAndUsageViewTestBase):
    description = 'Abnormal Daily Ice Usage View Tests'

    url_name = exposed_endpoints['profiles-days']['name']

    @classmethod
    def setUpClass(cls, *args, **kwargs):
        # Initialize the test data separately for each test
        super().setUpClass(skip_test_data_creation=True, *args, **kwargs)

    def setUp(self):
        super().setUp()
        self.prepare_initial_usage_view_test_data(init_wall_config_network=False)
        self.profile_id = 1
        self.day = 1
        self.num_crews = 1

    def test_missing_user_file_reference(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        # Simulate a missing user file reference
        WallConfigReference.objects.get(user=self.test_user, config_id=self.valid_config_id).delete()

        self.execute_test_case(
            self.client_get_method, status.HTTP_404_NOT_FOUND, test_case_source,
            profile_id=self.profile_id, day=self.day, num_crews=self.num_crews
        )

    def test_missing_wall_config_object(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        # Simulate an erroneous wall config object
        WallConfig.objects.filter(wall_config_hash=self.wall_config_hash).update(status=WallConfigStatusEnum.ERROR)

        self.execute_test_case(
            self.client_get_method, status.HTTP_409_CONFLICT, test_case_source,
            profile_id=self.profile_id, day=self.day, num_crews=self.num_crews, error_id_prefix=f'{test_case_source}_'
        )

    def test_invalid_token(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        self.execute_test_case(
            self.client_get_method, status.HTTP_401_UNAUTHORIZED, test_case_source,
            profile_id=self.profile_id, day=self.day, num_crews=self.num_crews, token=self.invalid_token
        )


class AbnormalCostOverviewProfileidViewTest(AbnormalCasesProfilesDaysViewTest):
    description = 'Abnormal Cost Overview Profileid View Tests'

    url_name = exposed_endpoints['cost-overview-profile']['name']

    def setUp(self):
        super().setUp()
        self.profile_id = 1
        self.day = None
        self.num_crews = None


class AbnormalCostOverviewViewTest(AbnormalCasesProfilesDaysViewTest):
    description = 'Abnormal Cost Overview View Tests'

    url_name = exposed_endpoints['cost-overview']['name']

    def setUp(self):
        super().setUp()
        self.profile_id = None
        self.day = None
        self.num_crews = None
