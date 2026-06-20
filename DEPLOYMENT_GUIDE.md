# Deployment Guide

## Local Development
1. Copy `.env.example` to `.env`.
2. Set real secrets for production-like testing.
3. Run the frontend with `npm run dev` from `frontend/`.
4. Start the backend with a virtualenv and installed requirements.

## Backend Setup
1. Create and activate a Python virtual environment.
2. Install dependencies from `backend/requirements.txt`.
3. Apply database migrations from `backend/`:
	- `alembic upgrade head`
4. Start API server:
	- `uvicorn app.main:app --reload --app-dir backend`

## Frontend Setup
1. Install dependencies from `frontend/`:
	- `npm install`
2. Build production bundle:
	- `npm run build`
3. Run preview or serve via Nginx container.

## Container Deployment
- Use the provided Dockerfiles and `docker-compose.yml` for the full stack.
- Ensure PostgreSQL, Redis, and the API are on the same network.
- Set `VITE_API_URL` for frontend builds if the API is not served from the same origin.
- Ensure Celery worker and beat processes are enabled for asynchronous compliance and incident workflows.

## Production Checklist
- Use real JWT and API signing secrets.
- Enable persistent volumes for PostgreSQL and Redis.
- Set explicit CORS origins and trusted hosts.
- Wire health endpoints to orchestrator probes.
- Confirm observability backends before enabling trace export.
- Run migration verification before release (`alembic current`, `alembic heads`).
- Validate incident and notification APIs post-deploy.
- Validate RBAC matrix with role-based smoke tests.