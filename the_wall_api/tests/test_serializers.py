from inspect import currentframe
from typing import Any, Generator, Type

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.handlers.wsgi import WSGIRequest
from rest_framework import serializers
from rest_framework.serializers import ListSerializer, Serializer, ValidationError
from rest_framework.test import APIRequestFactory

from the_wall_api.models import CONFIG_ID_MAX_LENGTH
from the_wall_api.serializers import (
    ProfilesDaysSerializer, WallConfigFileDeleteSerializer, WallConfigFileUploadSerializer
)
from the_wall_api.tests.test_utils import BaseTestcase, generate_valid_values, invalid_input_groups


def extract_error_detail(actual_errors: Any, field_name: str) -> Any:
    """Helper function to extract error details safely."""
    if isinstance(actual_errors, dict):
        error_detail = actual_errors.get(field_name, None)
        if isinstance(error_detail, list):
            return error_detail[0] if error_detail else None
        return error_detail
    else:
        return str(actual_errors)


class SerializerTest(BaseTestcase):

    serializer_class = Serializer

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.valid_config_id = 'valid_config_id'

    def validate_and_log(
        self, serializer_class: Type[Serializer], input_data: dict,
        expected_errors: dict, test_case_source: str, serializer_params: dict
    ) -> None:
        """Handles validation and logging of results."""
        actual_errors = None
        expect_errors = bool(expected_errors)
        serializer = serializer_class(**serializer_params)

        try:
            if expect_errors:
                # We expect validation to fail and raise a ValidationError
                validation_error = self.validate_with_errors(serializer, input_data)
                actual_errors = validation_error.detail
            else:
                # We expect no errors, validation should pass
                self.validate_without_errors(serializer)
                actual_errors = None

            self.log_test_serializer_result(input_data, expected_errors, actual_errors, test_case_source)

        except AssertionError as assrtn_err:
            self.log_test_serializer_result(input_data, expected_errors, str(assrtn_err), test_case_source)

        except Exception as err:
            actual_errors = f'{err.__class__.__name__}: {str(err)}'
            self.log_test_serializer_result(input_data, expected_errors, actual_errors, test_case_source, error_occured=True)

    def validate_with_errors(self, serializer: Serializer | ListSerializer, input_data: dict) -> ValidationError:
        try:
            with self.assertRaises(serializers.ValidationError) as validation_error_context:
                serializer.is_valid(raise_exception=True)
        except AssertionError:
            self.fail(f'Expected ValidationError was not raised for input data: {input_data}')

        return validation_error_context.exception

    def validate_without_errors(self, serializer: Serializer | ListSerializer) -> None:
        is_valid = serializer.is_valid()
        self.assertTrue(is_valid)

    def log_test_serializer_result(
        self, input_data: dict, expected_errors: dict,
        actual_errors: Any, test_case_source: str, error_occured: bool = False
    ):
        validation_passed_msg = 'Validation passed'
        expected_message = ', '.join(expected_errors.values()) if expected_errors else validation_passed_msg
        actual_message = validation_passed_msg if not actual_errors else ', '.join(
            [str(extract_error_detail(actual_errors, field)) for field in expected_errors.keys()]
        )
        passed = expected_message == actual_message
        self.log_test_result(passed, input_data, expected_message, actual_message, test_case_source, error_occurred=error_occured)

    def process_config_id_invalid(self, valid_data: dict, test_case_source: str | None = None):
        if test_case_source is None:
            test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore

        for error_message, invalid_config_id in invalid_input_groups['config_id']:
            input_data = valid_data.copy()
            if invalid_config_id != 'omit_config_id':
                input_data['config_id'] = invalid_config_id
            expected_errors = {'config_id': error_message}
            with self.subTest(config_id=invalid_config_id):
                self.validate_and_log(
                    self.serializer_class, input_data, expected_errors,
                    test_case_source, serializer_params={'data': input_data}
                )


