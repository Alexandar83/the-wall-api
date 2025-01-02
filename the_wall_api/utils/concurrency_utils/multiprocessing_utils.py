from concurrent.futures import ProcessPoolExecutor
from logging import Logger, LogRecord
import logging.handlers
from multiprocessing import current_process, Event, Lock, Manager, Process, Queue as mprcss_Queue, Value
from queue import Empty, Queue
from random import uniform
from threading import Thread
from time import sleep
from typing import Callable, Union

from django.conf import settings

from the_wall_api.utils.concurrency_utils.base_concurrency_utils import BaseWallBuilder

ICE_PER_FOOT = settings.ICE_PER_FOOT
MAX_CONCURRENT_NUM_CREWS_MULTIPROCESSING = settings.MAX_CONCURRENT_NUM_CREWS_MULTIPROCESSING
MAX_SECTION_HEIGHT = settings.MAX_SECTION_HEIGHT
VERBOSE_MULTIPROCESSING_LOGGING = settings.VERBOSE_MULTIPROCESSING_LOGGING


class MultiprocessingWallBuilder(BaseWallBuilder):

    def __init__(self, wall_construction):
        self.manager = Manager()
        super().__init__(wall_construction)
        if self.num_crews > MAX_CONCURRENT_NUM_CREWS_MULTIPROCESSING:
            from the_wall_api.utils.error_utils import WallConstructionError
            # Multiprocessing limitations, due to:
            # -the nature of the build simulation - 1 crew (process) per section
            # -CPU limitations
            raise WallConstructionError(
                f'Max. allowed number of sections for multiprocessing is {MAX_CONCURRENT_NUM_CREWS_MULTIPROCESSING}'
            )
        self.init_result_handler()
        if self.is_manager_required():
            self.init_multiprocessing_with_manager()
        else:
            self.init_multiprocessing()

    def init_result_handler(self) -> None:
        self.logger = BaseWallBuilder.setup_logger(self.filename, self.log_stream, manage_formatter=False)

        # result_queue usage:
        # -v1:
        #   -logging:
        #       -the result_handler thread in the main process collects the logs from the processes' qhandlers
        #   -managing wall_profile_data and test data:
        #       -the result_handler thread in the main process collects data put in the queue from the processes
        #
        # -v2 and 3:
        #   -logging:
        #       - qlistener in the main thread and qhandlers in the processes
        self.result_queue = self.create_queue()

        if self.is_manager_required():
            self.qlistener = logging.handlers.QueueListener(self.result_queue, *self.logger.handlers)
            self.qlistener.start()

            # result_queue_with_manager usage:
            # -v2 and v3:
            #   -managing wall_profile_data and test data:
            #       -the result_handler thread in the main process collects data put in the queue from the processes
            self.result_queue_with_manager = self.create_queue()
            result_handler_queue = self.result_queue_with_manager
        else:
            result_handler_queue = self.result_queue

        self.result_handler_thread = Thread(
            name='ResultHandlerThread', target=self.result_handler, daemon=True, args=(result_handler_queue,)
        )
        self.result_handler_thread.start()

    def init_multiprocessing(self) -> None:
        self.build_kwargs = {
            'CONCURRENT_SIMULATION_MODE': self.CONCURRENT_SIMULATION_MODE,
            'filename': self.filename,
            'result_queue': self.result_queue,
            'process_counter': Value('i', 1),
            'sections_queue': self.sections_queue,
            'day_event': Event(),
            'day_event_lock': Lock(),
            'finished_crews_for_the_day': Value('i', 0),
            'active_crews': Value('i', self.num_crews),
            'celery_task_aborted_mprcss': self.celery_task_aborted_mprcss,
            'daily_cost_section': self.daily_cost_section,
        }

    def init_multiprocessing_with_manager(self) -> None:
        self.build_kwargs = {
            'CONCURRENT_SIMULATION_MODE': self.CONCURRENT_SIMULATION_MODE,
            'filename': self.filename,
            'result_queue': self.result_queue,
            'process_counter': self.manager.Value('i', 1),
            'sections_queue': self.sections_queue,
            'finished_crews_for_the_day': self.manager.Value('i', 0),
            'active_crews': self.manager.Value('i', self.num_crews),
            'celery_task_aborted_mprcss': self.celery_task_aborted_mprcss,
            'daily_cost_section': self.daily_cost_section,
            'result_queue_with_manager': self.result_queue_with_manager,
        }

        if self.CONCURRENT_SIMULATION_MODE == 'multiprocessing_v3':
            self.build_kwargs['day_condition'] = self.manager.Condition()
        else:
            self.build_kwargs['day_event'] = self.manager.Event()
            self.build_kwargs['day_event_lock'] = self.manager.Lock()

        if settings.ACTIVE_TESTING:
            self.build_kwargs['testing_wall_construction_config_mprcss'] = self.convert_list(
                self.testing_wall_construction_config
            )

    def result_handler(self, result_queue: Union[Queue, mprcss_Queue]) -> None:
        """
        Dedicated thread for handling logging and accumulating results.
        """
        while True:
            if self.is_manager_required():
                result_queue = self.result_queue_with_manager
            else:
                result_queue = self.result_queue

            record = result_queue.get()
            if record is None:
                break

            if isinstance(record, LogRecord):
                # Logging
                self.logger.handle(record)

            elif record.get('type') == 'daily_progress_test_data':
                # Test data
                profile_id = record['profile_id']
                section_id = record['section_id']
                height = record['height']
                self.testing_wall_construction_config[profile_id - 1][section_id - 1] = height

            elif record.get('type') == 'wall_profile_data':
                # Build progress data
                profile_id = record['profile_id']
                current_process_day = record['current_process_day']
                BaseWallBuilder.update_wall_profile_data(self.wall_profile_data, current_process_day, profile_id)
                self.wall_profile_data['profiles_overview']['construction_days'] = current_process_day

    def create_queue(self) -> Union[Queue, mprcss_Queue]:
        if self.is_manager_required():
            return self.manager.Queue()
        else:
            return mprcss_Queue()

    def convert_list(self, list_to_convert: list):
        """
        Transform a normal Python nested list of lists into a nested list
        of multiprocessing.Manager().list and vice versa.
        """
        if isinstance(list_to_convert, list):
            # Return a managed list
            return self.manager.list([self.manager.list(profile) for profile in list_to_convert])
        else:
            # Return a normal list
            return list([list(profile) for profile in list_to_convert])

    def calc_wall_profile_data_concurrent(self) -> None:
        """
        Concurrent construction process simulation.
        Using a limited number of crews.
        """
        futures = self.manage_processes()

        # Stop the relevant result/logging listener
        # and store the testing results
        if self.is_manager_required():
            self.qlistener.stop()
            self.result_queue_with_manager.put(None)
            testing_wall_construction_config = self.build_kwargs.get('testing_wall_construction_config_mprcss')
            if testing_wall_construction_config is not None:
                self.testing_wall_construction_config.clear()
                self.testing_wall_construction_config.extend(
                    self.convert_list(testing_wall_construction_config)
                )
        self.result_queue.put(None)
        self.result_handler_thread.join()

        self.extract_log_data()

        # Raise any exceptions from the ProcessPoolExecutor
        for future in futures:
            future.result()

    def manage_processes(self) -> list:
        futures = []
        if self.is_manager_required():
            with ProcessPoolExecutor(max_workers=self.num_crews) as executor:
                futures = [executor.submit(MultiprocessingWallBuilder.build_section, **self.build_kwargs) for _ in range(self.num_crews)]
        else:
            process_list = []

            for _ in range(self.num_crews):  # Start with the available crews
                build_section_process = Process(
                    target=MultiprocessingWallBuilder.build_section, kwargs=self.build_kwargs
                )
                build_section_process.start()
                process_list.append(build_section_process)

            for process in process_list:
                process.join()

        return futures

    @staticmethod
    def build_section(result_queue: Union[Queue, mprcss_Queue], **build_kwargs) -> None:
        """
        Single wall section construction simulation.
        Logs the progress and the completion details in a log file.
        """
        logger = BaseWallBuilder.setup_logger(
            build_kwargs['filename'], queue=result_queue, source_name='processName'
        )
        process = current_process()
        build_kwargs['logger'] = logger
        try:
            MultiprocessingWallBuilder.assign_process_name(process, build_kwargs['process_counter'])
            build_kwargs['process_name'] = process.name
            MultiprocessingWallBuilder.process_sections(result_queue=result_queue, **build_kwargs)
        except Exception as bld_sctn_err:
            logger.error(f'Error in process {process.name}: {bld_sctn_err}', extra={'source_name': process.name})
            raise

    @staticmethod
    def assign_process_name(process, process_counter) -> None:
        """
        Assigns a shorter process name for better readability in the logs.
        """
        if not process.name.startswith('Crew-'):
            process.name = f'Crew-{process_counter.value}'
            process_counter.value += 1

    @staticmethod
    def process_sections(
        sections_queue: Union[Queue, mprcss_Queue], CONCURRENT_SIMULATION_MODE: str, **build_kwargs
    ) -> None:
        """
        Processes the sections for the crew until there are no more sections available.
        """
        current_process_day = 0
        while not sections_queue.empty():
            try:
                # Get the next section from the queue
                profile_id, section_id, height = sections_queue.get_nowait()
            except Empty:
                # No more sections to process
                break

            current_process_day = MultiprocessingWallBuilder.process_section(
                profile_id, section_id, height, current_process_day,
                CONCURRENT_SIMULATION_MODE=CONCURRENT_SIMULATION_MODE, **build_kwargs
            )

            if build_kwargs['celery_task_aborted_mprcss'].value:
                break

        # When there are no more sections available for the crew, relieve it
        manage_crew_release = MultiprocessingWallBuilder.get_manage_crew_release_func(
            CONCURRENT_SIMULATION_MODE
        )
        manage_crew_release(current_process_day, **build_kwargs)

    @staticmethod
    def process_section(
        profile_id: int, section_id: int, height: int, current_process_day: int, daily_cost_section: int,
        logger: Logger, process_name: str, CONCURRENT_SIMULATION_MODE: str,
        testing_wall_construction_config_mprcss: list | None = None,
        **build_kwargs
    ) -> int:
        # Initialize section construction variables
        total_ice_used = 0
        total_cost = 0

        while height < MAX_SECTION_HEIGHT:
            height += 1
            current_process_day += 1
            total_ice_used += ICE_PER_FOOT
            total_cost += daily_cost_section

            # Daily progress
            MultiprocessingWallBuilder.log_daily_progress(
                profile_id, section_id, current_process_day, height,
                logger, process_name, build_kwargs['result_queue'], testing_wall_construction_config_mprcss
            )

            # Section finalization
            MultiprocessingWallBuilder.log_section_completion(
                height, profile_id, section_id, current_process_day, logger, process_name
            )

            # Synchronize with the other crews at the end of the day
            end_of_day_synchronization = MultiprocessingWallBuilder.get_end_of_day_synchronization_func(
                CONCURRENT_SIMULATION_MODE
            )
            end_of_day_synchronization(current_process_day, profile_id, **build_kwargs)

            if build_kwargs['celery_task_aborted_mprcss'].value:
                return current_process_day

        return current_process_day

    @staticmethod
    def log_daily_progress(
        profile_id: int, section_id: int, current_process_day: int, height: int,
        logger: Logger, process_name: str, result_queue: Union[Queue, mprcss_Queue],
        testing_wall_construction_config_mprcss: list[list[int]] | None
    ) -> None:
        if VERBOSE_MULTIPROCESSING_LOGGING:
            section_progress_msg = BaseWallBuilder.get_section_progress_msg(
                profile_id, section_id, current_process_day, height
            )
            # Grace period to avoid the rare issue of the records not being received in the result
            # queue in the right order, although their timestamps show,
            # they're generated at the correct time
            sleep(uniform(0.01, 0.02))
            logger.debug(section_progress_msg, extra={'source_name': process_name})

        if settings.ACTIVE_TESTING:
            if testing_wall_construction_config_mprcss is None:
                result_queue.put_nowait({
                    'type': 'daily_progress_test_data',
                    'profile_id': profile_id,
                    'section_id': section_id,
                    'height': height,
                })
            else:
                testing_wall_construction_config_mprcss[profile_id - 1][section_id - 1] = height

    @staticmethod
    def log_section_completion(
        height: int, profile_id: int, section_id: int, current_process_day: int,
        logger: Logger, process_name: str
    ) -> None:
        if height == MAX_SECTION_HEIGHT:
            if VERBOSE_MULTIPROCESSING_LOGGING:
                sleep(0.05)     # Grace period to ensure finish section records are at the end of the day's records
            section_completion_msg = BaseWallBuilder.get_section_completion_msg(
                profile_id, section_id, current_process_day
            )
            logger.debug(section_completion_msg, extra={'source_name': process_name})

