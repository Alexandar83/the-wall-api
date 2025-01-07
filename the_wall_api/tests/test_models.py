from inspect import currentframe
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.utils import DataError

from the_wall_api.models import Wall, WallConfig, WallProgress, WallConfigReference
from the_wall_api.tests.test_utils import BaseTestcase


class UniqueConstraintTestBase(BaseTestcase):

    def evaluate_actual_error(self, actual_error: str, pattern: str = '') -> bool:
        if pattern:
            return bool(re.search(pattern, actual_error))
        return 'already exists' in actual_error


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
            'total_ice_amount': 10000,
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


class WallProgressUniqueConstraintTest(UniqueConstraintTestBase):
    description = 'Unique constraint tests for wall progress objects'

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
            total_ice_amount=10000,
            construction_days=10,
        )
        self.wall_progress_data = {
            'wall': self.wall,
            'day': 1,
            'ice_amount_data': {
                1: {
                    1: 1000,
                    2: 2000,
                    'dly_ttl': 3000
                }
            },
        }

    def test_wall_progress_unique_together(self):
        """Test that a duplicate WallProgress with the same wall_profile and day raises a ValidationError."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)  # type: ignore

        # First WallProgress creation should succeed
        WallProgress.objects.create(**self.wall_progress_data)

        # Attempt to create another WallProgress with the same wall_profile and day should raise a ValidationError
        passed = False
        error_occurred = False
        try:
            duplicate_progress = WallProgress(**self.wall_progress_data)
            duplicate_progress.full_clean()
            actual_error = 'None'
        except ValidationError as vldtn_err:
            actual_error = f'{vldtn_err.__class__.__name__}: {str(vldtn_err)}'
            passed = self.evaluate_actual_error(actual_error)
        except Exception as unknwn_err:
            error_occurred = True
            actual_error = f'{unknwn_err.__class__.__name__}: {str(unknwn_err)}'

        self.log_test_result(passed, self.wall_progress_data, 'ValidationError', actual_error, test_case_source, error_occurred=error_occurred)


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
        self.num_crews = 3
        self.day = 1
        self.profile_id = 1
        self.config_id = 'config_id_1'
        self.test_user = self.create_test_user(username=self.username, password=self.password)
        self.create_wall_objects_network()
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
            total_ice_amount=10000,
            construction_days=7,
        )
        self.wall_progress = WallProgress.objects.create(
            wall=self.wall,
            day=self.day,
            ice_amount_data={
                self.day: {
                    self.profile_id: 1000,
                    'dly_ttl': 1000
                }
            }
        )
        # Set up a file reference
        self.wallconfig_reference = WallConfigReference.objects.create(
            user=self.test_user,
            wall_config=self.wall_config_object,
            config_id=self.config_id
        )

    def setup_input_data(self) -> None:
        self.input_data = {
            'wall_config': str(self.wall_config_object),
            'wall': str(self.wall),
            'wall_progress': str(self.wall_progress),
        }

    def test_cascade_deletion_of_wall_config(self):
        """Test that deleting a WallConfig deletes related Wall, WallProfile and WallProgress records."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore
        passed = True
        actual_error = 'Validation passed'

        try:
            # Ensure that only the specific objects created for this test exist
            wall_config_object_exists = WallConfig.objects.filter(wall_config_hash=self.wall_config_hash).exists()
            wall_exists = Wall.objects.filter(wall_config_hash='test_wall_hash_12345').exists()
            wall_progress_exists = WallProgress.objects.filter(wall=self.wall).exists()
            wallconfig_reference_exists = WallConfigReference.objects.filter(
                user=self.test_user, config_id=self.config_id
            ).exists()

            self.assertTrue(wall_config_object_exists)
            self.assertTrue(wall_exists)
            self.assertTrue(wall_progress_exists)
            self.assertTrue(wallconfig_reference_exists)

            # Delete the wall config and test cascade deletion
            self.wall_config_object.delete()

            # Check that the specific related objects are deleted
            wall_config_object_exists_after_deletion = WallConfig.objects.filter(wall_config_hash=self.wall_config_hash).exists()
            wall_exists_after_deletion = Wall.objects.filter(wall_config_hash='test_wall_hash_12345').exists()
            wall_progress_exists_after_deletion = WallProgress.objects.filter(wall=self.wall).exists()
            wallconfig_reference_exists_after_deletion = WallConfigReference.objects.filter(
                user=self.test_user, config_id=self.config_id
            ).exists()

            self.assertFalse(wall_config_object_exists_after_deletion)
            self.assertFalse(wall_exists_after_deletion)
            self.assertFalse(wall_progress_exists_after_deletion)
            self.assertFalse(wallconfig_reference_exists_after_deletion)
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

    def test_cascade_deletion_of_wall(self):
        """Test that deleting a Wall deletes related WallProfiles and WallProgress records."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore
        passed = True
        actual_error = 'Validation passed'

        try:
            # Ensure that the specific objects created for this test exist
            wall_exists = Wall.objects.filter(wall_config_hash='test_wall_hash_12345').exists()
            wall_progress_exists = WallProgress.objects.filter(wall__wall_config_hash='test_wall_hash_12345').exists()

            self.assertTrue(wall_exists)
            self.assertTrue(wall_progress_exists)

            # Delete the wall and test cascade deletion
            self.wall.delete()

            # Check that the specific related objects are deleted
            wall_exists_after_delete = Wall.objects.filter(wall_config_hash='test_wall_hash_12345').exists()
            wall_progress_exists_after_delete = WallProgress.objects.filter(wall__wall_config_hash='test_wall_hash_12345').exists()

            if wall_exists_after_delete or wall_progress_exists_after_delete:
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

        self.max_total_ice_amount_wall = (
            settings.MAX_SECTION_HEIGHT *
            settings.MAX_WALL_PROFILE_SECTIONS *
            settings.MAX_WALL_LENGTH *
            settings.ICE_PER_FOOT * settings.ICE_COST_PER_CUBIC_YARD
        )

        self.expected_message = 'Configuration cost limit does not exceed model cost limit.'

    def test_max_total_ice_amount_wall(self):
        """Verify that the configuration wall limits do not exceed the model limits."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name, self.__class__.__name__)    # type: ignore
        error_occurred = False
        passed = True

        try:
            Wall.objects.create(
                wall_config=self.wall_config_object,
                wall_config_hash=self.wall_config_object.wall_config_hash,
                num_crews=5,
                total_ice_amount=self.max_total_ice_amount_wall,
                construction_days=1
            )
            actual_message = self.expected_message
        except DataError as data_err:
            actual_message = f'{data_err.__class__.__name__}: {str(data_err)}'
            passed = False
        except Exception as unknwn_err:
            error_occurred = True
            actual_message = f'{unknwn_err.__class__.__name__}: {str(unknwn_err)}'
            passed = False

        self.log_test_result(
            passed=passed,
            input_data={'model': 'Wall'},
            expected_message=self.expected_message,
            actual_message=actual_message,
            test_case_source=test_case_source,
            error_occurred=error_occurred
        )
