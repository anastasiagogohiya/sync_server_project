import unittest
import os
from unittest.mock import MagicMock, patch
from src.file_monitoring.monitoring import FileMonitoring
from src.exceptions import NetworkError
from src.loader import logger
from src.exceptions import FileProcessingError



class TestFileMonitoring(unittest.TestCase):
    def setUp(self):
        self.mock_disk = MagicMock()
        self.file_monitor = FileMonitoring(self.mock_disk, "local_folder", "cloud_folder")

    def test_cache_cloud_files(self):
        """Тест кеширования списка файлов из облака"""
        self.mock_disk.get_info.return_value = [{'name': 'file1.txt', 'size': 123}]
        self.file_monitor.cache_cloud_files()
        self.assertIn('file1.txt', self.file_monitor.cloud_files)

    def test_upload_new_files(self):
        """Тест загрузки новых файлов"""
        self.file_monitor.previous_files = {}
        current_state = {'file2.txt': 1000}
        self.file_monitor.cloud_files = {}
        self.file_monitor.upload_new_files(current_state)
        self.mock_disk.load.assert_called_once()

    def test_update_modified_files(self):
        """Тест обновления изменённых файлов"""
        self.file_monitor.previous_files = {'file2.txt': 1000}
        current_state = {'file2.txt': 2000}
        self.file_monitor.update_modified_files(current_state)
        self.mock_disk.reload.assert_called_once()

    def test_delete_removed_files(self):
        """Тест удаления удалённых файлов"""
        self.file_monitor.previous_files = {'file3.txt': 1000}
        current_state = {}
        self.file_monitor.delete_removed_files(current_state)
        self.mock_disk.delete.assert_called_once_with('file3.txt')

    def test_upload_new_files_network_error(self):
        """Тест обработки ошибки загрузки (сетевая ошибка)"""
        self.file_monitor.previous_files = {}
        current_state = {'file1.txt': 1000}
        self.mock_disk.load.side_effect = Exception("Network failure")
        with self.assertRaises(NetworkError):
            self.file_monitor.upload_new_files(current_state)

    def test_update_modified_files_network_error(self):
        """Тест обработки ошибки перезаписи (сетевая ошибка)"""
        self.file_monitor.previous_files = {'file1.txt': 1000}
        current_state = {'file1.txt': 2000}
        self.mock_disk.reload.side_effect = Exception("Network failure")
        with self.assertRaises(NetworkError):
            self.file_monitor.update_modified_files(current_state)

    def test_delete_removed_files_network_error(self):
        """Тест обработки ошибки удаления (сетевая ошибка)"""
        self.file_monitor.previous_files = {'file1.txt': 1000}
        current_state = {}
        self.mock_disk.delete.side_effect = Exception("Network failure")
        with self.assertRaises(NetworkError):
            self.file_monitor.delete_removed_files(current_state)

    def test_get_files_state_success(self):
        """Тест успешного получения состояния файлов."""
        # Патчим os.listdir и os.path.getmtime, чтобы не зависеть от реальной ФС
        with patch('os.listdir', return_value=['file1.txt', 'file2.txt']), \
                patch('os.path.isfile', return_value=True), \
                patch('os.path.getmtime', side_effect=[1672531200.0, 1672531300.0]):

            with patch.object(logger, 'debug') as mock_debug:
                result = self.file_monitor.get_files_state()

                # Проверяем, что логгер был вызван с нужным сообщением
                mock_debug.assert_called_once_with("Анализ локальной папки")

                # Проверяем результат
                expected = {'file1.txt': 1672531200.0, 'file2.txt': 1672531300.0}
                self.assertEqual(result, expected)

    def test_get_files_state_os_error(self):
        """Тест обработки ошибки доступа к файловой системе."""
        # Патчим os.listdir так, чтобы он вызывал OSError
        with patch('os.listdir', side_effect=OSError("Permission denied")), \
                patch.object(logger, 'error') as mock_error:
            # Проверяем, что вызывается исключение FileProcessingError
            with self.assertRaises(FileProcessingError):
                self.file_monitor.get_files_state()

            # Проверяем, что логгер записал ошибку
            mock_error.assert_called_once()
            call_args = mock_error.call_args[0][0]  # Первый аргумент вызова log.error
            self.assertIn("Ошибка при чтении папок/файлов", call_args)

    def test_mirror_sync_full_cycle(self):
        """
        Тест полного цикла зеркальной синхронизации:
        1. Удаление файла из облака (удаленного локально).
        2. Загрузка нового файла.
        3. Обновление существующего файла.
        4. Вызов обновления кэша.
        """
        # 1. Подготовка данных
        local_files_state = {
            'new_file.txt': 1672531200.0,  # Новый файл
            'updated_file.txt': 2000.0  # Файл, который нужно обновить (новее, чем в облаке)
        }

        # 2. Подготовка кэша облака (есть старый файл и файл, который будет удален)
        self.file_monitor.cloud_files = {
            'old_file_in_cloud.txt': 1000.0,  # Будет удален, так как нет в local_files_state
            'updated_file.txt': 1500.0  # Будет обновлен, так как локальная версия новее (2000 > 1500)
        }

        # 3. Патчим методы, чтобы изолировать тест
        with patch.object(self.file_monitor, 'get_files_state', return_value=local_files_state), \
                patch.object(self.file_monitor, 'cache_cloud_files') as mock_cache:
            # Вызываем метод
            self.file_monitor.mirror_sync()

            # 4. Проверка вызовов методов диска

            # Проверка удаления файла, которого нет локально
            self.mock_disk.delete.assert_called_once_with('old_file_in_cloud.txt')

            # Проверка загрузки нового файла
            expected_load_path = os.path.join("local_folder", "new_file.txt")
            self.mock_disk.load.assert_called_once_with(expected_load_path)

            # Проверка обновления существующего файла
            expected_reload_path = os.path.join("local_folder", "updated_file.txt")
            self.mock_disk.reload.assert_called_once_with(expected_reload_path)

            # 5. Проверка, что кэш был обновлен в конце
            mock_cache.assert_called_once()