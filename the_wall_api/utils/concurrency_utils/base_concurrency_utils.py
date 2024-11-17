# Different implementations of the concurrent wall build simulation

from abc import ABC, abstractmethod
from datetime import datetime
import logging
import logging.handlers
from multiprocessing import Queue as mprcss_Queue
import os
from queue import Queue
import re
from secrets import token_hex
from typing import Union

from django.conf import settings

BUILD_SIM_LOGS_DIR = settings.BUILD_SIM_LOGS_DIR
ICE_PER_FOOT = settings.ICE_PER_FOOT
MAX_MULTIPROCESSING_NUM_CREWS = settings.MAX_MULTIPROCESSING_NUM_CREWS


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
        self.max_crews = min(self.sections_count, self.num_crews)

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
        if self.celery_task_aborted:
            message = 'WRK_INTRRPTD: Work interrupted by a celery task abort signal.'
            self.logger.debug(message, extra={'source_name': 'MainThread'})
            return

        with open(self.filename, 'r') as log_file:
            for line in log_file:
                # Extract profile_id, day, ice used, and cost
                match = re.search(
                    r'HGHT_INCRS: Section ID: (\d+)-\d+ - DAY_(\d+) - .*Ice used: (\d+) cbc\. yrds\.', line)
                if match:
                    profile_id, day, ice_used = map(int, match.groups())

                    self.wall_profile_data.setdefault(profile_id, {}).setdefault(day, {'ice_used': 0})
                    self.wall_profile_data[profile_id][day]['ice_used'] += ice_used

    @staticmethod
    def setup_logger(filename: str) -> logging.Logger:
        """
        Set up the logger dynamically.
        Using the Django LOGGING config leads to Celery tasks hijacking
        each other's loggers in concurrent mode.
        """
        # Ensure the directory exists
        log_dir = os.path.dirname(filename)
        os.makedirs(log_dir, exist_ok=True)

        logger = logging.getLogger(filename)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        handler = logging.FileHandler(filename, mode='w')
        handler.setLevel(logging.DEBUG)

        formatter = logging.Formatter('%(asctime)s %(levelname)s [%(threadName)s] %(message)s')
        handler.setFormatter(formatter)

        # Handler to the logger
        logger.addHandler(handler)

        return logger

    @staticmethod
    def get_section_progress_msg(
        profile_id: int, section_id: int, day: int, height: int, daily_cost_section: int
    ) -> str:
        message = (
            f'HGHT_INCRS: Section ID: {profile_id}-{section_id} - DAY_{day} - '
            f'New height: {height} ft - Ice used: {ICE_PER_FOOT} cbc. yrds. - '
            f'Cost: {daily_cost_section} gold drgns.'
        )

        return message

    @staticmethod
    def get_section_completion_msg(
        profile_id: int, section_id: int, day: int, total_ice_used: int, total_cost: int
    ) -> str:
        message = (
            f'FNSH_SCTN: Section ID: {profile_id}-{section_id} - DAY_{day} - finished. '
            f'Ice used: {total_ice_used} cbc. yrds. - Cost: {total_cost} gold drgns.'
        )

        return message