# === Common logic ===
    @staticmethod
    def get_manage_crew_release_func(CONCURRENT_SIMULATION_MODE: str) -> Callable:
        if CONCURRENT_SIMULATION_MODE == 'multiprocessing_v3':
            return MultiprocessingWallBuilder.manage_crew_release_v3
        return MultiprocessingWallBuilder.manage_crew_release_v1_v2

    @staticmethod
    def get_end_of_day_synchronization_func(CONCURRENT_SIMULATION_MODE: str) -> Callable:
        if CONCURRENT_SIMULATION_MODE == 'multiprocessing_v3':
            return MultiprocessingWallBuilder.end_of_day_synchronization_v3
        return MultiprocessingWallBuilder.end_of_day_synchronization_v1_v2

    @staticmethod
    def check_notify_all_workers_to_resume_work(
        finished_crews_for_the_day, active_crews, celery_task_aborted_mprcss,
        day_event=None, day_condition=None
    ) -> bool:
        if finished_crews_for_the_day.value == active_crews.value or celery_task_aborted_mprcss.value:
            # Last crew to reach this point resets the counter and notifies all others,
            # or a revocation signal is received and the simulation is interrupted
            finished_crews_for_the_day.value = 0

            if day_event:
                day_event.set()         # Wake up all waiting processes
                sleep(0.01)             # Grace period to ensure the other processes register the event set
                day_event.clear()       # Reset the event for the next day
            elif day_condition:
                day_condition.notify_all()

            return True

        return False

