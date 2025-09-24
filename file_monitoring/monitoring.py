import os
from exceptions import FileProcessingError, NetworkError, StorageError
import time
import schedule
from loader import logger
from config import TOKEN, CLOUD_FOLDER, SYNC_FOLDER, PERIOD_OF_SYNC
from cloud_storage.yandex_disk import YandexDisk
from typing import Dict, Optional


class FileMonitoring:
    """Класс для мониторинга локальной папки и синхронизации с Яндекс.Диском."""

    def __init__(self, disk, local_folder: str, cloud_folder: str) -> None:
        self.disk = disk
        self.local_folder = local_folder
        self.cloud_folder = cloud_folder
        self.previous_files = {}
        self.cloud_files = {}  # будем здесь хранить список облачных файлов при старте


    def cache_cloud_files(self) -> None:
        """Загружает и кэширует список файлов из облачной папки."""

        cloud_files_info = self.disk.get_info() or []
        self.cloud_files = {f['name']: f['size'] for f in cloud_files_info}
        logger.debug(f"Облачные файлы загружены и закешированы: {list(self.cloud_files.keys())}")


    def mirror_sync(self) -> None:
        """Выполняет зеркальную синхронизацию: удаление из облака файлов,
        отсутствующих локально, и загрузку/обновление локальных файлов в облако."""

        logger.debug("Запуск зеркальной синхронизации....")
        local_files_state = self.get_files_state()
        local_files = set(local_files_state.keys())
        cloud_files_names = set(self.cloud_files.keys())

        # Удаление файлов из облака, отсутствующих локально
        for filename in cloud_files_names - local_files:
            logger.debug(f"Удаление файла из облака: {filename}")
            self.disk.delete(filename)

        # Загрузка или обновление локальных файлов в облако
        for filename in local_files:
            local_path = os.path.join(self.local_folder, filename)
            if filename not in self.cloud_files:
                logger.debug(f"Загрузка нового файла: {filename}")
                self.disk.load(local_path)
            else:
                logger.debug(f"Обновление файла в облаке: {filename}")
                self.disk.reload(local_path)

        # После зеркальной синхронизации обновляем кэш облачных файлов
        self.cache_cloud_files()


    def get_files_state(self) -> Dict[str, float]:
        """Анализирует локальную папку и возвращает словарь файлов
        и их времени изменения."""

        logger.debug("Анализ локальной папки")
        files = {}
        try:
            for filename in os.listdir(self.local_folder):
                path = os.path.join(self.local_folder, filename)
                if os.path.isfile(path):
                    files[filename] = os.path.getmtime(path)
        except OSError as e:
            logger.error(f"Ошибка при чтении папок/файлов: {e}")
            raise FileProcessingError(str(e)) from e
        else:
            return files


    def upload_new_files(self, current_state: Dict[str, float]) -> None:
        """Загружает на облако файлы, отсутствующие в предыдущем состоянии."""

        for filename, change_time in current_state.items():
            if filename not in self.previous_files:
                local_path = os.path.join(self.local_folder, filename)
                try:
                    self.disk.load(local_path)  # Загружаем с overwrite=True внутри load
                except Exception as e:
                    logger.error(f"Ошибка загрузки файла {filename}: {e}")
                    raise NetworkError(operation="загрузка файла", details=str(e)) from e


    def update_modified_files(self, current_state: Dict[str, float]) -> None:
        """Перезаписывает на облаке локально изменённые файлы."""

        logger.debug("Поиск изменённых файлов...")
        for filename, change_time in current_state.items():
            if filename in self.previous_files and self.previous_files[filename] != change_time:
                local_path = os.path.join(self.local_folder, filename)
                try:
                    self.disk.reload(local_path)  # reload должен делать перезапись с overwrite=True
                except Exception as e:
                    logger.error(f"Ошибка перезаписи файла {filename}: {e}")
                    raise NetworkError(operation="перезапись файла", details=str(e)) from e


    def delete_removed_files(self, current_state: Dict[str, float]) -> None:
        """Удаляет из облака файлы, которые были удалены локально."""

        logger.debug("Поиск удаленных файлов...")
        for filename in self.previous_files:
            if filename not in current_state:
                try:
                    self.disk.delete(filename)
                except Exception as e:
                    logger.error(f"Ошибка удаления {filename}: {e}")
                    raise NetworkError(str(e))


    def sync(self) -> None:
        """Запускает последовательную синхронизацию: загрузку новых файлов,
            обновление изменённых и удаление удалённых.
           Обновляет состояние previous_files. """
        logger.debug("Запуск синхронизации...")
        current_state = self.get_files_state()
        self.upload_new_files(current_state)
        self.update_modified_files(current_state)
        self.delete_removed_files(current_state)
        self.previous_files = current_state



def main():
    """
       Основная функция запуска программы синхронизации.
       - Инициализирует объекты для работы с Яндекс.Диском и мониторинга.
       - Загружает состояние облака и выполняет первую зеркальную синхронизацию.
       - Запускает периодическую синхронизацию с заданным интервалом.
       - Обрабатывает прерывание программы пользователем.
       """
    logger.debug("Передаем токен и имя папки синхронизации в инициацию класса YandexDisk")
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
            print('------------------------------------------------------------------------')
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