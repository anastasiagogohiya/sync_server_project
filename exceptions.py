class StorageError(Exception):
    """Базовый класс исключений для модуля хранения файлов."""
    def __init__(self, message=None):
        if message is None:
            message = "Общая ошибка модуля хранения файлов"
        super().__init__(message)

class ConfigError(StorageError):
    def __init__(self, param_name):
        message = f"Ошибка конфигурации: параметр '{param_name}' отсутствует или неверен."
        super().__init__(message)

class FileProcessingError(StorageError):
    def __init__(self, filename, details=None):
        message = f"Ошибка обработки файла '{filename}'"
        if details:
            message += f": {details}"
        super().__init__(message)

class NetworkError(StorageError):
    def __init__(self, operation=None, details=None):
        message = "Ошибка сети"
        if operation:
            message += f" при операции '{operation}'"
        if details:
            message += f": {details}"
        super().__init__(message)
