#!/usr/bin/env bash
# Generate apps/api/.env for an IP-only staging deployment.
#
# Usage:
#   ./ops/bootstrap_env.sh <public-ip>
#
# Produces apps/api/.env with strong random secrets, MinIO endpoints
# pointing to the in-compose service, and cookies set to non-secure so
# they work over plain HTTP. Safe to re-run — overwrites.

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <public-ip-or-host>"
  exit 1
fi

BASE="$1"
TARGET="apps/api/.env"

PEPPER=$(openssl rand -base64 32)
AUDIT=$(openssl rand -base64 32)
SESSION=$(openssl rand -base64 32)
PEM=$(openssl genpkey -algorithm ed25519 2>/dev/null | awk '{printf "%s\\n",$0}')

mkdir -p "$(dirname "$TARGET")"
cat > "$TARGET" <<ENVEOF
ENV=staging
LOG_LEVEL=INFO
BASE_URL=http://${BASE}
FRONTEND_BASE_URL=http://${BASE}
ALLOWED_ORIGINS=["http://${BASE}"]
DATABASE_URL=postgresql+asyncpg://ndsc:ndsc@db:5432/ndsc
REDIS_URL=redis://redis:6379/0
R2_ENDPOINT_URL=http://minio:9000
R2_REGION=us-east-1
R2_ACCESS_KEY_ID=devkey
R2_SECRET_ACCESS_KEY=devsecret
R2_HOT_BUCKET=ndsc-hot
R2_COLD_BUCKET=ndsc-cold
AUTH_PASSWORD_PEPPER=${PEPPER}
AUDIT_HMAC_KEY=${AUDIT}
SESSION_SIGNING_KEY=${SESSION}
CERT_ED25519_PRIVATE_KEY_PEM="${PEM}"
CLAMAV_HOST=clamav
CLAMAV_PORT=3310
COOKIE_SECURE=false
COOKIE_DOMAIN=
ENVEOF

chmod 600 "$TARGET"
echo "wrote $TARGET ($(wc -l < "$TARGET") lines)"
