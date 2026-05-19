import importlib
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


MODULE_NAME = "config"


@pytest.fixture(autouse=True)
def clean_env_and_module():
    """
    Очищает окружение от переменных конфигурации и выгружает модуль перед каждым тестом.
    """
    original_environ = dict(os.environ)

    vars_to_clean = ["TOKEN", "CLOUD_FOLDER", "SYNC_FOLDER", "PERIOD_OF_SYNC", "LOG_FILE_PATH"]
    for var in vars_to_clean:
        os.environ.pop(var, None)

    # Удаляем модуль из sys.modules, если он был загружен ранее
    if MODULE_NAME in sys.modules:
        del sys.modules[MODULE_NAME]

    yield

    # Восстанавливаем оригинальное окружение
    os.environ.clear()
    os.environ.update(original_environ)

    # Снова удаляем модуль, чтобы следующий тест начинал с чистого состояния
    if MODULE_NAME in sys.modules:
        del sys.modules[MODULE_NAME]


def write_env_file(env_path: Path, content: str):
    """Записывает содержимое в .env файл."""
    env_path.write_text(content)


def import_config_module():
    """Импортирует тестируемый модуль."""
    return importlib.import_module(MODULE_NAME)


def test_missing_env_file():
    """Тест: файл .env не найден – должно быть исключение FileNotFoundError."""
    with patch("pathlib.Path.exists", return_value=False):
        with pytest.raises(FileNotFoundError, match="Файл .env не найден по пути:"):
            import_config_module()


def test_missing_required_vars(tmp_path):
    """Тест: отсутствуют обязательные переменные – ValueError с перечислением."""
    env_path = tmp_path / ".env"
    write_env_file(env_path, "TOKEN=abc123\n")

    with patch("dotenv.find_dotenv", return_value=str(env_path)):
        with pytest.raises(ValueError) as exc_info:
            import_config_module()

    error_msg = str(exc_info.value)
    assert "Отсутствуют обязательные переменные" in error_msg
    assert "CLOUD_FOLDER" in error_msg
    assert "SYNC_FOLDER" in error_msg
    assert "PERIOD_OF_SYNC" in error_msg
    assert "LOG_FILE_PATH" in error_msg


def test_wrong_type_for_period_of_sync(tmp_path):
    """Тест: PERIOD_OF_SYNC имеет неверный тип – ValueError."""
    env_path = tmp_path / ".env"
    content = """
TOKEN=token123
CLOUD_FOLDER=cloud_folder
SYNC_FOLDER=sync_folder
PERIOD_OF_SYNC=not_an_integer
LOG_FILE_PATH=log.log
"""
    write_env_file(env_path, content)

    with patch("dotenv.find_dotenv", return_value=str(env_path)):
        with pytest.raises(ValueError) as exc_info:
            import_config_module()

    assert "Неверный тип данных у переменных: PERIOD_OF_SYNC" in str(exc_info.value)


def test_successful_config_loading(tmp_path):
    """Тест: корректный .env – переменные успешно загружаются."""
    env_path = tmp_path / ".env"
    content = """
TOKEN=abc123_token
CLOUD_FOLDER=my_cloud_folder
SYNC_FOLDER=my_sync_folder
PERIOD_OF_SYNC=42
LOG_FILE_PATH=/var/log/app.log
"""
    write_env_file(env_path, content)

    with patch("dotenv.find_dotenv", return_value=str(env_path)):
        config_module = import_config_module()

    assert config_module.TOKEN == "abc123_token"
    assert config_module.CLOUD_FOLDER == "my_cloud_folder"
    assert config_module.SYNC_FOLDER == "my_sync_folder"
    assert config_module.PERIOD_OF_SYNC == 42
    assert config_module.LOG_FILE_PATH == "/var/log/app.log"


def test_additional_whitespace_and_comments(tmp_path):
    """Тест: игнорирование комментариев и пробелов в .env."""
    env_path = tmp_path / ".env"
    content = """
# Комментарий
TOKEN=    spaced_token    
CLOUD_FOLDER=cloud   # trailing comment
SYNC_FOLDER=sync_folder
PERIOD_OF_SYNC=100
LOG_FILE_PATH=log.log
"""
    write_env_file(env_path, content)

    with patch("dotenv.find_dotenv", return_value=str(env_path)):
        config_module = import_config_module()

    assert config_module.TOKEN == "spaced_token"
    assert config_module.CLOUD_FOLDER == "cloud"
    assert config_module.PERIOD_OF_SYNC == 100