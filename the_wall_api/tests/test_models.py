from decimal import Decimal
from inspect import currentframe

from the_wall_api.models import Wall, WallProfile
from the_wall_api.serializers import WallProfileSerializer, WallProfileProgressSerializer
from the_wall_api.tests.test_utils import BaseTestcase
from rest_framework import serializers


class WallProfileModelEdgeCaseTest(BaseTestcase):

    def setUp(self):
        self.wall = Wall.objects.create(
            wall_config_hash='some_unique_hash',
            total_cost=Decimal('10000.00'),
        )
        self.base_data = {
            'wall_profile_config_hash': 'some_hash_value',
            'cost': Decimal('1000.00'),
            'max_day': 10
        }

    def test_invalid_wall_profile_config_hash(self):
        # Adding a test case for invalid hash values
        edge_cases = [None, '', 'short_hash', ' ' * 65]  # None, empty, too short, too long
        for case in edge_cases:
            test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore
            passed = False
            expected_error = 'ValidationError'

            input_data = self.base_data.copy()
            input_data['wall_profile_config_hash'] = case

            try:
                serializer = WallProfileSerializer(data=input_data)
                serializer.is_valid(raise_exception=True)
            except serializers.ValidationError as e:
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


class WallProfileProgressModelEdgeCaseTest(BaseTestcase):

    def setUp(self):
        self.wall = Wall.objects.create(
            wall_config_hash='some_unique_hash',
            total_cost=Decimal('10000.00'),
        )
        
        self.wall_profile = WallProfile.objects.create(
            wall_profile_config_hash='test_hash_simulation',
            cost=Decimal('1000.00'),
            max_day=10
        )
        
        self.base_data = {
            'wall_profile': self.wall_profile,
            'day': 1,
            'ice_used': 100,
            'cost': Decimal('500.00'),
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
                serializer = WallProfileProgressSerializer(data=input_data)
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
                serializer = WallProfileProgressSerializer(data=input_data)
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
                serializer = WallProfileProgressSerializer(data=input_data)
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
                serializer = WallProfileProgressSerializer(data=input_data)
                serializer.is_valid(raise_exception=True)
            except serializers.ValidationError as e:
                passed = True
                actual_error = f"{e.__class__.__name__}: {str(e)}"
            else:
                actual_error = 'None'

            self.log_test_result(passed, input_data, expected_error, actual_error, test_case_source)
