from copy import deepcopy
from inspect import currentframe
from typing import Any

from django.conf import settings

from the_wall_api.tests.test_utils import BaseTestcase
from the_wall_api.utils.message_themes import errors as error_messages
from the_wall_api.utils.wall_config_utils import (
    hash_calc, SEQUENTIAL, validate_wall_config_format, WallConstructionError
)
from the_wall_api.wall_construction import get_sections_count, WallConstruction

CONCURRENT_SIMULATION_MODE = settings.CONCURRENT_SIMULATION_MODE
MAX_SECTION_HEIGHT = settings.MAX_SECTION_HEIGHT
MAX_WALL_PROFILE_SECTIONS = settings.MAX_WALL_PROFILE_SECTIONS
MAX_WALL_LENGTH = settings.MAX_WALL_LENGTH
MAX_SECTIONS_COUNT_CONCURRENT_THREADING = settings.MAX_SECTIONS_COUNT_CONCURRENT_THREADING
MAX_SECTIONS_COUNT_CONCURRENT_MULTIPROCESSING = settings.MAX_SECTIONS_COUNT_CONCURRENT_MULTIPROCESSING
MAX_CONCURRENT_NUM_CREWS_THREADING = settings.MAX_CONCURRENT_NUM_CREWS_THREADING
MAX_CONCURRENT_NUM_CREWS_MULTIPROCESSING = settings.MAX_CONCURRENT_NUM_CREWS_MULTIPROCESSING


class WallConfigFormatTest(BaseTestcase):
    description = 'Wall config format tests'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.invalid_wall_config_msg = error_messages.INVALID_WALL_CONFIG

    def evaluate_wall_config_test_result(self, test_data: Any, expected_error: str, test_case_source: str) -> None:
        try:
            with self.assertRaises(WallConstructionError) as validation_error_context:
                validate_wall_config_format(test_data)
            actual_result = str(validation_error_context.exception)
        except AssertionError:
            actual_result = f'Expected Error \"{expected_error}\" was not raised!'

        passed = expected_error in actual_result and 'not raised!' not in actual_result

        if self._testMethodName == 'test_invalid_wall_section_count':
            test_data = '[[0] * MAX_WALL_PROFILE_SECTIONS] * MAX_WALL_LENGTH + [[0]]'
        if self._testMethodName == 'test_invalid_profile_section_count':
            test_data = '[[0] * (MAX_WALL_PROFILE_SECTIONS + 1)]'
        if self._testMethodName == 'test_invalid_wall_length':
            test_data = '[[0]] * (MAX_WALL_LENGTH + 1)'

        self.log_test_result(
            passed=passed,
            input_data=str(test_data),
            expected_message=expected_error,
            actual_message=actual_result,
            test_case_source=test_case_source
        )

    def test_invalid_wall_format_not_list(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)                # type: ignore
        test_data = '[Not a list]'
        self.evaluate_wall_config_test_result(test_data, error_messages.MUST_BE_NESTED_LIST, test_case_source)

    def test_invalid_profile_format_not_list(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)                # type: ignore
        test_data = ['[Not a list]']
        expected_error = error_messages.PROFILE_MUST_BE_LIST_OF_INTEGERS
        self.evaluate_wall_config_test_result(test_data, expected_error, test_case_source)

    def test_invalid_wall_section_count(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)                # type: ignore
        test_data = [[0] * MAX_WALL_PROFILE_SECTIONS] * MAX_WALL_LENGTH + [[0]]
        self.evaluate_wall_config_test_result(test_data, error_messages.MAXIMUM_NUMBER_OF_SECTIONS, test_case_source)

    def test_invalid_profile_section_count(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)                # type: ignore
        test_data = [[0] * (MAX_WALL_PROFILE_SECTIONS + 1)]
        self.evaluate_wall_config_test_result(test_data, error_messages.MAXIMUM_NUMBER_OF_PROFILE_SECTIONS, test_case_source)

    def test_invalid_wall_length(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)                # type: ignore
        test_data = [[0]] * (MAX_WALL_LENGTH + 1)
        self.evaluate_wall_config_test_result(test_data, error_messages.MAXIMUM_WALL_LENGTH, test_case_source)

    def test_invalid_section_height_format_not_int(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)                # type: ignore
        test_data = [['Not an int']]
        self.evaluate_wall_config_test_result(test_data, error_messages.SECTION_HEIGHT_MUST_BE_INTEGER, test_case_source)

    def test_maximum_section_height(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)                # type: ignore
        test_data = [[MAX_SECTION_HEIGHT + 1]]
        self.evaluate_wall_config_test_result(
            test_data, error_messages.section_height_must_be_less_than_limit(MAX_SECTION_HEIGHT), test_case_source
        )

    def test_negative_section_height(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)                # type: ignore
        test_data = [[-1]]
        self.evaluate_wall_config_test_result(
            test_data, error_messages.SECTION_HEIGHT_MUST_BE_GREATER_THAN_ZERO, test_case_source
        )


