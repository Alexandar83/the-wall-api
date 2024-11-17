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

CONCURRENT_SIMULATION_MODE = settings.CONCURRENT_SIMULATION_MODE
ICE_PER_FOOT = settings.ICE_PER_FOOT
MAX_MULTIPROCESSING_NUM_CREWS = settings.MAX_MULTIPROCESSING_NUM_CREWS
MAX_SECTION_HEIGHT = settings.MAX_SECTION_HEIGHT


class MultiprocessingWallBuilder(BaseWallBuilder):

    def __init__(self, wall_construction):
        self.manager = Manager()
        super().__init__(wall_construction)
        if self.max_crews > MAX_MULTIPROCESSING_NUM_CREWS:
            from the_wall_api.utils.error_utils import WallConstructionError
            # Multiprocessing limitations, due to:
            # -the nature of the build simulation - 1 crew (process) per section
            # -CPU limitations
            raise WallConstructionError(
                f'Max. allowed number of sections for multiprocessing is {MAX_MULTIPROCESSING_NUM_CREWS}'
            )
        self.init_result_handler()
        if self.is_manager_required():
            self.init_multiprocessing_with_manager()
        else:
            self.init_multiprocessing()

    def init_result_handler(self) -> None:
        self.logger = BaseWallBuilder.setup_logger(self.filename, manage_formatter=False)
        self.result_queue = self.create_queue()
        if self.is_manager_required():
            self.qlistener = logging.handlers.QueueListener(self.result_queue, *self.logger.handlers)
            self.qlistener.start()
        else:
            self.result_handler_thread = Thread(name='LoggerThread', target=self.result_handler, daemon=True)
            self.result_handler_thread.start()

    def init_multiprocessing(self) -> None:
        self.build_kwargs = {
            'filename': self.filename,
            'result_queue': self.result_queue,
            'process_counter': Value('i', 1),
            'sections_queue': self.sections_queue,
            'day_event': Event(),
            'day_event_lock': Lock(),
            'finished_crews_for_the_day': Value('i', 0),
            'active_crews': Value('i', self.max_crews),
            'celery_task_aborted_mprcss': self.celery_task_aborted_mprcss,
            'daily_cost_section': self.daily_cost_section,
        }

    def init_multiprocessing_with_manager(self) -> None:
        self.build_kwargs = {
            'filename': self.filename,
            'result_queue': self.result_queue,
            'process_counter': self.manager.Value('i', 1),
            'sections_queue': self.sections_queue,
            'finished_crews_for_the_day': self.manager.Value('i', 0),
            'active_crews': self.manager.Value('i', self.max_crews),
            'celery_task_aborted_mprcss': self.celery_task_aborted_mprcss,
            'daily_cost_section': self.daily_cost_section,
        }

        if CONCURRENT_SIMULATION_MODE == 'multiprocessing_v3':
            self.build_kwargs['day_condition'] = self.manager.Condition()
        else:
            self.build_kwargs['day_event'] = self.manager.Event()
            self.build_kwargs['day_event_lock'] = self.manager.Lock()

        if settings.ACTIVE_TESTING:
            self.build_kwargs['testing_wall_construction_config_mprcss'] = self.convert_list(
                self.testing_wall_construction_config
            )

    def result_handler(self) -> None:
        """
        Dedicated thread for handling logging and accumulating results.
        """
        while True:
            record = self.result_queue.get()
            if record is None:
                break

            if isinstance(record, LogRecord):
                self.logger.handle(record)
            else:
                profile_id = record['profile_id']
                section_id = record['section_id']
                height = record['height']
                self.testing_wall_construction_config[profile_id - 1][section_id - 1] = height

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
            testing_wall_construction_config = self.build_kwargs.get('testing_wall_construction_config_mprcss')
            if testing_wall_construction_config is not None:
                self.testing_wall_construction_config.clear()
                self.testing_wall_construction_config.extend(
                    self.convert_list(testing_wall_construction_config)
                )
        else:
            self.result_queue.put(None)
            self.result_handler_thread.join()

        # Extract the result from the logs and store it in the WallConstruction
        self.extract_log_data()

        # Raise any exceptions from the ProcessPoolExecutor
        for future in futures:
            future.result()

    def manage_processes(self) -> list:
        futures = []
        if self.is_manager_required():
            with ProcessPoolExecutor(max_workers=self.max_crews) as executor:
                futures = [executor.submit(MultiprocessingWallBuilder.build_section, **self.build_kwargs) for _ in range(self.max_crews)]
        else:
            process_list = []

            for _ in range(self.max_crews):  # Start with the available crews
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
    def process_sections(sections_queue: Union[Queue, mprcss_Queue], **build_kwargs) -> None:
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
                profile_id, section_id, height, current_process_day, **build_kwargs
            )

            if build_kwargs['celery_task_aborted_mprcss'].value:
                break

        # When there are no more sections available for the crew, relieve it
        manage_crew_release = MultiprocessingWallBuilder.get_manage_crew_release_func()
        manage_crew_release(**build_kwargs)

    @staticmethod
    def process_section(
        profile_id: int, section_id: int, height: int, current_process_day: int, daily_cost_section: int,
        logger: Logger, process_name: str, result_queue: Union[Queue, mprcss_Queue],
        testing_wall_construction_config_mprcss: list | None = None, **build_kwargs
    ) -> int:
        # Initialize section construction variables
        total_ice_used = 0
        total_cost = 0

        while height < MAX_SECTION_HEIGHT:
            height += 1
            current_process_day += 1
            total_ice_used += ICE_PER_FOOT
            total_cost += daily_cost_section

            # Log the daily progress
            MultiprocessingWallBuilder.log_daily_progress(
                profile_id, section_id, current_process_day, height, daily_cost_section,
                logger, process_name, result_queue, testing_wall_construction_config_mprcss
            )

            # Log the section finalization
            MultiprocessingWallBuilder.log_section_completion(
                height, profile_id, section_id, current_process_day, total_ice_used,
                total_cost, logger, process_name
            )

            # Synchronize with the other crews at the end of the day
            end_of_day_synchronization = MultiprocessingWallBuilder.get_end_of_day_synchronization_func()
            end_of_day_synchronization(**build_kwargs)

            if build_kwargs['celery_task_aborted_mprcss'].value:
                return current_process_day

        return current_process_day

    @staticmethod
    def log_daily_progress(
        profile_id: int, section_id: int, current_process_day: int, height: int,
        daily_cost_section: int, logger: Logger, process_name: str, result_queue: Union[Queue, mprcss_Queue],
        testing_wall_construction_config_mprcss: list[list[int]] | None
    ) -> None:
        section_progress_msg = BaseWallBuilder.get_section_progress_msg(
            profile_id, section_id, current_process_day, height, daily_cost_section
        )
        # Grace period to avoid the rare issue of the records not being received in the result
        # queue in the right order, although their timestamps show,
        # they're generated at the correct time
        sleep(uniform(0.01, 0.02))
        logger.debug(section_progress_msg, extra={'source_name': process_name})

        if settings.ACTIVE_TESTING:
            if testing_wall_construction_config_mprcss is None:
                result_queue.put_nowait({
                    'profile_id': profile_id,
                    'section_id': section_id,
                    'height': height,
                })
            else:
                testing_wall_construction_config_mprcss[profile_id - 1][section_id - 1] = height

    @staticmethod
    def log_section_completion(
        height: int, profile_id: int, section_id: int, current_process_day: int, total_ice_used: int,
        total_cost: int, logger: Logger, process_name: str
    ) -> None:
        if height == MAX_SECTION_HEIGHT:
            sleep(0.025)     # Grace period to ensure finish section records are at the end of the day's records
            section_completion_msg = BaseWallBuilder.get_section_completion_msg(
                profile_id, section_id, current_process_day, total_ice_used, total_cost
            )
            logger.debug(section_completion_msg, extra={'source_name': process_name})

