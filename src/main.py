from src.loader import logger
import time
import schedule
from src.cloud.yandex_disk import YandexDisk
from src.exceptions import StorageError
from src.file_monitoring.monitoring import FileMonitoring
from src.config import TOKEN, CLOUD_FOLDER, SYNC_FOLDER, PERIOD_OF_SYNC  # type: ignore


def main():
    logger.debug(
        "Передаем токен и имя папки синхронизации в инициацию класса YandexDisk"
    )
    yandex_disk = YandexDisk(TOKEN, CLOUD_FOLDER)
    logger.debug("Передаем Токен и Имя папок синхронизации в инициацию FileMonitoring")
    file_monitor = FileMonitoring(yandex_disk, SYNC_FOLDER, CLOUD_FOLDER)

    # Загрузка состояния облака один раз
    file_monitor.cache_cloud_files()

    # Первая зеркальная синхронизация при старте
    try:
        file_monitor.mirror_sync()
    except StorageError as e:
        logger.error(f"Ошибка во время первой зеркальной синхронизации: {e}")

    file_monitor.previous_files = file_monitor.get_files_state()

    def job():
        try:
            print(
                "------------------------------------------------------------------------"
            )
            file_monitor.sync()
        except StorageError as e:
            logger.error(f"Ошибка во время синхронизации: {e}")

    logger.debug(f"Задали период синхронизации каждые {PERIOD_OF_SYNC} секунд")
    schedule.every(PERIOD_OF_SYNC).seconds.do(job)

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.debug("Программа остановлена пользователем.")


if __name__ == "__main__":
    logger.info("Программа синхронизации запущена!")
    # Запуск кода monitoring.py
    main()
