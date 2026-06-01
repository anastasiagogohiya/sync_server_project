import unittest
import os
from unittest.mock import MagicMock, patch
from src.file_monitoring.monitoring import FileMonitoring
from src.exceptions import NetworkError, FileProcessingError
from src.loader import logger


class TestFileMonitoring(unittest.TestCase):
    def setUp(self):
        self.mock_disk = MagicMock()
        self.file_monitor = FileMonitoring(self.mock_disk, "local_folder", "cloud_folder")

    def test_cache_cloud_files(self):
        """Тест кеширования списка файлов из облака"""
        self.mock_disk.get_info.return_value = [{'name': 'file1.txt', 'size': 123}]
        self.file_monitor.cache_cloud_files()
        self.assertIn('file1.txt', self.file_monitor.cloud_files)

    def test_upload_new_and_modified_files(self):
        """Тест загрузки новых и изменённых файлов (объединённый метод upload)"""
        self.file_monitor.previous_files = {'old.txt': 1000}
        current_state = {
            'new.txt': 2000,      # новый файл
            'old.txt': 3000,      # изменённый
            'same.txt': 1000      # не изменился (в previous нет, но в current_state есть? нет, в previous нет, значит это новый?
                                 # но в этом примере same.txt нет в previous_files, значит он тоже новый)
        }
        # Чтобы проверить только new и old, укажем previous_files с old.txt
        # same.txt отсутствует в previous, значит будет загружен.
        # Но для чистоты теста: хотим проверить, что upload вызывается для новых и изменённых.
        self.file_monitor.upload(current_state)
        # upload вызывается для каждого файла, который либо отсутствует в previous, либо отличается по времени
        # здесь должно быть три вызова
        self.assertEqual(self.mock_disk.upload.call_count, 3)

    def test_upload_only_changed_files(self):
        """Тест: загружаются только новые и изменённые файлы"""
        self.file_monitor.previous_files = {'file1.txt': 1000, 'file2.txt': 2000}
        current_state = {
            'file1.txt': 1000,    # не изменился
            'file2.txt': 2500,    # изменился
            'file3.txt': 3000     # новый
        }
        self.file_monitor.upload(current_state)
        # Ожидаем вызовы для file2.txt и file3.txt
        expected_calls = [
            unittest.mock.call(os.path.join("local_folder", "file2.txt")),
            unittest.mock.call(os.path.join("local_folder", "file3.txt"))
        ]
        self.mock_disk.upload.assert_has_calls(expected_calls, any_order=True)
        self.assertEqual(self.mock_disk.upload.call_count, 2)

    def test_upload_network_error(self):
        """Тест обработки ошибки сети при загрузке/обновлении"""
        self.file_monitor.previous_files = {}
        current_state = {'file1.txt': 1000}
        self.mock_disk.upload.side_effect = Exception("Network failure")
        with self.assertRaises(NetworkError):
            self.file_monitor.upload(current_state)

    def test_delete_removed_files(self):
        """Тест удаления файлов, которых нет локально"""
        self.file_monitor.previous_files = {'file3.txt': 1000}
        current_state = {}
        self.file_monitor.delete_removed_files(current_state)
        self.mock_disk.delete.assert_called_once_with('file3.txt')

    def test_delete_removed_files_network_error(self):
        """Тест обработки ошибки удаления (сетевая ошибка)"""
        self.file_monitor.previous_files = {'file1.txt': 1000}
        current_state = {}
        self.mock_disk.delete.side_effect = Exception("Network failure")
        with self.assertRaises(NetworkError):
            self.file_monitor.delete_removed_files(current_state)

    def test_get_files_state_success(self):
        """Тест успешного получения состояния файлов"""
        with patch('os.listdir', return_value=['file1.txt', 'file2.txt']), \
             patch('os.path.isfile', return_value=True), \
             patch('os.path.getmtime', side_effect=[1672531200.0, 1672531300.0]):

            with patch.object(logger, 'debug') as mock_debug:
                result = self.file_monitor.get_files_state()
                mock_debug.assert_called_once_with("Анализ локальной папки")
                expected = {'file1.txt': 1672531200.0, 'file2.txt': 1672531300.0}
                self.assertEqual(result, expected)

    def test_get_files_state_os_error(self):
        """Тест обработки ошибки доступа к файловой системе"""
        with patch('os.listdir', side_effect=OSError("Permission denied")), \
             patch.object(logger, 'error') as mock_error:
            with self.assertRaises(FileProcessingError):
                self.file_monitor.get_files_state()
            mock_error.assert_called_once()
            self.assertIn("Ошибка при чтении папок/файлов", mock_error.call_args[0][0])

    def test_mirror_sync_full_cycle(self):
        """
        Тест полного цикла зеркальной синхронизации:
        1. Удаление файлов из облака, отсутствующих локально.
        2. Загрузка/обновление всех локальных файлов (через upload).
        3. Обновление кэша облачных файлов.
        """
        # Подготовка данных
        local_files_state = {
            'new_file.txt': 1672531200.0,
            'updated_file.txt': 2000.0
        }
        self.file_monitor.cloud_files = {
            'old_file_in_cloud.txt': 1000.0,
            'updated_file.txt': 1500.0
        }

        with patch.object(self.file_monitor, 'get_files_state', return_value=local_files_state), \
             patch.object(self.file_monitor, 'cache_cloud_files') as mock_cache:

            self.file_monitor.mirror_sync()

            # Проверка удаления лишнего файла
            self.mock_disk.delete.assert_called_once_with('old_file_in_cloud.txt')

            # Проверка загрузки/обновления всех локальных файлов
            expected_upload_calls = [
                unittest.mock.call(os.path.join("local_folder", "new_file.txt")),
                unittest.mock.call(os.path.join("local_folder", "updated_file.txt"))
            ]
            self.mock_disk.upload.assert_has_calls(expected_upload_calls, any_order=True)
            self.assertEqual(self.mock_disk.upload.call_count, 2)

            # Проверка обновления кэша
            mock_cache.assert_called_once()
            # Проверка, что previous_files обновился
            self.assertEqual(self.file_monitor.previous_files, local_files_state)

    def test_sync_periodic(self):
        """Тест периодической синхронизации (sync)"""
        current_state = {'file1.txt': 1000}
        with patch.object(self.file_monitor, 'get_files_state', return_value=current_state), \
             patch.object(self.file_monitor, 'upload') as mock_upload, \
             patch.object(self.file_monitor, 'delete_removed_files') as mock_delete:
            self.file_monitor.sync()
            mock_upload.assert_called_once_with(current_state)
            mock_delete.assert_called_once_with(current_state)
            self.assertEqual(self.file_monitor.previous_files, current_state)