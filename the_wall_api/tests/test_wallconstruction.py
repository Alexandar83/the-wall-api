from copy import deepcopy
from inspect import currentframe
from typing import Any

from django.conf import settings

from the_wall_api.tests.test_utils import BaseTestcase
from the_wall_api.utils.wall_config_utils import hash_calc, validate_wall_config_format, WallConstructionError
from the_wall_api.wall_construction import get_sections_count, WallConstruction

CONCURRENT_SIMULATION_MODE = settings.CONCURRENT_SIMULATION_MODE
MAX_SECTION_HEIGHT = settings.MAX_SECTION_HEIGHT
MAX_WALL_PROFILE_SECTIONS = settings.MAX_WALL_PROFILE_SECTIONS
MAX_WALL_LENGTH = settings.MAX_WALL_LENGTH


class WallConfigFormatTest(BaseTestcase):
    description = 'Wall config format tests'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.invalid_wall_config_msg = 'Invalid wall configuration file.'

    def evaluate_wall_config_test_result(self, test_data: Any, expected_error: str, test_case_source: str) -> None:
        try:
            with self.assertRaises(WallConstructionError) as validation_error_context:
                validate_wall_config_format(test_data, self.invalid_wall_config_msg)
            actual_result = str(validation_error_context.exception)
        except AssertionError:
            actual_result = f'Expected Error \"{expected_error}\" was not raised!'

        passed = expected_error in actual_result

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
        self.evaluate_wall_config_test_result(test_data, self.invalid_wall_config_msg, test_case_source)

    def test_invalid_wall_length(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)                # type: ignore
        test_data = [0] * (MAX_WALL_LENGTH + 1)
        self.evaluate_wall_config_test_result(test_data, 'exceeds the maximum wall length of', test_case_source)

    def test_invalid_profile_format_not_list(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)                # type: ignore
        test_data = ['[Not a list]']
        self.evaluate_wall_config_test_result(test_data, self.invalid_wall_config_msg, test_case_source)

    def test_invalid_section_count(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)                # type: ignore
        test_data = [[0] * (MAX_WALL_PROFILE_SECTIONS + 1)]
        self.evaluate_wall_config_test_result(test_data, 'exceeds the maximum number of sections', test_case_source)

    def test_invalid_section_height_format_not_int(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)                # type: ignore
        test_data = [['Not an int']]
        self.evaluate_wall_config_test_result(test_data, self.invalid_wall_config_msg, test_case_source)

    def test_invalid_section_height(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)                # type: ignore
        test_data = [[MAX_SECTION_HEIGHT + 1]]
        self.evaluate_wall_config_test_result(test_data, 'exceeds the maximum section height', test_case_source)


