# Local Offline Kiosk Guide (Windows + Postgres)

This guide explains how to run the kiosk system locally on a Windows machine when internet access is unreliable or unavailable.

Scope:
- New Windows machine setup
- Local Postgres runtime (not SQLite)
- Local app hosting for kiosk clients on the same LAN
- Offline-first operation using pre-staged data artifacts

Assumptions:
- You have a copy of required local artifacts from a prepared source machine.
- You are using Git Bash or Windows PowerShell as the command shell on Windows.
- Docker Desktop is installed and running.

Shell guidance:
- Commands are written for Git Bash by default.
- Where syntax differs, a PowerShell equivalent is provided.
- `cmd.exe` is not recommended for this guide.

## 1. What You Need Before Going Offline

Prepare and copy these assets onto external storage (or another transfer path):

1. Processed data directory:
- `data/transform/processed/<timestamp>/processed_games_*.csv`

2. Collaborative recommendation artifacts:
- `backend/database/game_embeddings_<timestamp>.npz`
- `backend/database/reverse_mappings_<timestamp>.json`

3. Content recommendation artifacts:
- `backend/database/content_embeddings_<timestamp>.npz`
- `backend/database/content_reverse_mappings_<timestamp>.json`
- `backend/database/content_feature_mappings_<timestamp>.json`
- `backend/database/content_embeddings_metadata_<timestamp>.json`

4. Optional but recommended for image reliability offline:
- `backend/database/images/` (or equivalent image cache directory)

5. Optional library import file (if needed for convention catalog):
- `data/library/bg_lib_games_<timestamp>.csv`

6. Optional fastest DB bootstrap input:
- A Postgres SQL backup (`.sql`) you can restore locally.

Without the image cache, missing images may fail to load offline because origin fetch requires internet.

## 2. Install Prerequisites on the New Windows Machine

Install:
- Git (with Git Bash)
- Python 3.13
- Poetry 2.3.x
- Node.js + npm
- Docker Desktop

Verify in Git Bash or PowerShell:

```bash
python --version
poetry --version
node --version
npm --version
docker --version
```

## 3. Clone Repo and Install Dependencies

Git Bash:

```bash
git clone <repo-url>
cd pax_tt_recommender
poetry env use 3.13
poetry install
cd frontend && npm ci && npm run build && cd ..
```

PowerShell:

```powershell
git clone <repo-url>
Set-Location pax_tt_recommender
poetry env use 3.13
poetry install
Set-Location frontend
npm ci
npm run build
Set-Location ..
```

## 4. Copy Offline Artifacts Into the Repo

Copy your prepared offline bundle so files are in these repo paths:
- `data/transform/processed/<timestamp>/...`
- `backend/database/game_embeddings_<timestamp>.npz`
- `backend/database/reverse_mappings_<timestamp>.json`
- `backend/database/content_embeddings_<timestamp>.npz`
- `backend/database/content_reverse_mappings_<timestamp>.json`
- `backend/database/content_feature_mappings_<timestamp>.json`
- `backend/database/content_embeddings_metadata_<timestamp>.json`
- `backend/database/images/...` (if available)
- `data/library/bg_lib_games_<timestamp>.csv` (if used)

## 5. Create and Configure `.env`

Generate a baseline `.env`:

```bash
bash scripts/deploy/generate_env_secrets.sh .env
```
This command is the same in Git Bash and PowerShell.

Update `.env` for local offline convention operation:

1. Database and security:
- `DATABASE_URL=postgresql://postgres:<postgres_password>@127.0.0.1:5432/boardgame_recommender`
- `NODE_ENV=production`
- `SECRET_KEY=<32+ char value>`

2. Convention guest mode:
- `CONVENTION_MODE=true`
- `CONVENTION_GUEST_ENABLED=true`

3. Image behavior (offline cache):
- `IMAGE_BACKEND=fly_local`
- `IMAGE_STORAGE_DIR=<absolute_windows_or_posix_path_to_repo>/backend/database/images`

4. CORS for kiosk browsers on local network:
- `CORS_ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000,http://<HOST_LAN_IP>:8000`

Load env values:

Git Bash:

```bash
set -a && source .env && set +a
```

PowerShell:

```powershell
Get-Content .env | ForEach-Object {
  if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
  $parts = $_ -split '=', 2
  if ($parts.Length -eq 2) { Set-Item -Path "Env:$($parts[0])" -Value $parts[1] }
}
```

## 6. Start Local Postgres (Docker)

Git Bash:

```bash
docker run --name boardgame-pg-local -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD="${POSTGRES_PASSWORD_LOCAL}" -e POSTGRES_DB=boardgame_recommender -p 5432:5432 -v bg_lib_pg_data:/var/lib/postgresql/data -d postgres:18.3
```

