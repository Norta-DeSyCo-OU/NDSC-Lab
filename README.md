# NDSC Lab

Production-ready academic content portal for Norta DeSyCo OU. Distributes video lectures, articles, and teaching material from the NDSC research-and-practice community.

> This is a Phase 7 scaffold built per the methodology in [`reference_waterfall_development_plan.md`](reference_waterfall_development_plan.md). The full design lives in [`docs/`](docs/), and the project charter and decision log are in [`CLAUDE.md`](CLAUDE.md). Read those first.

## Implemented in this scaffold

Foundation slices (M0) + most of identity (M1) + the certificate signing/verification core (M5 S-53..S-55):

- FastAPI backend with structured logging, Prometheus metrics, Sentry-compatible error monitoring, security headers, CSRF, sessions, Argon2id (with server-side pepper), HIBP k-anonymity, rate limiting (sliding window on Redis).
- Identity flows: signup → email verify → login → logout → forgot/reset password. Account-enumeration defenses (dummy Argon2; silent signup; rate limit).
- Central authorization policy module (default-deny) with unit tests.
- Tamper-evident audit log with HMAC chain over a canonical non-PII projection (D-15).
- Certificate issuance + Ed25519 signature embedding in PDF (WeasyPrint), public verification (`GET /verify/<id>` + `POST /verify/<id>` with PDF upload).
- Next.js 15 frontend with Tailwind 4, color tokens extracted from `nortadesyco.xyz`, dark/light toggle, signup/login/verify pages, cookie consent banner.
- Alembic initial migration covering all identity + audit + certification tables.
- Docker compose with Caddy, FastAPI, Next.js, Postgres, Redis, MinIO (R2 stand-in), ClamAV, Prometheus, Grafana.
- GitHub Actions CI: ruff, mypy, pytest, npm build, gitleaks, Semgrep, Trivy.

## What is scaffolded but not yet implemented

The remaining slices (S-2x..S-9x) are documented in [`docs/05_implementation_plan.md`](docs/05_implementation_plan.md). Each has a clear scope, acceptance criteria, and FR/NFR references. Notable gaps:

- Content authoring (TipTap editor, Markdown pipeline, attachments, drafts, review queue).
- Video upload (tus → R2 multipart, ClamAV scan, streaming).
- Comments, analytics dashboards, search.
- Course progress tracking, certificate auto-suggestion.
- Workshops UI.
- Admin panels.
- Legal pages, takedown queue, right-to-erasure execution job.
- OAuth (Google) endpoints.

## Run locally

```bash
# 1. Generate an Ed25519 keypair PEM for cert signing:
python -c "from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as P; from cryptography.hazmat.primitives import serialization as s; print(P.generate().private_bytes(encoding=s.Encoding.PEM, format=s.PrivateFormat.PKCS8, encryption_algorithm=s.NoEncryption()).decode())"

# 2. Copy env template and fill in secrets:
cp apps/api/.env.example apps/api/.env
# Paste the PEM into CERT_ED25519_PRIVATE_KEY_PEM (multiline OK)
# Generate random 32-byte values for AUTH_PASSWORD_PEPPER, AUDIT_HMAC_KEY, SESSION_SIGNING_KEY.

# 3. Boot the stack:
cd infra
docker compose up -d --build

# 4. Run migrations:
docker compose exec api alembic upgrade head

# Open: http://localhost  (Caddy → web)
# API:  http://localhost/api/healthz
```

## Run tests

```bash
cd apps/api
pip install -e ".[dev]"
pytest
```

## Deploy (Hetzner + Cloudflare + R2)

See `ops/runbooks/deploy.md` (TODO) and the architecture doc (`docs/02_architecture.md` §3).

## Project methodology

This project follows a waterfall lifecycle with one sanctioned backward pass between verification and implementation. See [`reference_waterfall_development_plan.md`](reference_waterfall_development_plan.md).

## License

Source code TBD; content distributed via the portal is licensed per content item (default CC-BY 4.0, contributor-overridable).
