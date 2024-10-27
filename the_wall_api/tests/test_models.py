from decimal import Decimal
from inspect import currentframe

from the_wall_api.models import Wall, WallConfig, WallProfile, WallProfileProgress
from the_wall_api.tests.test_utils import BaseTestcase
from django.core.exceptions import ValidationError


class WallProfileUniqueConstraintTest(BaseTestcase):
    description = 'Unique constraint tests for Wall profile objects'

    def setUp(self):
        self.wall_config_hash = 'some_unique_hash'
        # Set up the wall config instance
        self.wall_config_object = WallConfig.objects.create(
            wall_config_hash=self.wall_config_hash,
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
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore

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
            passed = True
            actual_error = f'{vldtn_err.__class__.__name__}: {str(vldtn_err)}'
        except Exception as err:
            error_occurred = True
            actual_error = f'{err.__class__.__name__}: {str(err)}'

        self.log_test_result(passed, input_data, 'ValidationError', actual_error, test_case_source, error_occurred=error_occurred)

    def test_wall_profile_with_different_profile_id(self):
        """Test that profiles with the same wall and config_hash can exist as long as profile_id is different."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore

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
        except Exception as err:
            error_occurred = True
            actual_error = f'{err.__class__.__name__}: {str(err)}'

        self.log_test_result(passed, input_data, 'Validation passed', actual_error, test_case_source, error_occurred=error_occurred)

    def test_wall_profile_with_same_profile_id(self):
        """Test that profiles with the same wall, config_hash, and profile_id raise a ValidationError."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore

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
            passed = True
            actual_error = f'{vldtn_err.__class__.__name__}: {str(vldtn_err)}'
        except Exception as err:
            error_occurred = True
            actual_error = f'{err.__class__.__name__}: {str(err)}'

        self.log_test_result(passed, input_data, 'ValidationError', actual_error, test_case_source, error_occurred=error_occurred)

    def test_wall_profile_with_different_hash_same_profile_id(self):
        """Test that profiles with different wall_profile_config_hash but same profile_id are allowed."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore

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
        except Exception as err:
            error_occurred = True
            actual_error = f'{err.__class__.__name__}: {str(err)}'

        self.log_test_result(passed, input_data, 'Validation passed', actual_error, test_case_source, error_occurred=error_occurred)

    def test_wall_profile_with_same_wall_but_different_hash(self):
        """Test that profiles with the same wall but different config_hash are allowed."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore

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
        except Exception as err:
            error_occurred = True
            actual_error = f'{err.__class__.__name__}: {str(err)}'

        self.log_test_result(passed, input_data, 'Validation passed', actual_error, test_case_source, error_occurred=error_occurred)


class WallConfigUniqueConstraintTest(BaseTestcase):
    description = 'Unique constraint tests for WallConfig objects'

    def setUp(self):
        self.wall_config_hash = 'unique_hash'

    def test_wall_config_unique_together(self):
        """Test that a duplicate wall_config with the same wall_config_hash raises a ValidationError."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore

        # First WallConfig creation should succeed
        WallConfig.objects.create(wall_config_hash=self.wall_config_hash)

        # Attempt to create another WallConfig with the same wall_config_hash should raise a ValidationError
        passed = False
        error_occurred = False
        try:
            duplicate_wall_config = WallConfig(wall_config_hash=self.wall_config_hash)
            duplicate_wall_config.full_clean()
            actual_error = 'None'
        except ValidationError as vldtn_err:
            passed = True
            actual_error = f'{vldtn_err.__class__.__name__}: {str(vldtn_err)}'
        except Exception as err:
            error_occurred = True
            actual_error = f'{err.__class__.__name__}: {str(err)}'

        self.log_test_result(passed, self.wall_config_hash, 'ValidationError', actual_error, test_case_source, error_occurred=error_occurred)


class WallUniqueConstraintTest(BaseTestcase):
    description = 'Unique constraint tests for Wall objects'

    def setUp(self):
        self.wall_config_hash = 'unique_hash'
        self.wall_config_object = WallConfig.objects.create(
            wall_config_hash=self.wall_config_hash,
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
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore

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
            passed = True
            actual_error = f'{vldtn_err.__class__.__name__}: {str(vldtn_err)}'
        except Exception as err:
            error_occurred = True
            actual_error = f'{err.__class__.__name__}: {str(err)}'

        self.log_test_result(passed, self.wall_data, 'ValidationError', actual_error, test_case_source, error_occurred=error_occurred)


class WallProfileProgressUniqueConstraintTest(BaseTestcase):
    description = 'Unique constraint tests for wall profile progress objects'

    def setUp(self):
        self.wall_config_hash = 'some_unique_hash'
        # Set up the wall config instance
        self.wall_config_object = WallConfig.objects.create(
            wall_config_hash=self.wall_config_hash,
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
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)  # type: ignore

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
            passed = True
            actual_error = f'{vldtn_err.__class__.__name__}: {str(vldtn_err)}'
        except Exception as err:
            error_occurred = True
            actual_error = f'{err.__class__.__name__}: {str(err)}'

        self.log_test_result(passed, self.progress_data, 'ValidationError', actual_error, test_case_source, error_occurred=error_occurred)


class CascadeDeletionTest(BaseTestcase):
    description = 'Cascade deletion tests'

    def setUp(self):
        self.wall_config_hash = 'test_wall_hash_12345'
        # Set up the wall config instance
        self.wall_config_object = WallConfig.objects.create(
            wall_config_hash=self.wall_config_hash,  # Unique hash for filtering
        )
        # Set up a wall instance with related profiles and progress, using unique identifiers
        self.wall = Wall.objects.create(
            wall_config=self.wall_config_object,
            wall_config_hash=self.wall_config_hash,  # Unique hash for filtering
            num_crews=3,
            total_cost=Decimal('5000.00'),
            construction_days=7,
        )
        self.wall_profile = WallProfile.objects.create(
            wall=self.wall,
            wall_profile_config_hash='test_profile_hash_12345',  # Unique hash for filtering
            cost=Decimal('1500.00'),
        )
        self.wall_profile_progress = WallProfileProgress.objects.create(
            wall_profile=self.wall_profile,
            day=1,
            ice_used=200,
        )

    def test_cascade_deletion_of_wall_config(self):
        """Test that deleting a WallConfig deletes related Wall, WallProfile and WallProfileProgress records."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore
        input_data = {
            'wall': str(self.wall),
            'wall_profile': str(self.wall_profile),
            'wall_profile_progress': str(self.wall_profile_progress),
        }
        passed = True
        actual_error = 'Validation passed'

        try:
            # Ensure that only the specific objects created for this test exist
            wall_config_object_exists = WallConfig.objects.filter(wall_config_hash=self.wall_config_hash).exists()
            wall_exists = Wall.objects.filter(wall_config_hash='test_wall_hash_12345').exists()
            wall_profile_exists = WallProfile.objects.filter(wall_profile_config_hash='test_profile_hash_12345').exists()
            wall_profile_progress_exists = WallProfileProgress.objects.filter(wall_profile=self.wall_profile).exists()

            self.assertTrue(wall_config_object_exists)
            self.assertTrue(wall_exists)
            self.assertTrue(wall_profile_exists)
            self.assertTrue(wall_profile_progress_exists)

            # Delete the wall config and test cascade deletion
            self.wall_config_object.delete()

            # Check that the specific related objects are deleted
            wall_exists = Wall.objects.filter(wall_config_hash='test_wall_hash_12345').exists()
            wall_profile_exists = WallProfile.objects.filter(wall_profile_config_hash='test_profile_hash_12345').exists()
            wall_profile_progress_exists = WallProfileProgress.objects.filter(wall_profile=self.wall_profile).exists()

            self.assertFalse(wall_exists)
            self.assertFalse(wall_profile_exists)
            self.assertFalse(wall_profile_progress_exists)
        except Exception as err:
            passed = False
            actual_error = f'{err.__class__.__name__}: {str(err)}'

        self.log_test_result(passed, input_data, 'ValidationError', actual_error, test_case_source)

    def test_cascade_deletion_of_wall(self):
        """Test that deleting a Wall deletes related WallProfiles and WallProfileProgress records."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore
        input_data = {
            'wall': str(self.wall),
            'wall_profile': str(self.wall_profile),
            'wall_profile_progress': str(self.wall_profile_progress),
        }
        passed = True
        actual_error = 'Validation passed'

        try:
            # Ensure that only the specific objects created for this test exist
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
        except Exception as e:
            passed = False
            actual_error = f'{e.__class__.__name__}: {str(e)}'

        self.log_test_result(
            passed=passed,
            input_data=input_data,
            expected_message='Validation passed',
            actual_message=actual_error,
            test_case_source=test_case_source
        )

    def test_cascade_deletion_of_wall_profile(self):
        """Test that deleting a WallProfile deletes related WallProfileProgress records."""
        test_case_source = self._get_test_case_source(currentframe().f_code.co_name)    # type: ignore
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
        except Exception as e:
            passed = False
            actual_error = f'{e.__class__.__name__}: {str(e)}'

        self.log_test_result(
            passed=passed,
            input_data=input_data,
            expected_message='Validation passed',
            actual_message=actual_error,
            test_case_source=test_case_source
        )