PowerShell:

```powershell
docker run --name boardgame-pg-local -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD="$env:POSTGRES_PASSWORD_LOCAL" -e POSTGRES_DB=boardgame_recommender -p 5432:5432 -v bg_lib_pg_data:/var/lib/postgresql/data -d postgres:18.3
```

If this step fails with a port-binding error, `5432` is already in use by another local Postgres instance.
Typical errors:

```text
Bind for 0.0.0.0:5432 failed: port is already allocated
```

```text
listen tcp 0.0.0.0:5432: bind: Only one usage of each socket address...
```

Fix:
1. Change Docker mapping to a free host port, for example `-p 5433:5432`.
2. Update `.env` `DATABASE_URL` host port to match, for example:
   `postgresql://postgres:<postgres_password>@127.0.0.1:5433/boardgame_recommender`.

Health check:

```bash
docker ps --filter "name=boardgame-pg-local"
```
This command is the same in Git Bash and PowerShell.

## 7. Initialize Schema

```bash
poetry run alembic -c backend/alembic.ini upgrade head
```
This command is the same in Git Bash and PowerShell.

## 8. Load Data Into Local Postgres

Choose one path.

Path A: Restore from SQL backup (fastest when available):

Git Bash:

```bash
cat /path/to/offline_backup.sql | docker exec -i boardgame-pg-local psql -U postgres -d boardgame_recommender
```

PowerShell:

```powershell
Get-Content C:\path\to\offline_backup.sql -Raw | docker exec -i boardgame-pg-local psql -U postgres -d boardgame_recommender
```

Path B: Re-import from processed CSV artifacts:

```bash
poetry run python backend/app/import_data.py --delete-existing
```
This command is the same in Git Bash and PowerShell.

Optional library import:

```bash
poetry run python backend/app/import_library_data.py --csv data/library/bg_lib_games_<timestamp>.csv --delete-existing
```
This command is the same in Git Bash and PowerShell.

## 9. Place Recommendation Artifacts

Ensure these files exist in `backend/database/`:
- `game_embeddings_<timestamp>.npz`
- `reverse_mappings_<timestamp>.json`
- `content_embeddings_<timestamp>.npz`
- `content_reverse_mappings_<timestamp>.json`
- `content_feature_mappings_<timestamp>.json`
- `content_embeddings_metadata_<timestamp>.json`

The app loads the latest timestamped files from this directory.

## 10. Place Image Cache

Ensure cached game images are present under:
- `backend/database/images/games/`

If thumbnails are available, include:
- `backend/database/images/thumbnails/`

## 11. Create Admin User

Git Bash:

```bash
printf '%s' '<strong-admin-password>' | poetry run python backend/app/main.py --username <admin_username> --password-stdin --admin
```

PowerShell:

```powershell
"<strong-admin-password>" | poetry run python backend/app/main.py --username <admin_username> --password-stdin --admin
```

## 12. Start the Local App Server

```bash
poetry run uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```
This command is the same in Git Bash and PowerShell.

This serves:
- API from `http://<host>:8000/api`
- built frontend from `http://<host>:8000/`

## 13. Allow LAN Access Through Windows Firewall

Run in an elevated PowerShell window:

```powershell
netsh advfirewall firewall add rule name="BG Library Local Kiosk 8000" dir=in action=allow protocol=TCP localport=8000
```

## 14. Connect Kiosk Devices

On each kiosk device browser:
1. Open `http://<HOST_LAN_IP>:8000/`
2. Open `http://<HOST_LAN_IP>:8000/kiosk/setup`
3. Log in as admin and enroll device
4. Confirm guest mode is active

## 15. Validation Checklist

Run from host machine:

```bash
curl -sS http://localhost:8000/api
```

```bash
curl -sS http://localhost:8000/api/version
```

```bash
curl -sS http://localhost:8000/api/recommendations/status
```

```bash
curl -sS "http://localhost:8000/api/recommendations/224517?limit=5"
```
These commands are the same in Git Bash and PowerShell.

Expected:
- API returns 200 responses.
- Recommendations status indicates collaborative/content artifacts available.
- Recommendation endpoint returns results.

## 16. Convention-Day Cutover Pattern

If Fly/internet is unstable:
1. Start local Postgres container.
2. Start local app server.
3. Point kiosk devices to `http://<HOST_LAN_IP>:8000`.
4. Verify one recommendation call and one image-heavy game details view.

## 17. Known Offline Limitations

1. Any image not already cached locally may fail to load offline.
2. Any workflow requiring new BGG fetches will fail without internet.
3. This setup is single-host; prepare spare hardware if high availability is required.
