import pytest
from unittest.mock import patch, MagicMock, mock_open
import requests

from src.cloud.yandex_disk import YandexDisk
from src.exceptions import NetworkError, FileProcessingError


# Фикстура для создания экземпляра YandexDisk с валидными параметрами
@pytest.fixture
def yandex_disk():
    return YandexDisk(token="test_token", cloud_folder="test_folder")


# Тесты для __init__
class TestInit:
    def test_valid_init(self):
        """Инициализация с корректными параметрами."""
        disk = YandexDisk(token="abc", cloud_folder="folder")
        assert disk.token == "abc"
        assert disk.cloud_folder == "folder"
        assert disk.base_url == "https://cloud-api.yandex.net/v1/disk/resources"
        assert disk.headers["Authorization"] == "OAuth abc"

    def test_init_with_empty_token(self):
        """Пустой токен вызывает ValueError."""
        with pytest.raises(ValueError, match="требуется токен доступа"):
            YandexDisk(token="", cloud_folder="folder")

    def test_init_with_empty_cloud_folder(self):
        """Пустая облачная папка вызывает ValueError."""
        with pytest.raises(ValueError, match="требуется путь к облачной папке"):
            YandexDisk(token="token", cloud_folder="")


# Тесты для _request (внутренний метод)
class TestRequest:
    def test_successful_request(self, yandex_disk):
        """Успешный запрос возвращает Response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None

        with patch("requests.request", return_value=mock_response) as mock_req:
            response = yandex_disk._request("GET", params={"a": 1})

        assert response == mock_response
        mock_req.assert_called_once_with(
            "GET",
            yandex_disk.base_url,
            headers=yandex_disk.headers,
            params={"a": 1},
            data=None,
        )

    def test_request_with_custom_url(self, yandex_disk):
        """Запрос с переданным URL."""
        mock_response = MagicMock()
        with patch("requests.request", return_value=mock_response) as mock_req:
            yandex_disk._request("POST", url="https://custom.url", data="test")

        mock_req.assert_called_once_with(
            "POST",
            "https://custom.url",
            headers=yandex_disk.headers,
            params=None,
            data="test",
        )

    def test_request_raises_network_error(self, yandex_disk):
        """При сбое запроса поднимается NetworkError."""
        with patch(
            "requests.request", side_effect=requests.RequestException("Connection error")
        ):
            with pytest.raises(NetworkError) as exc_info:
                yandex_disk._request("GET")

        assert "GET https://cloud-api.yandex.net/v1/disk/resources" in str(exc_info.value)


# Тесты для get_info
class TestGetInfo:
    def test_get_info_success(self, yandex_disk):
        """Получение списка файлов из облачной папки."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "_embedded": {
                "items": [
                    {"name": "file1.txt", "size": 100},
                    {"name": "file2.jpg", "size": 200},
                ]
            }
        }
        with patch.object(yandex_disk, "_request", return_value=mock_response) as mock_req:
            result = yandex_disk.get_info()

        expected = [{"name": "file1.txt", "size": 100}, {"name": "file2.jpg", "size": 200}]
        assert result == expected
        mock_req.assert_called_once_with(
            "GET",
            params={
                "path": "test_folder",
                "fields": "_embedded.items.name,_embedded.items.size",
            },
        )

    def test_get_info_empty_folder(self, yandex_disk):
        """Пустая папка – возвращается пустой список."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"_embedded": {"items": []}}
        with patch.object(yandex_disk, "_request", return_value=mock_response):
            result = yandex_disk.get_info()
        assert result == []

    def test_get_info_no_embedded(self, yandex_disk):
        """Ответ без поля _embedded – возвращается пустой список."""
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        with patch.object(yandex_disk, "_request", return_value=mock_response):
            result = yandex_disk.get_info()
        assert result == []

    def test_get_info_request_fails(self, yandex_disk):
        """Если _request бросает исключение, оно пробрасывается дальше."""
        with patch.object(
            yandex_disk, "_request", side_effect=NetworkError("Ошибка")
        ):
            with pytest.raises(NetworkError):
                yandex_disk.get_info()


# Тесты для _get_upload_link
class TestGetUploadLink:
    def test_get_upload_link_success(self, yandex_disk):
        """Успешное получение ссылки для загрузки."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"href": "https://upload.url"}
        with patch.object(yandex_disk, "_request", return_value=mock_response) as mock_req:
            href = yandex_disk._get_upload_link("path/to/file", overwrite=True)

        assert href == "https://upload.url"
        mock_req.assert_called_once_with(
            "GET",
            url="https://cloud-api.yandex.net/v1/disk/resources/upload",
            params={"path": "path/to/file", "overwrite": "true"},
        )

    def test_get_upload_link_missing_href(self, yandex_disk):
        """Ответ без href – NetworkError."""
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        with patch.object(yandex_disk, "_request", return_value=mock_response):
            with pytest.raises(NetworkError, match="Нет поля href"):
                yandex_disk._get_upload_link("some/path")