class WallConstructionCreationTest(BaseTestcase):
    description = 'Wall construction creation tests'

    def run_wall_construction_test(
        self, config: list, num_crews: int, simulation_type: str, expected_message: str, test_case_source: str
    ) -> None:
        """Helper method to run wall construction tests and log results."""
        # Avoid printing of big volumes of data
        if 'test_maximum_sections_profile' not in test_case_source:
            config_output = config
        else:
            config_output = '[[0 for _ in range(MAX_WALL_PROFILE_SECTIONS)] for _ in range(MAX_WALL_LENGTH)]'
        sections_count = get_sections_count(config)
        wall_config_hash = hash_calc(config)

        try:
            wall_construction = WallConstruction(config, sections_count, num_crews, wall_config_hash, simulation_type)
            profile_data = wall_construction.wall_profile_data

            if config:
                # Verify that all sections have been incremented correctly if the config is not empty
                daily_details = profile_data['profiles_overview']['daily_details']
                for day_data in daily_details.values():
                    for ice_amounts in day_data.values():
                        self.assertGreater(ice_amounts, 0)
                if simulation_type == f'{SEQUENTIAL}-legacy':
                    for profile in wall_construction.wall_construction_config:
                        for section in profile:
                            self.assertEqual(section, settings.MAX_SECTION_HEIGHT)

            self.log_test_result(
                passed=True, input_data=config_output, expected_message=expected_message,
                actual_message=expected_message, test_case_source=test_case_source
            )
        except AssertionError as assert_err:
            self.log_test_result(
                passed=False, input_data=config_output, expected_message=expected_message,
                actual_message=str(assert_err), test_case_source=test_case_source
            )
        except Exception as err:
            self.log_test_result(
                passed=False, input_data=config_output, expected_message=expected_message,
                actual_message=str(err), test_case_source=test_case_source, error_occurred=True
            )

    def test_empty_profiles(self):
        config = []
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore
        self.run_wall_construction_test(
            config=config,
            num_crews=0,
            simulation_type='sequential',
            expected_message='Empty profile list handled correctly',
            test_case_source=test_case_source
        )

    def test_minimum_section_heights(self):
        config = [[0, 0, 0]]
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore
        self.run_wall_construction_test(
            config=config,
            num_crews=0,
            simulation_type='sequential',
            expected_message='Minimum section heights handled correctly',
            test_case_source=test_case_source
        )

    def test_single_section_profile(self):
        config = [[15]]
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore
        self.run_wall_construction_test(
            config=config,
            num_crews=0,
            simulation_type='sequential',
            expected_message='Single section profile handled correctly',
            test_case_source=test_case_source
        )

    def test_mixed_profiles(self):
        config = [[0, 15, MAX_SECTION_HEIGHT - 1], [25, 10]]
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore
        self.run_wall_construction_test(
            config=config,
            num_crews=0,
            simulation_type='sequential',
            expected_message='Mixed profiles handled correctly',
            test_case_source=test_case_source
        )

    def test_concurrent_simulation(self):
        config = [[0, 15, MAX_SECTION_HEIGHT - 1], [25, 10]]
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore
        self.run_wall_construction_test(
            config=config,
            num_crews=2,
            simulation_type='concurrent',
            expected_message='Concurrent simulation handled correctly',
            test_case_source=test_case_source
        )

    def test_maximum_sections_profile(self):
        config = [[0 for _ in range(MAX_WALL_PROFILE_SECTIONS)] for _ in range(MAX_WALL_LENGTH)]
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore
        self.run_wall_construction_test(
            config=config,
            num_crews=0,
            simulation_type='sequential',
            expected_message='Maximum length profile handled correctly',
            test_case_source=test_case_source
        )


