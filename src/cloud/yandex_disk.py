from src.loader import logger
import requests
import os
from src.exceptions import NetworkError, FileProcessingError
from typing import Optional, Dict, Any, List


class YandexDisk:
    """
    Класс для работы с REST API Яндекс.Диска.
    Обеспечивает операции получения информации, загрузки,
    перезаписи и удаления файлов в облачной папке.
    """

    def __init__(self, token: str, cloud_folder: str) -> None:
        logger.debug("Инициация класса YandexDisk")
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
            "Authorization": f"OAuth {self.token}",
        }
        self._ensure_folder()

    def _request(
        self,
        method: str,
        url: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
    ) -> requests.Response:
        """
        Универсальный метод для выполнения HTTP-запросов к API Яндекс.Диска.
        Логирует запросы и преобразует исключения в NetworkError.
        """
        url = url or self.base_url
        logger.debug(f"{method} запрос к {url} с параметрами {params}")
        try:
            response = requests.request(
                method, url, headers=self.headers, params=params, data=data, timeout=30
            )
            response.raise_for_status()
            logger.debug(f"Успешный ответ: {response.status_code}")
            return response
        except requests.RequestException as e:
            logger.error(f"Ошибка запроса: {e}")
            raise NetworkError(operation=f"{method} {url}", details=str(e)) from e

    def _ensure_folder(self) -> None:
        """Проверяет существование облачной папки и создаёт её при отсутствии."""
        params = {"path": self.cloud_folder}
        try:
            self._request("GET", params=params)
            logger.debug(f"Облачная папка {self.cloud_folder} уже существует.")
        except NetworkError as e:
            # Если папка не найдена (404), создаём её
            if "404" in str(e):
                try:
                    self._request("PUT", params={"path": self.cloud_folder})
                    logger.info(f"Облачная папка {self.cloud_folder} успешно создана.")
                except Exception as create_err:
                    logger.error(f"Не удалось создать папку {self.cloud_folder}: {create_err}")
                    raise
            else:
                # Другая сетевая ошибка — пробрасываем дальше
                raise

    def get_info(self) -> List[Dict[str, Any]]:
        """
        Получает информацию о файлах в облачной папке.
        :return: Список словарей с ключами 'name' и 'size'
        """
        logger.debug("Получение списка файлов из облачной папки")
        params = {
            "path": self.cloud_folder,
            "fields": "_embedded.items.name,_embedded.items.size",
        }
        response = self._request("GET", params=params)
        items = response.json().get("_embedded", {}).get("items", [])
        logger.debug(f"Найдено {len(items)} файлов")
        return [{"name": item["name"], "size": item["size"]} for item in items]

    def _get_upload_link(self, path: str, overwrite: bool = True) -> str:
        """
        Получает ссылку для загрузки файла на Яндекс.Диск.
        :param path: Путь к файлу в облаке
        :param overwrite: Перезаписывать ли существующий файл
        :return: URL для PUT-запроса
        """
        logger.debug(f"Запрос адреса загрузки для {path} (overwrite={overwrite})")
        params = {"path": path, "overwrite": str(overwrite).lower()}
        response = self._request("GET", url=f"{self.base_url}/upload", params=params)
        href = response.json().get("href")
        if not href:
            logger.error("Ссылка на загрузку не получена")
            raise NetworkError(
                operation="Получение ссылки загрузки", details="Нет поля href в ответе"
            )
        logger.debug(f"Получена ссылка загрузки: {href[:80]}...")  # обрезаем для лога
        return href

    def upload(self, local_path: str) -> None:
        """
        Загружает файл на Яндекс.Диск (или перезаписывает, если уже существует).
        :param local_path: Путь к локальному файлу
        """
        filename = os.path.basename(local_path)
        cloud_file_path = f"{self.cloud_folder}/{filename}"
        logger.debug(f"Загрузка/перезапись файла {filename} в {cloud_file_path}")

        url = self._get_upload_link(cloud_file_path, overwrite=True)
        try:
            with open(local_path, "rb") as f:
                response = requests.put(url, data=f, timeout=30)
            response.raise_for_status()
            logger.info(f"Файл {filename} успешно загружен/перезаписан.")
        except FileNotFoundError as e:
            logger.error(f"Файл {local_path} не найден: {e}")
            raise FileProcessingError(filename, "Файл не найден") from e
        except requests.RequestException as e:
            logger.error(f"Ошибка загрузки/перезаписи файла {filename}: {e}")
            raise NetworkError(operation="загрузка/перезапись файла", details=str(e)) from e

    def delete(self, filename: str) -> None:
        """
        Удаляет файл из облачной папки.
        :param filename: Имя файла в облаке (без пути)
        """
        cloud_file_path = f"{self.cloud_folder}/{filename}"
        logger.debug(f"Удаление файла {filename} из {cloud_file_path}")
        params = {"path": cloud_file_path}
        # _request уже выбросит исключение при ошибке
        self._request("DELETE", params=params)
        logger.info(f"Файл {filename} успешно удалён.")