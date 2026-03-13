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

## 7. Backup Path (R2 CDN)
- R2/CDN code path is retained for rollback (`IMAGE_BACKEND=r2_cdn`) but is not the primary runtime path.
- Use BGG -> Fly-local commands in Section 4 as the first-line operational workflow.
- Use R2 commands only when explicitly running backup/rollback image-seeding procedures.

## 8. Count Objects in R2 (Backup-Only)

```bash
fly ssh console -a bg-lib-app-dev -C "python -c 'import os,boto3; from botocore.config import Config; s3=boto3.client(\"s3\", endpoint_url=os.environ[\"R2_ENDPOINT_URL\"], aws_access_key_id=os.environ[\"R2_ACCESS_KEY_ID\"], aws_secret_access_key=os.environ[\"R2_SECRET_ACCESS_KEY\"], region_name=os.getenv(\"R2_REGION\",\"auto\"), config=Config(connect_timeout=5, read_timeout=20, retries={\"max_attempts\":3})); bucket=os.environ[\"R2_BUCKET_NAME\"]; paginator=s3.get_paginator(\"list_objects_v2\"); pages=list(paginator.paginate(Bucket=bucket, Prefix=\"games/\")); count=sum(len(p.get(\"Contents\",[])) for p in pages); print(f\"R2 objects under games/: {count} (pages={len(pages)})\")'"
```

## 9. Cloudflare/R2 Backup Commands

Copy existing images from R2 to Fly volume (no local staging).

Dev:

```bash
fly ssh console -a bg-lib-app-dev -C "python -c 'import os,boto3,pathlib; from botocore.config import Config; s3=boto3.client(\"s3\", endpoint_url=os.environ[\"R2_ENDPOINT_URL\"], aws_access_key_id=os.environ[\"R2_ACCESS_KEY_ID\"], aws_secret_access_key=os.environ[\"R2_SECRET_ACCESS_KEY\"], region_name=os.getenv(\"R2_REGION\",\"auto\"), config=Config(connect_timeout=5, read_timeout=20, retries={\"max_attempts\":3})); bucket=os.environ[\"R2_BUCKET_NAME\"]; root=pathlib.Path(os.getenv(\"IMAGE_STORAGE_DIR\",\"/data/images\")); root.mkdir(parents=True, exist_ok=True); ns={\"s3\":s3,\"bucket\":bucket,\"root\":root,\"downloaded\":0,\"skipped\":0}; exec(\"for page in s3.get_paginator(\\\"list_objects_v2\\\").paginate(Bucket=bucket, Prefix=\\\"games/\\\"):\\n    for obj in page.get(\\\"Contents\\\", []):\\n        key=obj[\\\"Key\\\"]\\n        p=root / key\\n        if p.exists():\\n            skipped += 1\\n            continue\\n        p.parent.mkdir(parents=True, exist_ok=True)\\n        s3.download_file(bucket, key, str(p))\\n        downloaded += 1\", ns, ns); print(f\"R2->Fly copy complete: downloaded={ns['downloaded']} skipped_existing={ns['skipped']} dest={root}\")'"
```

Prod:

```bash
fly ssh console -a bg-lib-app -C "python -c 'import os,boto3,pathlib; from botocore.config import Config; s3=boto3.client(\"s3\", endpoint_url=os.environ[\"R2_ENDPOINT_URL\"], aws_access_key_id=os.environ[\"R2_ACCESS_KEY_ID\"], aws_secret_access_key=os.environ[\"R2_SECRET_ACCESS_KEY\"], region_name=os.getenv(\"R2_REGION\",\"auto\"), config=Config(connect_timeout=5, read_timeout=20, retries={\"max_attempts\":3})); bucket=os.environ[\"R2_BUCKET_NAME\"]; root=pathlib.Path(os.getenv(\"IMAGE_STORAGE_DIR\",\"/data/images\")); root.mkdir(parents=True, exist_ok=True); ns={\"s3\":s3,\"bucket\":bucket,\"root\":root,\"downloaded\":0,\"skipped\":0}; exec(\"for page in s3.get_paginator(\\\"list_objects_v2\\\").paginate(Bucket=bucket, Prefix=\\\"games/\\\"):\\n    for obj in page.get(\\\"Contents\\\", []):\\n        key=obj[\\\"Key\\\"]\\n        p=root / key\\n        if p.exists():\\n            skipped += 1\\n            continue\\n        p.parent.mkdir(parents=True, exist_ok=True)\\n        s3.download_file(bucket, key, str(p))\\n        downloaded += 1\", ns, ns); print(f\"R2->Fly copy complete: downloaded={ns['downloaded']} skipped_existing={ns['skipped']} dest={root}\")'"
```

Resume behavior:
- Safe to rerun.
- Existing files are skipped; only missing files are copied.
