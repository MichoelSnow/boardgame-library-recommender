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

environment="$1"

case "$environment" in
  prod)
    config_file="fly.toml"
    app_name="bg-lib-app"
    ;;
  dev)
    config_file="fly.dev.toml"
    app_name="bg-lib-app-dev"
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
