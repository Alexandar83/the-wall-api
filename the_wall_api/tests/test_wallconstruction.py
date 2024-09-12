import copy
from inspect import currentframe
from unittest.mock import patch

from the_wall_api.utils import WallConstructionError
from the_wall_api.wall_construction import WallConstruction
from the_wall_api.tests.test_utils import BaseTestcase
from django.conf import settings


class WallConstructionTests(BaseTestcase):

    def _run_wall_construction_test(self, config, num_crews, simulation_type, expected_message, test_case_source):
        """Helper method to run wall construction tests and log results."""
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
            
            # Avoid printing big data
            if test_case_source in [
                'test_maximum_length_profile', 'test_compare_sqntl_and_cncrrnt_various_cases'
            ]:
                config_ok = ''
            else:
                config_ok = config
                
            self.log_test_result(
                passed=True,
                input_data=config_ok,
                expected_message=expected_message,
                actual_message=expected_message,
                test_case_source=test_case_source
            )
        except AssertionError as assert_err:
            self.log_test_result(
                passed=False,
                input_data=config,
                expected_message=expected_message,
                actual_message=str(assert_err),
                test_case_source=test_case_source
            )

    @patch('the_wall_api.utils.load_wall_profiles_from_config')
    def test_empty_profiles(self, mock_load_config):
        mock_load_config.return_value = []
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore
        self._run_wall_construction_test(
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
        self._run_wall_construction_test(
            config=mock_load_config.return_value,
            num_crews=None,
            simulation_type='sequential',
            expected_message='Minimum section heights handled correctly',
            test_case_source=test_case_source
        )

    @patch('the_wall_api.utils.load_wall_profiles_from_config')
    def test_maximum_section_heights(self, mock_load_config):
        mock_load_config.return_value = [[30, 30, 30]]
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore
        self._run_wall_construction_test(
            config=mock_load_config.return_value,
            num_crews=None,
            simulation_type='sequential',
            expected_message='Maximum section heights handled correctly',
            test_case_source=test_case_source
        )

    @patch('the_wall_api.utils.load_wall_profiles_from_config')
    def test_single_section_profile(self, mock_load_config):
        mock_load_config.return_value = [[15]]
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore
        self._run_wall_construction_test(
            config=mock_load_config.return_value,
            num_crews=None,
            simulation_type='sequential',
            expected_message='Single section profile handled correctly',
            test_case_source=test_case_source
        )

    @patch('the_wall_api.utils.load_wall_profiles_from_config')
    def test_mixed_profiles(self, mock_load_config):
        mock_load_config.return_value = [[0, 15, 30], [25, 10]]
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore
        self._run_wall_construction_test(
            config=mock_load_config.return_value,
            num_crews=None,
            simulation_type='sequential',
            expected_message='Mixed profiles handled correctly',
            test_case_source=test_case_source
        )

    @patch('the_wall_api.utils.load_wall_profiles_from_config')
    def test_concurrent_simulation(self, mock_load_config):
        mock_load_config.return_value = [[0, 15, 30], [25, 10]]
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore
        self._run_wall_construction_test(
            config=mock_load_config.return_value,
            num_crews=2,
            simulation_type='concurrent',
            expected_message='Concurrent simulation handled correctly',
            test_case_source=test_case_source
        )

    def test_invalid_concurrent_initialization(self):
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore
        config = [[0, 0, 0]]
        output_msg = 'Initialization error handled correctly'

        try:
            with self.assertRaises(WallConstructionError):
                WallConstruction(config, None, simulation_type='concurrent')
            self.log_test_result(
                passed=True,
                input_data=config,
                expected_message=output_msg,
                actual_message=output_msg,
                test_case_source=test_case_source
            )
        except AssertionError as assert_err:
            self.log_test_result(
                passed=False,
                input_data=config,
                expected_message=output_msg,
                actual_message=str(assert_err),
                test_case_source=test_case_source
            )

    @patch('the_wall_api.utils.load_wall_profiles_from_config')
    def test_maximum_length_profile(self, mock_load_config):
        max_length_profile = [[0] * 2000]
        mock_load_config.return_value = max_length_profile
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore
        self._run_wall_construction_test(
            config=mock_load_config.return_value,
            num_crews=None,
            simulation_type='sequential',
            expected_message='Maximum length profile handled correctly',
            test_case_source=test_case_source
        )

    def test_compare_sqntl_and_cncrrnt_various_cases(self):
        test_cases = [
            {
                'description': 'Basic case with small profiles',
                'config': [
                    [0, 15, 30],
                    [10, 20, 30],
                    [5, 25, 30]
                ]
            },
            {
                'description': 'Profiles with all zero sections',
                'config': [
                    [0, 0, 0],
                    [0, 0, 0]
                ]
            },
            {
                'description': 'Profiles with all sections at maximum height',
                'config': [
                    [30, 30, 30],
                    [30, 30, 30]
                ]
            },
            {
                'description': 'Profiles with mixed minimum and maximum sections',
                'config': [
                    [0, 30, 15],
                    [30, 0, 25],
                    [15, 15, 15]
                ]
            },
            {
                'description': 'Large profile with many sections',
                'config': [
                    [0] * 1000,
                    [30] * 1000
                ]
            }
        ]

        for case in test_cases:
            with self.subTest(case['description']):
                self._compare_sqntl_and_cncrrnt_for_config(case['config'], case['description'])

    def _compare_sqntl_and_cncrrnt_for_config(self, config, description):
        """Helper method to run comparison test for a given configuration."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore

        try:
            # Deep copy to ensure independent simulations
            sequential_config = copy.deepcopy(config)
            concurrent_config = copy.deepcopy(config)

            # Run both sequential and concurrent simulations
            wall_sequential = WallConstruction(sequential_config, num_crews=None, simulation_type='sequential')
            wall_concurrent = WallConstruction(concurrent_config, num_crews=2, simulation_type='concurrent')

            # Compare daily ice usage and cost overview results
            result_msg = self._compare_cost_overview(wall_sequential, wall_concurrent)

            self.log_test_result(
                passed=True,
                input_data=result_msg,
                expected_message=f'{description}: Sequential and concurrent results should be identical',
                actual_message=f'{description}: Sequential and concurrent results are identical',
                test_case_source=test_case_source
            )
        except AssertionError as assert_err:
            self.log_test_result(
                passed=False,
                input_data=config,
                expected_message=f'{description}: Sequential and concurrent results should be identical',
                actual_message=str(assert_err),
                test_case_source=test_case_source
            )

    def _compare_cost_overview(self, wall_sequential, wall_concurrent):
        """Helper method to compare internal method outputs for sequential and concurrent constructions."""
        sequential_cost_overview = wall_sequential._sim_calc_details()
        concurrent_cost_overview = wall_concurrent._sim_calc_details()

        # Set maxDiff to None to view full diff when assertions fail
        self.maxDiff = None

        self.assertEqual(
            sequential_cost_overview['total_cost'], concurrent_cost_overview['total_cost'],
            msg=f'Difference in cost overview: Sequential: {sequential_cost_overview} | Concurrent: {concurrent_cost_overview}'
        )

        return f'Sequential cost calculation: {sequential_cost_overview} | Concurrent cost calculation: {concurrent_cost_overview}'
