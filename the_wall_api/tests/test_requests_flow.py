from inspect import currentframe
from io import BytesIO
import json
from time import sleep
from typing import Any, Literal

from django.conf import settings
from django.urls import reverse
from rest_framework import status
from rest_framework.response import Response

from the_wall_api.models import (
    WallConfig, WallConfigReference, WallConfigReferenceStatusEnum, WallConfigStatusEnum
)
from the_wall_api.utils.storage_utils import manage_wall_config_object
from the_wall_api.tests.test_celery_concurrent_tasks import ConcurrentCeleryTasksTestBase
from the_wall_api.utils.api_utils import exposed_endpoints
from the_wall_api.utils.message_themes import (
    errors as error_messages, info as info_messages, success as success_messages
)
from the_wall_api.utils.wall_config_utils import hash_calc


class RequestsFlowTestBase(ConcurrentCeleryTasksTestBase):

    @classmethod
    def setUpClass(cls, *args, **kwargs):
        super().setUpClass(*args, **kwargs)
        cls.valid_config_id = 'test_config_1'
        cls.profile_id = None
        cls.day = None

    def setUp(self, *args, **kwargs):
        super().setUp(*args, **kwargs)
        self.num_crews = 0

    def prepare_status_dict(
        self, phase_2_status: WallConfigStatusEnum,
        phase_1_status: WallConfigStatusEnum = WallConfigStatusEnum.CELERY_CALCULATION,
        grace_period: float | None = None, phase_1_polling_period: float | None = None, phase_2_polling_period: float | None = None,
    ) -> None:
        """Prepare a dict with expected status and polling period for the different phases of the upload process."""
        if grace_period is None:
            grace_period = 0.5
        if phase_1_polling_period is None:
            phase_1_polling_period = 2
        if phase_2_polling_period is None:
            phase_2_polling_period = 2 if 'threading' in settings.CONCURRENT_SIMULATION_MODE else 6
        self.wall_config_status_dict = {
            'celery_task_start_grace_period': {
                'grace_period': grace_period
            },
            # Task sent to Celery
            'phase_1': {
                'status': phase_1_status,
                'polling_period': phase_1_polling_period
            },
            # Waiting for Celery task to finish
            'phase_2': {
                'status': phase_2_status,
                'polling_period': phase_2_polling_period
            }
        }

    def run_test_case(
        self, config_id: str, expected_message: str | None, expected_status: Literal[200, 201, 202, 400, 404, 409] | None,
        input_data: dict, test_case_source: str,
        prepare_wall_config: bool = True, wall_construction_config: list[list[int]] | None = None,
        wall_config_initial_status: WallConfigStatusEnum | None = None, prepare_cache: bool = False,
        request_type: str = 'upload',
        wall_config_status_dict: dict[str, Any] | None = None, second_get_request: bool = False,
        expected_first_request_status: Literal[202] | None = None, expected_first_request_message: str | None = None,
        prepare_wall_config_reference: bool = True, reference_status: WallConfigReferenceStatusEnum | None = None,
        prepare_2nd_wall_config_reference: bool = False,
        cncrrncy_test_sleep_period: float = 0, error_id_prefix: str | None = None
    ) -> None:
        """Main test case runner."""
        try:
            # Prepare a wall config
            if prepare_wall_config:
                response = self.process_wall_config(
                    wall_construction_config,
                    wall_config_initial_status, prepare_wall_config_reference,
                    config_id, reference_status,
                    prepare_2nd_wall_config_reference, request_type, prepare_cache,
                    cncrrncy_test_sleep_period, error_id_prefix,
                    wall_config_status_dict, second_get_request,
                    expected_first_request_status, expected_first_request_message
                )
            else:
                # Test wall reference not existing
                response = self.get_profiles_days(
                    config_id, error_id_prefix=error_id_prefix
                )

            # Evaluate the response
            self.check_response_and_log(
                response, expected_status, expected_message, input_data, test_case_source
            )

        except NotImplementedError as not_implmntd_err:
            if expected_message == str(not_implmntd_err):
                self.log_test_result(
                    True, input_data, str(expected_message), str(not_implmntd_err), test_case_source
                )
            else:
                actual_message = f'{not_implmntd_err.__class__.__name__}: {str(not_implmntd_err)}'
                self.log_test_result(
                    False, input_data, str(expected_message), actual_message, test_case_source, error_occurred=True
                )
        except AssertionError as assrtn_err:
            self.log_test_result(
                False, input_data, str(expected_message), str(assrtn_err), test_case_source
            )
        except Exception as unknwn_err:
            actual_message = f'{unknwn_err.__class__.__name__}: {str(unknwn_err)}'
            self.log_test_result(
                False, input_data, str(expected_message), actual_message, test_case_source, error_occurred=True
            )

    def process_wall_config(
        self, wall_construction_config: list[list[int]] | None,
        wall_config_initial_status: WallConfigStatusEnum | None, prepare_wall_config_reference: bool,
        config_id: str, reference_status: WallConfigReferenceStatusEnum | None,
        prepare_2nd_wall_config_reference: bool, request_type: str, prepare_cache: bool,
        cncrrncy_test_sleep_period: float, error_id_prefix: str | None,
        wall_config_status_dict: dict[str, Any] | None, second_get_request: bool,
        expected_first_request_status: Literal[202] | None, expected_first_request_message: str | None,
    ) -> Response:
        """Manages prerequisite objects creation and requests sending."""
        wall_config_object, wall_config_hash = self.create_wall_config(
            wall_construction_config, wall_config_initial_status
        )

        if prepare_wall_config_reference:
            # Prepare a wall config reference
            self.prepare_wall_config_reference(
                wall_config_object, config_id, reference_status, prepare_2nd_wall_config_reference
            )

        if request_type == 'upload' or prepare_cache:
            # Send a file upload request for upload requests tests
            # or to prepare cache for profiles requests
            wall_config_file = self.create_valid_wall_config_file(wall_construction_config)
            response = self.upload_file(
                self.valid_config_id, wall_config_file, cncrrncy_test_sleep_period, error_id_prefix
            )
        else:
            # Send a get request
            response = self.get_profiles_days(
                self.valid_config_id, cncrrncy_test_sleep_period, error_id_prefix=error_id_prefix,
            )
            if second_get_request:
                self.assert_first_get_request_response(
                    response, expected_first_request_status, expected_first_request_message
                )

        if wall_config_status_dict is not None:
            self.check_wall_config_after_request(wall_config_status_dict, wall_config_hash)

        if prepare_cache or second_get_request:
            # Fetch the prepared cache
            response = self.get_profiles_days(
                self.valid_config_id, cncrrncy_test_sleep_period, error_id_prefix=error_id_prefix,
            )

        return response

    def create_wall_config(
        self, wall_construction_config: list[list[int]] | None = None,
        wall_config_status: WallConfigStatusEnum | None = None
    ) -> tuple[WallConfig, str]:
        wall_construction_config = wall_construction_config or self.wall_construction_config
        wall_config_hash = hash_calc(wall_construction_config)

        wall_config_object = manage_wall_config_object({
            'wall_config_hash': wall_config_hash,
            'initial_wall_construction_config': wall_construction_config
        })

        if isinstance(wall_config_object, str):
            raise ValueError('Wall config object creation failed!')

        if wall_config_status is not None and isinstance(wall_config_object, WallConfig):
            wall_config_object.status = wall_config_status
            wall_config_object.save()

        return wall_config_object, wall_config_hash

    def prepare_wall_config_reference(
        self, config_object: WallConfig, config_id: str, reference_status: WallConfigReferenceStatusEnum | None = None,
        prepare_2nd_wall_config_reference: bool = False
    ) -> WallConfigReference:
        wall_config_reference = WallConfigReference.objects.create(
            user=self.test_user,
            wall_config=config_object,
            config_id=config_id,
        )

        if reference_status is not None:
            wall_config_reference.status = reference_status
            wall_config_reference.save()

        if prepare_2nd_wall_config_reference:
            self.prepare_2nd_wall_config_reference()

        return wall_config_reference

    def prepare_2nd_wall_config_reference(self) -> None:
        """Prepare a user task different from the current one."""
        wall_config_object_2 = WallConfig.objects.create(
            wall_config_hash='test_wall_config_hash_2',
            wall_construction_config=[[0], [1]],
            status=WallConfigStatusEnum.CELERY_CALCULATION
        )

        WallConfigReference.objects.create(
            user=self.test_user,
            wall_config=wall_config_object_2,
            config_id=self.valid_config_id
        )

    def create_valid_wall_config_file(self, wall_construction_config: list[list[int]] | None = None) -> BytesIO:
        wall_construction_config = wall_construction_config or self.wall_construction_config
        json_content = json.dumps(wall_construction_config).encode('utf-8')
        valid_config_file = BytesIO(json_content)
        valid_config_file.name = 'wall_config.json'
        return valid_config_file

    def upload_file(
        self, config_id: str, wall_config_file: BytesIO, cncrrncy_test_sleep_period: float = 0,
        error_id_prefix: str | None = None
    ) -> Response:
        """Send a file upload request."""
        url = self.prepare_url(exposed_endpoints['wallconfig-files-upload']['name'])

        request_params = {
            'data': {
                'config_id': config_id,
                'wall_config_file': wall_config_file
            },
            'headers': {
                'Authorization': f'Token {self.valid_token}'
            }
        }
        test_data: dict = {'test_source': 'test_requests_flow'}
        if cncrrncy_test_sleep_period:
            test_data['cncrrncy_test_sleep_period'] = cncrrncy_test_sleep_period
        if error_id_prefix:
            test_data['error_id_prefix'] = error_id_prefix

        request_params['data']['test_data'] = json.dumps(test_data)

        response: Response = self.client.post(url, **request_params)  # type: ignore
        return response

    def get_profiles_days(
        self, config_id: str, cncrrncy_test_sleep_period: float = 0, error_id_prefix: str | None = None,
        test_case_source: str | None = None
    ) -> Response:
        """Send a profiles days get request."""
        url = self.prepare_url(exposed_endpoints['profiles-days']['name'], self.profile_id, self.day)
        query_params: dict[str, Any] = {'config_id': config_id, 'num_crews': self.num_crews}

        request_params = {
            'query_params': query_params,
            'headers': {
                'Authorization': f'Token {self.valid_token}'
            }
        }

        test_data: dict = {'test_source': 'test_requests_flow'}
        if cncrrncy_test_sleep_period:
            test_data['cncrrncy_test_sleep_period'] = cncrrncy_test_sleep_period
        if error_id_prefix:
            test_data['error_id_prefix'] = error_id_prefix

        request_params['query_params']['test_data'] = json.dumps(test_data)

        response: Response = self.client.get(url, **request_params)  # type: ignore
        return response

    def prepare_url(self, url_name: str, profile_id: int | None = None, day: int | None = None) -> str:
        if profile_id is not None and day is not None:
            return reverse(url_name, kwargs={'profile_id': profile_id, 'day': day})
        elif day is not None:
            return reverse(url_name, kwargs={'day': day})
        return reverse(url_name)

    def assert_first_get_request_response(
        self, response: Response, expected_first_request_status: Literal[202] | None,
        expected_first_request_message: str | None
    ) -> None:
        self.assertEqual(
            response.status_code, expected_first_request_status,
            f'First request status code should be {expected_first_request_status}!'
        )
        assertion_error_message = f'First request message should be {expected_first_request_message}!'
        if response.data:
            self.assertEqual(
                response.data.get('info'), expected_first_request_message,
                assertion_error_message
            )
        else:
            raise AssertionError(assertion_error_message)

    def check_wall_config_after_request(
        self, wall_config_status_dict: dict[str, Any], wall_config_hash: str
    ) -> None:
        for phase, phase_details in wall_config_status_dict.items():
            # Grace period for the Celery orchestration task to start and change the status to CELERY_CALCULATION
            if phase == 'celery_task_start_grace_period':
                sleep(phase_details['grace_period'])
                continue

            # Provide enough time for a Celery task to complete
            config_with_correct_status_exists = False
            retries_count = 8

            for _ in range(retries_count + 1):
                config_with_correct_status_exists = WallConfig.objects.filter(
                    wall_config_hash=wall_config_hash, status=phase_details['status']
                ).exists()
                if config_with_correct_status_exists:
                    break

                if phase_details['status'] == WallConfigStatusEnum.INITIALIZED:
                    sleep(0.5)
                else:
                    sleep(phase_details['polling_period'])

            # Evaluate the expected phase status
            if not config_with_correct_status_exists:
                sleep(30)
                raise ValueError(
                    f"Wall config status after {phase} is not with the expected status: {phase_details['status']}"
                )

    def check_response_and_log(
        self, response: Response, expected_status: Literal[200, 201, 202, 400, 404, 409] | None,
        expected_message: str | None, input_data: dict, test_case_source: str
    ):
        error_occured = False
        passed = response.status_code == expected_status
        if not passed:
            expected_message = str(expected_status)
            actual_message = str(response.status_code)
        else:
            response_data = response.data
            actual_message = None
            if expected_message is not None:
                if response_data:
                    actual_message = response_data.get('error')
                    if not actual_message:
                        actual_message = response_data.get('info')
                    if not actual_message:
                        actual_message = response_data.get('details')
                if actual_message:
                    passed = expected_message == actual_message
                else:
                    passed = False
                    error_occured = True
                    actual_message = 'Incorrect response message!'

        self.log_test_result(
            passed=passed,
            input_data=input_data,
            expected_message=str(expected_message),
            actual_message=str(actual_message),
            test_case_source=test_case_source,
            error_occurred=error_occured
        )


