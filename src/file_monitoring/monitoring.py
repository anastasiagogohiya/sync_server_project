import os
from src.exceptions import FileProcessingError, NetworkError
from src.loader import logger
from typing import Any, Dict


class FileMonitoring:
    """Класс для мониторинга локальной папки и синхронизации с Яндекс.Диском."""

    def __init__(self, disk, local_folder: str, cloud_folder: str) -> None:
        self.disk = disk
        self.local_folder = local_folder
        #if not os.path.isdir(local_folder):
        #    raise FileProcessingError(filename=local_folder, details="Папка не существует")
        self.cloud_folder = cloud_folder
        self.previous_files: Dict[str, Any] = {} # для кеширования изменений
        self.cloud_files: Dict[
            str, Any
        ] = {}  # для кеширования будем здесь хранить список облачных файлов при старте

    def _safe_call(self, operation: str, func, *args, **kwargs):
        """Выполняет функцию с обработкой ошибок и преобразованием в NetworkError."""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Ошибка при {operation}: {e}")
            raise NetworkError(operation=operation, details=str(e)) from e


    def cache_cloud_files(self) -> None:
        """Загружает и кэширует список файлов из облачной папки."""

        cloud_files_info = self.disk.get_info() or []
        self.cloud_files = {f["name"]: f["size"] for f in cloud_files_info}
        logger.debug(
            f"Облачные файлы загружены и закешированы: {list(self.cloud_files.keys())}"
        )

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
            self._safe_call("удаление", self.disk.delete, filename)

        # Загрузка или обновление локальных файлов в облако
        for filename in local_files:
            local_path = os.path.join(self.local_folder, filename)
            logger.debug(f"Загрузка/обновление: {filename}")
            self._safe_call("загрузка/обновление", self.disk.upload, local_path)

        # После зеркальной синхронизации обновляем кэш облачных файлов
        self.cache_cloud_files()
        self.previous_files = local_files_state # обновляем статус файлов

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
            raise FileProcessingError(details=str(e))
        else:
            return files


    def upload(self, current_status: Dict[str, float]) -> None:
        """Загружает на облако файлы, отсутствующие в предыдущем состоянии.
        Перезаписывает на облаке локально изменённые файлы."""

        logger.debug("Поиск изменённых файлов...")
        for filename, change_time in current_status.items():
            # если файл новый или изменилось время файла существующего
            if filename not in self.previous_files\
                    or self.previous_files[filename] != change_time:
                local_path = os.path.join(self.local_folder, filename)
                self._safe_call("загрузка/обновление", self.disk.upload, local_path)


    def delete_removed_files(self, current_state: Dict[str, float]) -> None:
        """Удаляет из облака файлы, которые были удалены локально."""

        logger.debug("Поиск удаленных файлов...")
        for filename in self.previous_files:
            if filename not in current_state:
                self._safe_call("удаление", self.disk.delete, filename)

    def sync(self) -> None:
        """Запускает последовательную синхронизацию: загрузку новых файлов,
         обновление изменённых и удаление удалённых.
        Обновляет состояние previous_files."""
        logger.debug("Запуск синхронизации...")
        current_state = self.get_files_state()
        self.upload(current_state)
        self.delete_removed_files(current_state)
        self.previous_files = current_state