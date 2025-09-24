import os
from dotenv import load_dotenv, find_dotenv

# Загрузка .env
if not find_dotenv():
    raise FileNotFoundError("Отсутствует файл .env")
load_dotenv()

TOKEN = os.getenv("TOKEN", None)
CLOUD_FOLDER = os.getenv("CLOUD_FOLDER", None)
SYNC_FOLDER = os.getenv("SYNC_FOLDER", None)
period = os.getenv("PERIOD_OF_SYNC", None)
PERIOD_OF_SYNC = int(period)
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH")

# Валидация
missing_vars = [var for var in ("TOKEN", "CLOUD_FOLDER", "SYNC_FOLDER", "PERIOD_OF_SYNC", "LOG_FILE_PATH") if not globals().get(var)]
if missing_vars:
    raise ValueError(f"Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")
