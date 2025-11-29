import os
import logging
from logging.handlers import RotatingFileHandler

filepath = "model_testing/logs/model_logs/model_testing.log"
name = "model_logger"
os.makedirs(os.path.dirname(filepath), exist_ok=True)

logger = logging.getLogger(name)
logger.setLevel(logging.INFO)

file_handler = RotatingFileHandler(
    filepath,
    maxBytes=1_000_000,
    backupCount=5,
    encoding="utf-8"
)

formatter = logging.Formatter(
    "%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    "%Y-%m-%d %H:%M:%S"
)

file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
