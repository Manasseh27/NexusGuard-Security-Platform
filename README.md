# NexusGuard Security Platform

Enterprise-inspired cybersecurity operations platform built with FastAPI, React, PostgreSQL, Redis and Docker.

## Overview

NexusGuard is a centralized security operations platform designed to help security teams monitor infrastructure, manage compliance, process security events and streamline incident response workflows.

The platform combines compliance monitoring, audit logging, SIEM event processing, device management and AI-assisted security operations into a unified dashboard.

---

## Features

### Security Operations

* Security Event Monitoring
* SIEM Event Processing Pipeline
* Incident Tracking and Management
* Audit Logging

### Compliance & Governance

* Compliance Monitoring Engine
* Compliance Scoring
* Compliance Exception Management
* CIS Benchmark Evaluation

### Access Management

* JWT Authentication
* Role-Based Access Control (RBAC) Architecture
* Multi-Role User Management

### Infrastructure

* Dockerized Deployment
* PostgreSQL Database
* Redis Integration
* FastAPI Backend
* React Frontend

### AI Features

* AI Security Copilot
* Security Recommendations
* Workflow Assistance

---

## Technology Stack

### Backend

* Python
* FastAPI
* SQLAlchemy
* PostgreSQL
* Redis

### Frontend

* React
* TypeScript
* Vite

### DevOps

* Docker
* Docker Compose

---

## Project Structure

backend/ – FastAPI APIs and business logic

frontend/ – React user interface

infrastructure/ – deployment and infrastructure resources

tests/ – unit and integration tests

docs/ – architecture and project documentation

---
## Development Demo Accounts

When `ENABLE_DEMO_DATA=true` is configured, the platform automatically seeds the following development accounts:

| Username | Password    | Role             |
| -------- | ----------- | ---------------- |
| admin    | admin123    | Administrator    |
| engineer | engineer123 | Engineer         |
| analyst  | analyst123  | Security Analyst |
| viewer   | viewer123   | Viewer           |

**Note:** These accounts are intended for local development and testing only and should never be enabled in production environments.

## Running Locally

```bash
docker compose up --build
```

Frontend:
http://localhost:3000

Backend:
http://localhost:8000

---

## Current Development Status

Implemented:

* Authentication Backend
* RBAC Architecture
* Compliance Engine
* Incident Management APIs
* Audit Logging
* SIEM Pipeline
* Docker Deployment

Planned Improvements:

* User Registration
* Advanced RBAC Enforcement
* Dashboard Data Integration
* AI Copilot Enhancements
* API Documentation

---

## Author

Manasseh M

Cybersecurity Engineering Student
