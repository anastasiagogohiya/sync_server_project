import unittest
from unittest.mock import MagicMock
from file_monitoring.monitoring import FileMonitoring
from exceptions import NetworkError, FileProcessingError



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


if __name__ == '__main__':
    unittest.main()
