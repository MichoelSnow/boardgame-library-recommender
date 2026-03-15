#!/usr/bin/env bash
set -euo pipefail

# Generate a complete deployment-oriented env file section set.
# - Writes predictable, sectioned keys.
# - Replaces managed keys atomically (no duplicate stale entries).
# - Ensures private permissions on target file.
#
# Usage:
#   bash scripts/deploy/generate_env_secrets.sh .env
# Optional:
#   bash scripts/deploy/generate_env_secrets.sh .env my-unique-prefix
#   APP_PREFIX=my-unique-prefix bash scripts/deploy/generate_env_secrets.sh .env

OUT_FILE="${1:-.env}"
PREFIX_ARG="${2:-}"

if ! command -v openssl >/dev/null 2>&1; then
  echo "Error: openssl is required but not found in PATH." >&2
  exit 1
fi

sanitize() {
  tr '[:upper:]' '[:lower:]' \
    | tr -cd 'a-z0-9-' \
    | sed -E 's/^-+//; s/-+$//; s/-+/-/g'
}

gen_secret() {
  openssl rand -base64 72 | tr -dc 'A-Za-z0-9' | head -c 48
  printf '\n'
}

rewrite_fly_app_name() {
  local file_path="$1"
  local app_name="$2"
  if [ ! -f "${file_path}" ]; then
    return 0
  fi

  local dir base tmp
  dir="$(dirname "${file_path}")"
  base="$(basename "${file_path}")"
  tmp="$(mktemp "${dir}/.${base}.tmp.XXXXXX")"
  awk -v new_app="${app_name}" '
    BEGIN { replaced=0 }
    /^app[[:space:]]*=[[:space:]]*["\x27][^"\x27]+["\x27][[:space:]]*$/ && replaced==0 {
      printf "app = \x27%s\x27\n", new_app
      replaced=1
      next
    }
    { print }
  ' "${file_path}" > "${tmp}"
  mv "${tmp}" "${file_path}"
}

rewrite_workflow_deploy_app_name() {
  local file_path="$1"
  local app_name="$2"
  if [ ! -f "${file_path}" ]; then
    return 0
  fi

  local dir base tmp
  dir="$(dirname "${file_path}")"
  base="$(basename "${file_path}")"
  tmp="$(mktemp "${dir}/.${base}.tmp.XXXXXX")"
  awk -v new_app="${app_name}" '
    BEGIN { replaced=0 }
    /^[[:space:]]+-a[[:space:]]+.*\\[[:space:]]*$/ && replaced==0 {
      printf "            -a \"%s\" \\\n", new_app
      replaced=1
      next
    }
    { print }
  ' "${file_path}" > "${tmp}"
  mv "${tmp}" "${file_path}"
}

default_prefix="$(printf '%s' "${USER:-bg-user}" | sanitize)"
if [ -z "${default_prefix}" ]; then
  default_prefix="bg-user"
fi
if [ -n "${PREFIX_ARG}" ]; then
  app_prefix_raw="${PREFIX_ARG}"
elif [ -n "${APP_PREFIX:-}" ]; then
  app_prefix_raw="${APP_PREFIX}"
else
  app_prefix_raw="${default_prefix}-bg"
fi
app_prefix="$(printf '%s' "${app_prefix_raw}" | sanitize)"
if [ -z "${app_prefix}" ]; then
  app_prefix="bg-app"
fi

FLY_APP_NAME_DEV="${app_prefix}-app-dev"
FLY_APP_NAME_PROD="${app_prefix}-app"
FLY_DB_APP_NAME_DEV="${app_prefix}-db-dev"
FLY_DB_APP_NAME_PROD="${app_prefix}-db"

POSTGRES_PASSWORD_LOCAL="$(gen_secret)"
POSTGRES_PASSWORD_DEV="$(gen_secret)"
POSTGRES_PASSWORD_PROD="$(gen_secret)"
SECRET_KEY="$(gen_secret)"
SECRET_KEY_DEV="$(gen_secret)"
SECRET_KEY_PROD="$(gen_secret)"

umask 077
touch "${OUT_FILE}"
chmod 600 "${OUT_FILE}"

tmp_file="$(mktemp)"

