.PHONY: help dev test lint format migrate docker-up docker-down

help:
	@echo "Payments Classification MCP - Available Commands"
	@echo ""
	@echo "Development:"
	@echo "  make dev              Start development server with auto-reload"
	@echo "  make test             Run all tests"
	@echo "  make test-cov         Run tests with coverage report"
	@echo "  make lint             Run linting checks"
	@echo "  make format           Format code with black and ruff"
	@echo ""
	@echo "Database:"
	@echo "  make migrate          Run Alembic migrations"
	@echo "  make migrate-create   Create a new migration (use: make migrate-create m=description)"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up        Start Docker Compose services"
	@echo "  make docker-down      Stop Docker Compose services"

dev:
	poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	poetry run pytest

test-cov:
	poetry run pytest --cov=app --cov-report=html

lint:
	poetry run ruff check . && poetry run mypy . && poetry run black --check .

format:
	poetry run black . && poetry run ruff check . --fix

migrate:
	poetry run alembic upgrade head

migrate-create:
	poetry run alembic revision --autogenerate -m "$(m)"

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-build:
	docker-compose build

docker-logs:
	docker-compose logs -f app
