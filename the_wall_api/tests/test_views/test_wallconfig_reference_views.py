from copy import deepcopy
from inspect import currentframe
from io import BytesIO
import json

from django.urls import reverse
from rest_framework import status

from the_wall_api.tests.test_views.base_test_views import BaseViewTest
from the_wall_api.utils.api_utils import exposed_endpoints


class WallConfigReferenceViewTest(BaseViewTest):
    description = 'Wall Config Reference View Tests'

    url_name = exposed_endpoints['wallconfig-files-upload']['name']

    def setUp(self) -> None:
        super().setUp()
        self.create_test_user(
            client=self.client, username=self.username, password=self.password
        )

        # Valid test data
        self.valid_config_id = 'valid_config_id'
        self.init_valid_wall_config_file()
        self.valid_token = self.generate_test_user_token(
            client=self.client, username=self.username, password=self.password
        )

        # Invalid test data
        self.invalid_wall_config_file = 'invalid_wall_config_file'
        self.invalid_token = 'invalid_token'

    def init_valid_wall_config_file(self):
        wall_config = [
            [21, 25, 28],
            [17],
            [17, 22, 17, 19, 17]
        ]
        json_content = json.dumps(wall_config).encode('utf-8')
        self.valid_wall_config_file = BytesIO(json_content)
        self.valid_wall_config_file.name = 'wall_config.json'

    def prepare_url(self) -> str:
        return reverse(self.url_name)

    def prepare_final_test_data(self, wall_config_file: BytesIO, token: str) -> tuple[str, dict, dict]:
        url = self.prepare_url()
        request_params = {
            'data': {
                'config_id': self.valid_config_id,
                'wall_config_file': wall_config_file
            },
            'headers': {
                'Authorization': f'Token {token}'
            }
        }
        input_data = deepcopy(request_params)

        return url, request_params, input_data

    def test_wallconfig_file_upload_success(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore

        self.execute_test_case(
            self.client_post_method, status.HTTP_201_CREATED, test_case_source,
            wall_config_file=self.valid_wall_config_file, token=self.valid_token
        )

    def test_wallconfig_file_upload_with_invalid_file(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore

        self.execute_test_case(
            self.client_post_method, status.HTTP_400_BAD_REQUEST, test_case_source,
            wall_config_file=self.invalid_wall_config_file, token=self.valid_token
        )

    def test_wallconfig_file_upload_with_invalid_token(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore

        self.execute_test_case(
            self.client_post_method, status.HTTP_401_UNAUTHORIZED, test_case_source,
            wall_config_file=self.valid_wall_config_file, token=self.invalid_token
        )
