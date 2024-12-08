from typing import Any
from inspect import currentframe

from django.conf import settings
from django.test.utils import override_settings

from the_wall_api.utils.api_utils import exposed_endpoints
from the_wall_api.utils.open_api_schema_utils.djoser_utils import TokenCreateExtendSchemaView
from the_wall_api.tests.test_djoser_integration import DjoserIntegrationTestBase
from the_wall_api.tests.test_views.test_cost_and_usage_views import (
    CostAndUsageViewTestBase
)
from the_wall_api.tests.test_views.test_wallconfig_file_views import (
    WallConfigFileDeleteViewTestBase, WallConfigFileListViewTestBase, WallConfigFileUploadViewTestBase
)


class WallConfigFileUploadThrottlingTest(WallConfigFileUploadViewTestBase):
    description = 'Wall Config File Upload Throttling Tests'
    url_name = exposed_endpoints['wallconfig-files-upload']['name']
    throttle_scope = 'wallconfig-files-management'

    @classmethod
    def setUpClass(cls, *args, **kwargs):
        super().setUpClass(bypass_throttling=False, *args, **kwargs)

    @WallConfigFileUploadViewTestBase.cache_clear
    def setUp(self) -> None:
        super().setUp()
        self.throttling_counter = 0

    def pre_request_hook(self, request_params: dict[str, Any]) -> None:
        config_id = f'{self.valid_config_id}_{self.throttling_counter}'
        self.throttling_counter += 1
        request_params['data']['config_id'] = config_id

    def post_request_hook(self, request_params: dict[str, Any]) -> None:
        request_params['data']['wall_config_file'].seek(0)

    @override_settings(MAX_USER_WALL_CONFIGS=settings.MAX_USER_WALL_CONFIGS + 2)
    def test_wall_config_file_upload_throttling(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        self.execute_throttling_test(
            self.client_post_method, test_case_source, self.throttle_scope,
            wall_config_file=self.valid_wall_config_file, token=self.valid_token
        )


class WallConfigFileListThrottlingTest(WallConfigFileListViewTestBase):
    description = 'Wall Config File List Throttling Tests'
    url_name = exposed_endpoints['wallconfig-files-list']['name']
    throttle_scope = 'user'

    @classmethod
    def setUpClass(cls, *args, **kwargs):
        super().setUpClass(bypass_throttling=False, *args, **kwargs)

    @WallConfigFileListViewTestBase.cache_clear
    def setUp(self) -> None:
        super().setUp()

    def test_wall_config_file_list_throttling(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        self.execute_throttling_test(
            self.client_get_method, test_case_source, self.throttle_scope,
            token=self.valid_token
        )


class WallConfigFileDeleteThrottlingTest(WallConfigFileDeleteViewTestBase):
    description = 'Wall Config File Delete Throttling Tests'
    url_name = exposed_endpoints['wallconfig-files-delete']['name']
    throttle_scope = 'wallconfig-files-management'

    @classmethod
    def setUpClass(cls, *args, **kwargs):
        super().setUpClass(bypass_throttling=False, *args, **kwargs)

    @WallConfigFileDeleteViewTestBase.cache_clear
    def setUp(self) -> None:
        super().setUp()

    def test_wall_config_file_delete_throttling(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        self.execute_throttling_test(
            self.client_delete_method, test_case_source, self.throttle_scope,
            config_id_list='random_id_list', token=self.valid_token
        )


class CostAndUsageThrottlingTestBase(CostAndUsageViewTestBase):

    @classmethod
    def setUpClass(cls, *args, **kwargs):
        super().setUpClass(bypass_throttling=False, *args, **kwargs)

    @CostAndUsageViewTestBase.cache_clear
    def setUp(self) -> None:
        super().setUp()


class DailyIceUsageThrottlingTest(CostAndUsageThrottlingTestBase):
    description = 'Daily Ice Usage Throttling Tests'
    url_name = exposed_endpoints['daily-ice-usage']['name']
    throttle_scope = 'user'

    def test_daily_ice_usage_throttling(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        valid_profile_id = self.get_valid_profile_ids()[0]
        valid_day = self.get_valid_days_for_profile_sequential(valid_profile_id)[0]

        self.execute_throttling_test(
            self.client_get_method, test_case_source, self.throttle_scope,
            profile_id=valid_profile_id, day=valid_day
        )


class CostOverviewThrottlingTest(CostAndUsageThrottlingTestBase):
    description = 'Cost Overview Throttling Tests'
    url_name = exposed_endpoints['cost-overview']['name']
    throttle_scope = 'user'

    def test_cost_overview_throttling(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        self.execute_throttling_test(
            self.client_get_method, test_case_source, self.throttle_scope
        )


class CostOverviewProfileidThrottlingTest(CostAndUsageThrottlingTestBase):
    description = 'Cost Overview Profileid Throttling Tests'
    url_name = exposed_endpoints['cost-overview-profile']['name']
    throttle_scope = 'user'

    def test_cost_overview_profileid_throttling(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        valid_profile_id = self.get_valid_profile_ids()[0]

        self.execute_throttling_test(
            self.client_get_method, test_case_source, self.throttle_scope,
            profile_id=valid_profile_id
        )


class DjoserThrottlingTestBase(DjoserIntegrationTestBase):

    @classmethod
    def setUpClass(cls, *args, **kwargs):
        super().setUpClass(bypass_throttling=False, *args, **kwargs)

    @DjoserIntegrationTestBase.cache_clear
    def setUp(self, create_test_user=True, generate_token=True, *args, **kwargs):
        if create_test_user:
            self.create_test_user(self.username, self.password)

        super().setUp(generate_token=generate_token, *args, **kwargs)

        self.request_params: dict[str, Any] = {'data': self.input_data}
        if generate_token:
            self.request_params['HTTP_AUTHORIZATION'] = f'Token {self.valid_token}'


class CreateUserThrottlingTest(DjoserThrottlingTestBase):
    description = 'Create User Throttling Tests'
    throttle_scope = 'anon'

    def setUp(self):
        super().setUp(create_test_user=False, generate_token=False)
        self.throttling_counter = 0

    def pre_request_hook(self, request_params: dict[str, Any]) -> None:
        request_params['data']['username'] = f'{self.username}_{self.throttling_counter}'
        self.throttling_counter += 1

    def test_create_user_throttling(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        self.execute_throttling_test(
            self.client_post_method, self.users_url, self.request_params, self.throttle_scope,
            self.input_data, test_case_source
        )


class SetPasswordThrottlingTest(DjoserThrottlingTestBase):
    description = 'Set Password Throttling Tests'
    throttle_scope = 'user-management'

    def test_set_password_throttling(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        self.execute_throttling_test(
            self.client_post_method, self.reset_password_url, self.request_params, self.throttle_scope,
            self.input_data, test_case_source
        )


class TokenCreateThrottlingTest(DjoserThrottlingTestBase):
    description = 'Token Create Throttling Tests'
    throttle_scope = 'anon'

    def test_token_create_throttling(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        self.execute_throttling_test(
            self.client_post_method, self.token_generation_url, self.request_params, self.throttle_scope,
            self.input_data, test_case_source
        )


class TokenDestroyThrottlingTest(DjoserThrottlingTestBase):
    description = 'Token Destroy Throttling Tests'
    throttle_scope = 'user-management'

    def setUp(self):
        super().setUp()
        TokenCreateExtendSchemaView.throttle_classes = []   # Avoid throttling for the token generation

    def pre_request_hook(self, request_params: dict[str, Any]) -> None:
        valid_token = self.generate_test_user_token(
            client=self.client, username=self.username, password=self.password
        )
        request_params['HTTP_AUTHORIZATION'] = f'Token {valid_token}'

    def test_token_destroy_throttling(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        self.execute_throttling_test(
            self.client_post_method, self.token_deletion_url, self.request_params, self.throttle_scope,
            self.input_data, test_case_source
        )