class WallConstructionCreationTest(BaseTestcase):
    description = 'Wall construction creation tests'

    def run_wall_construction_test(
            self, config: list, num_crews: int, simulation_type: str, expected_message: str, test_case_source: str
    ) -> None:
        """Helper method to run wall construction tests and log results."""
        # Avoid printing of big volumes of data
        if 'test_maximum_length_profile' not in test_case_source:
            config_output = config
        else:
            config_output = '[[0] * MAX_WALL_PROFILE_SECTIONS] * MAX_WALL_LENGTH'
        sections_count = get_sections_count(config)
        wall_config_hash = hash_calc(config)

        try:
            wall_construction = WallConstruction(config, sections_count, num_crews, wall_config_hash, simulation_type)
            profile_data = wall_construction.wall_profile_data

            if config:
                # Verify that all sections have been incremented correctly if the config is not empty
                for day_data in profile_data[1].values():
                    self.assertGreater(day_data['ice_used'], 0)
                # iterate over wall_construction.testing_wall_construction_config
                for profile in wall_construction.testing_wall_construction_config:
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

    def test_maximum_length_profile(self):
        config = [[0] * MAX_WALL_PROFILE_SECTIONS] * MAX_WALL_LENGTH
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
            range_args = (1, 10)
        elif 'max length' not in config_case:
            range_args = (1, 10, 3)
            config_output = (
                '[[0] * MAX_WALL_PROFILE_SECTIONS for _ in range(int(MAX_WALL_LENGTH / 10))] +'
                '[[MAX_SECTION_HEIGHT - 1] * MAX_WALL_PROFILE_SECTIONS for _ in range(int(MAX_WALL_LENGTH / 10))]'
            )
        else:
            config_output = '[[0] * MAX_WALL_PROFILE_SECTIONS for _ in range(MAX_WALL_LENGTH)]'
            range_args = (9, 10)

        wall_config_hash = hash_calc(config)

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
            expected_message='',
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
            wall_concurrent = WallConstruction(
                wall_construction_config=concurrent_config,
                sections_count=sections_count,
                num_crews=num_crews,
                wall_config_hash=wall_config_hash,
                simulation_type='concurrent'
            )
            self.compare_total_wall_costs(wall_sequential, wall_concurrent, input_data, test_case_source)
            self.compare_profile_costs(wall_sequential, wall_concurrent, input_data, test_case_source)
        except AssertionError as assert_err:
            self.log_test_result(
                passed=False,
                input_data=input_data,
                expected_message='',
                actual_message=str(assert_err),
                test_case_source=test_case_source
            )
        except Exception as wall_cnstrctn_err:
            self.log_wall_construction_error(wall_cnstrctn_err, num_crews, config_output, test_case_source)

    def compare_total_wall_costs(
            self, wall_sequential: WallConstruction, wall_concurrent: WallConstruction, input_data: dict, test_case_source: str
    ) -> None:
        """Compare the total costs of sequential and concurrent simulations."""
        sequential_cost = wall_sequential.sim_calc_details['total_cost']
        concurrent_cost = wall_concurrent.sim_calc_details['total_cost']
        self.assertEqual(
            sequential_cost, concurrent_cost,
            msg=f'Difference in total costs: Sequential: {sequential_cost}, Concurrent: {concurrent_cost}'
        )
        self.log_test_result(
            passed=True,
            input_data=input_data,
            expected_message=sequential_cost,
            actual_message=concurrent_cost,
            test_case_source=test_case_source
        )

    def compare_profile_costs(
            self, wall_sequential: WallConstruction, wall_concurrent: WallConstruction,
            input_data: dict, test_case_source: str
    ) -> None:
        """Compare the profile costs of sequential and concurrent simulations."""
        for profile_id, sequential_profile_cost in wall_sequential.sim_calc_details['profile_costs'].items():
            concurrent_profile_cost = wall_concurrent.sim_calc_details['profile_costs'].get(profile_id, 0)
            input_data['profile_id'] = profile_id
            self.assertEqual(
                sequential_profile_cost, concurrent_profile_cost,
                msg=(
                    f'Difference in profile costs: Profile {profile_id}: Sequential: '
                    f'{sequential_profile_cost}, Concurrent: {concurrent_profile_cost}'
                )
            )
        expected_message = 'Sequential profile costs match the concurrent values'
        self.log_test_result(
            passed=True,
            input_data=input_data,
            expected_message=expected_message,
            actual_message=expected_message,
            test_case_source=test_case_source
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
        if 'multiprocessing' not in CONCURRENT_SIMULATION_MODE:
            test_cases += [
                {
                    'config_case': 'Long wall with many profiles',
                    'config': (
                        [[0] * MAX_WALL_PROFILE_SECTIONS for _ in range(int(MAX_WALL_LENGTH / 10))] +
                        [[MAX_SECTION_HEIGHT - 1] * MAX_WALL_PROFILE_SECTIONS for _ in range(int(MAX_WALL_LENGTH / 10))]
                    )
                },
                {
                    'config_case': 'Long wall with max length',
                    'config': [[0] * MAX_WALL_PROFILE_SECTIONS for _ in range(MAX_WALL_LENGTH)]
                }
            ]

        for case in test_cases:
            self.compare_sequential_and_concurrent_results(case['config'], case['config_case'])
