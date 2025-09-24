from loader import logger
from file_monitoring.monitoring import main


if __name__ == '__main__':
    logger.info("Программа синхронизации запущена!")
    # Запуск кода monitoring.py
    main()