# === Common logic (end) ===

# === v1, v2 Event sync. ===
    @staticmethod
    def manage_crew_release_v1_v2(
        current_process_day: int, logger, day_event_lock, finished_crews_for_the_day,
        active_crews, celery_task_aborted_mprcss, day_event, **build_kwargs
    ) -> None:
        with day_event_lock:
            relieved_crew_msg = BaseWallBuilder.get_relieved_crew_msg(current_process_day)
            logger.debug(relieved_crew_msg, extra={'source_name': build_kwargs['process_name']})

            active_crews.value -= 1
            MultiprocessingWallBuilder.check_notify_all_workers_to_resume_work(
                finished_crews_for_the_day, active_crews, celery_task_aborted_mprcss, day_event=day_event
            )

    @staticmethod
    def end_of_day_synchronization_v1_v2(
        current_process_day: int, profile_id: int, day_event_lock, finished_crews_for_the_day,
        active_crews, celery_task_aborted_mprcss, day_event, **build_kwargs
    ) -> None:
        with day_event_lock:
            # Put build progress data
            if 'result_queue_with_manager' in build_kwargs:
                # v2
                wall_profile_data_queue = build_kwargs['result_queue_with_manager']
            else:
                # v1
                wall_profile_data_queue = build_kwargs['result_queue']
            wall_profile_data_queue.put_nowait({
                'type': 'wall_profile_data',
                'profile_id': profile_id,
                'current_process_day': current_process_day
            })

            # Synchronize with the other crews
            finished_crews_for_the_day.value += 1
            other_crews_notified = MultiprocessingWallBuilder.check_notify_all_workers_to_resume_work(
                finished_crews_for_the_day, active_crews, celery_task_aborted_mprcss, day_event=day_event
            )

        if not other_crews_notified:
            day_event.wait()

