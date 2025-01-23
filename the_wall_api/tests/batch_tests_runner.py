# Run Django test multiple times and aggregate results
#
# Arguments:
# --test_path_list: list of paths to test modules
# - v: verbose mode
# - i: number of times to run the test
# --mode-list: list of CONCURRENT_SIMULATION_MODE values
# --disable-logfile: disable batch runner file logging
#
# Help:
# python the_wall_api/tests/batch_tests_runner.py -h
#
# Example 1:
# python the_wall_api/tests/batch_tests_runner.py -v -i 10 \
# --test-path-list "[the_wall_api.tests.test_urls, \
# the_wall_api.tests.test_models.WallConfigUniqueConstraintTest, \
# the_wall_api.tests.test_caching]"
#
# Example 2:
# python the_wall_api/tests/batch_tests_runner.py -i 10 \
# --mode-list "[threading_v1, multiprocessing_v3]"

import argparse
from copy import copy
from datetime import datetime
from dotenv import dotenv_values
import os
from functools import partial
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import re
import subprocess
from time import time
from typing import Any


CONCURRENT_SIMULATION_MODE_LIST = [
    'threading_v1',
    'threading_v2',
    'multiprocessing_v1',
    'multiprocessing_v2',
    'multiprocessing_v3'
]

total_passed = 0
total_failed = 0
total_errors = 0


def configure_test_logger(disable_logfile: bool = False, verbose: bool = False) -> logging.Logger:
    """
    Console logging is always enabled.
    File logging is conditional.
    """
    logger = logging.getLogger('batch_test_runner')
    logger.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(console_handler)

    if not disable_logfile and not verbose:
        log_file_path = get_log_file_path()
        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=1024 * 1024 * 5,
            backupCount=2
        )
        file_handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(file_handler)

    return logger


def get_log_file_path() -> str:
    PROJECT_MODE = os.getenv('PROJECT_MODE', 'dev')
    if PROJECT_MODE == 'dev':
        dev_env_file_path = find_dev_env_file()
        env_values = dotenv_values(dev_env_file_path)
        logs_dir_name = env_values.get('LOGS_DIR_NAME')
    else:
        # Prod
        logs_dir_name = os.getenv('LOGS_DIR_NAME')

    if not logs_dir_name:
        logs_dir_name = 'logs'
    test_suite_logs_dir = os.path.join(logs_dir_name, 'test_suite')

    return os.path.join(test_suite_logs_dir, 'batch_test_runner.log')


def find_dev_env_file() -> Path:
    """Recursively search for the dev. .env file."""
    # Find the project root
    current_file = Path(__file__).resolve()
    project_root = current_file.parents[2]

    env_file = 'the_wall_api_dev.env'
    for path in project_root.rglob(env_file):
        return path.resolve()
    raise FileNotFoundError(f'Environment file "{env_file}:" not found starting from {project_root}')


class NoMetavarHelpFormatter(argparse.HelpFormatter):
    """Custom formatter to suppress metavar and avoid extra spaces."""
    def _format_action_invocation(self, action):
        # For optional arguments, only show the option flags, e.g., '-i, --iterations'
        if action.option_strings:
            return ', '.join(action.option_strings)
        # For positional arguments, retain the original formatting
        return super()._format_action_invocation(action)


def parse_list_arg(arg, concurrency_mode_check=False):
    """Parse a string that represents a list in the format "[arg1, arg2]"."""
    if arg.startswith('[') and arg.endswith(']'):
        arg = arg[1:-1].strip()
        items = [item.strip() for item in arg.split(',')]

        if concurrency_mode_check:
            if items == ['all']:
                items = copy(CONCURRENT_SIMULATION_MODE_LIST)

            # Check if all items are valid
            if any(item not in CONCURRENT_SIMULATION_MODE_LIST for item in items):
                raise argparse.ArgumentTypeError(
                    'Invalid CONCURRENT_SIMULATION_MODE value(s).\n\n'
                    'Allowed values:\n' + '\n'.join(CONCURRENT_SIMULATION_MODE_LIST)
                )

        # Check if all items are non-empty strings
        if all(items):
            return items

    # Raise an error if the format is invalid
    raise argparse.ArgumentTypeError('The test_path_list argument must be in the format "[arg1, arg2]".')


def main(
    disable_log_file: bool, verbose: bool, test_path_list: list[str], concurrency_mode_list: list[str], iterations: int
) -> None:
    logger = configure_test_logger(disable_log_file, verbose)

    logger.info(f'Concurrency mode list: {concurrency_mode_list}')
    if test_path_list:
        logger.info(f'Test paths list: {test_path_list}')
    else:
        test_path_list = ['']
    logger.info(f'Verbose output: {verbose}')
    logger.info(f'Batch runs: {iterations}')
    logger.info('')

    for iter_num in range(iterations):
        for concurrency_mode in concurrency_mode_list:
            run_test_batch(verbose, logger, iter_num + 1, test_path_list, concurrency_mode, disable_log_file)

    logger.info('\nBATCH TESTS FINISHED!\n')


