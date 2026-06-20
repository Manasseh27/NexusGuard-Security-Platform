# NexusGuard Security Platform - Deployment Guide

## Overview

This guide covers production deployment of NexusGuard on Kubernetes with Helm, CI/CD automation, and operational best practices.

## Pre-Deployment Checklist

### Security ✅ REQUIRED
- [ ] All secrets configured in environment (.env production)
- [ ] SECRET_KEY is strong and unique (openssl rand -hex 32)
- [ ] Database password is strong and rotated
- [ ] TLS certificates are valid and not self-signed
- [ ] CORS origins are restricted (no wildcard)
- [ ] API keys are provisioned and rotated
- [ ] Rate limits are configured appropriately
- [ ] Audit logging is enabled

### Infrastructure ✅ REQUIRED
- [ ] Kubernetes cluster is running (1.24+)
- [ ] PostgreSQL database is provisioned
- [ ] Redis cache is running
- [ ] RabbitMQ message broker is running
- [ ] Storage volumes are configured
- [ ] Network policies are in place
- [ ] Ingress controller is installed

### Testing ✅ REQUIRED
- [ ] All unit tests pass: `pytest tests/unit/`
- [ ] All integration tests pass: `pytest tests/integration/`
- [ ] Load tests completed: `k6 run tests/load/main.js`
- [ ] Security scanning completed: `safety check`, `bandit -r app/`
- [ ] Docker image scanned: `trivy image nexusguard:latest`

### Documentation ✅ REQUIRED
- [ ] API documentation generated (auto via Swagger)
- [ ] Deployment runbook is written
- [ ] Incident response procedures are documented
- [ ] Backup/restore procedures are tested
- [ ] Health check endpoints are documented

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Internet                                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │   Ingress   │
                    │ (nginx/aws) │
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
    ┌───▼───┐         ┌────▼────┐       ┌────▼────┐
    │Pod-1  │         │Pod-2    │       │Pod-N    │
    │Backend│         │Backend  │       │Backend  │
    └───┬───┘         └────┬────┘       └────┬────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
    ┌───▼────┐        ┌────▼────┐    ┌──────▼──────┐
    │PostgreSQL       │Redis    │    │RabbitMQ     │
    │(Persistent)     │(Cache)  │    │(Async tasks)│
    └────────┘        └─────────┘    └─────────────┘
```

## Kubernetes Deployment

### 1. Create Namespace

```bash
kubectl create namespace nexusguard
kubectl label namespace nexusguard istio-injection=enabled
```

### 2. Configure Secrets

```bash
# Create database password secret
kubectl create secret generic db-credentials \
  --from-literal=password=<strong-db-password> \
  -n nexusguard

# Create API secrets
kubectl create secret generic api-secrets \
  --from-literal=SECRET_KEY=$(openssl rand -hex 32) \
  --from-literal=API_KEY_SECRET=$(openssl rand -hex 32) \
  -n nexusguard

# Create TLS certificate
kubectl create secret tls tls-cert \
  --cert=path/to/cert.crt \
  --key=path/to/key.key \
  -n nexusguard
```

### 3. Configure ConfigMap

```bash
kubectl create configmap app-config \
  --from-literal=ENVIRONMENT=production \
  --from-literal=ENABLE_HTTPS=true \
  --from-literal=CORS_ORIGINS=https://nexusguard.example.com \
  -n nexusguard
```

### 4. Deploy with Helm

```bash
# Add Helm chart repository
helm repo add nexusguard ./infrastructure/helm
helm repo update

# Create values-prod.yaml (see template below)

# Deploy
helm install nexusguard nexusguard/cisco-security \
  -f infrastructure/helm/values-prod.yaml \
  -n nexusguard

