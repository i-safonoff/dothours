# Обёртки над командами, которые иначе приходится помнить наизусть.
.DEFAULT_GOAL := help
.PHONY: help install lint fmt test cov run migrate migration up down logs stack-up stack-down worker beat smoke

help:  ## Показать эти команды
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## Поставить зависимости
	poetry install

lint:  ## Линт и проверка форматирования
	poetry run ruff check .
	poetry run ruff format --check .

fmt:  ## Отформатировать код
	poetry run ruff format .
	poetry run ruff check --fix .

test:  ## Тесты (SQLite в памяти, внешние сервисы не нужны)
	poetry run pytest

cov:  ## Тесты с HTML-отчётом о покрытии
	poetry run pytest --cov-report=html
	@echo "Отчёт: htmlcov/index.html"

run:  ## Локальный API с автоперезагрузкой
	poetry run uvicorn app.main:app --reload

worker:  ## Локальный Celery worker
	poetry run celery -A app.worker.celery_app.celery_app worker --loglevel=info

beat:  ## Локальный Celery beat
	poetry run celery -A app.worker.celery_app.celery_app beat --loglevel=info

migrate:  ## Накатить миграции
	poetry run alembic upgrade head

migration:  ## Сгенерировать миграцию: make migration m="add something"
	poetry run alembic revision --autogenerate -m "$(m)"

up:  ## Поднять API, БД, Redis, worker и beat
	docker compose up --build -d

down:  ## Остановить стек
	docker compose down

logs:  ## Логи стека
	docker compose logs -f

stack-up:  ## Поднять всё вместе с Prometheus и Grafana
	docker compose -f docker-compose.yml -f docker-compose.observability.yml up --build -d

stack-down:  ## Остановить всё, включая мониторинг
	docker compose -f docker-compose.yml -f docker-compose.observability.yml down

smoke:  ## Проверить, что поднятый стек отвечает
	@curl -fsS http://localhost:8000/health && echo " — API отвечает"
	@curl -fsS http://localhost:8000/metrics >/dev/null && echo "/metrics отдаёт метрики"