# === v1, v2 Event sync. (end)===

# === v3 Condition sync. ===
    @staticmethod
    def manage_crew_release_v3(
        current_process_day: int, logger, day_condition, finished_crews_for_the_day,
        active_crews, celery_task_aborted_mprcss, **build_kwargs
    ) -> None:
        with day_condition:
            relieved_crew_msg = BaseWallBuilder.get_relieved_crew_msg(current_process_day)
            logger.debug(relieved_crew_msg, extra={'source_name': build_kwargs['process_name']})

            active_crews.value -= 1
            MultiprocessingWallBuilder.check_notify_all_workers_to_resume_work(
                finished_crews_for_the_day, active_crews, celery_task_aborted_mprcss, day_condition=day_condition
            )

    @staticmethod
    def end_of_day_synchronization_v3(
        current_process_day: int, profile_id: int, day_condition, finished_crews_for_the_day, active_crews,
        celery_task_aborted_mprcss, result_queue_with_manager, **build_kwargs
    ) -> None:
        with day_condition:
            result_queue_with_manager.put_nowait({
                'type': 'wall_profile_data',
                'profile_id': profile_id,
                'current_process_day': current_process_day
            })

            finished_crews_for_the_day.value += 1
            if MultiprocessingWallBuilder.check_notify_all_workers_to_resume_work(
                finished_crews_for_the_day, active_crews, celery_task_aborted_mprcss, day_condition=day_condition
            ):
                return
            else:
                day_condition.wait()
# === v3 Condition sync. (end)===
