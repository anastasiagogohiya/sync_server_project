# Makefile

# Переменная для Python из виртуального окружения
VENV = venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip
RUFF = $(VENV)/bin/ruff
MYPY = $(VENV)/bin/mypy
PYTEST = $(VENV)/bin/pytest

# Запуск программы
.PHONY: run
run:
	$(PYTHON) -m src.main

# Линтеры, тесты, покрытие тестами
.PHONY: help lint format type-check test coverage all

help:
	@echo "Доступные команды:"
	@echo "  make launch-linux - создать venv и установить зависимости (Linux/macOS)"
	@echo "  make launch-win   - создать venv и установить зависимости (Windows)"
	@echo "  make run          - запустить программу"
	@echo "  make lint         - запустить ruff (линтер)"
	@echo "  make format       - автоматически исправить форматирование ruff"
	@echo "  make type-check   - проверить типы mypy"
	@echo "  make test         - запустить pytest"
	@echo "  make coverage     - запустить pytest с coverage (отчёт с пропущенными строками)"
	@echo "  make all          - выполнить все проверки (lint, type-check, coverage)"

lint:
	$(RUFF) check src/

format:
	$(RUFF) check --fix src/
	$(RUFF) format src/

type-check:
	$(MYPY) src

test:
	$(PYTEST)

coverage:
	$(PYTEST) --cov --cov-report=term-missing

all: lint type-check test coverage
	@echo "✅ All checks passed!"

# Создание окружения, установка зависимостей, создание .env файла из шаблона
.PHONY: launch-linux launch-win

launch-linux:
	python3 -m venv $(VENV) && \
	$(PIP) install -e . && \
	$(PIP) install -e .[dev] && \
	cp .env.example .env || true

launch-win:
	python -m venv $(VENV) && \
	$(VENV)\Scripts\python -m pip install -e . && \
	$(VENV)\Scripts\python -m pip install -e .[dev] && \
	copy .env.example .env