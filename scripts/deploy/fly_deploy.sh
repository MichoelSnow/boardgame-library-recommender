#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/deploy/fly_deploy.sh prod
  scripts/deploy/fly_deploy.sh dev

This wraps fly deploy and injects build metadata so /api/version reports:
  - git_sha
  - build_timestamp
EOF
}

if [ $# -ne 1 ]; then
  usage
  exit 1
fi

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

environment="$1"

require_var() {
  local name="$1"
  local value="${!name:-}"
  if [ -z "${value}" ]; then
    echo "Error: required env var ${name} is not set."
    exit 1
  fi
}

case "$environment" in
  prod)
    config_file="fly.toml"
    require_var "FLY_APP_NAME_PROD"
    app_name="${FLY_APP_NAME_PROD}"
    ;;
  dev)
    config_file="fly.dev.toml"
    require_var "FLY_APP_NAME_DEV"
    app_name="${FLY_APP_NAME_DEV}"
    ;;
  *)
    usage
    exit 1
    ;;
esac

if ! command -v fly >/dev/null 2>&1; then
  echo "Error: fly CLI is not installed or not on PATH."
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "Error: git is not installed or not on PATH."
  exit 1
fi

git_sha="$(git rev-parse HEAD)"
build_timestamp="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"

echo "Deploying ${app_name} with git_sha=${git_sha} build_timestamp=${build_timestamp}"

fly deploy \
  -c "${config_file}" \
  -a "${app_name}" \
  --build-arg "GIT_SHA=${git_sha}" \
  --build-arg "BUILD_TIMESTAMP=${build_timestamp}"
