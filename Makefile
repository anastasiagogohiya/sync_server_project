# Makefile

# Запуск программы
.PHONY: run
run:
	python -m src.main

# Линтеры, тесты, покрытие тестами
.PHONY: help lint format type-check test coverage all

help:
	@echo "Доступные команды:"
	@echo "  make lint        - запустить ruff (линтер)"
	@echo "  make format      - автоматически исправить форматирование ruff"
	@echo "  make type-check  - проверить типы mypy"
	@echo "  make test        - запустить pytest"
	@echo "  make coverage    - запустить pytest с coverage (отчёт с пропущенными строками)"
	@echo "  make all         - выполнить все проверки (lint, type-check, coverage)"

lint:
	ruff check src/

format:
	ruff check --fix src/
	ruff format src/

type-check:
	mypy src

test:
	pytest

coverage:
	pytest --cov --cov-report=term-missing

all: lint type-check test coverage
	@echo "✅ All checks passed!"



# Создание окружения, установка зависимостей, создание .env файла из шаблона
.PHONY: launch-linux launch-win

launch-linux:
	cd data_synchronization_server_project && \
	python -m venv venv && \
	venv/bin/python -m pip install -e . && \
	venv/bin/python -m pip install -e .[dev] && \
	cp .env.example .env || true

launch-win:
	cd data_synchronization_server_project && \
	python -m venv venv && \
	venv\Scripts\python -m pip install -e . && \
	venv\Scripts\python -m pip install -e .[dev] && \
	copy .env.example .env