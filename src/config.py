import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
from typing import Dict, Any

# 1. Определяем путь к .env
project_root: Path = Path(__file__).parent.parent
env_path: Path = Path(find_dotenv() or str(project_root / ".env"))

# 2. Проверка существования файла
if not env_path.exists():
    raise FileNotFoundError(f"Файл .env не найден по пути: {env_path}")

# Загружаем переменные окружения из файла
load_dotenv(env_path)

# 3. Список обязательных переменных
REQUIRED_VARS: Dict[str, Any] = {
    "TOKEN": str,
    "CLOUD_FOLDER": str,
    "SYNC_FOLDER": str,
    "PERIOD_OF_SYNC": int,
    "LOG_FILE_PATH": str,
}

# 4. Загрузка и валидация
missing_vars: list[str] = []
wrong_types: list[str] = []
config: Dict[str, Any] = {}

for var, var_type in REQUIRED_VARS.items():
    value = os.getenv(var)

    if value is None:
        missing_vars.append(var)
        continue

    try:
        # Преобразование типа происходит здесь, что безопасно
        config[var] = var_type(value)
    except (TypeError, ValueError):
        wrong_types.append(var)

# 5. Генерация ошибок, если что-то пошло не так
if missing_vars or wrong_types:
    error_msg = ""
    if missing_vars:
        error_msg += f"Отсутствуют обязательные переменные: {', '.join(missing_vars)}\n"
    if wrong_types:
        error_msg += f"Неверный тип данных у переменных: {', '.join(wrong_types)}"
    raise ValueError(error_msg)

# 6. Экспорт переменных в глобальное пространство имен этого модуля
globals().update(config)