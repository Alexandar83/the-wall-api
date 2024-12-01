from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from inspect import currentframe

from the_wall_api.tests.test_utils import BaseTestcase
from the_wall_api.utils.api_utils import exposed_endpoints


class URLTests(BaseTestcase):
    description = 'URL tests'

    def test_admin_endpoint(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        url = reverse('admin:index')
        response = self.client.get(url)
        passed = response.status_code == status.HTTP_302_FOUND
        self.log_test_result(
            passed=passed,
            input_data={'url': url},
            expected_message=str(status.HTTP_302_FOUND),
            actual_message=str(response.status_code),
            test_case_source=test_case_source
        )

    def test_admin_endpoint_super_user(self):
        User.objects.create_superuser('admin', 'admin@example.com', 'password')
        self.client.login(username='admin', password='password')

        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        url = reverse('admin:index')
        response = self.client.get(url)
        passed = response.status_code == status.HTTP_200_OK
        self.log_test_result(
            passed=passed,
            input_data={'url': url},
            expected_message=str(status.HTTP_200_OK),
            actual_message=str(response.status_code),
            test_case_source=test_case_source
        )

    def test_schema_endpoint(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        url = reverse(exposed_endpoints['schema']['name'])
        response = self.client.get(url)
        passed = response.status_code == status.HTTP_200_OK
        self.log_test_result(
            passed=passed,
            input_data={'url': url},
            expected_message=str(status.HTTP_200_OK),
            actual_message=str(response.status_code),
            test_case_source=test_case_source
        )

    def test_swagger_ui_endpoint(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        url = reverse(exposed_endpoints['swagger-ui']['name'])
        response = self.client.get(url)
        passed = response.status_code == status.HTTP_200_OK
        self.log_test_result(
            passed=passed,
            input_data={'url': url},
            expected_message=str(status.HTTP_200_OK),
            actual_message=str(response.status_code),
            test_case_source=test_case_source
        )

    def test_redoc_ui_endpoint(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        url = reverse(exposed_endpoints['redoc']['name'])
        response = self.client.get(url)
        passed = response.status_code == status.HTTP_200_OK
        self.log_test_result(
            passed=passed,
            input_data={'url': url},
            expected_message=str(status.HTTP_200_OK),
            actual_message=str(response.status_code),
            test_case_source=test_case_source
        )

    def test_404_handling(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        url = '/nonexistent-url/'
        response = self.client.get(url)
        passed = response.status_code == status.HTTP_404_NOT_FOUND
        self.log_test_result(
            passed=passed,
            input_data={'url': url},
            expected_message=str(status.HTTP_404_NOT_FOUND),
            actual_message=str(response.status_code),
            test_case_source=test_case_source
        )
