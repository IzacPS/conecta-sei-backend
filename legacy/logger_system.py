import sys
import queue
import datetime
import threading
from typing import Optional


class UILogger:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(UILogger, cls).__new__(cls)
            cls._instance.log_queue = None
        return cls._instance

    def set_queue(self, queue_obj: queue.Queue):
        self.log_queue = queue_obj

    def log(self, message: str):
        if self.log_queue:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.log_queue.put(f"[{timestamp}] {message}")


class StdoutRedirector:
    def __init__(self, logger: UILogger):
        self.logger = logger

    def write(self, text: str):
        if text.strip():
            self.logger.log(text.strip())

    def flush(self):
        pass


def setup_logging(log_queue: queue.Queue):
    logger = UILogger()
    logger.set_queue(log_queue)
    sys.stdout = StdoutRedirector(logger)
    return logger