# Verify deployment
kubectl rollout status deployment/nexusguard-backend -n nexusguard
kubectl get pods -n nexusguard
```

### 5. Helm Values (values-prod.yaml)

```yaml
# Backend deployment
backend:
  replicaCount: 3
  
  image:
    repository: nexusguard/backend
    tag: "2.0.0"
    pullPolicy: IfNotPresent
  
  resources:
    requests:
      memory: "256Mi"
      cpu: "250m"
    limits:
      memory: "512Mi"
      cpu: "500m"
  
  env:
    ENVIRONMENT: production
    ENABLE_HTTPS: "true"
    RATE_LIMIT_ENABLED: "true"
    AUDIT_LOG_ENABLED: "true"
  
  service:
    type: ClusterIP
    port: 8000
  
  ingress:
    enabled: true
    className: nginx
    annotations:
      cert-manager.io/cluster-issuer: "letsencrypt-prod"
    hosts:
      - host: api.nexusguard.example.com
        paths:
          - path: /
            pathType: Prefix
    tls:
      - secretName: api-tls-cert
        hosts:
          - api.nexusguard.example.com

# Frontend deployment
frontend:
  replicaCount: 2
  
  image:
    repository: nexusguard/frontend
    tag: "2.0.0"
  
  service:
    type: ClusterIP
    port: 80
  
  ingress:
    enabled: true
    hosts:
      - host: nexusguard.example.com
        paths:
          - path: /
            pathType: Prefix

# PostgreSQL
postgresql:
  enabled: true
  auth:
    username: nexus_user
    password: <secretKeyRef: db-credentials>
  primary:
    persistence:
      enabled: true
      size: 20Gi

# Redis
redis:
  enabled: true
  auth:
    enabled: true
    password: <secretKeyRef: redis-password>
```

## CI/CD Pipeline

### GitHub Actions Configuration

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [ main ]
    tags: [ "v*" ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      
      - name: Install dependencies
        run: |
          python -m pip install -r backend/requirements.txt
          python -m pip install -r requirements-test.txt
      
      - name: Run tests
        run: |
          cd backend
          pytest tests/ --cov=app --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
      
      - name: Security scan
        run: |
          pip install safety bandit
          safety check
          bandit -r backend/app/

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build backend image
        run: |
          docker build -t nexusguard/backend:${{ github.sha }} ./backend
          docker tag nexusguard/backend:${{ github.sha }} nexusguard/backend:latest
      
      - name: Build frontend image
        run: |
          docker build -t nexusguard/frontend:${{ github.sha }} ./frontend
          docker tag nexusguard/frontend:${{ github.sha }} nexusguard/frontend:latest
      
      - name: Push to registry
        run: |
          echo ${{ secrets.DOCKER_PASSWORD }} | docker login -u ${{ secrets.DOCKER_USERNAME }} --password-stdin
          docker push nexusguard/backend:${{ github.sha }}
          docker push nexusguard/frontend:${{ github.sha }}
      
      - name: Scan image
        run: |
          docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
            aquasec/trivy image nexusguard/backend:${{ github.sha }}

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure kubectl
        run: |
          mkdir -p $HOME/.kube
          echo ${{ secrets.KUBE_CONFIG }} | base64 -d > $HOME/.kube/config
      
      - name: Deploy with Helm
        run: |
          helm upgrade --install nexusguard ./infrastructure/helm/cisco-security \
            -f infrastructure/helm/values-prod.yaml \
            --set image.tag=${{ github.sha }} \
            -n nexusguard
      
      - name: Wait for deployment
        run: |
          kubectl rollout status deployment/nexusguard-backend -n nexusguard --timeout=5m
      
      - name: Health check
        run: |
          kubectl exec -n nexusguard deployment/nexusguard-backend \
            -- curl -f http://localhost:8000/api/v1/health/ready || exit 1
```

## Health Checks

### Kubernetes Probes

```yaml
livenessProbe:
  httpGet:
    path: /api/v1/health/live
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /api/v1/health/ready
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 2
```

### Health Check Endpoints

```python
@app.get("/api/v1/health/live")
async def liveness_probe():
    """Liveness probe - is the service running?"""
    return {"status": "alive"}

@app.get("/api/v1/health/ready")
async def readiness_probe(db: AsyncSession = Depends(get_db)):
    """Readiness probe - is the service ready to handle requests?"""
    try:
        # Check database connection
        await db.execute(text("SELECT 1"))
        
        # Check Redis connection
        await redis_client.ping()
        
        return {"status": "ready", "components": {
            "database": "healthy",
            "cache": "healthy"
        }}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "error": str(e)}
        )
```

