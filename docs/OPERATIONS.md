# NexusGuard Security Platform - Operations Manual

## Overview

This manual provides operational guidance for running NexusGuard in production, including daily tasks, troubleshooting, performance tuning, and incident response.

## Table of Contents

1. [Daily Operations](#daily-operations)
2. [Monitoring & Alerting](#monitoring--alerting)
3. [Troubleshooting](#troubleshooting)
4. [Performance Tuning](#performance-tuning)
5. [Incident Response](#incident-response)
6. [Backup & Recovery](#backup--recovery)
7. [Maintenance Windows](#maintenance-windows)

## Daily Operations

### Morning Checklist (09:00)

```bash
#!/bin/bash
# Daily operation checks

# Check cluster health
kubectl get nodes
kubectl get pods -n nexusguard
kubectl top nodes

# Check resource usage
kubectl top pods -n nexusguard | head -20

# Check recent errors in logs
kubectl logs -n nexusguard deployment/nexusguard-backend --tail=50 | grep ERROR

# Check database connections
kubectl exec -it postgres-0 -n nexusguard -- \
  psql -U nexus_user -d nexusguard -c \
  "SELECT count(*) as active_connections FROM pg_stat_activity;"

# Check cache utilization
kubectl exec -it redis-0 -n nexusguard -- redis-cli INFO memory

# Verify backups completed
aws s3 ls s3://nexusguard-backups/ --recursive --human-readable \
  --summarize | tail -5
```

### Metrics Dashboard Review

**Key Metrics to Monitor:**

| Metric | Warning | Critical |
|--------|---------|----------|
| API Response Time (p99) | >1000ms | >2000ms |
| Error Rate | >0.5% | >5% |
| Database Connections | >80% pool | 100% pool |
| Cache Hit Ratio | <80% | <70% |
| Disk Usage | >80% | >95% |
| Memory Usage | >80% | >90% |
| Queue Depth | >1000 | >5000 |

### Weekly Tasks (Friday)

- [ ] Review and archive logs older than 1 week
- [ ] Analyze error trends
- [ ] Check certificate expiry (if < 30 days, renew)
- [ ] Verify backup integrity
- [ ] Review security audit logs
- [ ] Update dependency vulnerability list
- [ ] Check for pending patches/updates

### Monthly Tasks

- [ ] Security audit review
- [ ] Database maintenance (VACUUM, ANALYZE)
- [ ] Performance analysis and tuning recommendations
- [ ] Capacity planning review
- [ ] Test disaster recovery procedure
- [ ] Review and update runbooks
- [ ] Security certificate renewal if needed
- [ ] Third-party vulnerability scan

## Monitoring & Alerting

### Alert Configuration

```yaml
# Prometheus AlertManager rules
groups:
  - name: nexusguard.rules
    rules:
      # High error rate
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High error rate detected"
          value: "{{ $value }}"
      
      # Slow API responses
      - alert: SlowAPIResponse
        expr: histogram_quantile(0.99, http_request_duration_seconds) > 2
        for: 5m
        annotations:
          summary: "API response time above 2s"
      
      # Database connection pool exhausted
      - alert: DatabaseConnectionPoolExhausted
        expr: db_connection_pool_available < 1
        for: 1m
        annotations:
          summary: "Database connection pool exhausted"
      
      # Cache down
      - alert: CacheDown
        expr: up{job="redis"} == 0
        for: 1m
        annotations:
          summary: "Redis cache is down"
      
      # Disk space low
      - alert: DiskSpaceLow
        expr: node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes < 0.2
        for: 10m
        annotations:
          summary: "Disk space below 20%"
```

### Alert Notification Channels

- **Page on-call**: Critical alerts only (error rate >5%, service down)
- **Slack #alerts**: Warning alerts (warning thresholds exceeded)
- **Email**: Daily summary report
- **PagerDuty**: Incident escalation

### Alert Fatigue Prevention

- Tune alert thresholds based on baseline
- Aggregate related alerts into single notification
- Auto-resolve known false positives
- Review and silence unnecessary alerts weekly

## Troubleshooting

### Service Won't Start

```bash
# Check pod status
kubectl describe pod <pod-name> -n nexusguard

# Check events
kubectl get events -n nexusguard --sort-by='.lastTimestamp'

# Check logs
kubectl logs <pod-name> -n nexusguard

# Common causes:
# 1. Database not ready - check postgres-0 pod
# 2. Secrets missing - verify kubectl get secrets -n nexusguard
# 3. Resource limits exceeded - check kubectl describe node
```

### High API Response Time

```bash
# Identify slow endpoints
kubectl exec -it prometheus-0 -n nexusguard -- \
  promtool query instant \
  'topk(10, rate(http_request_duration_seconds_bucket[5m]))'

# Check database performance
kubectl exec -it postgres-0 -n nexusguard -- psql -U nexus_user -d nexusguard <<EOF
-- Slow queries
SELECT query, mean_time, calls FROM pg_stat_statements 
  ORDER BY mean_time DESC LIMIT 10;

-- Missing indexes
SELECT schemaname, tablename, indexname FROM pg_indexes 
  WHERE indexdef LIKE '%USING btree%'
  ORDER BY tablename;
EOF

# Check connection pool
kubectl logs <pod-name> -n nexusguard | grep "pool_exhausted"

# Restart pod (last resort)
kubectl rollout restart deployment/nexusguard-backend -n nexusguard
```

### Database Connection Failures

```bash
# Test connection
kubectl exec -it postgres-0 -n nexusguard -- \
  psql -U nexus_user -d nexusguard -c "SELECT 1"

# Check connection from app pod
kubectl exec -it <app-pod> -n nexusguard -- \
  python -c "
import asyncpg
import asyncio
asyncio.run(asyncpg.connect('$DATABASE_URL'))
"

# Check network connectivity
kubectl exec -it <app-pod> -n nexusguard -- \
  ping postgres-0.postgres

# Check firewall rules
kubectl get networkpolicies -n nexusguard
```

### High Memory Usage

```bash
# Find memory hogs
kubectl top pods -n nexusguard --sort-by=memory

# Analyze heap usage (if process supports it)
kubectl exec -it <pod-name> -n nexusguard -- \
  python -c "
import tracemalloc
tracemalloc.start()
# ... app code ...
snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')
for stat in top_stats[:10]:
    print(stat)
"

# Restart pod
kubectl delete pod <pod-name> -n nexusguard

# Increase memory limits in Helm values
# helm upgrade ... --set backend.resources.limits.memory=1Gi
```

### Redis Cache Issues

```bash
# Check Redis health
kubectl exec -it redis-0 -n nexusguard -- redis-cli ping

# Monitor Redis commands
kubectl exec -it redis-0 -n nexusguard -- redis-cli monitor

# Check memory usage
kubectl exec -it redis-0 -n nexusguard -- redis-cli INFO memory

# Clear cache (if necessary)
kubectl exec -it redis-0 -n nexusguard -- redis-cli FLUSHDB

# Check key distribution
kubectl exec -it redis-0 -n nexusguard -- \
  redis-cli --bigkeys --memkeys
```

## Performance Tuning

### Database Optimization

```bash
# Enable query logging
kubectl exec -it postgres-0 -n nexusguard -- \
  psql -U postgres -c \
  "ALTER SYSTEM SET log_min_duration_statement = 500;"

# Reload config
kubectl exec -it postgres-0 -n nexusguard -- \
  psql -U postgres -c "SELECT pg_reload_conf();"

# Analyze query plans
EXPLAIN ANALYZE
SELECT * FROM devices WHERE tenant_id = 'xxx' AND monitoring_state = 'DRIFTING';

# Add missing indexes
CREATE INDEX idx_devices_tenant_state 
  ON devices(tenant_id, monitoring_state);

# Vacuum and analyze
VACUUM ANALYZE;
```

### API Response Time Optimization

```python
# 1. Add caching for frequently accessed data
@app.get("/api/v1/compliance/fleet/summary", cache_ttl=300)
async def fleet_summary(current_user = Depends(get_current_user)):
    return await compliance_service.get_fleet_summary(current_user.tenant_id)

# 2. Paginate large result sets
@app.get("/api/v1/devices")
async def list_devices(
    skip: int = 0,
    limit: int = 20,  # Default page size
):
    return await device_service.list_devices(skip=skip, limit=limit)

# 3. Use select() to limit columns
from sqlalchemy import select
stmt = select(Device.id, Device.hostname, Device.ip_address)
```

### Scaling Recommendations

```bash
# If CPU usage > 80%:
# - Increase pod replicas
helm upgrade nexusguard ... --set backend.replicaCount=5

# If memory usage > 80%:
# - Reduce cache TTL
# - Implement garbage collection
# - Increase memory limits

# If database is bottleneck:
# - Add read replicas
# - Increase connection pool size
# - Implement query caching

# If network is bottleneck:
# - Enable gzip compression (already enabled)
# - Reduce payload sizes
# - Use CDN for static assets
```

## Incident Response

### Critical Incident Procedure

1. **Acknowledge**: P1/Critical incident created
2. **Page**: On-call engineer notified
3. **Assess**: Identify affected systems (10 min)
4. **Respond**: Start mitigation (within 15 min)
5. **Communicate**: Status updates every 15 min
6. **Resolve**: Fix and deploy (within 1 hour if possible)
7. **Restore**: Verify functionality
8. **Postmortem**: Schedule within 24 hours

### Common Incidents

**Incident: Service Down**

```bash
# 1. Check pod status
kubectl get pods -n nexusguard

# 2. View recent logs
kubectl logs <pod-name> -n nexusguard --tail=100

# 3. Restart service
kubectl rollout restart deployment/nexusguard-backend -n nexusguard

# 4. Verify recovery
kubectl rollout status deployment/nexusguard-backend -n nexusguard

# 5. Check health endpoint
kubectl exec -it <pod-name> -n nexusguard -- \
  curl http://localhost:8000/api/v1/health/ready
```

**Incident: Database Down**

```bash
# 1. Check database pod
kubectl describe pod postgres-0 -n nexusguard

# 2. Check persistent volume
kubectl get pv

# 3. If restart needed:
kubectl delete pod postgres-0 -n nexusguard

# 4. Verify recovery
kubectl exec -it postgres-0 -n nexusguard -- \
  psql -U postgres -c "SELECT 1"
```

**Incident: High Error Rate**

```bash
# 1. Identify error patterns
kubectl logs -n nexusguard deployment/nexusguard-backend \
  | grep ERROR | head -20

# 2. Check for cascading failures
kubectl get events -n nexusguard

# 3. Check dependent services
kubectl get pods -n nexusguard -o wide

# 4. Scale up if needed
kubectl scale deployment nexusguard-backend \
  --replicas=5 -n nexusguard

# 5. Monitor recovery
watch kubectl top pods -n nexusguard
```

**Incident: Memory Leak**

```bash
# 1. Identify process with high memory
kubectl top pods -n nexusguard --sort-by=memory

# 2. Collect heap dump (if supported)
kubectl exec <pod-name> -n nexusguard -- \
  jmap -dump:live,format=b,file=/tmp/heap.bin 1

# 3. Extract and analyze
kubectl cp <pod-name>:/tmp/heap.bin ./heap.bin

# 4. Restart pod to release memory
kubectl delete pod <pod-name> -n nexusguard

# 5. Schedule code review
```

### Incident Communication Template

```
Subject: [INCIDENT] NexusGuard API - High Error Rate - P2

Current Status: INVESTIGATING
Started: 2024-01-15 14:32 UTC
Duration: 5 minutes
Affected: API endpoints
Impact: 2.3% of requests failing

What we know:
- Error spike started at 14:32
- Affecting /api/v1/compliance/evaluate endpoint
- Database response times increased 10x

What we're doing:
- Scaling up backend pods
- Analyzing database slow query log
- Rolling back recent deployment

ETA for resolution: 15:00 UTC

Next update: 14:45 UTC
```

## Backup & Recovery

### Backup Schedule

- **Database**: Every 6 hours (retained 30 days)
- **Kubernetes State**: Daily (retained 30 days)
- **Configuration**: Every commit (version controlled)
- **Logs**: Every day, archived after 90 days

### Recovery Test

```bash
# Monthly recovery drill
# 1. Restore from backup to staging
kubectl apply -f staging/backup-restore.yaml

# 2. Verify data integrity
kubectl exec -it postgres-staging-0 -- \
  psql -U nexus_user -d nexusguard -c \
  "SELECT count(*) FROM devices;"

# 3. Run health checks
curl https://staging-api.nexusguard/api/v1/health/ready

# 4. Document results
# (Attach recovery time, issues, resolutions to ticket)
```

### Recovery Procedure

```bash
# 1. Identify latest valid backup
aws s3 ls s3://nexusguard-backups/

# 2. Restore database
kubectl exec -it postgres-0 -n nexusguard -- \
  pg_restore -Fc -d nexusguard \
  /backups/nexusguard-20240115.dump

# 3. Verify application
kubectl rollout restart deployment/nexusguard-backend -n nexusguard

# 4. Validate functionality
kubectl run -it test-curl \
  --image=curlimages/curl \
  -- curl http://nexusguard-backend:8000/api/v1/health/ready
```

## Maintenance Windows

### Planned Maintenance Procedure

```bash
# 1. Announce maintenance (24 hours before)
# 2. Create maintenance window in monitoring system
# 3. Drain existing connections
kubectl patch service nexusguard-backend \
  -p '{"spec":{"type":"ExternalName"}}'

# 4. Perform maintenance
# (upgrades, patches, etc.)

# 5. Verify all systems
kubectl get pods -n nexusguard
kubectl logs -f deployment/nexusguard-backend

# 6. Restore service
kubectl patch service nexusguard-backend \
  -p '{"spec":{"type":"ClusterIP"}}'

# 7. Run smoke tests
kubectl run smoke-tests --image=nexusguard/smoke-tests
```

### Zero-Downtime Deployment

```bash
# 1. Build and test new image
docker build -t nexusguard/backend:v2.0.1 .
docker push nexusguard/backend:v2.0.1

# 2. Update deployment
kubectl set image deployment/nexusguard-backend \
  nexusguard-backend=nexusguard/backend:v2.0.1 \
  --record -n nexusguard

# 3. Monitor rollout
kubectl rollout status deployment/nexusguard-backend \
  --timeout=5m -n nexusguard

# 4. Verify health
for i in {1..10}; do
  curl http://nexusguard-backend:8000/api/v1/health/ready
  sleep 10
done

# 5. Rollback if needed
kubectl rollout undo deployment/nexusguard-backend -n nexusguard
```

## Contacts & Escalation

- **On-Call Engineer**: [team member info]
- **Team Lead**: [contact info]
- **CTO**: [contact info]
- **Vendors**: [support contacts]

## Useful Commands

```bash
# View real-time logs
kubectl logs -f deployment/nexusguard-backend -n nexusguard

# Watch resource usage
watch kubectl top pods -n nexusguard

# Get into pod shell
kubectl exec -it <pod-name> -n nexusguard -- /bin/bash

# Port forward for debugging
kubectl port-forward svc/nexusguard-backend 8000:8000 -n nexusguard

# View resource requests/limits
kubectl describe nodes

# Get deployment history
kubectl rollout history deployment/nexusguard-backend -n nexusguard

# Get detailed event logs
kubectl get events -n nexusguard --sort-by='.lastTimestamp'
```

## Documentation Links

- Architecture: `docs/ARCHITECTURE.md`
- Deployment: `docs/DEPLOYMENT.md`
- API: `http://api.nexusguard.example.com/api/docs`
- Runbooks: `docs/RUNBOOKS/`