class FileUploadRequestsFlowTest(RequestsFlowTestBase):
    description = 'File Upload Requests Flow Tests'

    def test_another_user_task_is_being_processed(self):
        """"Another user's config_id is being processed."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        another_config_id = 'another_config_id'
        self.run_test_case(
            config_id=another_config_id,
            expected_message=error_messages.user_tasks_in_progress([another_config_id]),
            expected_status=status.HTTP_409_CONFLICT,
            input_data={'another_config_id': another_config_id},
            test_case_source=test_case_source,
            reference_status=WallConfigReferenceStatusEnum.CELERY_CALCULATION,
            error_id_prefix=f'expected test suite error for {test_case_source}_'
        )

    def test_wall_config_already_uploaded(self):
        """Wall config is already uploaded for this user."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        existing_config_id = 'existing_config_id'
        self.run_test_case(
            config_id=existing_config_id,
            expected_message=error_messages.wall_config_already_uploaded(existing_config_id),
            expected_status=status.HTTP_400_BAD_REQUEST,
            input_data={'existing_config_id': existing_config_id},
            test_case_source=test_case_source,
            error_id_prefix=f'expected test suite error for {test_case_source}_'
        )

    def test_wall_config_already_uploaded_with_error_status(self):
        """Wall config is already uploaded for this user and the current status is erroneous."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        existing_config_id = 'existing_config_id'
        status_label = WallConfigStatusEnum.ERROR.label
        error_message_suffix = error_messages.wall_config_already_uploaded_suffix(status_label)
        expected_message = error_messages.wall_config_already_uploaded(existing_config_id, error_message_suffix)

        self.run_test_case(
            config_id=existing_config_id,
            expected_message=expected_message,
            expected_status=status.HTTP_400_BAD_REQUEST,
            input_data={'existing_config_id': existing_config_id, 'wall_config.status': WallConfigStatusEnum.ERROR},
            test_case_source=test_case_source,
            wall_config_initial_status=WallConfigStatusEnum.ERROR,
            error_id_prefix=f'expected test suite error for {test_case_source}_'
        )

    def test_upload_success_1(self):
        """"The wall config is partially calculated from another user."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        self.run_test_case(
            config_id=self.valid_config_id,
            expected_message=None,
            expected_status=status.HTTP_201_CREATED,
            input_data={'config_id': self.valid_config_id, 'wall_config.status': WallConfigStatusEnum.PARTIALLY_CALCULATED},
            test_case_source=test_case_source,
            wall_config_initial_status=WallConfigStatusEnum.PARTIALLY_CALCULATED,
            prepare_wall_config_reference=False
        )

    def test_upload_success_2(self):
        """Larger wall config is freshly uploaded. No full-range caching."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        self.prepare_status_dict(
            phase_1_status=WallConfigStatusEnum.INITIALIZED, phase_2_status=WallConfigStatusEnum.INITIALIZED,
            phase_1_polling_period=2, phase_2_polling_period=0
        )

        self.run_test_case(
            config_id=self.valid_config_id,
            expected_message=None,
            expected_status=status.HTTP_201_CREATED,
            input_data={'config_id': self.valid_config_id, 'wall_construction_config': f'[[0] * {settings.MAX_SECTIONS_COUNT_FULL_RANGE_CACHING + 1}]'},
            test_case_source=test_case_source,
            wall_construction_config=[[0] * (settings.MAX_SECTIONS_COUNT_FULL_RANGE_CACHING + 1)],
            wall_config_status_dict=self.wall_config_status_dict,
            prepare_wall_config_reference=False
        )


class FileUploadRequestsFlowTest2(RequestsFlowTestBase):
    """Additional class to force a full re-setup of the Celery worker to improve results consistency."""
    description = 'File Upload Requests Flow Tests 2'

    def test_upload_success_3(self):
        """The wall config is freshly uploaded. Full-range caching."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        self.prepare_status_dict(phase_2_status=WallConfigStatusEnum.CALCULATED)

        self.run_test_case(
            config_id=self.valid_config_id,
            expected_message=None,
            expected_status=status.HTTP_201_CREATED,
            input_data={'config_id': self.valid_config_id, 'wall_construction_config': '[[21, 25, 28], [17], [17, 22, 17, 19, 17]]'},
            test_case_source=test_case_source,
            wall_config_status_dict=self.wall_config_status_dict,
            prepare_wall_config_reference=False,
            cncrrncy_test_sleep_period=0.01
        )


