from loader import logger
import requests
from exceptions import NetworkError, FileProcessingError
from typing import Optional, Dict, Any


class YandexDisk:
    """
       Класс для работы с REST API Яндекс.Диска.
       Обеспечивает операции получения информации, загрузки,
       перезаписи и удаления файлов в облачной папке.
       """

    def __init__(self, token: str, cloud_folder: str) -> None:
        logger.debug("Работа инициации класса YandexDisk")
        if not token:
            logger.error("Токен не передан в конструктор.")
            raise ValueError("Для YandexDisk требуется токен доступа")
        if not cloud_folder:
            logger.error("Путь к облачной папке не передан в конструктор.")
            raise ValueError("Для YandexDisk требуется путь к облачной папке")

        self.token = token
        self.cloud_folder = cloud_folder
        self.base_url = "https://cloud-api.yandex.net/v1/disk/resources"
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"OAuth {self.token}"
        }



    def _request(self,
        method: str,
        url: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None
    ) -> requests.Response:
        """Метод для выполнения HTTP запросов к API Яндекс.Диска."""
        url = url or self.base_url
        logger.debug(f"{method} запрос к {url} с параметрами {params}")
        try:
            response = requests.request(method, url, headers=self.headers, params=params, data=data)
            response.raise_for_status()
            logger.debug(f"Успешный ответ: {response.status_code}")
            return response
        except requests.RequestException as e:
            logger.error(f"Ошибка запроса: {e}")
            raise NetworkError(operation=f"{method} {url}", details=str(e)) from e


    def get_info(self) -> Optional[list]:
        """Получение информации о файлах в облачной папке."""
        logger.debug("Анализ файлов на облачном диске")
        params = {"path": self.cloud_folder, "fields": "_embedded.items.name,_embedded.items.size"}
        response = self._request("GET", params=params)
        if response:
            items = response.json().get("_embedded", {}).get("items", [])
            logger.debug(f"Найдено {len(items)} файлов")
            return [{"name": item["name"], "size": item["size"]} for item in items]
        return None


    def _get_upload_link(self, path: str, overwrite: bool = False) -> str:
        """Получение ссылки для загрузки файла на Яндекс.Диск."""

        logger.debug(f"Запрос адреса загрузки для {path} (overwrite={overwrite})")
        params = {"path": path, "overwrite": str(overwrite).lower()}
        response = self._request("GET", url=f"{self.base_url}/upload", params=params)
        href = response.json().get("href")
        if not href:
            logger.error("Ссылка на загрузку не получена")
            raise NetworkError(operation="Получение ссылки загрузки", details="Нет поля href в ответе")
        logger.debug(f"Получена ссылка загрузки: {href}")
        return href


    def load(self, local_path: str) -> None:
        """Загрузка нового файла на Яндекс.Диск."""

        logger.debug(f"Новые файлы найдены: {local_path}")
        filename = local_path.split("/")[-1]
        cloud_file_path = f"{self.cloud_folder}/{filename}"
        logger.debug(f"Загрузка файла {filename} в {cloud_file_path}")
        url = self._get_upload_link(cloud_file_path)
        try:
            with open(local_path, "rb") as f:
                response = requests.put(url, data=f, timeout=30)
            response.raise_for_status()
            logger.info(f"Файл {filename} успешно загружен.")
        except FileNotFoundError as e:
            logger.error(f"Файл {local_path} не найден: {e}")
            raise FileProcessingError(filename, "Файл не найден") from e
        except requests.RequestException as e:
            logger.error(f"Ошибка загрузки файла {filename}: {e}")
            raise NetworkError(operation="загрузка файла", details=str(e)) from e


    def reload(self, local_path: str) -> None:
        """Перезапись файла на Яндекс.Диске."""

        logger.debug(f"Найден измененный файл {local_path}")
        filename = local_path.split("/")[-1]
        cloud_file_path = f"{self.cloud_folder}/{filename}"
        logger.debug(f"Перезапись файла {filename} в {cloud_file_path}")
        url = self._get_upload_link(cloud_file_path, overwrite=True) # разрешаю перезапись измененых файлов
        try:
            with open(local_path, "rb") as f:
                response = requests.put(url, data=f, timeout=30)
            response.raise_for_status()
            logger.info(f"Файл {filename} успешно перезаписан.")
        except FileNotFoundError as e:
            logger.error(f"Файл {local_path} не найден: {e}")
            raise FileProcessingError(filename, "Файл не найден") from e
        except requests.RequestException as e:
            logger.error(f"Ошибка перезаписи файла {filename}: {e}")
            raise NetworkError(operation="перезапись файла", details=str(e)) from e


    def delete(self, filename: str) -> None:
        """Удаление файла из облачной папки."""

        logger.debug(f"Удаленые файлы найдены {filename}")
        cloud_file_path = f"{self.cloud_folder}/{filename}"
        logger.debug(f"Запрос на удаление файла {filename} из {cloud_file_path}")
        params = {"path": cloud_file_path}
        response = self._request("DELETE", params=params)
        if response.status_code == 204:
            logger.info(f"Файл {filename} успешно удалён.")
        else:
            logger.error(f"Не удалось удалить файл {filename}, HTTP {response.status_code}")
            raise NetworkError(operation="удаление файла", details=f"HTTP {response.status_code}")