import copy
from inspect import currentframe
from unittest.mock import patch

from the_wall_api.wall_construction import WallConstruction
from the_wall_api.tests.test_utils import BaseTestcase
from django.conf import settings

MAX_HEIGHT = settings.MAX_HEIGHT
MAX_LENGTH = settings.MAX_LENGTH


class WallConstructionCreationTest(BaseTestcase):
    description = 'Wall construction creation tests'

    def run_wall_construction_test(self, config, num_crews, simulation_type, expected_message, test_case_source):
        """Helper method to run wall construction tests and log results."""
        # Avoid printing of big volumes of data
        config_output = config if 'test_maximum_length_profile' not in test_case_source else '[[0] * MAX_LENGTH]'

        try:
            wall_construction = WallConstruction(config, num_crews, simulation_type)
            profile_data = wall_construction.wall_profile_data

            if config:
                # Verify that all sections have been incremented correctly if the config is not empty
                for day_data in profile_data[1].values():
                    self.assertGreater(day_data['ice_used'], 0)
                # iterate over wall_construction.testing_wall_construction_config
                for profile in wall_construction.testing_wall_construction_config:
                    for section in profile:
                        self.assertEqual(section, settings.MAX_HEIGHT)
                
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

    @patch('the_wall_api.utils.load_wall_profiles_from_config')
    def test_empty_profiles(self, mock_load_config):
        mock_load_config.return_value = []
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore
        self.run_wall_construction_test(
            config=mock_load_config.return_value,
            num_crews=None,
            simulation_type='sequential',
            expected_message='Empty profile list handled correctly',
            test_case_source=test_case_source
        )

    @patch('the_wall_api.utils.load_wall_profiles_from_config')
    def test_minimum_section_heights(self, mock_load_config):
        mock_load_config.return_value = [[0, 0, 0]]
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore
        self.run_wall_construction_test(
            config=mock_load_config.return_value,
            num_crews=None,
            simulation_type='sequential',
            expected_message='Minimum section heights handled correctly',
            test_case_source=test_case_source
        )

    @patch('the_wall_api.utils.load_wall_profiles_from_config')
    def test_single_section_profile(self, mock_load_config):
        mock_load_config.return_value = [[15]]
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore
        self.run_wall_construction_test(
            config=mock_load_config.return_value,
            num_crews=None,
            simulation_type='sequential',
            expected_message='Single section profile handled correctly',
            test_case_source=test_case_source
        )

    @patch('the_wall_api.utils.load_wall_profiles_from_config')
    def test_mixed_profiles(self, mock_load_config):
        mock_load_config.return_value = [[0, 15, MAX_HEIGHT - 1], [25, 10]]
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore
        self.run_wall_construction_test(
            config=mock_load_config.return_value,
            num_crews=None,
            simulation_type='sequential',
            expected_message='Mixed profiles handled correctly',
            test_case_source=test_case_source
        )

    @patch('the_wall_api.utils.load_wall_profiles_from_config')
    def test_concurrent_simulation(self, mock_load_config):
        mock_load_config.return_value = [[0, 15, MAX_HEIGHT - 1], [25, 10]]
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore
        self.run_wall_construction_test(
            config=mock_load_config.return_value,
            num_crews=2,
            simulation_type='concurrent',
            expected_message='Concurrent simulation handled correctly',
            test_case_source=test_case_source
        )

    @patch('the_wall_api.utils.load_wall_profiles_from_config')
    def test_maximum_length_profile(self, mock_load_config):
        max_length_profile = [[0] * MAX_LENGTH]
        mock_load_config.return_value = max_length_profile
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore
        self.run_wall_construction_test(
            config=mock_load_config.return_value,
            num_crews=None,
            simulation_type='sequential',
            expected_message='Maximum length profile handled correctly',
            test_case_source=test_case_source
        )