# === Common logic ===
    @staticmethod
    def get_manage_crew_release_func() -> Callable:
        if CONCURRENT_SIMULATION_MODE == 'multiprocessing_v3':
            return MultiprocessingWallBuilder.manage_crew_release_v3
        return MultiprocessingWallBuilder.manage_crew_release_v1_v2

    @staticmethod
    def get_end_of_day_synchronization_func() -> Callable:
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
        day_event_lock, finished_crews_for_the_day, active_crews, celery_task_aborted_mprcss,
        day_event, **build_kwargs
    ) -> None:
        with day_event_lock:
            active_crews.value -= 1
            MultiprocessingWallBuilder.check_notify_all_workers_to_resume_work(
                finished_crews_for_the_day, active_crews, celery_task_aborted_mprcss, day_event=day_event
            )

    @staticmethod
    def end_of_day_synchronization_v1_v2(
        day_event_lock, finished_crews_for_the_day, active_crews, celery_task_aborted_mprcss,
        day_event, **build_kwargs
    ) -> None:
        with day_event_lock:
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
        day_condition, finished_crews_for_the_day, active_crews, celery_task_aborted_mprcss, **build_kwargs
    ) -> None:
        with day_condition:
            active_crews.value -= 1
            MultiprocessingWallBuilder.check_notify_all_workers_to_resume_work(
                finished_crews_for_the_day, active_crews, celery_task_aborted_mprcss, day_condition=day_condition
            )

    @staticmethod
    def end_of_day_synchronization_v3(
        day_condition, finished_crews_for_the_day, active_crews, celery_task_aborted_mprcss, **build_kwargs
    ) -> None:
        with day_condition:
            finished_crews_for_the_day.value += 1
            if MultiprocessingWallBuilder.check_notify_all_workers_to_resume_work(
                finished_crews_for_the_day, active_crews, celery_task_aborted_mprcss, day_condition=day_condition
            ):
                return
            else:
                day_condition.wait()
# === v3 Condition sync. (end)===