class ProfilesRequestsFlowTest(RequestsFlowTestBase):
    description = 'Profiles requests flow tests'

    @classmethod
    def setUpClass(cls, *args, **kwargs):
        super().setUpClass(*args, **kwargs)
        cls.profile_id = 1
        cls.day = 1

    def test_no_wall_config_reference_for_user(self):
        """Attempt to retrieve data for a config_id that does not exist for the user."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        not_existing_config_id = 'not_existing_config_id'
        self.run_test_case(
            config_id=not_existing_config_id,
            expected_message=error_messages.file_does_not_exist_for_user(not_existing_config_id, self.username),
            expected_status=status.HTTP_404_NOT_FOUND,
            input_data={'config_id': not_existing_config_id},
            test_case_source=test_case_source,
            prepare_wall_config=False,
            prepare_wall_config_reference=False
        )

    def test_another_user_task_is_being_processed_1(self):
        """"The task is not related to the current config_id."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        another_config_id = 'another_config_id'
        self.run_test_case(
            config_id=another_config_id,
            expected_message=error_messages.user_tasks_in_progress([another_config_id]),
            expected_status=status.HTTP_409_CONFLICT,
            input_data={'another_config_id': another_config_id},
            test_case_source=test_case_source,
            request_type='profiles-days',
            reference_status=WallConfigReferenceStatusEnum.CELERY_CALCULATION,
            prepare_2nd_wall_config_reference=True,
            error_id_prefix=f'expected test suite error for {test_case_source}_'
        )

    def test_another_user_task_is_being_processed_2(self):
        """"The task is related to the current config_id."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        self.run_test_case(
            config_id=self.valid_config_id,
            expected_message=info_messages.REQUEST_BEING_PROCESSED,
            expected_status=status.HTTP_202_ACCEPTED,
            input_data={'config_id': self.valid_config_id},
            test_case_source=test_case_source,
            request_type='profiles-days',
            reference_status=WallConfigReferenceStatusEnum.CELERY_CALCULATION
        )

    @ConcurrentCeleryTasksTestBase.cache_clear
    def test_fetched_resource_is_cached(self):
        """"Prepare cache with an upload and fetch it."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        profile_day_ice_amount = len(self.wall_construction_config[self.profile_id - 1]) * settings.ICE_PER_FOOT
        self.prepare_status_dict(phase_2_status=WallConfigStatusEnum.CALCULATED)
        self.run_test_case(
            config_id=self.valid_config_id,
            expected_message=success_messages.profiles_days_details(
                self.profile_id, self.day, profile_day_ice_amount
            ),
            expected_status=status.HTTP_200_OK,
            input_data={'config_id': self.valid_config_id, 'wall_construction_config': '[[21, 25, 28], [17], [17, 22, 17, 19, 17]]'},
            test_case_source=test_case_source,
            prepare_cache=True,
            request_type='profiles-days',
            wall_config_status_dict=self.wall_config_status_dict,
            prepare_wall_config_reference=False
        )

    def test_wall_config_status_celery_calculation(self):
        """Test an edge case (normally should not be possible) to confirm the raised exception, handling the case."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        self.run_test_case(
            config_id=self.valid_config_id,
            expected_message=error_messages.must_be_handled_in('error_utils.verify_no_other_user_tasks_in_progress()'),
            expected_status=None,
            input_data={'wall_config_initial_status': WallConfigStatusEnum.CELERY_CALCULATION},
            test_case_source=test_case_source,
            wall_config_initial_status=WallConfigStatusEnum.CELERY_CALCULATION,
            request_type='profiles-days'
        )

    def test_wall_config_status_error(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        self.run_test_case(
            config_id=self.valid_config_id,
            expected_message=error_messages.resource_not_found_status(
                WallConfigStatusEnum.ERROR.label
            ),
            expected_status=status.HTTP_409_CONFLICT,
            input_data={'config_id': self.valid_config_id},
            test_case_source=test_case_source,
            wall_config_initial_status=WallConfigStatusEnum.ERROR,
            request_type='profiles-days',
            error_id_prefix=f'expected test suite error for {test_case_source}_'
        )

    @ConcurrentCeleryTasksTestBase.cache_clear
    def test_synchronous_calculation(self):
        """
        The sections in the wall config are less than or equal to MAX_SECTIONS_COUNT_SYNCHRONOUS_RESPONSE.
        Synchronous calculation + caching of the result.
        """
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore
        profile_day_ice_amount = len(self.wall_construction_config[self.profile_id - 1]) * settings.ICE_PER_FOOT

        self.run_test_case(
            config_id=self.valid_config_id,
            expected_message=success_messages.profiles_days_details(
                self.profile_id, self.day, profile_day_ice_amount
            ),
            expected_status=status.HTTP_200_OK,
            input_data={'config_id': self.valid_config_id, 'wall_construction_config': '[[21, 25, 28], [17], [17, 22, 17, 19, 17]]'},
            test_case_source=test_case_source,
            request_type='profiles-days'
        )

    @ConcurrentCeleryTasksTestBase.cache_clear
    def test_asynchronous_calculation(self):
        """
        The sections in the wall config are more than MAX_SECTIONS_COUNT_SYNCHRONOUS_RESPONSE.
        Asynchronous calculation + caching of the result.
        """
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        self.num_crews = 300

        sections_range = int(settings.MAX_SECTIONS_COUNT_SYNCHRONOUS_RESPONSE / settings.MAX_WALL_PROFILE_SECTIONS) + 1
        wall_construction_config = [[settings.MAX_SECTION_HEIGHT - 1] * settings.MAX_WALL_PROFILE_SECTIONS for _ in range(sections_range)]

        phase_2_polling_period = 5 if 'threading' in settings.CONCURRENT_SIMULATION_MODE else 8
        self.prepare_status_dict(
            phase_2_status=WallConfigStatusEnum.PARTIALLY_CALCULATED,
            phase_2_polling_period=phase_2_polling_period
        )

        input_data = {
            'config_id': self.valid_config_id,
            'wall_construction_config': (
                f'[[{settings.MAX_SECTION_HEIGHT - 1}] * '
                f'{settings.MAX_WALL_PROFILE_SECTIONS} for _ in range({sections_range})]'
            )
        }

        self.run_test_case(
            config_id=self.valid_config_id,
            expected_message=success_messages.profiles_days_details(
                self.profile_id, self.day, self.num_crews * settings.ICE_PER_FOOT
            ),
            expected_status=status.HTTP_200_OK,
            input_data=input_data,
            test_case_source=test_case_source,
            wall_construction_config=wall_construction_config,
            request_type='profiles-days',
            wall_config_status_dict=self.wall_config_status_dict,
            second_get_request=True,
            expected_first_request_status=status.HTTP_202_ACCEPTED,
            expected_first_request_message=info_messages.REQUEST_BEING_PROCESSED,
            cncrrncy_test_sleep_period=0.01
        )