## Scaling

### Horizontal Pod Autoscaling

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: nexusguard-hpa
  namespace: nexusguard
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: nexusguard-backend
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Pod Disruption Budget

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: nexusguard-pdb
  namespace: nexusguard
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: nexusguard-backend
```

## Backup & Recovery

### Database Backups

```bash
# Daily automated backup
0 2 * * * pg_dump -Fc nexusguard | gzip > /backups/nexusguard-$(date +%Y%m%d).sql.gz

# Restore from backup
gunzip < /backups/nexusguard-20240115.sql.gz | pg_restore -d nexusguard
```

### Kubernetes Backup (Velero)

```bash
# Install Velero
velero install --provider aws --bucket nexusguard-backups --secret-file credentials-velero

# Create daily backup schedule
velero schedule create nexusguard-daily \
  --schedule="0 2 * * *" \
  --include-namespaces nexusguard \
  --ttl 720h
```

## Monitoring & Logging

### Prometheus Scrape Config

```yaml
- job_name: 'nexusguard'
  static_configs:
    - targets: ['localhost:8001']
  relabel_configs:
    - source_labels: [__address__]
      target_label: instance
```

### Grafana Dashboard

Key metrics to monitor:
- API response time (p50, p95, p99)
- Error rates by endpoint
- Database connection pool usage
- Cache hit ratio
- Queue depth (Celery tasks)
- Compliance evaluation time

### Log Aggregation (ELK Stack)

```yaml
# Logstash configuration
input {
  tcp {
    port => 5000
    codec => json
  }
}

filter {
  if [docker][image] == "nexusguard/backend" {
    grok {
      match => { "message" => "%{LOGLEVEL:level} %{DATA:logger} %{GREEDYDATA:msg}" }
    }
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "nexusguard-%{+YYYY.MM.dd}"
  }
}
```

## Rolling Updates

```bash
# Zero-downtime deployment
kubectl set image deployment/nexusguard-backend \
  nexusguard-backend=nexusguard/backend:new-version \
  --record -n nexusguard

# Watch rollout
kubectl rollout status deployment/nexusguard-backend -n nexusguard

# Rollback if needed
kubectl rollout undo deployment/nexusguard-backend -n nexusguard
```

## Troubleshooting

### Check Pod Status
```bash
kubectl describe pod <pod-name> -n nexusguard
kubectl logs <pod-name> -n nexusguard
```

### Database Issues
```bash
# Check connection
kubectl exec -it <pod-name> -n nexusguard \
  -- psql $DATABASE_URL -c "SELECT 1"
```

### Performance Debugging
```bash
# CPU/Memory usage
kubectl top nodes
kubectl top pods -n nexusguard

# Slow queries
kubectl exec -it postgres-0 -n nexusguard \
  -- psql -U nexus_user -d nexusguard -c \
  "SELECT * FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"
```

## Security Hardening in Production

1. **Network Policies**: Restrict traffic between pods
2. **Pod Security Policy**: Enforce security standards
3. **RBAC**: Limit service account permissions
4. **Secrets Management**: Use external vault (HashiCorp, AWS Secrets Manager)
5. **Image Scanning**: Scan all container images for vulnerabilities
6. **Log Retention**: Configure appropriate log retention policies
7. **Backup Encryption**: Encrypt all backups at rest
8. **Access Auditing**: Log all administrative actions

## Disaster Recovery

### RTO/RPO Goals
- **RTO (Recovery Time Objective)**: 1 hour
- **RPO (Recovery Point Objective)**: 15 minutes

### Disaster Recovery Procedures
1. Automated daily backups to S3
2. Cross-region backup replication
3. Tested recovery procedures (monthly)
4. Incident response runbook
5. Communication procedures

## Operations Runbook

See `docs/OPERATIONS.md` for:
- Daily checks and maintenance
- Common issues and solutions
- Performance tuning guide
- Incident response procedures
- Escalation contacts