class SequentialVsConcurrentTest(BaseTestcase):
    description = 'Sequential and Concurrent simulation results comparison'

    def setUp(self, *args, **kwargs):
        super().setUp(*args, **kwargs)
        self.expected_message = 'Sequential and concurrent simulation results match.'

    def compare_sequential_and_concurrent_results(self, config: list, config_case: str) -> None:
        """Compare a sequential with multiple concurrent simulations."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore
        test_case_source += ' - ' + config_case
        sections_count = get_sections_count(config)

        # Deep copy to ensure independent simulations
        sequential_config = deepcopy(config)
        concurrent_config = deepcopy(config)

        # Avoid printing of big volumes of data
        if 'Long wall' not in config_case:
            config_output = config
            range_args = (1, MAX_CONCURRENT_NUM_CREWS_MULTIPROCESSING + 1)
        else:
            if 'threading' in CONCURRENT_SIMULATION_MODE:
                range_args = (
                    MAX_CONCURRENT_NUM_CREWS_THREADING,
                    MAX_CONCURRENT_NUM_CREWS_THREADING + 1
                )
                config_output_msg = 'THREADING'
            else:
                range_args = (
                    MAX_CONCURRENT_NUM_CREWS_MULTIPROCESSING,
                    MAX_CONCURRENT_NUM_CREWS_MULTIPROCESSING + 1
                )
                config_output_msg = 'MULTIPROCESSING'
            config_output = (
                f'[[0] * 100 for _ in range(int(MAX_SECTIONS_COUNT_CONCURRENT_{config_output_msg} / 200))] +'
                f'[[MAX_SECTION_HEIGHT - 1] * 100 for _ in range(int(MAX_SECTIONS_COUNT_CONCURRENT_{config_output_msg} / 200))]'
            )

        wall_config_hash = hash_calc(config)

        self.run_comparison_and_handle_result(
            sequential_config, sections_count, wall_config_hash,
            concurrent_config, config_output, range_args, test_case_source
        )

    def run_comparison_and_handle_result(
        self, sequential_config: list, sections_count: int, wall_config_hash: str,
        concurrent_config: list, config_output: list | str, range_args: tuple, test_case_source: str
    ):
        try:
            wall_sequential = WallConstruction(
                wall_construction_config=sequential_config,
                sections_count=sections_count,
                num_crews=0,
                wall_config_hash=wall_config_hash,
                simulation_type='sequential'
            )
        except Exception as wall_cnstrctn_err:
            # Unexpected sequential construction error - stop further tests
            self.log_wall_construction_error(wall_cnstrctn_err, 0, config_output, test_case_source)
            return

        for num_crews in range(*range_args):
            self.run_comparison_tests(
                wall_sequential, concurrent_config, sections_count, num_crews, config_output, test_case_source
            )

    def log_wall_construction_error(
        self, wall_cnstrctn_err: Exception, num_crews: int, config_output: list | str, test_case_source: str
    ) -> None:
        self.log_test_result(
            passed=False,
            input_data={'config': config_output, 'num_crews': num_crews},
            expected_message=self.expected_message,
            actual_message=f'{wall_cnstrctn_err.__class__.__name__}: {str(wall_cnstrctn_err)}',
            test_case_source=test_case_source,
            error_occurred=True
        )

    def run_comparison_tests(
        self, wall_sequential: WallConstruction, concurrent_config: list,
        sections_count: int, num_crews: int, config_output: list | str, test_case_source: str
    ) -> None:
        """Run sequential vs concurrent comparison for a given number of crews."""
        input_data = {'config': config_output, 'num_crews': num_crews}
        wall_config_hash = hash_calc(concurrent_config)
        try:
            self.inner_func(
                concurrent_config=concurrent_config,
                sections_count=sections_count,
                num_crews=num_crews,
                wall_config_hash=wall_config_hash,
                wall_sequential=wall_sequential,
                input_data=input_data,
                test_case_source=test_case_source
            )
        except AssertionError as assert_err:
            self.log_test_result(
                passed=False,
                input_data=input_data,
                expected_message=self.expected_message,
                actual_message=str(assert_err),
                test_case_source=test_case_source
            )
        except Exception as wall_cnstrctn_err:
            self.log_wall_construction_error(wall_cnstrctn_err, num_crews, config_output, test_case_source)

    def inner_func(
        self, concurrent_config: list, sections_count: int, num_crews: int, wall_config_hash: str,
        wall_sequential: WallConstruction, input_data: dict, test_case_source: str
    ) -> None:
        wall_concurrent = WallConstruction(
            wall_construction_config=concurrent_config,
            sections_count=sections_count,
            num_crews=num_crews,
            wall_config_hash=wall_config_hash,
            simulation_type='concurrent'
        )
        # Compare no num_crews sequential vs concurrent total wall costs
        self.compare_wall_data(wall_sequential, wall_concurrent, input_data, test_case_source)

        wall_sequential_num_crews = WallConstruction(
            wall_construction_config=deepcopy(concurrent_config),
            sections_count=sections_count,
            num_crews=num_crews,
            wall_config_hash=wall_config_hash,
            simulation_type='sequential'
        )
        # Compare num_crews sequential vs concurrent total wall costs
        self.compare_wall_data(wall_sequential_num_crews, wall_concurrent, input_data, test_case_source)

        # Compare num_crews sequential vs concurrent wall progress
        self.compare_wall_progress_data(wall_sequential_num_crews, wall_concurrent)

        self.log_test_result(
            passed=True,
            input_data=input_data,
            expected_message=self.expected_message,
            actual_message=self.expected_message,
            test_case_source=test_case_source
        )

    def compare_wall_data(
        self, wall_sequential: WallConstruction, wall_concurrent: WallConstruction, input_data: dict, test_case_source: str
    ) -> None:
        """Compare the total costs and construction days of sequential and concurrent simulations."""
        # Costs
        sequential_ice_amount = wall_sequential.wall_profile_data['profiles_overview']['total_ice_amount']
        concurrent_ice_amount = wall_concurrent.wall_profile_data['profiles_overview']['total_ice_amount']
        self.assertEqual(
            sequential_ice_amount, concurrent_ice_amount,
            msg=f'Difference in total costs: Sequential: {sequential_ice_amount}, Concurrent: {concurrent_ice_amount}'
        )

        if wall_sequential.num_crews == wall_concurrent.num_crews:
            # Construction days
            sequential_construction_days = wall_sequential.wall_profile_data['profiles_overview']['construction_days']
            concurrent_construction_days = wall_concurrent.wall_profile_data['profiles_overview']['construction_days']
            self.assertEqual(
                sequential_construction_days, concurrent_construction_days,
                msg=(
                    f'Difference in construction days: Sequential: {sequential_construction_days} '
                    f', Concurrent: {concurrent_construction_days}'
                )
            )

    def compare_wall_progress_data(
        self, wall_sequential: WallConstruction, wall_concurrent: WallConstruction
    ) -> None:
        """Compare the profiles-days costs of sequential and concurrent simulations."""
        daily_details_sequential = wall_sequential.wall_profile_data['profiles_overview']['daily_details']
        daily_details_concurrent = wall_concurrent.wall_profile_data['profiles_overview']['daily_details']

        for day, day_data in daily_details_sequential.items():
            for profile_key in day_data:
                sequential_ice_amount = day_data[profile_key]
                concurrent_ice_amount = daily_details_concurrent[day][profile_key]
                self.assertEqual(
                    sequential_ice_amount, concurrent_ice_amount,
                    msg=(
                        f'Difference in profile ice amount: Profile {profile_key}: Sequential: '
                        f'{sequential_ice_amount}, Concurrent: {concurrent_ice_amount}'
                    )
                )

    def test_compare_sequential_and_concurrent(self):
        test_cases = [
            {
                'config_case': 'Basic case with small profiles',
                'config': [
                    [21, 25, 28],
                    [17],
                    [17, 22, 17, 19, 17],
                ]
            },
            {
                'config_case': 'Profiles with all zero sections',
                'config': [
                    [0, 0, 0],
                    [0, 0, 0],
                    [0, 0, 0]
                ]
            },
            {
                'config_case': 'Profiles with mixed minimum and maximum sections',
                'config': [
                    [0, MAX_SECTION_HEIGHT - 1, 15],
                    [MAX_SECTION_HEIGHT - 1, 0, 25],
                    [15, 15, 15]
                ]
            }
        ]
        # Limit test cases for maximum sections count in concurrent mode
        if 'threading' in CONCURRENT_SIMULATION_MODE:
            sections_range = int(MAX_SECTIONS_COUNT_CONCURRENT_THREADING / 200)
        else:
            sections_range = int(MAX_SECTIONS_COUNT_CONCURRENT_MULTIPROCESSING / 200)

        test_cases += [
            {
                'config_case': 'Long wall with many profiles',
                'config': (
                    [[0] * 100 for _ in range(sections_range)] +                        # Profile 1
                    [[MAX_SECTION_HEIGHT - 1] * 100 for _ in range(sections_range)]     # Profile 2
                )
            }
        ]

        for case in test_cases:
            self.compare_sequential_and_concurrent_results(case['config'], case['config_case'])