class SequentialVsConcurrentTest(BaseTestcase):
    description = 'Sequential and Concurrent simulation results comparison'

    def compare_sequential_and_concurrent_results(self, config, config_case):
        """Compare a sequential with multiple concurrent simulations."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore
        test_case_source += ' - ' + config_case
        sections_count = sum(len(profile) for profile in config)

        # Deep copy to ensure independent simulations
        sequential_config = copy.deepcopy(config)
        concurrent_config = copy.deepcopy(config)

        # Avoid printing of big volumes of data
        config_output = config if 'Large' not in config_case else '[0] * (MAX_LENGTH / 2), [MAX_HEIGHT - 1] * (MAX_LENGTH / 2)'
        
        try:
            wall_sequential = WallConstruction(sequential_config, sections_count, num_crews=0, simulation_type='sequential')
        except Exception as wall_cnstrctn_err:
            # Unexpected sequential construction error - stop further tests
            self.log_wall_construction_error(wall_cnstrctn_err, 0, config_output, test_case_source)
            return

        for num_crews in range(1, 10):
            self.run_comparison_tests(wall_sequential, concurrent_config, sections_count, num_crews, config_output, test_case_source)

    def log_wall_construction_error(self, wall_cnstrctn_err, num_crews, config_output, test_case_source):
        self.log_test_result(
            passed=False,
            input_data={'config': config_output, 'num_crews': num_crews},
            expected_message='',
            actual_message=f'{wall_cnstrctn_err.__class__.__name__}: {str(wall_cnstrctn_err)}',
            test_case_source=test_case_source,
            error_occurred=True
        )

    def run_comparison_tests(self, wall_sequential, concurrent_config, sections_count, num_crews, config_output, test_case_source):
        """Run sequential vs concurrent comparison for a given number of crews."""
        input_data = {'config': config_output, 'num_crews': num_crews}
        try:
            wall_concurrent = WallConstruction(concurrent_config, sections_count, num_crews=num_crews, simulation_type='concurrent')
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

    def compare_total_wall_costs(self, wall_sequential, wall_concurrent, input_data, test_case_source):
        """Compare the total costs of sequential and concurrent simulations."""
        sequential_cost = wall_sequential.sim_calc_details['total_cost']
        concurrent_cost = wall_concurrent.sim_calc_details['total_cost']
        with self.subTest('Compare wall total costs', config=input_data['config'], num_crews=input_data['num_crews']):
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

    def compare_profile_costs(self, wall_sequential, wall_concurrent, input_data, test_case_source):
        """Compare the profile costs of sequential and concurrent simulations."""
        for profile_id, sequential_profile_cost in wall_sequential.sim_calc_details['profile_costs'].items():
            concurrent_profile_cost = wall_concurrent.sim_calc_details['profile_costs'].get(profile_id, 0)
            input_data['profile_id'] = profile_id
            with self.subTest('Compare profile costs', config=input_data['config'], num_crews=input_data['num_crews'], profile_id=profile_id):
                self.assertEqual(
                    sequential_profile_cost, concurrent_profile_cost,
                    msg=f'Difference in profile costs: Profile {profile_id}: Sequential: {sequential_profile_cost}, Concurrent: {concurrent_profile_cost}'
                )
            self.log_test_result(
                passed=True,
                input_data=input_data,
                expected_message=sequential_profile_cost,
                actual_message=concurrent_profile_cost,
                test_case_source=test_case_source
            )

    def test_compare_sequential_and_concurrent(self):
        test_cases = [
            {
                'config_case': 'Basic case with small profiles',
                'config': [
                    [0, 15, MAX_HEIGHT - 1],
                    [10, 20, MAX_HEIGHT - 1],
                    [5, 25, MAX_HEIGHT - 1]
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
                    [0, MAX_HEIGHT - 1, 15],
                    [MAX_HEIGHT - 1, 0, 25],
                    [15, 15, 15]
                ]
            },
            {
                'config_case': 'Large profile with many sections',
                'config': [
                    [0] * int(MAX_LENGTH / 2),
                    [MAX_HEIGHT - 1] * int(MAX_LENGTH / 2)
                ]
            }
        ]

        for case in test_cases:
            self.compare_sequential_and_concurrent_results(case['config'], case['config_case'])
