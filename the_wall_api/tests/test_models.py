from decimal import Decimal
from inspect import currentframe
import re
from typing import Callable

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import DecimalField
from django.db.utils import DataError

from the_wall_api.models import Wall, WallConfig, WallProfile, WallProfileProgress, WallConfigReference
from the_wall_api.tests.test_utils import BaseTestcase


class UniqueConstraintTestBase(BaseTestcase):

    def evaluate_actual_error(self, actual_error: str, pattern: str = '') -> bool:
        if pattern:
            return bool(re.search(pattern, actual_error))
        return 'already exists' in actual_error


class WallProfileUniqueConstraintTest(UniqueConstraintTestBase):
    description = 'Unique constraint tests for Wall profile objects'

    def setUp(self, *args, **kwargs):
        self.wall_config_hash = 'some_unique_hash'
        # Set up the wall config instance
        self.wall_config_object = WallConfig.objects.create(
            wall_config_hash=self.wall_config_hash,
            wall_construction_config=[]
        )
        # Set up a wall instance
        self.wall = Wall.objects.create(
            wall_config=self.wall_config_object,
            wall_config_hash=self.wall_config_hash,
            num_crews=5,
            total_cost=Decimal('10000.00'),
            construction_days=10,
        )
        self.wall_profile_data = {
            'wall_profile_config_hash': 'some_hash_value',
            'cost': Decimal('1000.00'),
            'wall': self.wall,
        }

    def test_unique_wall_profile_no_profile_id(self):
        """Test that multiple profiles with the same config_hash can exist if profile_id is NULL."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore

        # First profile with profile_id NULL (sequential mode)
        WallProfile.objects.create(**self.wall_profile_data)

        # Attempting to create another profile with the same wall_profile_config_hash and NULL profile_id should raise an error
        input_data = self.wall_profile_data.copy()
        input_data['profile_id'] = None
        passed = False
        error_occurred = False

        try:
            duplicate_profile = WallProfile(**input_data)
            duplicate_profile.full_clean()
            actual_error = 'None'
        except ValidationError as vldtn_err:
            actual_error = f'{vldtn_err.__class__.__name__}: {str(vldtn_err)}'
            passed = self.evaluate_actual_error(actual_error, pattern=r'Constraint\s“.+?”\sis\sviolated')
        except Exception as unknwn_err:
            error_occurred = True
            actual_error = f'{unknwn_err.__class__.__name__}: {str(unknwn_err)}'

        self.log_test_result(passed, input_data, 'ValidationError', actual_error, test_case_source, error_occurred=error_occurred)

    def test_wall_profile_with_different_profile_id(self):
        """Test that profiles with the same wall and config_hash can exist as long as profile_id is different."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore

        # First profile with profile_id set
        WallProfile.objects.create(**self.wall_profile_data, profile_id=1)

        # A second profile with a different profile_id should succeed
        input_data = self.wall_profile_data.copy()
        input_data['profile_id'] = 2
        passed = True
        error_occurred = False

        try:
            WallProfile.objects.create(**input_data)
            actual_error = 'Validation passed'
        except ValidationError as vldtn_err:
            passed = False
            actual_error = f'{vldtn_err.__class__.__name__}: {str(vldtn_err)}'
        except Exception as unknwn_err:
            error_occurred = True
            actual_error = f'{unknwn_err.__class__.__name__}: {str(unknwn_err)}'

        self.log_test_result(passed, input_data, 'Validation passed', actual_error, test_case_source, error_occurred=error_occurred)

    def test_wall_profile_with_same_profile_id(self):
        """Test that profiles with the same wall, config_hash, and profile_id raise a ValidationError."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore

        # First profile with profile_id set
        WallProfile.objects.create(**self.wall_profile_data, profile_id=1)

        # A second profile with the same profile_id should raise a ValidationError
        input_data = self.wall_profile_data.copy()
        input_data['profile_id'] = 1
        passed = False
        error_occurred = False

        try:
            duplicate_profile = WallProfile(**input_data)
            duplicate_profile.full_clean()
            actual_error = 'None'
        except ValidationError as vldtn_err:
            actual_error = f'{vldtn_err.__class__.__name__}: {str(vldtn_err)}'
            passed = self.evaluate_actual_error(actual_error, pattern=r'Constraint\s“.+?”\sis\sviolated')
        except Exception as unknwn_err:
            error_occurred = True
            actual_error = f'{unknwn_err.__class__.__name__}: {str(unknwn_err)}'

        self.log_test_result(passed, input_data, 'ValidationError', actual_error, test_case_source, error_occurred=error_occurred)

    def test_wall_profile_with_different_hash_same_profile_id(self):
        """Test that profiles with different wall_profile_config_hash but same profile_id are allowed."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore

        # First profile with profile_id 1
        WallProfile.objects.create(**self.wall_profile_data, profile_id=1)

        # A second profile with a different wall_profile_config_hash but same profile_id should succeed
        input_data = self.wall_profile_data.copy()
        input_data['wall_profile_config_hash'] = 'different_hash_value'
        input_data['profile_id'] = 1
        passed = True
        error_occurred = False

        try:
            WallProfile.objects.create(**input_data)
            actual_error = 'Validation passed'
        except ValidationError as vldtn_err:
            passed = False
            actual_error = f'{vldtn_err.__class__.__name__}: {str(vldtn_err)}'
        except Exception as unknwn_err:
            error_occurred = True
            actual_error = f'{unknwn_err.__class__.__name__}: {str(unknwn_err)}'

        self.log_test_result(passed, input_data, 'Validation passed', actual_error, test_case_source, error_occurred=error_occurred)

    def test_wall_profile_with_same_wall_but_different_hash(self):
        """Test that profiles with the same wall but different config_hash are allowed."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore

        # First profile with a specific config_hash
        WallProfile.objects.create(**self.wall_profile_data, profile_id=1)

        # A second profile with a different config_hash but same profile_id should succeed
        input_data = self.wall_profile_data.copy()
        input_data['wall_profile_config_hash'] = 'another_unique_hash'
        input_data['profile_id'] = 1
        passed = True
        error_occurred = False

        try:
            WallProfile.objects.create(**input_data)
            actual_error = 'Validation passed'
        except ValidationError as vldtn_err:
            passed = False
            actual_error = f'{vldtn_err.__class__.__name__}: {str(vldtn_err)}'
        except Exception as unknwn_err:
            error_occurred = True
            actual_error = f'{unknwn_err.__class__.__name__}: {str(unknwn_err)}'

        self.log_test_result(passed, input_data, 'Validation passed', actual_error, test_case_source, error_occurred=error_occurred)


class WallConfigUniqueConstraintTest(UniqueConstraintTestBase):
    description = 'Unique constraint tests for WallConfig objects'

    def setUp(self, *args, **kwargs):
        self.wall_config_hash = 'unique_hash'

    def test_wall_config_unique_constraint(self):
        """Test that a duplicate wall_config with the same wall_config_hash raises a ValidationError."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        # First WallConfig creation should succeed
        WallConfig.objects.create(wall_config_hash=self.wall_config_hash, wall_construction_config=[])

        # Attempt to create another WallConfig with the same wall_config_hash should raise a ValidationError
        passed = False
        error_occurred = False
        try:
            duplicate_wall_config = WallConfig(wall_config_hash=self.wall_config_hash)
            duplicate_wall_config.full_clean()
            actual_error = 'None'
        except ValidationError as vldtn_err:
            actual_error = f'{vldtn_err.__class__.__name__}: {str(vldtn_err)}'
            passed = self.evaluate_actual_error(actual_error)
        except Exception as unknwn_err:
            error_occurred = True
            actual_error = f'{unknwn_err.__class__.__name__}: {str(unknwn_err)}'

        self.log_test_result(passed, self.wall_config_hash, 'ValidationError', actual_error, test_case_source, error_occurred=error_occurred)