# Тесты для load
class TestLoad:
    @patch("builtins.open", new_callable=mock_open, read_data=b"data")
    @patch("requests.put")
    def test_load_success(self, mock_put, mock_file_open, yandex_disk):
        """Успешная загрузка нового файла."""
        # Мокаем получение ссылки
        with patch.object(
            yandex_disk, "_get_upload_link", return_value="https://upload.url"
        ) as mock_get_link:
            mock_put.return_value = MagicMock(status_code=201)
            mock_put.return_value.raise_for_status.return_value = None

            yandex_disk.load("local/path/file.txt")

        mock_get_link.assert_called_once_with("test_folder/file.txt")
        mock_file_open.assert_called_once_with("local/path/file.txt", "rb")
        mock_put.assert_called_once_with(
            "https://upload.url", data=mock_file_open.return_value, timeout=30
        )

    def test_load_file_not_found(self, yandex_disk):
        """Загрузка несуществующего файла – FileProcessingError."""
        with patch.object(yandex_disk, "_get_upload_link", return_value="url"):
            with patch("builtins.open", side_effect=FileNotFoundError):
                with pytest.raises(FileProcessingError, match="Файл не найден"):
                    yandex_disk.load("missing.txt")

    @patch("builtins.open", new_callable=mock_open)
    @patch("requests.put")
    def test_load_network_error(self, mock_put, mock_file_open, yandex_disk):
        """Ошибка при PUT-запросе – NetworkError."""
        with patch.object(yandex_disk, "_get_upload_link", return_value="url"):
            mock_put.side_effect = requests.RequestException("Timeout")
            with pytest.raises(NetworkError, match="загрузка файла"):
                yandex_disk.load("local/file.txt")


# Тесты для reload (аналогичны load, но с overwrite=True)
class TestReload:
    @patch("builtins.open", new_callable=mock_open)
    @patch("requests.put")
    def test_reload_success(self, mock_put, mock_file_open, yandex_disk):
        """Успешная перезапись файла."""
        with patch.object(
            yandex_disk, "_get_upload_link", return_value="https://upload.url"
        ) as mock_get_link:
            mock_put.return_value = MagicMock(status_code=200)
            mock_put.return_value.raise_for_status.return_value = None

            yandex_disk.reload("local/path/file.txt")

        mock_get_link.assert_called_once_with("test_folder/file.txt", overwrite=True)
        mock_put.assert_called_once()

    def test_reload_file_not_found(self, yandex_disk):
        """Перезапись отсутствующего локального файла."""
        with patch.object(yandex_disk, "_get_upload_link", return_value="url"):
            with patch("builtins.open", side_effect=FileNotFoundError):
                with pytest.raises(FileProcessingError):
                    yandex_disk.reload("missing.txt")


# Тесты для delete
class TestDelete:
    def test_delete_success(self, yandex_disk):
        """Успешное удаление файла."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        with patch.object(yandex_disk, "_request", return_value=mock_response) as mock_req:
            yandex_disk.delete("file_to_delete.txt")

        mock_req.assert_called_once_with(
            "DELETE", params={"path": "test_folder/file_to_delete.txt"}
        )

    def test_delete_failure_non_204(self, yandex_disk):
        """Ответ с кодом не 204 – NetworkError."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        with patch.object(yandex_disk, "_request", return_value=mock_response):
            with pytest.raises(NetworkError, match="HTTP 500"):
                yandex_disk.delete("bad_file.txt")

    def test_delete_request_exception(self, yandex_disk):
        """Исключение при запросе – пробрасывается NetworkError."""
        with patch.object(
            yandex_disk, "_request", side_effect=NetworkError("Delete failed")
        ):
            with pytest.raises(NetworkError):
                yandex_disk.delete("some_file.txt")