class ProfilesDaysSerializerTest(SerializerTest):
    """
    The tests in this class cover all 'profiles' serializers:
    - ProfilesDaysSerializer
    - ProfilesOverviewDaySerializer
    - ProfilesOverviewSerializer
    , because ProfilesDaysSerializer inherits both the other two serializers.
    """

    description = 'Profiles days serializer tests'

    serializer_class = ProfilesDaysSerializer

    def both_fields_invalid_inner(
        self, invalid_profile_ids, invalid_days, profile_error_message, day_error_message, test_case_source
    ):
        """Helper function to test all combinations of profile and day values."""
        for profile_id in invalid_profile_ids:
            for day in invalid_days:
                input_data = {'profile_id': profile_id, 'day': day, 'config_id': self.valid_config_id}
                expected_errors = {
                    'profile_id': profile_error_message,
                    'day': day_error_message,
                }
                with self.subTest(profile_id=profile_id, day=day):
                    self.validate_and_log(
                        self.serializer_class, input_data, expected_errors,
                        test_case_source, serializer_params={'data': input_data}
                    )

    def num_crews_invalid_inner(self, profile_id, day, test_case_source):
        """Helper function to test all combinations of profile and day values."""
        for error_message, invalid_num_crews in invalid_input_groups['num_crews'].items():
            for num_crews in invalid_num_crews:
                input_data = {
                    'profile_id': profile_id, 'day': day, 'num_crews': num_crews, 'config_id': self.valid_config_id
                }
                expected_errors = {'num_crews': error_message}
                with self.subTest(profile_id=profile_id, day=day, num_crews=num_crews):
                    self.validate_and_log(
                        self.serializer_class, input_data, expected_errors,
                        test_case_source, serializer_params={'data': input_data}
                    )

    def test_all_fields_valid(self):
        valid_values = generate_valid_values()
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore

        for profile_id in valid_values:
            for day in valid_values:
                input_data = {'profile_id': profile_id, 'day': day, 'config_id': self.valid_config_id}
                expected_errors = {}
                with self.subTest(profile_id=profile_id, day=day):
                    self.validate_and_log(
                        self.serializer_class, input_data, expected_errors,
                        test_case_source, serializer_params={'data': input_data}
                    )

    def test_profile_id_invalid(self):
        valid_values = generate_valid_values()
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore

        for error_message, invalid_profile_ids in invalid_input_groups['profile_id'].items():
            for profile_id in invalid_profile_ids:
                for day in valid_values:
                    input_data = {'profile_id': profile_id, 'day': day, 'config_id': self.valid_config_id}
                    expected_errors = {'profile_id': error_message}
                    with self.subTest(profile_id=profile_id, day=day):
                        self.validate_and_log(
                            self.serializer_class, input_data, expected_errors,
                            test_case_source, serializer_params={'data': input_data}
                        )

    def test_day_invalid(self):
        valid_values = generate_valid_values()
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore

        for error_message, invalid_days in invalid_input_groups['day'].items():
            for day in invalid_days:
                for profile_id in valid_values:
                    input_data = {'profile_id': profile_id, 'day': day, 'config_id': self.valid_config_id}
                    expected_errors = {'day': error_message}
                    with self.subTest(profile_id=profile_id, day=day):
                        self.validate_and_log(
                            self.serializer_class, input_data, expected_errors,
                            test_case_source, serializer_params={'data': input_data}
                        )

    def test_profile_id_day_invalid(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        for profile_error_message, invalid_profile_ids in invalid_input_groups['profile_id'].items():
            for day_error_message, invalid_days in invalid_input_groups['day'].items():
                self.both_fields_invalid_inner(
                    invalid_profile_ids,
                    invalid_days,
                    profile_error_message,
                    day_error_message,
                    test_case_source
                )

    def test_num_crews_valid(self):
        valid_values = generate_valid_values()
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore

        for profile_id in valid_values:
            for day in valid_values:
                for num_crews in valid_values:
                    input_data = {
                        'profile_id': profile_id, 'day': day, 'num_crews': num_crews, 'config_id': self.valid_config_id
                    }
                    expected_errors = {}
                    with self.subTest(profile_id=profile_id, day=day, num_crews=num_crews):
                        self.validate_and_log(
                            self.serializer_class, input_data, expected_errors,
                            test_case_source, serializer_params={'data': input_data}
                        )

    def test_num_crews_invalid(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore

        for profile_id in generate_valid_values():
            for day in generate_valid_values():
                self.num_crews_invalid_inner(profile_id, day, test_case_source)

    def test_config_id_invalid(self, *args, **kwargs):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore

        valid_profile = valid_day = generate_valid_values()[0]

        valid_data = {'profile_id': valid_profile, 'day': valid_day}
        self.process_config_id_invalid(valid_data, test_case_source)


class WallConfigFileSerializerTestBase(SerializerTest):

    serializer_class = WallConfigFileUploadSerializer

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_user = cls.create_test_user(username=cls.username, password=cls.password)

    def setUp(self, *args, **kwargs):
        # Test context
        test_request = self.init_test_request()
        test_request.user = self.test_user
        self.test_context = {'request': test_request}

        # Valid test data
        self.valid_config_id = 'valid_config_id'
        self.valid_wall_config_file = SimpleUploadedFile(
            'wall_config.json', b'[]', content_type='application/json'
        )

    def init_test_request(self):
        raise NotImplementedError


class WallConfigFileUploadSerializerTest(WallConfigFileSerializerTestBase):
    description = 'Wall config file upload serializer tests'

    def init_test_request(self) -> WSGIRequest:
        factory = APIRequestFactory()
        return factory.post('/', {}, content_type='application/json')

    def test_valid_upload(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore

        input_data = {'config_id': self.valid_config_id, 'wall_config_file': self.valid_wall_config_file}
        expected_errors = {}

        self.validate_and_log(
            self.serializer_class, input_data, expected_errors,
            test_case_source, serializer_params={'data': input_data, 'context': self.test_context}
        )

    def test_no_file_supplied(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore

        expected_errors = {'wall_config_file': 'No file was submitted.'}
        input_data = {'config_id': self.valid_config_id}

        self.validate_and_log(
            self.serializer_class, input_data, expected_errors,
            test_case_source, serializer_params={'data': input_data, 'context': self.test_context}
        )

    def test_invalid_file(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore

        for error_type, (error_message, invalid_wall_config_file) in invalid_input_groups['wall_config_file'].items():
            if error_type != 'non_serializable_data':
                expected_errors = {'wall_config_file': error_message}
            else:
                expected_errors = {'non_field_errors': error_message}

            input_data = {'config_id': self.valid_config_id, 'wall_config_file': invalid_wall_config_file}
            with self.subTest(wall_config_file=invalid_wall_config_file):
                self.validate_and_log(
                    self.serializer_class, input_data, expected_errors,
                    test_case_source, serializer_params={'data': input_data, 'context': self.test_context}
                )

    def test_no_config_id_supplied(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore

        input_data = {'wall_config_file': self.valid_wall_config_file}
        expected_errors = {'config_id': 'This field is required.'}

        self.validate_and_log(
            self.serializer_class, input_data, expected_errors,
            test_case_source, serializer_params={'data': input_data, 'context': self.test_context}
        )

    def test_config_id_invalid(self, *args, **kwargs):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore

        valid_data = {'wall_config_file': self.valid_wall_config_file}
        self.process_config_id_invalid(valid_data, test_case_source)


class WallConfigFileDeleteSerializerTest(WallConfigFileSerializerTestBase):
    description = 'Wall config file delete serializer tests'

    serializer_class = WallConfigFileDeleteSerializer

    def init_test_request(self) -> WSGIRequest:
        factory = APIRequestFactory()
        return factory.delete('/', {}, content_type='application/json')

    def generate_too_long_config_id(self) -> Generator[str, None, None]:
        result = ''
        while len(result) < CONFIG_ID_MAX_LENGTH + 1:
            if result:
                result += '_'
            result += 'too_long_config_id'

        i = 1
        while True:
            yield f'{result}_{i}'
            i += 1

    def test_valid_delete(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore

        input_data = {'config_id_list': self.valid_config_id}
        expected_errors = {}

        self.validate_and_log(
            self.serializer_class, input_data, expected_errors,
            test_case_source, serializer_params={'data': input_data, 'context': self.test_context}
        )

    def test_invalid_delete(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore

        for error_message, invalid_config_id_list in invalid_input_groups['config_id_list']:
            input_data = {'config_id_list': invalid_config_id_list}
            expected_errors = {'config_id_list': error_message}

            with self.subTest(config_id=invalid_config_id_list):
                self.validate_and_log(
                    self.serializer_class, input_data, expected_errors,
                    test_case_source, serializer_params={'data': input_data, 'context': self.test_context}
                )

    def test_invalid_length(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore

        invalid_values_generator = self.generate_too_long_config_id()

        invalid_config_id_list = next(invalid_values_generator)
        invalid_config_id_list += ',' + next(invalid_values_generator)
        config_id_list = invalid_config_id_list.split(',')

        invalid_input_data = {'config_id_list': invalid_config_id_list}
        expected_errors = {'config_id_list': f'Config IDs with invalid length: {str(config_id_list)}.'}
        self.validate_and_log(
            self.serializer_class, invalid_input_data, expected_errors,
            test_case_source, serializer_params={'data': invalid_input_data, 'context': self.test_context}
        )
