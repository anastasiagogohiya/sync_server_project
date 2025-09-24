from loguru import logger
from config import LOG_FILE_PATH, SYNC_FOLDER
import sys


logger.remove()
logger = logger.bind(SYNC_FOLDER=SYNC_FOLDER)
logger.add(sys.stdout, level="DEBUG",
           format="{extra[SYNC_FOLDER]} | {time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")
logger.add(LOG_FILE_PATH, rotation="3 MB", encoding="utf-8",
           level="INFO",
           format="{extra[SYNC_FOLDER]} | {time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")