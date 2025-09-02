# CertificationService

FastAPI microservice that orchestrates certification workflows across domains (core, transport, banking, healthcare). It exposes internal APIs for workflow creation, status tracking, history querying, and self-monitoring. Execution is delegated to an ExecutionService via a client stub.

## Run (development)

- Entrypoint: `src/api/main.py` (FastAPI app object: `app`)
- Dependencies are listed in `requirements.txt`.
- Start (example): `uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload`

## API overview

- GET `/` — Health check
- GET `/health/report` — Service health report
- GET `/docs/websocket-usage` — Notes regarding websockets
- POST `/workflow` — Create certification workflow (accepts Git params, domain, stages, optional notification)
- GET `/workflow/{workflow_id}` — Get workflow by id
- POST `/workflow/{workflow_id}/status` — Update stage status (callback from ExecutionService)
- GET `/query/history` — Query certification history (script/domain/author/branch/commit/stage/status + pagination)

## Environment and configuration

- Replace the `ExecutionServiceClient` base URL with environment variable-driven configuration when available (e.g., `EXECUTION_SERVICE_URL`).
- For persistence, replace the in-memory repository with a PostgreSQL-backed implementation using env vars provided by CertificationService_database.

## Notes

- This service has no direct end-user UI; it is intended for internal services and CI/CD systems.
- Notifications (webhook/email/slack) are stubbed for now.

