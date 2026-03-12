# Ownership and SLOs

## Data Contract Ownership
- Backend API/schema is the canonical contract source.
- Frontend integration must follow backend contract intentionally.
- Contract changes require coordinated updates to:
  - backend behavior/schemas
  - frontend consumers
  - tests
  - docs when user-visible behavior changes

## Service Targets
### Latency
- Catalog/search/list endpoints: p95 < 1000 ms
- Recommendation endpoints: p95 < 2500 ms
- Image delivery: first meaningful image < 1500 ms under representative convention conditions

### Reliability
- Error rate during convention hours: < 1%
- 5xx rate target during convention hours: < 0.5%

### Recovery
- Incident acknowledgment: within 5 minutes
- Primary app path recovery: within 15 minutes

### Data Loss
- Committed writes: no loss beyond last successful transaction
- Rebuild intermediates: reproducible and not primary recovery point

## Usage Rule
- New architecture changes and runbooks should align with these targets.

## Auth Failure Alert Threshold
- Alert when auth failures spike above 30/min for 5 consecutive minutes.
- Treat this as abuse/misconfiguration signal; investigate before tuning thresholds.