class WallUniqueConstraintTest(UniqueConstraintTestBase):
    description = 'Unique constraint tests for Wall objects'

    def setUp(self, *args, **kwargs):
        self.wall_config_hash = 'unique_hash'
        self.wall_config_object = WallConfig.objects.create(
            wall_config_hash=self.wall_config_hash,
            wall_construction_config=[]
        )
        # Set up the wall instance
        self.wall_data = {
            'wall_config': self.wall_config_object,
            'wall_config_hash': 'unique_hash',
            'num_crews': 5,
            'total_cost': Decimal('10000.00'),
            'construction_days': 10,
        }

    def test_wall_unique_together(self):
        """Test that a duplicate wall with the same wall_config_hash and num_crews raises a ValidationError."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        # First Wall creation should succeed
        Wall.objects.create(**self.wall_data)

        # Attempt to create another Wall with the same wall_config_hash and num_crews should raise a ValidationError
        passed = False
        error_occurred = False
        try:
            duplicate_wall = Wall(**self.wall_data)
            duplicate_wall.full_clean()
            actual_error = 'None'
        except ValidationError as vldtn_err:
            actual_error = f'{vldtn_err.__class__.__name__}: {str(vldtn_err)}'
            passed = self.evaluate_actual_error(actual_error)
        except Exception as unknwn_err:
            error_occurred = True
            actual_error = f'{unknwn_err.__class__.__name__}: {str(unknwn_err)}'

        self.log_test_result(passed, self.wall_data, 'ValidationError', actual_error, test_case_source, error_occurred=error_occurred)


class WallProfileProgressUniqueConstraintTest(UniqueConstraintTestBase):
    description = 'Unique constraint tests for wall profile progress objects'

    def setUp(self, *args, **kwargs):
        self.wall_config_hash = 'some_unique_hash'
        # Set up the wall config instance
        self.wall_config_object = WallConfig.objects.create(
            wall_config_hash=self.wall_config_hash,
            wall_construction_config=[]
        )
        # Set up a wall and a wall profile
        self.wall = Wall.objects.create(
            wall_config=self.wall_config_object,
            wall_config_hash=self.wall_config_hash,
            num_crews=5,
            total_cost=Decimal('10000.00'),
            construction_days=10,
        )
        self.wall_profile = WallProfile.objects.create(
            wall=self.wall,
            wall_profile_config_hash='profile_hash',
            cost=Decimal('1000.00'),
        )
        self.progress_data = {
            'wall_profile': self.wall_profile,
            'day': 1,
            'ice_used': 100,
        }

    def test_wall_profile_progress_unique_together(self):
        """Test that a duplicate WallProfileProgress with the same wall_profile and day raises a ValidationError."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        # First WallProfileProgress creation should succeed
        WallProfileProgress.objects.create(**self.progress_data)

        # Attempt to create another WallProfileProgress with the same wall_profile and day should raise a ValidationError
        passed = False
        error_occurred = False
        try:
            duplicate_progress = WallProfileProgress(**self.progress_data)
            duplicate_progress.full_clean()
            actual_error = 'None'
        except ValidationError as vldtn_err:
            actual_error = f'{vldtn_err.__class__.__name__}: {str(vldtn_err)}'
            passed = self.evaluate_actual_error(actual_error)
        except Exception as unknwn_err:
            error_occurred = True
            actual_error = f'{unknwn_err.__class__.__name__}: {str(unknwn_err)}'

        self.log_test_result(passed, self.progress_data, 'ValidationError', actual_error, test_case_source, error_occurred=error_occurred)


