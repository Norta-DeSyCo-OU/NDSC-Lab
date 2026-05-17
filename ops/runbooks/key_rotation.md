# Runbook — Rotate Ed25519 cert signing key

Implements FR-CERT-001 multi-key verification window.

## Steps

```bash
# 1. Generate new keypair (off-server, offline machine preferred).
python -c "from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as P; from cryptography.hazmat.primitives import serialization as s; print(P.generate().private_bytes(encoding=s.Encoding.PEM, format=s.PrivateFormat.PKCS8, encryption_algorithm=s.NoEncryption()).decode())" > new_key.pem

# 2. Pick a new key_id (e.g., k2).

# 3. Add the new active key to signing_keys (one row).
docker compose exec db psql -U ndsc -d ndsc -c "
  INSERT INTO signing_keys (id, key_id, algo, public_key_pem, private_key_ref, state, created_at)
  VALUES (gen_random_uuid()::text, 'k2', 'ed25519', '<paste pub PEM>', 'env:CERT_ED25519_PRIVATE_KEY_PEM', 'active', now());
"

# 4. Mark the old key as retired (verification still accepts it).
docker compose exec db psql -U ndsc -d ndsc -c "
  UPDATE signing_keys SET state='retired', retired_at=now() WHERE key_id='k1';
"

# 5. Update env on the app container:
#    CERT_ED25519_PRIVATE_KEY_PEM = (contents of new_key.pem)
#    CERT_ED25519_KEY_ID = k2
docker compose up -d --no-deps --force-recreate api

# 6. Confirm.
curl -s http://localhost/.well-known/ndsc-cert-pubkey.json | jq

# 7. Wipe the new_key.pem from disk; private key now lives only in env + operator's offsite backup.
shred -u new_key.pem
```

## Verification window

- New certs issued from now on are signed with `k2`.
- Old certs continue to verify because the verification path consults the row for each cert's `signing_key_id` (which still has its `public_key_pem`).
