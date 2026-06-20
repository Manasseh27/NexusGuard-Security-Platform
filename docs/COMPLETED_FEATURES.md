# COMPLETED FEATURES

Date: 2026-06-05

## Incident Management
- Added enterprise incident lifecycle states: `NEW`, `ASSIGNED`, `INVESTIGATING`, `CONTAINED`, `RESOLVED`, `CLOSED`.
- Added persistent incident model with assignment, ownership, source, severity, and tenant scoping.
- Added incident comments and immutable timeline/audit entries.
- Added incident APIs for CRUD-like operations, assignment, status transitions, comments, and timeline retrieval.

## Notifications
- Added persistent notification model for event-driven notification tracking.
- Added notification API for create/list/mark-read operations.
- Added event bridge dispatch on notification creation (`domain.notification.created`).
- Added incident-triggered in-app notifications for assignment and closure milestones.

## RBAC and Access Enforcement
- Expanded backend permission matrix with incident and notification permissions.
- Added frontend route-level permission guards and token/session-based protected routing.
- Aligned role model to include `super_admin`, `security_analyst`, `soc_analyst`, and `auditor`.

## Workflow Wiring Improvements
- Replaced bulk compliance placeholder queue response with real Celery dispatch.
- Replaced force-poll placeholder with real Celery compliance job dispatch and task IDs.
- Corrected monitoring poll API route to match frontend API client contract.

## Frontend Improvements
- Added incidents page with:
  - real API integration
  - create incident workflow
  - status transition actions
  - filtering and loading/error states
- Added incidents and notifications API client methods and shared TypeScript models.
- Fixed frontend TypeScript build blocker (`ignoreDeprecations` config).

## Repository Hygiene
- Added root `.gitignore` for Python/Node/build artifacts and secrets.
- Removed repository-local virtual environments and generated artifacts:
  - `.venv`
  - `.venv-1`
  - `.pytest_cache`
  - `frontend/dist`
