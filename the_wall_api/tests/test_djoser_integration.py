from inspect import currentframe
from typing import Callable

from django.http import HttpResponse
from django.urls import reverse

from the_wall_api.tests.test_utils import BaseTestcase
from the_wall_api.utils.api_utils import exposed_endpoints


class DjoserIntegrationTestBase(BaseTestcase):
    users_url = reverse(exposed_endpoints['user-create']['name'])
    reset_password_url = reverse(exposed_endpoints['user-set-password']['name'])
    token_generation_url = reverse(exposed_endpoints['token-login']['name'])
    token_deletion_url = reverse(exposed_endpoints['token-logout']['name'])

    @classmethod
    def setUpClass(cls, bypass_throttling: bool = True, *args, **kwargs):
        super().setUpClass(bypass_throttling=bypass_throttling, *args, **kwargs)

    def setUp(self, generate_token: bool = False, *args, **kwargs):
        super().setUp(generate_token=generate_token, *args, **kwargs)
        self.input_data = {'username': self.username, 'password': self.password}
        self.users_me_url = reverse(
            exposed_endpoints['user-delete']['name'], kwargs={'username': self.username}
        )

    def check_result_and_log(
        self, assertions: list[Callable], input_data: dict, expected_message: str, test_case_source: str
    ) -> None:
        error_occurred = False
        passed = True
        actual_message = expected_message

        for assertion in assertions:
            try:
                assertion()
            except AssertionError as assrtn_err:
                passed = False
                actual_message = str(assrtn_err)
                break
            except Exception as unknwn_err:
                passed = False
                actual_message = f'{unknwn_err.__class__.__name__}: {str(unknwn_err)}'
                error_occurred = True
                break

        self.log_test_result(
            passed=passed,
            input_data=input_data,
            expected_message=expected_message,
            actual_message=actual_message,
            test_case_source=test_case_source,
            error_occurred=error_occurred
        )

    def process_request_chain(self, request_type: str = 'user_creation') -> HttpResponse:
        # Create a user
        response = self.client.post(
            path=self.users_url,
            data=self.input_data
        )

        # Generate a token
        if request_type in ['token_generation', 'token_deletion', 'reset_password', 'user_deletion']:
            response = self.client.post(
                path=self.token_generation_url,
                data=self.input_data
            )

        # Delete the token
        if request_type == 'token_deletion':
            response_data = response.json()
            self.input_data['auth_token'] = response_data['auth_token']
            response = self.client.post(
                path=self.token_deletion_url,
                HTTP_AUTHORIZATION=f'Token {response_data["auth_token"]}'
            )

        # Set a new password
        if request_type == 'reset_password':
            response_data = response.json()
            new_password = 'NewP@ssword123'
            set_password_data = {
                'current_password': self.password,
                'new_password': new_password
            }

            self.input_data['auth_token'] = response_data['auth_token']
            self.input_data.update(set_password_data)

            response = self.client.post(
                path=self.reset_password_url,
                data=set_password_data,
                HTTP_AUTHORIZATION=f'Token {response_data["auth_token"]}'
            )

            response = self.client.post(
                path=self.token_generation_url,
                data={'username': self.username, 'password': new_password}
            )

        # Delete the user
        if request_type == 'user_deletion':
            response_data = response.json()
            self.input_data['auth_token'] = response_data['auth_token']
            response = self.client.delete(
                path=self.users_me_url,
                data={'current_password': self.input_data['password']},
                HTTP_AUTHORIZATION=f'Token {response_data["auth_token"]}',
                content_type='application/json'
            )

        return response


class DjoserIntegrationTest(DjoserIntegrationTestBase):
    description = 'Djoser integration tests'

    def test_user_creation(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        response = self.process_request_chain('user_creation')

        assertions = [
            lambda: self.assertEqual(response.status_code, 201, 'User creation failed!')
        ]
        response_data = response.json()
        assertions.extend([
            lambda: self.assertIn('username', response_data, 'Username not found in response!')
        ])
        expected_message = 'User creation successful.'
        self.check_result_and_log(assertions, self.input_data, expected_message, test_case_source)

    def test_user_creation_without_password(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        self.input_data.pop('username', None)
        response = self.process_request_chain('user_creation')

        assertions = [
            lambda: self.assertEqual(
                response.status_code, 400, 'User creation without password should not succeed!'
            )
        ]
        expected_message = 'User creation without password unsuccessful.'
        self.check_result_and_log(assertions, self.input_data, expected_message, test_case_source)

    def test_token_generation(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        response = self.process_request_chain('token_generation')

        assertions = [
            lambda: self.assertEqual(response.status_code, 200, 'Token generation failed!')
        ]
        response_data = response.json()
        assertions.append(
            lambda: self.assertIn('auth_token', response_data, 'Token not found in response!')
        )
        expected_message = 'Token generation successful.'
        self.check_result_and_log(assertions, self.input_data, expected_message, test_case_source)

    def test_token_deletion(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        self.client.post(
            path=self.token_generation_url,
            data=self.input_data
        )
        response = self.process_request_chain('token_deletion')

        assertions = [
            lambda: self.assertEqual(response.status_code, 204, 'Token deletion failed!')
        ]
        expected_message = 'Token deletion successful.'
        self.check_result_and_log(assertions, self.input_data, expected_message, test_case_source)

    def test_reset_password(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        reset_response = self.process_request_chain('reset_password')

        assertions = [
            lambda: self.assertEqual(reset_response.status_code, 200, 'Password reset failed!')
        ]

        token_generation_response = self.client.post(
            path=self.token_generation_url,
            data={
                'username': self.username,
                'password': self.input_data['new_password']
            }
        )
        assertions.append(
            lambda: self.assertEqual(
                token_generation_response.status_code, 200, 'Token generation after password reset failed!'
            )
        )
        response_data = token_generation_response.json()
        assertions.append(
            lambda: self.assertIn(
                'auth_token', response_data, 'Token not found in response after password reset!'
            )
        )
        expected_message = 'Password reset successful.'
        self.check_result_and_log(assertions, self.input_data, expected_message, test_case_source)

    def test_user_deletion(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        response = self.process_request_chain('user_deletion')

        assertions = [
            lambda: self.assertEqual(response.status_code, 204, 'User deletion failed!')
        ]
        expected_message = 'User deletion successful.'
        self.check_result_and_log(assertions, self.input_data, expected_message, test_case_source)

    def test_unauthorized_access(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        response_dict = {
            'user_info': self.client.get(path=self.users_me_url),
            'token_deletion': self.client.post(path=self.token_deletion_url, data=self.input_data),
            'user_deletion': self.client.delete(path=self.users_me_url, data={'current_password': self.input_data['password']})
        }

        assertions = []
        for request_type, response in response_dict.items():
            assertions.append(
                lambda: self.assertEqual(response.status_code, 401, f'Unauthorized access check failure for {request_type}!')
            )
            response_data = response.json()
            assertions.append(
                lambda: self.assertEqual(
                    'Authentication credentials were not provided.',
                    response_data['detail'],
                    'Not authenticated message not found in response!'
                )
            )

        expected_message = 'Unauthorized access check successful.'
        self.check_result_and_log(assertions, self.input_data, expected_message, test_case_source)
