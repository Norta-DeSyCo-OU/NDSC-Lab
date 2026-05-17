# Runbook — Restore from backup

Implements NFR-AVAIL-003/4 and exercised quarterly per S-80.

## Pre-flight

- Operator workstation has `age` private key for the backup recipient.
- Read-only credentials for the cold R2 bucket.

## Steps

```bash
# 1. Provision a fresh Hetzner Cloud server (CCX13+), Ubuntu 24.04.
hcloud server create --type ccx13 --image ubuntu-24.04 --name ndsc-restore --location fsn1

# 2. Bootstrap docker + ufw + tailscale (cloud-init or infra/host.yml playbook).

# 3. Pull latest backup.
aws --endpoint-url="$R2_ENDPOINT" s3 cp \
  "s3://$R2_COLD_BUCKET/pg/$(date +%Y/%m/)" ./bk/ --recursive
LATEST=$(ls -1 bk/*.age | sort | tail -1)

# 4. Decrypt.
age -d -i /path/to/age.key "$LATEST" > restore.dump

# 5. Restore.
docker compose up -d db
docker compose exec -T db dropdb -U ndsc ndsc || true
docker compose exec -T db createdb -U ndsc ndsc
cat restore.dump | docker compose exec -T db pg_restore -U ndsc -d ndsc --no-owner --no-acl

# 6. Start the rest of the stack.
docker compose up -d
docker compose exec api alembic upgrade head

# 7. Smoke tests.
curl -fsS http://localhost/healthz
curl -fsS http://localhost/api/csrf
```

## Acceptance

- `GET /healthz` returns 200.
- A known cert ID still verifies (`POST /verify/<id>` with its PDF) → `valid: true`.
- RTO measured from "step 1" to "step 7 pass" ≤ 4 h.
