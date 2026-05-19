import sys
from pathlib import Path
from loguru import logger

from src.config import LOG_FILE_PATH, SYNC_FOLDER # type: ignore

def setup_logger() -> logger:  # type: ignore
    """
    Настраивает и возвращает экземпляр логгера Loguru.
    """
    # 1. Убедимся, что директория для лог-файла существует
    log_path = Path(LOG_FILE_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # 2. Удаляем стандартный обработчик Loguru
    logger.remove()

    # 3. Добавляем обработчик для вывода в консоль (stdout)
    logger.add(
        sys.stdout,
        level="DEBUG",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        colorize=True,
        backtrace=True,
        diagnose=True,
        enqueue=True # для многопоточности
    )

    # 4. Добавляем обработчик для записи в файл
    # Используем уровень INFO для файла, чтобы не засорять его
    logger.add(
        str(log_path),
        rotation="3 MB",
        retention="60 days",
        compression="zip", # Сжимать старые логи
        encoding="utf-8",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        enqueue=True
    )

    # 5. Привязываем контекст (SYNC_FOLDER) ко всем будущим сообщениям
    return logger.opt(colors=True).bind(SYNC_FOLDER=SYNC_FOLDER)

logger = setup_logger()