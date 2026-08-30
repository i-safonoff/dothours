# Wrappers around commands that are otherwise easy to forget.
.DEFAULT_GOAL := help
.PHONY: help install lint fmt test cov run migrate migration up down logs stack-up stack-down worker beat smoke

help:  ## Show this list
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	poetry install

lint:  ## Lint and check formatting
	poetry run ruff check .
	poetry run ruff format --check .

fmt:  ## Format the code
	poetry run ruff format .
	poetry run ruff check --fix .

test:  ## Run tests (in-memory SQLite, no external services needed)
	poetry run pytest

cov:  ## Run tests with an HTML coverage report
	poetry run pytest --cov-report=html
	@echo "Report: htmlcov/index.html"

run:  ## Local API with auto-reload
	poetry run uvicorn app.main:app --reload

worker:  ## Local Celery worker
	poetry run celery -A app.worker.celery_app.celery_app worker --loglevel=info

beat:  ## Local Celery beat
	poetry run celery -A app.worker.celery_app.celery_app beat --loglevel=info

migrate:  ## Apply migrations
	poetry run alembic upgrade head

migration:  ## Generate a migration: make migration m="add something"
	poetry run alembic revision --autogenerate -m "$(m)"

up:  ## Bring up the API, DB, Redis, worker, and beat
	docker compose up --build -d

down:  ## Stop the stack
	docker compose down

logs:  ## Tail the stack's logs
	docker compose logs -f

stack-up:  ## Bring up everything, including Prometheus and Grafana
	docker compose -f docker-compose.yml -f docker-compose.observability.yml up --build -d

stack-down:  ## Stop everything, including monitoring
	docker compose -f docker-compose.yml -f docker-compose.observability.yml down

smoke:  ## Check that a running stack responds
	@curl -fsS http://localhost:8000/health && echo " — API is up"
	@curl -fsS http://localhost:8000/metrics >/dev/null && echo "/metrics is serving"
