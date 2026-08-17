.PHONY: help install dev lint format type-check test test-integration clean train up down verify load-test load-test-heavy demo

help:
	@echo "NEXUS — End-to-End AI Platform"
	@echo ""
	@echo "Available targets:"
	@echo "  install          Install production dependencies"
	@echo "  dev              Install dev dependencies + pre-commit hooks"
	@echo "  lint             Run ruff linter"
	@echo "  format           Format code with ruff"
	@echo "  type-check       Run mypy type checking"
	@echo "  test             Run unit tests"
	@echo "  test-integration Run integration tests"
	@echo "  train            Run ML training pipeline"
	@echo "  verify           Full self-check against live API (reports/*.json)"
	@echo "  load-test        Quick load test via Locust (1 min, 10 users)"
	@echo "  load-test-heavy  Heavy load test via Locust (3 min, 50 users)"
	@echo "  demo             Run orchestrated demo scenario via API"
	@echo "  clean            Remove caches and temp files"
	@echo "  up               Start all services (Docker Compose)"
	@echo "  down             Stop all services (Docker Compose)"

install:
	uv pip install -e .

dev:
	uv pip install -e ".[dev]"
	pre-commit install

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

type-check:
	mypy src/nexus/

test:
	pytest tests/ -m "not integration" -v

test-integration:
	pytest tests/ -m "integration" -v

train:
	PYTHONPATH="" python -m nexus.training.pipeline

hpo:
	PYTHONPATH="" python -m nexus.training.hpo

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .ruff_cache/

up:
	docker compose up -d

down:
	docker compose down

verify:
	PYTHONPATH="" python scripts/verify.py --base-url http://localhost:8000

load-test:
	uvicorn_check=$(shell curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/api/v1/health) ; \
	if [ "$$uvicorn_check" != "200" ]; then echo "API is not running on :8000"; exit 1; fi
	PYTHONPATH="" locust -f load_tests/locustfile.py --host http://localhost:8000 \
		--headless -u 10 -r 2 -t 60s --only-summary --csv reports/loadtest_smoke

load-test-heavy:
	PYTHONPATH="" locust -f load_tests/locustfile.py --host http://localhost:8000 \
		--headless -u 50 -r 5 -t 180s --only-summary --csv reports/loadtest_heavy

# Capacity profiling: rate limiter disabled to measure raw throughput
RATE_LIMIT_OFF = RATE_LIMIT_PER_MINUTE=100000 RATE_LIMIT_BURST=100000

profile:
	uvicorn_check=$(shell curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/api/v1/health) ; \
	if [ "$$uvicorn_check" != "200" ]; then echo "API is not running on :8000 (start with: make up)"; exit 1; fi
	@echo "Note: for raw-capacity numbers ensure RATE_LIMIT_PER_MINUTE is raised in .env and API restarted"

demo:
	PYTHONPATH="" python scripts/run_demo.py
