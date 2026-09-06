#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  api_key="$(openssl rand -hex 32)"
  postgres_password="$(openssl rand -hex 24)"
  sed -e "s/replace-at-startup/${api_key}/" -e "s/replace-postgres-password/${postgres_password}/g" .env.example > .env
  chmod 600 .env
  echo "Evolution API credentials generated in infra/evolution/.env"
fi

docker compose up -d
echo "Evolution API available at http://127.0.0.1:8080"
