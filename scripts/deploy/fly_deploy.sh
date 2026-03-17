#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/deploy/fly_deploy.sh prod
  scripts/deploy/fly_deploy.sh dev
  scripts/deploy/fly_deploy.sh prod --config fly.convention.toml
  scripts/deploy/fly_deploy.sh dev --config fly.convention.dev.toml

This wraps fly deploy and injects build metadata so /api/version reports:
  - git_sha
  - build_timestamp
EOF
}

environment=""
config_override=""

while [ $# -gt 0 ]; do
  case "$1" in
    prod|dev)
      if [ -n "${environment}" ]; then
        echo "Error: environment specified more than once."
        usage
        exit 1
      fi
      environment="$1"
      shift
      ;;
    --config|-c)
      if [ $# -lt 2 ]; then
        echo "Error: --config requires a file path."
        usage
        exit 1
      fi
      config_override="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Error: unknown argument '$1'."
      usage
      exit 1
      ;;
  esac
done

if [ -z "${environment}" ]; then
  echo "Error: environment must be 'dev' or 'prod'."
  usage
  exit 1
fi

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

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

if [ -n "${config_override}" ]; then
  config_file="${config_override}"
fi

if [ ! -f "${config_file}" ]; then
  echo "Error: config file '${config_file}' does not exist."
  exit 1
fi

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

echo "Deploying ${app_name} using config=${config_file} with git_sha=${git_sha} build_timestamp=${build_timestamp}"

fly deploy \
  -c "${config_file}" \
  -a "${app_name}" \
  --build-arg "GIT_SHA=${git_sha}" \
  --build-arg "BUILD_TIMESTAMP=${build_timestamp}"
