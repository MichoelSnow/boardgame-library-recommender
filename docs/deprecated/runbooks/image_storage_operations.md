# Image Storage Operations

This runbook is the canonical operations guide for image storage in `dev` and `prod`.

## Rollout Status
- `dev`: active and validated on Fly-local image storage.
- `prod`: pending by policy; do not run production image migration steps until:
  1. changes are merged to `main`
  2. production deploy is completed
  3. post-deploy validation passes

## Active Model
- Runtime path on Fly uses local volume storage.
- App config:
  - `IMAGE_BACKEND=fly_local`
  - `IMAGE_STORAGE_DIR=/data/images`
- Storage layout:
  - originals: `/data/images/games/<bgg_id>.<ext>`
  - thumbnails: `/data/images/thumbnails/<bgg_id>.webp`
- Image URL flow:
  - card grid prefers `/images/thumbnails/<bgg_id>.webp`
  - details view prefers `/images/games/<bgg_id>.<ext>`
  - `/api/images/{game_id}/cached?image_url=<origin-url>` fills missing originals and generates thumbnail sidecar

## 1. Bring Stack Up

```bash
scripts/deploy/fly_stack.sh dev up
scripts/deploy/fly_stack.sh prod up
```

## 2. Count Files on Fly Volume

Dev:

```bash
fly ssh console -a bg-lib-app-dev -C 'sh -lc "find /data/images/games -type f | wc -l"'
```

Prod:

```bash
fly ssh console -a bg-lib-app -C 'sh -lc "find /data/images/games -type f | wc -l"'
```

## 3. Trigger On-Demand Cache Fill

Use any valid game ID + source URL:

Dev:

```bash
curl -I "https://bg-lib-app-dev.fly.dev/api/images/224517/cached?image_url=https%3A%2F%2Fcf.geekdo-images.com%2F...%2Fpic123.jpg"
```

Prod:

```bash
curl -I "https://bg-lib-app.fly.dev/api/images/224517/cached?image_url=https%3A%2F%2Fcf.geekdo-images.com%2F...%2Fpic123.jpg"
```

Expected:
- `307` redirect to `/images/games/<id>.<ext>`

## 4. Seed Images from BGG Directly to Fly Volume (Primary)

Use the app-machine seed script (BGG origin -> Fly local volume):

Dev:

```bash
fly ssh console -a bg-lib-app-dev -C 'sh -lc "cd /app && poetry run python -m data_pipeline.src.assets.sync_fly_images --scope all-qualified --max-rank 10000"'
```

Prod:

```bash
fly ssh console -a bg-lib-app -C 'sh -lc "cd /app && poetry run python -m data_pipeline.src.assets.sync_fly_images --scope all-qualified --max-rank 10000"'
```

Common variants:

```bash
# Dry run candidate count (no writes)
fly ssh console -a bg-lib-app-dev -C 'sh -lc "cd /app && poetry run python -m data_pipeline.src.assets.sync_fly_images --scope all-qualified --max-rank 10000 --dry-run"'

# Library-only fill
fly ssh console -a bg-lib-app-dev -C 'sh -lc "cd /app && poetry run python -m data_pipeline.src.assets.sync_fly_images --scope library-only"'

# Top-rank only fill
fly ssh console -a bg-lib-app-dev -C 'sh -lc "cd /app && poetry run python -m data_pipeline.src.assets.sync_fly_images --scope top-rank-only --max-rank 10000"'
```

## 5. Verify Runtime Health After Image Changes

Dev:

```bash
poetry run python scripts/validate/validate_fly_health_checks.py --env dev
poetry run python scripts/validate/validate_performance_gate.py --env dev
```

Prod:

```bash
poetry run python scripts/validate/validate_fly_health_checks.py --env prod
poetry run python scripts/validate/validate_performance_gate.py --env prod
```

## 6. Optional: Increase Volume Size

```bash
fly volumes list -a bg-lib-app-dev
fly volumes extend <DEV_APP_VOLUME_ID> --size 10 -a bg-lib-app-dev
```

Prod:

```bash
fly volumes list -a bg-lib-app
fly volumes extend <PROD_APP_VOLUME_ID> --size 10 -a bg-lib-app
```

## 7. Backup Path
- Use BGG -> Fly-local commands in Section 4 as the operational fallback path.
