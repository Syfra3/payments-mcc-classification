.PHONY: help dev test test-cov test-unit test-integration test-e2e lint format type-check migrate migrate-create migrate-downgrade docker-up docker-down docker-build docker-logs clean install

help:
	@echo "Payments Classification MCP - Available Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install          Install dependencies with dev tools"
	@echo ""
	@echo "Development:"
	@echo "  make dev              Start development server with auto-reload"
	@echo ""
	@echo "Testing:"
	@echo "  make test             Run all tests"
	@echo "  make test-cov         Run tests with coverage report"
	@echo "  make test-unit        Run unit tests only"
	@echo "  make test-integration Run integration tests only"
	@echo "  make test-e2e         Run E2E tests only"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint             Run linting checks"
	@echo "  make format           Format code with black and ruff"
	@echo "  make type-check       Run mypy type checking"
	@echo ""
	@echo "Database:"
	@echo "  make migrate          Run Alembic migrations"
	@echo "  make migrate-create   Create a new migration (use: make migrate-create m=description)"
	@echo "  make migrate-downgrade Revert last migration"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up        Start Docker Compose services"
	@echo "  make docker-down      Stop Docker Compose services"
	@echo "  make docker-build     Build Docker image"
	@echo "  make docker-logs      View Docker service logs"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean            Remove cache and build artifacts"

dev:
	poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	poetry run pytest

test-cov:
	poetry run pytest --cov=app --cov-report=html

test-unit:
	poetry run pytest tests/unit/ -v

test-integration:
	poetry run pytest tests/integration/ -v

test-e2e:
	poetry run pytest tests/e2e/ -v

lint:
	poetry run ruff check . && poetry run mypy . && poetry run black --check .

format:
	poetry run black . && poetry run ruff check . --fix

type-check:
	poetry run mypy app/

migrate:
	poetry run alembic upgrade head

migrate-create:
	poetry run alembic revision --autogenerate -m "$(m)"

migrate-downgrade:
	poetry run alembic downgrade -1

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-build:
	docker-compose build

docker-logs:
	docker-compose logs -f app

install:
	poetry install

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*~" -delete
	rm -rf .pytest_cache .coverage htmlcov .mypy_cache dist/ build/ *.egg-info 2>/dev/null || true
