# NEXUS — End-to-End AI Platform

> Real-time content moderation platform with full MLOps lifecycle management,
> A/B testing, drift detection, and product analytics.

[![CI](https://github.com/Mirael-Shell/nexus/actions/workflows/ci.yml/badge.svg)](https://github.com/Mirael-Shell/nexus/actions)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/tests-51%20passed-brightgreen.svg)](#-тестирование)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## 🎯 О проекте

**NEXUS** — платформа для real-time модерации контента (текст + изображения),
демонстрирующая полный жизненный цикл ML-модели: от обучения до продакшна,
от экспериментов до мониторинга и автоматического переобучения.

Проект создан как **портфолио для ролей MLOps Engineer и AI Product Manager**,
показывающее техническую глубину и продуктовое мышление одновременно.

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────────────────┐
│                        NEXUS Platform                                │
│                                                                     │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────────────┐   │
│  │  Frontend   │────▶│   API       │────▶│   PostgreSQL        │   │
│  │  React/TS   │     │   FastAPI   │     │   SQLAlchemy async  │   │
│  │  :3000      │     │   :8000     │     │   :5432             │   │
│  └─────────────┘     └──────┬──────┘     └─────────────────────┘   │
│                             │                                       │
│         ┌───────────────────┼───────────────────┐                  │
│         ▼                   ▼                   ▼                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐    │
│  │  MLflow     │    │  MinIO      │    │  Prometheus         │    │
│  │  Registry   │    │  S3 Store   │    │  + Grafana          │    │
│  │  :5000      │    │  :9000      │    │  :9090 / :3030      │    │
│  └─────────────┘    └─────────────┘    └─────────────────────┘    │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Analytics & Training                        │  │
│  │  • Bayesian A/B Testing (Beta-Binomial, Monte Carlo)          │  │
│  │  • Drift Detection (KS-test, Chi-square)                      │  │
│  │  • Optuna HPO (TPE Sampler)                                   │  │
│  │  • Cost Tracker (ROI, Margin, Unit Economics)                 │  │
│  │  • ONNX Export & Benchmarking                                 │  │
│  │  • Airflow DAG (Automated Retraining)                         │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Быстрый старт

### Требования

- Docker Desktop 4.30+
- Python 3.11+ (для локальной разработки)
- Node.js 20+ (для фронтенда)
- 8GB RAM (для всех Docker-сервисов)

### Запуск (Docker Compose)

```bash
# Клонировать и запустить
git clone https://github.com/Mirael-Shell/nexus.git
cd nexus
cp .env.example .env
docker compose up -d

# Проверить
curl http://localhost:8000/api/v1/health
# → {"status":"ok","model_loaded":true,"database_connected":true}
```

### Сервисы

| Сервис | URL | Назначение |
|---|---|---|
| **Frontend (Dashboard)** | http://localhost:3000 | React SPA: predict, models, experiments, drift, cost |
| **API** | http://localhost:8000/docs | FastAPI Swagger UI |
| **MLflow** | http://localhost:5000 | Experiment tracking + Model Registry |
| **MinIO Console** | http://localhost:9001 | S3 artifacts (minio/minio12345) |
| **Prometheus** | http://localhost:9090 | Metrics collection |
| **Grafana** | http://localhost:3030 | Dashboards (admin/admin) |

### Локальная разработка

```bash
# Backend
uv venv .venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]"
make test      # 12 unit tests
make lint      # ruff check + format

# Frontend
cd frontend
npm install
npm run dev    # http://localhost:5173

# Training
make train     # Train + log to MLflow + register model
make hpo       # Optuna hyperparameter optimization
```

---

## 📊 API Endpoints

### Inference
| Method | Path | Описание |
|---|---|---|
| POST | `/api/v1/predict` | Классификация текста (safe/spam/toxic) |
| GET | `/api/v1/predict/{id}` | Получить сохранённое предсказание |
| POST | `/api/v1/moderate/image` | Модерация изображения (multi-modal) |
| POST | `/api/v1/feedback` | Feedback (thumbs up/down) |

### Model Registry
| Method | Path | Описание |
|---|---|---|
| GET | `/api/v1/models` | Список версий модели |
| POST | `/api/v1/models/{ver}/promote` | Promote → Staging/Production/Archived |

### A/B Experiments
| Method | Path | Описание |
|---|---|---|
| POST | `/api/v1/experiments` | Создать эксперимент |
| GET | `/api/v1/experiments` | Список экспериментов |
| POST | `/api/v1/experiments/{id}/start` | Запустить |
| POST | `/api/v1/experiments/{id}/stop` | Остановить |
| GET | `/api/v1/experiments/{id}/analyze` | Bayesian analysis |

### Monitoring
| Method | Path | Описание |
|---|---|---|
| GET | `/api/v1/health` | Health check |
| GET | `/metrics` | Prometheus metrics |
| POST | `/api/v1/drift/analyze` | Drift detection (KS, chi-square) |
| GET | `/api/v1/cost/summary` | Cost analytics + unit economics |

---

## 🔧 Технологический стек

### Backend
- **FastAPI** + **uvicorn** — async REST API
- **SQLAlchemy 2.0** async + **asyncpg** — PostgreSQL ORM
- **Pydantic v2** — schemas и валидация
- **structlog** — structured logging
- **prometheus-client** — custom metrics

### ML / MLOps
- **PyTorch** — training (CPU-only в Docker)
- **MLflow** — experiment tracking + model registry
- **Optuna** — hyperparameter optimization (TPE sampler)
- **MinIO** — S3-compatible artifact storage
- **ONNX** — model export & optimization

### Frontend
- **React 19** + **Vite** + **TypeScript**
- **Tailwind CSS v4** (via @tailwindcss/vite)
- Dark theme dashboard

### Infrastructure
- **Docker Compose** — 8 services
- **Kubernetes** — Deployments, Services, HPA, Ingress
- **GitHub Actions** — CI/CD (lint → test → build → docker)
- **Prometheus + Grafana** — monitoring
- **Airflow** — orchestration DAGs

---

## 🧪 Тестирование

```bash
make test          # 51 unit tests (pytest + httpx AsyncClient)
make lint          # ruff check + format
make verify        # 20 integration checks against live API (reports/*.json)
make demo          # orchestrated end-to-end demo scenario
make load-test     # Locust load testing (smoke: 10 users / 1 min)
```

CI pipeline (GitHub Actions):
1. **Backend**: ruff lint → ruff format → pytest (51 tests)
2. **Frontend**: tsc --noEmit → npm run build
3. **Docker**: compose build smoke test

---

## 🔐 Безопасность

- **API Key Authentication** — `X-API-Key` header (опционально, через env var)
- **Rate Limiting** — sliding window, configurable RPM
- **Secret Management** — K8s Secrets, .env для локальной разработки

---

## ☸️ Kubernetes

```bash
# Apply manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/config.yaml
kubectl apply -f k8s/api.yaml
kubectl apply -f k8s/frontend.yaml
kubectl apply -f k8s/hpa.yaml
kubectl apply -f k8s/ingress.yaml

# Check
kubectl get pods -n nexus
kubectl get hpa -n nexus
```

Features:
- **Horizontal Pod Autoscaler** — auto-scale 2-10 pods based on CPU/memory
- **Liveness & Readiness Probes** — health checking
- **Resource Limits** — requests + limits per container
- **Ingress** — TLS termination, path-based routing

---

## 🧪 Испытательный стенд

Полный цикл проверки платформы вживую:

### Demo Engine (🎬 таб в UI)
Оркестрируемый сценарий в одно нажатие — 5 фаз с live-визуализацией через WebSocket:
1. Baseline traffic — смешанный поток сообщений
2. Toxicity spike — симуляция рейда + автоматические алерты
3. Filter API — production rules + pgvector similarity boost
4. Human-in-the-loop feedback — коррекция предсказаний
5. Retrain — переобучение на скорректированных данных + отчёт с метриками

CLI-вариант: `make demo`

### Autonomous Verifier (`make verify`)
20 проверок по всем функциям против живого API: infrastructure → inference → filter → guardrails → data loop → observability → experiments → streaming → latency burst (30 req, p95 < 500ms). Результат — JSON-отчёт в `reports/`, exit code 0/1.

### Load Testing (`make load-test`)
Locust-сценарии с weighted-профилем трафика (predict / filter / guardrails / stats). Smoke: 10 users / 60s, heavy: 50 users / 180s. CSV-отчёты в `reports/`.

---

## 📈 Для портфолио

### MLOps компетенции
- Full ML lifecycle: train → log → register → deploy → monitor → retrain
- Experiment tracking (MLflow) + Model Registry (staging/production)
- CI/CD pipeline (GitHub Actions)
- Infrastructure as Code (Docker Compose + K8s manifests)
- Monitoring (Prometheus + Grafana) с custom metrics
- Drift detection (KS-test, chi-square) с severity scoring
- Hyperparameter optimization (Optuna TPE)
- Model optimization (ONNX export + benchmarking)
- Orchestration (Airflow DAG для automated retraining)

### AI Product Manager компетенции
- A/B testing framework с Bayesian analysis (Beta-Binomial)
- Expected loss + stopping rule — data-driven decisions
- Cost analytics: revenue model, ROI, margin, unit economics
- Product metrics: feedback loop, satisfaction tracking
- Multi-modal support (text + image moderation)
- API design: RESTful, well-documented, versioned

---

## 📄 Лицензия

MIT License — см. [LICENSE](LICENSE).