class WallConfigReferenceUniqueConstraintTest(UniqueConstraintTestBase):
    description = 'Unique constraint tests for wall config reference objects'

    def setUp(self, *args, **kwargs):
        self.wall_config_hash = 'unique_hash'
        self.wall_config_object = WallConfig.objects.create(
            wall_config_hash=self.wall_config_hash,
            wall_construction_config=[]
        )
        self.test_user = self.create_test_user(username=self.username, password=self.password)
        self.config_id = 'config_id_1'

    def test_wall_config_reference_unique_together(self):
        """Test that a duplicate WallConfigReference with the same wall_config and user raises a ValidationError."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        # First WallConfigReference creation should succeed
        WallConfigReference.objects.create(
            config_id=self.config_id, user=self.test_user, wall_config=self.wall_config_object
        )

        # Attempt to create another WallConfigReference with the same wall_config and user should raise a ValidationError
        passed = False
        error_occurred = False
        try:
            duplicate_reference = WallConfigReference(
                config_id=self.config_id, user=self.test_user, wall_config=self.wall_config_object
            )
            duplicate_reference.full_clean()
            actual_error = 'None'
        except ValidationError as vldtn_err:
            actual_error = f'{vldtn_err.__class__.__name__}: {str(vldtn_err)}'
            passed = self.evaluate_actual_error(actual_error)
        except Exception as unknwn_err:
            error_occurred = True
            actual_error = f'{unknwn_err.__class__.__name__}: {str(unknwn_err)}'

        self.log_test_result(passed, self.wall_config_object, 'ValidationError', actual_error, test_case_source, error_occurred=error_occurred)


class CascadeDeletionTest(BaseTestcase):
    description = 'Cascade deletion tests'

    def setUp(self, *args, **kwargs):
        self.wall_config_hash = 'test_wall_hash_12345'
        self.wall_profile_config_hash = 'test_profile_hash_12345'
        self.num_crews = 3
        self.day = 1
        self.profile_id = 1
        self.config_id = 'config_id_1'
        self.test_user = self.create_test_user(username=self.username, password=self.password)
        self.create_wall_objects_network()
        self.init_redis_cache_keys()
        self.setup_input_data()

    def create_wall_objects_network(self) -> None:
        # Set up the wall config instance
        self.wall_config_object = WallConfig.objects.create(
            wall_config_hash=self.wall_config_hash,  # Unique hash for filtering
            wall_construction_config=[]
        )
        # Set up a wall instance with related profiles and progress, using unique identifiers
        self.wall = Wall.objects.create(
            wall_config=self.wall_config_object,
            wall_config_hash=self.wall_config_hash,  # Unique hash for filtering
            num_crews=self.num_crews,
            total_cost=Decimal('5000.00'),
            construction_days=7,
        )
        self.wall_profile = WallProfile.objects.create(
            wall=self.wall,
            wall_profile_config_hash=self.wall_profile_config_hash,  # Unique hash for filtering
            cost=Decimal('1500.00'),
        )
        self.wall_profile_progress = WallProfileProgress.objects.create(
            wall_profile=self.wall_profile,
            day=self.day,
            ice_used=200,
        )
        # Set up a file reference
        self.wallconfig_reference = WallConfigReference.objects.create(
            user=self.test_user,
            wall_config=self.wall_config_object,
            config_id=self.config_id
        )

    def init_redis_cache_keys(self) -> None:
        self.wall_cache_key = ''
        self.wall_profile_cache_key = ''
        self.daily_ice_usage_cache_key = ''

    def setup_input_data(self) -> None:
        self.input_data = {
            'wall_config': str(self.wall_config_object),
            'wall': str(self.wall),
            'wall_profile': str(self.wall_profile),
            'wall_profile_progress': str(self.wall_profile_progress),
        }

    def test_cascade_deletion_of_wall_config(self):
        """Test that deleting a WallConfig deletes related Wall, WallProfile and WallProfileProgress records."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore
        passed = True
        actual_error = 'Validation passed'

        try:
            # Ensure that only the specific objects created for this test exist
            wall_config_object_exists = WallConfig.objects.filter(wall_config_hash=self.wall_config_hash).exists()
            wall_exists = Wall.objects.filter(wall_config_hash='test_wall_hash_12345').exists()
            wall_profile_exists = WallProfile.objects.filter(wall_profile_config_hash='test_profile_hash_12345').exists()
            wall_profile_progress_exists = WallProfileProgress.objects.filter(wall_profile=self.wall_profile).exists()
            wallconfig_reference_exists = WallConfigReference.objects.filter(
                user=self.test_user, config_id=self.config_id
            ).exists()

            self.assertTrue(wall_config_object_exists)
            self.assertTrue(wall_exists)
            self.assertTrue(wall_profile_exists)
            self.assertTrue(wall_profile_progress_exists)
            self.assertTrue(wallconfig_reference_exists)

            # Delete the wall config and test cascade deletion
            self.wall_config_object.delete()

            # Check that the specific related objects are deleted
            wall_exists = Wall.objects.filter(wall_config_hash='test_wall_hash_12345').exists()
            wall_profile_exists = WallProfile.objects.filter(wall_profile_config_hash='test_profile_hash_12345').exists()
            wall_profile_progress_exists = WallProfileProgress.objects.filter(wall_profile=self.wall_profile).exists()
            wallconfig_reference_exists = WallConfigReference.objects.filter(
                user=self.test_user, config_id=self.config_id
            ).exists()

            self.assertFalse(wall_exists)
            self.assertFalse(wall_profile_exists)
            self.assertFalse(wall_profile_progress_exists)
            self.assertFalse(wallconfig_reference_exists)
        except Exception as unknwn_err:
            passed = False
            actual_error = f'{unknwn_err.__class__.__name__}: {str(unknwn_err)}'

        self.log_test_result(
            passed=passed,
            input_data=self.input_data,
            expected_message='ValidationError',
            actual_message=actual_error,
            test_case_source=test_case_source
        )

    def test_cascade_deletion_of_wall(self):
        """Test that deleting a Wall deletes related WallProfiles and WallProfileProgress records."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore
        passed = True
        actual_error = 'Validation passed'

        try:
            # Ensure that the specific objects created for this test exist
            wall_exists = Wall.objects.filter(wall_config_hash='test_wall_hash_12345').exists()
            wall_profile_exists = WallProfile.objects.filter(wall_profile_config_hash='test_profile_hash_12345').exists()
            wall_profile_progress_exists = WallProfileProgress.objects.filter(wall_profile=self.wall_profile).exists()

            self.assertTrue(wall_exists)
            self.assertTrue(wall_profile_exists)
            self.assertTrue(wall_profile_progress_exists)

            # Delete the wall and test cascade deletion
            self.wall.delete()

            # Check that the specific related objects are deleted
            wall_exists_after_delete = Wall.objects.filter(wall_config_hash='test_wall_hash_12345').exists()
            wall_profile_exists_after_delete = WallProfile.objects.filter(wall_profile_config_hash='test_profile_hash_12345').exists()
            wall_profile_progress_exists_after_delete = WallProfileProgress.objects.filter(wall_profile=self.wall_profile).exists()

            if wall_exists_after_delete or wall_profile_exists_after_delete or wall_profile_progress_exists_after_delete:
                passed = False
                actual_error = 'Cascade deletion failed'
        except Exception as unknwn_err:
            passed = False
            actual_error = f'{unknwn_err.__class__.__name__}: {str(unknwn_err)}'

        self.log_test_result(
            passed=passed,
            input_data=self.input_data,
            expected_message='Validation passed',
            actual_message=actual_error,
            test_case_source=test_case_source
        )

    def test_cascade_deletion_of_wall_profile(self):
        """Test that deleting a WallProfile deletes related WallProfileProgress records."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore
        input_data = {
            'wall': str(self.wall),
            'wall_profile': str(self.wall_profile),
            'wall_profile_progress': str(self.wall_profile_progress),
        }
        passed = True
        actual_error = 'Validation passed'

        try:
            # Ensure that only the specific objects created for this test exist
            wall_profile_exists = WallProfile.objects.filter(wall_profile_config_hash='test_profile_hash_12345').exists()
            wall_profile_progress_exists = WallProfileProgress.objects.filter(wall_profile=self.wall_profile).exists()

            self.assertTrue(wall_profile_exists)
            self.assertTrue(wall_profile_progress_exists)

            # Delete the wall profile and test cascade deletion
            self.wall_profile.delete()

            # Check that the specific related progress objects are deleted
            wall_profile_exists_after_delete = WallProfile.objects.filter(wall_profile_config_hash='test_profile_hash_12345').exists()
            wall_profile_progress_exists_after_delete = WallProfileProgress.objects.filter(
                wall_profile__wall_profile_config_hash=self.wall_profile.wall_profile_config_hash,
            ).exists()

            if wall_profile_exists_after_delete or wall_profile_progress_exists_after_delete:
                passed = False
                actual_error = 'Cascade deletion failed'
        except Exception as unknwn_err:
            passed = False
            actual_error = f'{unknwn_err.__class__.__name__}: {str(unknwn_err)}'

        self.log_test_result(
            passed=passed,
            input_data=input_data,
            expected_message='Validation passed',
            actual_message=actual_error,
            test_case_source=test_case_source
        )

    def test_cascade_deletion_of_user(self):
        """Test that deleting a User deletes related WallConfigReference records."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore
        passed = True
        actual_error = 'Validation passed'

        try:
            # Ensure that the specific objects created for this test exist
            wallconfig_reference_exists = WallConfigReference.objects.filter(
                config_id=self.config_id
            ).exists()

            self.assertTrue(wallconfig_reference_exists)

            # Delete the user and test cascade deletion
            self.test_user.delete()

            # Check that the specific related objects are deleted
            wallconfig_reference_exists_after_delete = WallConfigReference.objects.filter(
                config_id=self.config_id
            ).exists()

            if wallconfig_reference_exists_after_delete:
                passed = False
                actual_error = 'Cascade deletion failed'
        except Exception as unknwn_err:
            passed = False
            actual_error = f'{unknwn_err.__class__.__name__}: {str(unknwn_err)}'

        self.log_test_result(
            passed=passed,
            input_data=self.input_data,
            expected_message='Validation passed',
            actual_message=actual_error,
            test_case_source=test_case_source
        )


class MaxTotalCostTest(BaseTestcase):
    description = 'Max total cost tests'

    def setUp(self, *args, **kwargs):
        self.wall_config_object = WallConfig.objects.create(
            wall_config_hash='wall_config_hash',
            wall_construction_config=[]
        )
        self.wall_object = None

        self.max_total_cost_wall_profile = (
            settings.MAX_SECTION_HEIGHT *
            settings.MAX_WALL_PROFILE_SECTIONS *
            settings.ICE_PER_FOOT * settings.ICE_COST_PER_CUBIC_YARD
        )
        self.max_total_cost_wall = settings.MAX_WALL_LENGTH * self.max_total_cost_wall_profile

        self.expected_message = 'Configuration cost limit does not exceed model cost limit.'

    def _get_total_cost_limit(self, model_class: type[Wall] | type[WallProfile]) -> tuple[str, str]:
        """
        Extracts and returns the max_digits and decimal_places for the `total_cost` field.
        """
        if model_class == Wall:
            cost_field = 'total_cost'
        elif model_class == WallProfile:
            cost_field = 'cost'
        else:
            raise ValueError(f'Invalid model class: {model_class}')

        field = model_class._meta.get_field(cost_field)
        if not isinstance(field, DecimalField):
            raise ValueError(f"The field '{cost_field}' is not a DecimalField.")
        max_digits = field.max_digits
        decimal_places = field.decimal_places
        integer_places = max_digits - decimal_places

        return str(integer_places), cost_field

    def run_max_total_cost_test(
        self, test_case_source: str, test_func: Callable, model_type: type[Wall] | type[WallProfile], config_limit: int | float
    ) -> None:
        error_occurred = False
        if model_type == Wall:
            model_type_name = 'Wall'
        elif model_type == WallProfile:
            model_type_name = 'WallProfile'
        else:
            raise ValueError(f'Invalid model type: {model_type}')
        try:
            test_func()
            actual_message = self.expected_message
        except DataError as data_err:
            if 'numeric field overflow' in str(data_err):
                integer_places, cost_field = self._get_total_cost_limit(model_type)
                config_limit_formatted = f'{config_limit:,}'.replace(',', ' ')
                actual_message = (
                    f"{model_type_name} '{cost_field}' configuration limit ({config_limit_formatted}) "
                    f'exceeds model limit (10^{integer_places}).'
                )
            else:
                error_occurred = True
                actual_message = f'{data_err.__class__.__name__}: {str(data_err)}'
        except Exception as unknwn_err:
            error_occurred = True
            actual_message = f'{unknwn_err.__class__.__name__}: {str(unknwn_err)}'

        passed = actual_message == self.expected_message
        self.log_test_result(
            passed=passed,
            input_data={'model': model_type_name},
            expected_message=self.expected_message,
            actual_message=actual_message,
            test_case_source=test_case_source,
            error_occurred=error_occurred
        )

    def test_max_total_cost_wall_profile(self):
        """Verify that the configuration wall profile limits do not exceed the model limits."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore
        wall = Wall.objects.create(
            wall_config=self.wall_config_object,
            wall_config_hash=self.wall_config_object.wall_config_hash,
            num_crews=5,
            total_cost=100,
            construction_days=1
        )

        def create_wall_profile() -> None:
            WallProfile.objects.create(
                wall=wall,
                wall_profile_config_hash='profile_hash',
                cost=self.max_total_cost_wall_profile
            )

        self.run_max_total_cost_test(
            test_case_source, create_wall_profile, WallProfile, self.max_total_cost_wall_profile
        )

    def test_max_total_cost_wall(self):
        """Verify that the configuration wall limits do not exceed the model limits."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore

        def create_wall() -> None:
            Wall.objects.create(
                wall_config=self.wall_config_object,
                wall_config_hash=self.wall_config_object.wall_config_hash,
                num_crews=5,
                total_cost=self.max_total_cost_wall,
                construction_days=1
            )

        self.run_max_total_cost_test(
            test_case_source, create_wall, Wall, self.max_total_cost_wall
        )
