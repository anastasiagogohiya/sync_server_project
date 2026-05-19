# 🏗️ Архитектура проекта: Сервис синхронизации файлов

## 🌳 Структура проекта
```plaintext
data_synchronization_server_project/
├── .env                  # переменные окружения (не в репозитории)
├── .env.example          
├── .gitignore
├── pyproject.toml        # зависимости, настройки
├── Makefile              # команды
├── README.md
├── ARCHITECTURE.md      
├── src/
│   ├── main.py           # точка входа
│   ├── config.py         # чтение и валидация .env
│   ├── loader.py         # настройка логирования (loguru)
│   ├── exceptions.py     # пользовательские исключения
│   ├── cloud/
│   │   └── yandex_disk.py # обёртка над API Яндекс.Диска
│   └── file_monitoring/
│       └── monitoring.py  # логика сравнения и синхронизации
├── tests/    
└── logs/                 # файлы логов (создаётся автоматически)


```