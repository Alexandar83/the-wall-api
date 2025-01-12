# Different implementations of the concurrent wall build simulation

from abc import ABC, abstractmethod
from datetime import datetime
from io import StringIO
import logging
import logging.handlers
from multiprocessing import Queue as mprcss_Queue
import os
from queue import Queue
from secrets import token_hex
from typing import Union

from django.conf import settings

from the_wall_api.utils.message_themes import (
    base as base_messages, errors as error_messages, info as info_messages
)

BUILD_SIM_LOGS_DIR = settings.BUILD_SIM_LOGS_DIR
ICE_PER_FOOT = settings.ICE_PER_FOOT


class BaseWallBuilder(ABC):

    def __getattr__(self, name):
        return getattr(self._wall_construction, name)

    def __init__(self, wall_construction):
        self._wall_construction = wall_construction
        timestamp = datetime.now().strftime('%Y_%m_%d_%H_%M_%S_%f')
        self.filename = os.path.join(
            BUILD_SIM_LOGS_DIR,
            f'{timestamp}_{self.wall_config_hash}_{self.num_crews}_{token_hex(4)}.log'
        )
        self.sections_queue = self.init_sections_queue()

    @abstractmethod
    def create_queue(self) -> Union[Queue, mprcss_Queue]:
        pass

    @abstractmethod
    def calc_wall_profile_data_concurrent(self):
        pass

    def init_sections_queue(self):
        queue = self.create_queue()
        for profile_id, profile in enumerate(self.wall_construction_config, 1):
            for section_id, height in enumerate(profile, 1):
                queue.put((profile_id, section_id, height))
        return queue

    def extract_log_data(self) -> None:
        # Write the log stream to the log file without any formatting

        if self.celery_task_aborted:
            self.log_stream.write(info_messages.INTERRUPTED_BY_ABORT_SIGNAL)

        with open(self.filename, 'w') as log_file:
            log_file.write(self.log_stream.getvalue())

        if self.proxy_wall_creation_call:
            print(base_messages.DONE)
            print(info_messages.proxy_wall_results(self.filename))

    @staticmethod
    def setup_logger(
        filename: str, log_stream: StringIO | None = None, queue: Union[Queue, mprcss_Queue, None] = None,
        manage_formatter: bool = True, source_name: str = ''
    ) -> logging.Logger:
        """
        Set up the logger dynamically.
        Using the Django LOGGING config leads to Celery tasks hijacking
        each other's loggers in concurrent mode.
        """
        if queue is None:
            logger_name = filename
        else:
            logger_name = 'qlistener_logger' + filename

        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        if queue:
            handler = logging.handlers.QueueHandler(queue)
        else:
            if log_stream is None:
                raise ValueError(error_messages.LOG_STREAM_REQUIRED_WHEN_NO_QUEUE)
            handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.DEBUG)

        if manage_formatter:
            # Formatter
            formatter = logging.Formatter(f'%(asctime)s %(levelname)s [%({source_name})s] %(message)s')
            handler.setFormatter(formatter)

        # Handler to the logger
        logger.addHandler(handler)

        return logger

    @staticmethod
    def get_section_progress_msg(profile_id: int, section_id: int, day: int, height: int) -> str:
        message = (
            f'| DAY_{day} | {profile_id}-{section_id} | New height: {height} ft'
        )

        return message

    @staticmethod
    def get_section_completion_msg(profile_id: int, section_id: int, day: int) -> str:
        message = f'| DAY_{day} | {profile_id}-{section_id} | section finished'

        return message

    @staticmethod
    def get_relieved_crew_msg(day: int) -> str:
        message = f'| DAY_{day} | relieved'

        return message

    @staticmethod
    def update_wall_profile_data(wall_profile_data: dict, day: int, profile_id: int) -> None:
        daily_details = wall_profile_data['profiles_overview']['daily_details'].setdefault(day, {})
        # Profile daily amount - overview is derived
        daily_details.setdefault(profile_id, 0)
        daily_details[profile_id] += settings.ICE_PER_FOOT
        # Profiles daily overview
        daily_details.setdefault('dly_ttl', 0)
        daily_details['dly_ttl'] += settings.ICE_PER_FOOT
        # Wall total overview
        wall_profile_data['profiles_overview']['total_ice_amount'] += settings.ICE_PER_FOOT