def run_test_batch(
    verbose: bool, logger: logging.Logger, iter_num: int, test_path_list: list[str], concurrency_mode: str, disable_log_file: bool = True
) -> None:
    passed_pattern = re.compile(r'Total PASSED in all tests:\s*(\d+)')
    failed_pattern = re.compile(r'Total FAILED in all tests:\s*(\d+)')
    errors_pattern = re.compile(r'Total ERRORS in all tests:\s*(\d+)')

    concurrency_mode_str = '' if verbose else f' {concurrency_mode}'
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f'\n========{concurrency_mode_str} BATCH RUN #{iter_num} START {start_timestamp} ========')
    iteration_start = time()
    for test_path in test_path_list:
        result = run_sub_process(test_path, concurrency_mode, verbose)

        if verbose:
            continue

        # Log summarized test output from the iteration
        log_iteration_results(result, logger, test_path)

        passed_match = passed_pattern.search(result.stderr)
        failed_match = failed_pattern.search(result.stderr)
        errors_match = errors_pattern.search(result.stderr)

        global total_passed
        global total_failed
        global total_errors
        if passed_match:
            total_passed += int(passed_match.group(1))
        if failed_match:
            total_failed += int(failed_match.group(1))
        if errors_match:
            total_errors += int(errors_match.group(1))

    # Log accumulated test results
    log_total_results(
        logger, iter_num, concurrency_mode, total_passed, total_failed, total_errors, iteration_start, verbose
    )


def run_sub_process(test_path, concurrency_mode: str, verbose: bool = True) -> subprocess.CompletedProcess:
    """Cross-platform subprocess call."""
    subprocess_kwargs: dict[str, Any] = {'text': True}
    if os.name == 'nt':
        # Windows

        # Test path
        test_path_suffix = '' if not test_path else f' {test_path}'
        # Env. vars
        env_var_logging = 'set TEST_SUITE_FILE_LOGGING_ENABLED=False'       # Disable test suite file logging
        env_var_mode = f'set CONCURRENT_SIMULATION_MODE={concurrency_mode}'
        test_command = f'python manage.py test{test_path_suffix}'
        args = f'{env_var_logging}&& {env_var_mode}&& {test_command}'
        subprocess_kwargs['args'] = args
        # Shell
        subprocess_kwargs['shell'] = True
    else:
        # Unix

        # Test command args
        args = ['python', 'manage.py', 'test']
        # Test path
        if test_path:
            args.append(test_path)
        subprocess_kwargs['args'] = args
        # Shell
        subprocess_kwargs['shell'] = False
        # Env. vars
        subprocess_kwargs['env'] = {
            **os.environ,
            'CONCURRENT_SIMULATION_MODE': concurrency_mode,
            'TEST_SUITE_FILE_LOGGING_ENABLED': 'False',                     # Disable test suite file logging
        }

    if not verbose:
        subprocess_kwargs['stdout'] = subprocess.PIPE
        subprocess_kwargs['stderr'] = subprocess.PIPE

    result = subprocess.run(**subprocess_kwargs)

    return result


def log_iteration_results(result: subprocess.CompletedProcess, logger: logging.Logger, test_path: str) -> None:
    """Keep the amount of output light to maintain readability for longer runs"""
    filter_stdout = re.compile(r'^(multiprocessing_v|threading_v|Found |System check identified)', re.MULTILINE)
    # Log FAILED and ERROR cases
    error_or_failed_pattern = re.compile(r'TEST #\d+:\s+(ERROR|FAILED)')
    # Data to log for the FAILED and ERROR cases
    detailed_output_pattern = re.compile(r'^(TEST|Timestamp|Test method|Input values|Expected result|Actual result)', re.MULTILINE)

    # STDOUT
    for line in result.stdout.splitlines():
        if not filter_stdout.match(line):
            logger.info(line)

    # STDERR
    if error_or_failed_pattern.search(result.stderr):
        logger.info('')
        if test_path:
            logger.info(f'== {test_path} ==')
        for line in result.stderr.splitlines():
            if detailed_output_pattern.match(line):
                if 'TEST' in line:
                    logger.info('')
                logger.info(line)


def log_total_results(
    logger: logging.Logger, iter_num: int, concurrency_mode: str, total_passed: int, total_failed: int,
    total_errors: int, iteration_start: float, verbose: bool
) -> None:
    concurrency_mode_str = '' if verbose else f' {concurrency_mode}'
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f'\n========{concurrency_mode_str} BATCH RUN #{iter_num} END {end_timestamp} ==========')
    if not verbose:
        logger.info('Accumulated test results:')
        logger.info(f'PASSED: {total_passed}')
        logger.info(f'FAILED: {total_failed}')
        logger.info(f'ERRORS: {total_errors}')
    logger.info(f'BATCH RUN TIME: {round(time() - iteration_start, 3)} seconds')
    logger.info('')


if __name__ == '__main__':
    print()
    parser = argparse.ArgumentParser(
        description='Run Django test multiple times and aggregate results.',
        formatter_class=NoMetavarHelpFormatter
    )
    parser.add_argument('-v', '--verbose', action='store_true', help='Print detailed test output (default: False)')
    parser.add_argument('-i', '--iterations', type=int, default=1, help='Number of iterations (default: 1)')
    parser.add_argument('--disable-logfile', action='store_true', help='Disable batch runner file logging (default: False)')
    parser.add_argument(
        '--mode-list',
        type=partial(parse_list_arg, concurrency_mode_check=True),
        default='[all]',
        help=(
            'List of CONCURRENT_SIMULATION_MODE values in the format "[arg1, arg2]".\n'
            f'Possible values: {CONCURRENT_SIMULATION_MODE_LIST}'
        )
    )
    parser.add_argument(
        '--test-path-list',
        type=parse_list_arg,
        help='List of test paths in the format "[arg1, arg2]"'
    )
    args = parser.parse_args()
    main(args.disable_logfile, args.verbose, args.test_path_list, args.mode_list, args.iterations)
