from decimal import Decimal
from inspect import currentframe

from the_wall_api.models import WallProfile
from the_wall_api.serializers import WallProfileSerializer, SimulationResultSerializer
from the_wall_api.tests.test_utils import BaseTestcase
from rest_framework import serializers


class WallProfileModelEdgeCaseTest(BaseTestcase):

    def setUp(self):
        self.base_data = {
            'wall_config_profile_id': 1,
            'num_crews': 5,
            'max_day': 10
        }

    def test_invalid_wall_config_profile_id(self):
        edge_cases = [-1, 0, 'string']
        for case in edge_cases:
            test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore
            passed = False
            expected_error = 'ValidationError'

            input_data = self.base_data.copy()
            input_data['wall_config_profile_id'] = case

            try:
                serializer = WallProfileSerializer(data=input_data)
                serializer.is_valid(raise_exception=True)
            except serializers.ValidationError as e:
                passed = True
                actual_error = f"{e.__class__.__name__}: {str(e)}"
            else:
                actual_error = 'None'

            self.log_test_result(passed, input_data, expected_error, actual_error, test_case_source)

    def test_invalid_num_crews(self):
        edge_cases = [-2, -1, 0, 'string', None]
        for case in edge_cases:
            test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore
            passed = False
            expected_error = 'ValidationError'

            input_data = self.base_data.copy()
            input_data['num_crews'] = case

            try:
                serializer = WallProfileSerializer(data=input_data)
                serializer.is_valid(raise_exception=True)
            except serializers.ValidationError as e:
                if case is None:
                    passed = True  # None is valid here
                    actual_error = 'None'
                else:
                    passed = True
                    actual_error = f"{e.__class__.__name__}: {str(e)}"
            else:
                actual_error = 'None'

            self.log_test_result(passed, input_data, expected_error, actual_error, test_case_source)

    def test_invalid_max_day(self):
        edge_cases = [-1, 0, 'string']
        for case in edge_cases:
            test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore
            passed = False
            expected_error = 'ValidationError'

            input_data = self.base_data.copy()
            input_data['max_day'] = case

            try:
                serializer = WallProfileSerializer(data=input_data)
                serializer.is_valid(raise_exception=True)
            except serializers.ValidationError as e:
                passed = True
                actual_error = f"{e.__class__.__name__}: {str(e)}"
            else:
                actual_error = 'None'

            self.log_test_result(passed, input_data, expected_error, actual_error, test_case_source)


class SimulationResultModelEdgeCaseTest(BaseTestcase):

    def setUp(self):
        self.wall_profile = WallProfile.objects.create(
            wall_config_profile_id=1,
            config_hash='test_hash_simulation',
            num_crews=5,
            max_day=10
        )
        self.base_data = {
            'wall_profile': self.wall_profile.id,
            'day': 1,
            'ice_used': 100,
            'cost': Decimal('500.00'),
            'simulation_type': 'single_threaded'
        }

    def test_invalid_wall_profile(self):
        edge_cases = [None, 9999]  # None and a non-existent profile ID
        for case in edge_cases:
            test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore
            passed = False
            expected_error = 'ValidationError'

            input_data = self.base_data.copy()
            input_data['wall_profile'] = case

            try:
                serializer = SimulationResultSerializer(data=input_data)
                serializer.is_valid(raise_exception=True)
            except serializers.ValidationError as e:
                passed = True
                actual_error = f"{e.__class__.__name__}: {str(e)}"
            else:
                actual_error = 'None'

            self.log_test_result(passed, input_data, expected_error, actual_error, test_case_source)

    def test_invalid_day(self):
        edge_cases = [-1, 0, 'string']
        for case in edge_cases:
            test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore
            passed = False
            expected_error = 'ValidationError'

            input_data = self.base_data.copy()
            input_data['day'] = case

            try:
                serializer = SimulationResultSerializer(data=input_data)
                serializer.is_valid(raise_exception=True)
            except serializers.ValidationError as e:
                passed = True
                actual_error = f"{e.__class__.__name__}: {str(e)}"
            else:
                actual_error = 'None'

            self.log_test_result(passed, input_data, expected_error, actual_error, test_case_source)

    def test_invalid_ice_used(self):
        edge_cases = [-1, 'string']
        for case in edge_cases:
            test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore
            passed = False
            expected_error = 'ValidationError'

            input_data = self.base_data.copy()
            input_data['ice_used'] = case

            try:
                serializer = SimulationResultSerializer(data=input_data)
                serializer.is_valid(raise_exception=True)
            except serializers.ValidationError as e:
                passed = True
                actual_error = f"{e.__class__.__name__}: {str(e)}"
            else:
                actual_error = 'None'

            self.log_test_result(passed, input_data, expected_error, actual_error, test_case_source)

    def test_invalid_cost(self):
        edge_cases = [Decimal('-100.00'), 'string', Decimal('100.001')]
        for case in edge_cases:
            test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore
            passed = False
            expected_error = 'ValidationError'

            input_data = self.base_data.copy()
            input_data['cost'] = case

            try:
                serializer = SimulationResultSerializer(data=input_data)
                serializer.is_valid(raise_exception=True)
            except serializers.ValidationError as e:
                passed = True
                actual_error = f"{e.__class__.__name__}: {str(e)}"
            else:
                actual_error = 'None'

            self.log_test_result(passed, input_data, expected_error, actual_error, test_case_source)
