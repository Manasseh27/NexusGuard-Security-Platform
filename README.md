# Cisco Security Platform v2.0

Enterprise-grade cybersecurity compliance and network automation platform.

## Quick Start

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Start the full stack
docker-compose up -d

# 3. Access the platform
#    API:      http://localhost:8000/api/docs
#    Frontend: http://localhost:3000
#    Grafana:  http://localhost:3001  (admin/admin)
#    Prometheus: http://localhost:9090
```

## Demo Credentials

| Username  | Password     | Role      |
|-----------|-------------|-----------|
| admin     | admin123    | Admin     |
| engineer  | engineer123 | Engineer  |
| analyst   | analyst123  | Analyst   |
| viewer    | viewer123   | Viewer    |

## Stack

- **Backend**: FastAPI + SQLAlchemy 2.0 + asyncpg
- **Frontend**: React + TypeScript + Recharts
- **Database**: PostgreSQL 16 + pgvector
- **Cache**: Redis 7
- **Workers**: Celery
- **AI**: OpenAI / Anthropic Claude / Ollama (local)
- **Observability**: Prometheus + Grafana + OpenTelemetry
- **Policy Engine**: Open Policy Agent (OPA)
- **Deployment**: Helm + Kubernetes + ArgoCD

## Architecture

See [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md)

## Running Tests

```bash
cd backend
pip install -r requirements.txt
pytest tests/unit -v --cov=app
```
