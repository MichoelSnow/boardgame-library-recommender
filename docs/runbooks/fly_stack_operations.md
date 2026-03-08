# Fly Stack Operations

## Quick Wake Commands
Fly machines may be stopped when idle because `auto_stop_machines = 'stop'`.
Use stack orchestration for all normal operations:

```bash
scripts/deploy/fly_stack.sh dev up
scripts/deploy/fly_stack.sh prod up
```

For cost-control shutdown:

```bash
scripts/deploy/fly_stack.sh dev down
scripts/deploy/fly_stack.sh prod down
```

Status check:

```bash
scripts/deploy/fly_stack.sh dev status
scripts/deploy/fly_stack.sh prod status
```

Fallback note:
- If a machine does not exist (for example after `fly scale count 0`), deploy that app to recreate it before running `scripts/deploy/fly_stack.sh ... up`.
- Do not use `fly scale count 0` as a temporary stop mechanism in normal operations; it destroys machines and can force recreation/re-attachment steps. Use `scripts/deploy/fly_stack.sh <env> down` for temporary shutdown.

Cross-app dependency note:
- Fly does not provide native "start app A automatically starts app B" linking across separate apps.
- Use explicit orchestration for safe ordering via `scripts/deploy/fly_stack.sh`.

## One-Time DB App (Re)Bootstrap Notes
Use this only when introducing `fly.db.*.toml` to an existing DB app or fixing an app that accidentally created duplicate machine/volume resources.

1. Inspect current DB resources:
```bash
fly machines list -a pax-tt-db-dev
fly volumes list -a pax-tt-db-dev
```
2. Keep the intended data volume (for example `pg_data_dev`) and delete unintended duplicate machine/volume resources first.
3. If you need deterministic re-attachment to an existing volume and there is no live traffic:
   - stop stack: `scripts/deploy/fly_stack.sh dev down`
   - destroy old DB machine (volume is retained): `fly machine destroy <DB_MACHINE_ID> -a pax-tt-db-dev`
   - ensure only the intended volume remains in `fly volumes list`
   - deploy DB config: `fly deploy -a pax-tt-db-dev -c fly.db.dev.toml`
4. Re-verify:
```bash
fly machines list -a pax-tt-db-dev
fly volumes list -a pax-tt-db-dev
fly ips list -a pax-tt-db-dev
```
5. Repeat the same pattern for `prod` with `pax-tt-db-prod` and `fly.db.prod.toml`.

## DB Keepalive (App-Driven)
To keep DB machines aligned with app runtime without a 24/7 external scheduler:
- app runtime sends periodic lightweight DB pings while app machine is running
- when app machine stops, keepalive stops automatically
- DB autostop handles idle shutdown when no traffic remains

Runtime settings (configured in Fly app profiles):
- `DB_KEEPALIVE_ENABLED=true`
- `DB_KEEPALIVE_INTERVAL_SECONDS=60`

Notes:
- Keepalive does not generate inbound app traffic and does not prevent app autostop.
- Keepalive is only enabled for Postgres-backed runtime.
- DB Fly configs intentionally omit per-DB `tcp_checks` so idle DB machines can autostop reliably under low/no traffic.
- DB health coverage is provided by app-level checks and periodic production alerting (`scripts/alerts/run_prod_health_alerts.py`).