awk '
  BEGIN {
    skip["DATABASE_PATH"]=1
    skip["POSTGRES_USER"]=1
    skip["POSTGRES_DB"]=1
    skip["POSTGRES_HOST_LOCAL"]=1
    skip["POSTGRES_PORT_LOCAL"]=1
    skip["POSTGRES_PASSWORD_LOCAL"]=1
    skip["POSTGRES_PASSWORD_DEV"]=1
    skip["POSTGRES_PASSWORD_PROD"]=1
    skip["SECRET_KEY"]=1
    skip["SECRET_KEY_DEV"]=1
    skip["SECRET_KEY_PROD"]=1
    skip["FLY_REGION"]=1
    skip["FLY_APP_NAME_DEV"]=1
    skip["FLY_APP_NAME_PROD"]=1
    skip["FLY_DB_APP_NAME_DEV"]=1
    skip["FLY_DB_APP_NAME_PROD"]=1
    # Remove old naming variants if present.
    skip["LOCAL_POSTGRES_HOST"]=1
    skip["LOCAL_POSTGRES_PORT"]=1
    skip["LOCAL_POSTGRES_PASSWORD"]=1
  }
  /^# ===== (Core Local Runtime|Local Postgres|Fly Postgres \+ App Secrets|Fly App Naming \(must be globally unique on Fly.io\)) =====$/ {
    next
  }
  /^[A-Za-z_][A-Za-z0-9_]*=/ {
    split($0, parts, "=")
    if (parts[1] in skip) {
      next
    }
  }
  { print }
' "${OUT_FILE}" > "${tmp_file}"

{
  printf '# ===== Core Local Runtime =====\n'
  printf 'DATABASE_PATH=backend/database/boardgames.db\n'
  printf 'SECRET_KEY=%s\n' "${SECRET_KEY}"

  printf '\n'
  printf '# ===== Local Postgres =====\n'
  printf 'POSTGRES_USER=postgres\n'
  printf 'POSTGRES_DB=boardgame_recommender\n'
  printf 'POSTGRES_HOST_LOCAL=127.0.0.1\n'
  printf 'POSTGRES_PORT_LOCAL=5432\n'
  printf 'POSTGRES_PASSWORD_LOCAL=%s\n' "${POSTGRES_PASSWORD_LOCAL}"

  printf '\n'
  printf '# ===== Fly Postgres + App Secrets =====\n'
  printf 'POSTGRES_PASSWORD_DEV=%s\n' "${POSTGRES_PASSWORD_DEV}"
  printf 'POSTGRES_PASSWORD_PROD=%s\n' "${POSTGRES_PASSWORD_PROD}"
  printf 'SECRET_KEY_DEV=%s\n' "${SECRET_KEY_DEV}"
  printf 'SECRET_KEY_PROD=%s\n' "${SECRET_KEY_PROD}"

  printf '\n'
  printf '# ===== Fly App Naming (must be globally unique on Fly.io) =====\n'
  printf 'FLY_REGION=iad\n'
  printf 'FLY_APP_NAME_DEV=%s\n' "${FLY_APP_NAME_DEV}"
  printf 'FLY_APP_NAME_PROD=%s\n' "${FLY_APP_NAME_PROD}"
  printf 'FLY_DB_APP_NAME_DEV=%s\n' "${FLY_DB_APP_NAME_DEV}"
  printf 'FLY_DB_APP_NAME_PROD=%s\n' "${FLY_DB_APP_NAME_PROD}"
} >> "${tmp_file}"

normalized_file="$(mktemp)"
awk '
  BEGIN { seen=0; blank=0 }
  /^[[:space:]]*$/ {
    if (!seen) next
    if (blank) next
    blank=1
    print ""
    next
  }
  {
    seen=1
    blank=0
    print
  }
' "${tmp_file}" > "${normalized_file}"

mv "${normalized_file}" "${tmp_file}"
mv "${tmp_file}" "${OUT_FILE}"
chmod 600 "${OUT_FILE}"

# Keep Fly app config names aligned with generated env values.
rewrite_fly_app_name "fly.dev.toml" "${FLY_APP_NAME_DEV}"
rewrite_fly_app_name "fly.toml" "${FLY_APP_NAME_PROD}"
rewrite_fly_app_name "fly.db.dev.toml" "${FLY_DB_APP_NAME_DEV}"
rewrite_fly_app_name "fly.db.prod.toml" "${FLY_DB_APP_NAME_PROD}"
rewrite_fly_app_name "fly.convention.toml" "${FLY_APP_NAME_PROD}"
rewrite_fly_app_name "fly.convention.dev.toml" "${FLY_APP_NAME_DEV}"
rewrite_workflow_deploy_app_name ".github/workflows/fly-deploy.yml" "${FLY_APP_NAME_DEV}"
rewrite_workflow_deploy_app_name ".github/workflows/fly-deploy-prod.yml" "${FLY_APP_NAME_PROD}"

echo "Wrote managed env keys to ${OUT_FILE}."
echo "Fly app names defaulted to:"
echo "  ${FLY_DB_APP_NAME_DEV}, ${FLY_DB_APP_NAME_PROD}, ${FLY_APP_NAME_DEV}, ${FLY_APP_NAME_PROD}"
echo "If needed, rerun with APP_PREFIX=<your-unique-prefix>."
echo "Updated app names in fly*.toml and .github/workflows/fly-deploy*.yml."
