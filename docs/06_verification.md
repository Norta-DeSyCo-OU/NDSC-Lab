<!-- markdownlint-disable MD013 MD024 -->
# 06 — Plan Verification & Audit

| Project | NDSC Lab |
|---|---|
| Document version | 1.0 |
| Date | 2026-05-13 |
| Phase | 5 — Plan verification & audit |
| Inputs | All previous phase docs v1.0 |

> Goal: find design and plan defects on paper, not in production. Output is the defect list in §7 — every Critical/High defect is then resolved in Phase 6 (`05_implementation_plan.md` Change log + delta to the affected doc).

---

## 1. Traceability matrix

### 1.1 FR → architecture component → slice → test layer

(Truncated to one row per FR group for readability; per-ID matrix lives in code as a CSV regenerated from frontmatter on each requirement.)

| FR / NFR | Arch element | Slice(s) | Test(s) |
|---|---|---|---|
| FR-AUTH-001..009 | Identity context; Argon2 + pepper; Redis sessions; OIDC | S-10, S-11, S-12, S-13, S-14, S-15 | unit (hashing, lockout); integration (signup→verify→login full flow); e2e (browser) |
| FR-ROLE-001..006 | Identity policy module; role_transitions | S-20, S-21, S-22 | unit per policy rule; integration; e2e |
| FR-PROFILE-001..005 | Curation context; contributor_profiles; profile_sections | S-23, S-24 | integration; e2e |
| FR-CONTENT-001..011 | Content context; state machine | S-30, S-35, S-36 | unit (state machine); integration; e2e |
| FR-VIDEO-001..005 | Content + R2 + ClamAV | S-32, S-33, S-34 | integration (with minio + clamav stub); e2e |
| FR-ART-001..005 | TipTap + Markdown + KaTeX + Shiki + nh3 sanitize | S-31 | unit (sanitization fuzz); integration |
| FR-TM-001..003 | R2 + quota trigger | S-32 | integration |
| FR-COL-001..004 | Curation; UserCourseProgress | S-50, S-51, S-52 | integration |
| FR-CERT-001..006 | Certification; KeyStore; PDF + Ed25519 | S-53..57 | unit (sign/verify); integration; e2e |
| FR-COM-001..004 | Comments | S-45 | integration; e2e |
| FR-VIEW-001..007 | Analytics; Redis dedup; aggregator | S-43, S-44 | unit (dedup, threshold); load |
| FR-SEARCH-001..003 | Postgres FTS | S-41 | unit (query); load |
| FR-WS-001..004 | Workshops | S-60 | integration; e2e |
| FR-ADMIN-001..010 | Admin & Audit | S-61..67, S-37 | integration; e2e |
| FR-LEG-001..005 | Legal & Privacy | S-70..73 | integration |
| NFR-PERF-* | CDN + FTS index + range streaming | S-40, S-41, S-87 | k6 load + synthetic monitor |
| NFR-AVAIL-* | Backups + monitor + alerts | S-80 | restore drill |
| NFR-SEC-* | Argon2 + CSP + CSRF + ClamAV + WAF + rate-limit + audit-chain | S-81, S-83, S-85, S-84 | unit, integration, ZAP DAST, manual review |
| NFR-PRIV-* | GDPR + EU residency + erasure + export | S-72, S-73, infra (Hetzner EU + R2 EU jurisdictional) | manual audit |
| NFR-A11Y-* | UI tokens + axe + manual | S-86 | axe + screen-reader |
| NFR-UX-* | Tailwind tokens + themes | S-04, S-67 | visual review |
| NFR-OBS-* | Prom + Grafana + GlitchTip + uptime monitor + alerts | S-07, S-80 | synthetic monitor |
| NFR-MAINT-* | Docker compose + Alembic + CI gates + runbooks | M0, all | CI evidence |

### 1.2 Reverse coverage

Reverse pass executed: every component and slice traces forward to ≥ 1 requirement; every requirement traces back to ≥ 1 slice + ≥ 1 test layer. **No orphan requirements, no orphan slices.**

---

## 2. Threat model (STRIDE per protocol)

Notation: **S**poof **T**amper **R**epudiate **I**nfo-disclose **D**oS **E**oP. For each: threat → mitigation → residual.

### 2.1 P-SIGNUP

| ID | Threat | Cat | Mitigation | Residual |
|---|---|---|---|---|
| T-S1 | Account-enumeration via signup response timing | I | Constant-time response shape; silent success; rate-limit | Low — timing on Argon2 dominates |
| T-S2 | Mass account creation (bots) | D | CF managed challenge; rate-limit /signup 10/IP/h; email verify required | Low |
| T-S3 | CSRF on signup | T | CSRF token + SameSite cookie | Low |
| T-S4 | Verify-link replay | T | Single-use token + DB consumed flag; HMAC w/ exp | Low |
| T-S5 | Weak password | I | HIBP check + min 12 chars + Argon2id | Low |
| T-S6 | Underage signup | R | Age confirmation logged; per ToS user attestation | Low — legal residual accepted |

### 2.2 P-LOGIN

| ID | Threat | Cat | Mitigation | Residual |
|---|---|---|---|---|
| T-L1 | Brute force passwords | I | Argon2id, lockout (FR-AUTH-007), HIBP enforced | Low |
| T-L2 | Credential stuffing | I | HIBP on set; per-account + per-IP lockout; CF Bot Fight Mode | Medium — accept; MFA deferred (CON-008) |
| T-L3 | Session fixation | E | Server-side opaque sid; new sid on auth | Low |
| T-L4 | Session theft via XSS | E | Strict CSP + HTTPOnly + SameSite=Lax; nonce-based inline scripts | Low |
| T-L5 | Session theft via network | I | TLS 1.2+, HSTS preload | Low |
| T-L6 | Forgot-pwd token replay | T | Single-use, 1 h TTL, single email per request | Low |

### 2.3 P-OAUTH

| ID | Threat | Cat | Mitigation | Residual |
|---|---|---|---|---|
| T-O1 | OAuth state CSRF | T | Random state, signed cookie, validated | Low |
| T-O2 | PKCE bypass | E | S256 code_verifier mandatory | Low |
| T-O3 | id_token forgery | S | Verify signature, iss, aud, exp, nonce | Low |
| T-O4 | Account takeover via OAuth email collision | E | Linking step requires confirmation by existing user | Low |

### 2.4 P-UPLOAD

| ID | Threat | Cat | Mitigation | Residual |
|---|---|---|---|---|
| T-U1 | Malware upload | T,I | ClamAV scan; quarantine; admin notification | Low |
| T-U2 | Bypass scan via direct R2 PUT | T | R2 keys not exposed to client; presigned multipart URLs limited to designated keys | Low |
| T-U3 | Quota exhaustion | D | Per-user quota enforced on commit | Low |
| T-U4 | Unsafe file types (HTML/SVG XSS) | I | MIME allowlist; serve with `Content-Disposition: attachment` + `X-Content-Type-Options: nosniff`; SVG sanitized | Low |
| T-U5 | Path-traversal / R2 key clobber | I | Server-generated keys; user input only in metadata | Low |
| T-U6 | Slow upload DoS | D | tus chunk timeout; per-upload size cap | Low |

### 2.5 P-COMMENT-MOD

| ID | Threat | Cat | Mitigation | Residual |
|---|---|---|---|---|
| T-C1 | XSS via Markdown | T,I | nh3 sanitize allowlist; no raw HTML; CSP | Low |
| T-C2 | Spam | D | Rate-limit + admin moderation; report queue | Medium — accept; Akismet later |
| T-C3 | Comment forgery | S | Auth required; CSRF | Low |

### 2.6 P-VIEW

| ID | Threat | Cat | Mitigation | Residual |
|---|---|---|---|---|
| T-V1 | Inflation by client | T | Server-side threshold validation; dedup window; rate-limit; aggregator dedup | Medium — analytics-only blast radius |
| T-V2 | PII leak in events | I | No body content stored; only IDs + minimal metadata; retention 90 d | Low |

### 2.7 P-CERT

| ID | Threat | Cat | Mitigation | Residual |
|---|---|---|---|---|
| T-Cert1 | Forged certificate | S | Ed25519 signature; public verification | Low |
| T-Cert2 | Replay/reuse of a revoked cert | T | Verification consults `certificates.revoked_at` | Low |
| T-Cert3 | Issuer key compromise | E | Key in env, never on disk in containers; rotation supported; multi-key verification window; offsite backup of public keys | Medium — accept; HSM future |
| T-Cert4 | Privilege escalation to issue certs | E | `cert.issue` policy admin-only; audit-logged | Low |

### 2.8 P-ERASE

| ID | Threat | Cat | Mitigation | Residual |
|---|---|---|---|---|
| T-E1 | Tricked erasure by attacker w/ session | T | Password re-confirm required; email confirmation; 7-day grace allowing cancellation | Low |
| T-E2 | Incomplete erasure leaves PII | R | Worker validates emptiness of user-owned blobs; logs success only on full execution; integrity test in CI | Low |

### 2.9 P-BACKUP

| ID | Threat | Cat | Mitigation | Residual |
|---|---|---|---|---|
| T-B1 | Backup key exfil | I | age recipient pubkey only on host; private offsite; backups encrypted at rest | Low |
| T-B2 | Prod app deletes its own backups | T | Cold-bucket IAM write-only from prod; delete creds only on operator machine | Low |
| T-B3 | Untested backups | R | Quarterly restore drill (S-80, S-88) | Low |

### 2.10 P-DEPLOY

| ID | Threat | Cat | Mitigation | Residual |
|---|---|---|---|---|
| T-D1 | Supply-chain compromise (dep) | T | pip-audit + npm audit + Renovate weekly + lockfiles + Trivy | Medium — industry baseline |
| T-D2 | Secret leak in CI logs | I | gitleaks gate + GH masked secrets; CI logs scrubbed | Low |
| T-D3 | Image tampering | T | Image digests pinned at deploy; ghcr.io with OIDC-bound push | Low |

### 2.11 Authorization (cross-cutting)

| ID | Threat | Cat | Mitigation | Residual |
|---|---|---|---|---|
| T-A1 | IDOR (e.g., GET /items/{id} as User → draft) | E | Policy checks on every mutating + read of non-published; resource-scope filter on queries | Low |
| T-A2 | Confused deputy: admin actions chained through user request | E | Centralized policy with explicit-deny default; integration tests per role × action | Low |
| T-A3 | SSRF via embed/oEmbed | I | Allowlist of hosts; no arbitrary URL fetches with user-controlled scheme | Low |
| T-A4 | SQL injection | T,I | SQLAlchemy parameter binding everywhere; no string-interp queries; Semgrep ruleset blocks raw cursor.execute with f-string | Low |
| T-A5 | Template injection | T | Jinja autoescape on; no `Markup()` from user input | Low |
| T-A6 | Open redirect | T | Allowlist of relative paths only for post-login redirect | Low |

---

## 3. Security property statements (informal "formal")

For high-stakes invariants, expressed in plain English; can be formalized later in TLA+/Alloy if needed.

**SP-1 (Role monotonicity within a request):** No request handler may upgrade `actor.role` mid-request.

**SP-2 (Write authorization):** ∀ mutating endpoint `e`, ∀ request `r` reaching `e` ⇒ `authorize(r.actor, e.action, r.target) = ALLOW`. *Enforced by middleware that refuses to dispatch a handler without the marker decorator that records the action; integration tests assert default-deny.*

**SP-3 (Audit completeness):** ∀ action in the set `AUDITED ⊇ {item.publish, item.delete, item.unpublish, user.role.grant, user.role.revoke, user.ban, user.unban, cert.issue, cert.revoke, takedown.decide, comment.delete, platform_setting.write, contributor_tunable.write}`: a row is appended to `audit_log` within the same DB transaction as the action.

**SP-4 (Audit append-only):** No SQL role except `migrate_owner` may UPDATE or DELETE `audit_log`. *Enforced via PG GRANT.*

**SP-5 (Erasure terminality):** After successful execution of an erasure request, no row in any table contains the erased user's `email` plaintext; `audit_log.actor_user_id` columns referencing the user are pseudonymized.

**SP-6 (Cert authenticity):** ∀ cert `c` returned by `/verify/<id>`, signature verifies under at least one key in `signing_keys` whose `key_id == c.signing_key_id`.

**SP-7 (Origin firewall):** No path to origin VPS port 443 from non-Cloudflare IPs. *Enforced by Hetzner cloud firewall + reverse-DNS sanity in Caddy.*

**SP-8 (PII residency):** All persistent user-record storage is in EU jurisdictions (Hetzner Falkenstein/Nuremberg DC + Cloudflare R2 with EU jurisdictional restriction).

These statements are listed in `ops/security_invariants.md` and are checked manually each release; CI integration tests cover SP-2, SP-3, SP-4 mechanically.

---

## 4. Scalability analysis

**Workload assumption (Y0):** 1000 users, 100 concurrent at peak, 50 RPS, 10 video starts/min, 5k view events/day.

**Workload growth (Y2):** 10× users = 10k users, 1000 concurrent peak, 500 RPS, 100 video starts/min, 50k view events/day.

| Hot path | Y0 budget | Y2 implication |
|---|---|---|
| Public item page | CDN cache hit ≥ 80% expected; origin ~10 RPS | Origin still ~100 RPS at Y2 — single FastAPI uvicorn worker handles. |
| Search | 5 RPS, FTS p95 < 100 ms at Y0 | At 50k items + 50 RPS, GIN holds; if articles ≥ 200k revisit with OpenSearch. |
| View events | 5k/d ≈ 0.06 RPS | 50k/d ≈ 0.6 RPS — trivial. |
| Aggregation | 5k rows/d | 50k/d still completes in seconds nightly. |
| Argon2 logins | Y0: 100 logins/h ≈ 0.03 RPS at ~100 ms CPU each | Y2: 1k/h ≈ 0.3 RPS — fine on 2 vCPU. |
| Video stream | R2 → CF (free egress) → client | unchanged — CF absorbs. |

**Little's Law sanity check:** L = λ × W. At 50 RPS with W=80 ms, L=4 in-flight requests. Far below uvicorn worker concurrency.

**Single points of failure (and acceptance):**

| SPoF | Impact | Acceptance |
|---|---|---|
| Single VPS host | 100% downtime if host dies | Accepted at 99% target; recovery via S-80 restore drill within RTO 4 h. |
| Single Redis | Sessions lost on crash → user re-login; queue lost → retried jobs idempotent | Accept; AOF + RDB on. |
| Cloudflare account | Edge down → degraded mode (direct origin via emergency DNS) | Accept; runbook. |
| Resend | Auth emails delayed | Accept; degrade: show "didn't get email? contact admin"; fallback SMTP not in v1. |

**No design changes required for 10× growth** beyond box upsize (CCX23/CCX33 ≤ 30 EUR/mo) and possibly horizontal app split. Single PG remains adequate (vertical scaling room).

---

## 5. FMEA — Failure Mode and Effects

| Component | Failure mode | Effect | Detection | Mitigation |
|---|---|---|---|---|
| Postgres | OOM | All writes fail | Prom alert | Restart; tune shared_buffers; daily backup ensures recovery |
| Redis | OOM / loss | Sessions invalid; queue jobs lost | Prom alert | Re-login required; jobs idempotent + retried |
| R2 | Outage | New uploads fail; existing items unreachable | Healthcheck `/readyz` | Degraded read-only mode; queue uploads in Redis until back |
| ClamAV | Definitions stale | False clean | freshclam log + age check | Block publication until age < 36 h |
| Resend | Outage | Auth emails delayed | Webhook events not arriving | Retry queue; in-app banner asks user to retry later |
| CF edge | Outage | All traffic affected | uptime monitor | Emergency DNS to bypass CF (rare; document) |
| Google OIDC | Outage | OAuth login down | Detected on login failure | Email/password still works |
| Cert signing key | Loss | Cannot issue; existing still verify | Manual | Restore from offsite operator-held private key copy |
| Backup bucket | Lost | Recovery impossible | Daily verify job (download last + age decrypt test) | Multi-region R2 + monthly export to second cold provider (optional add-on) |

---

## 6. Cost projection (10× scale)

| Item | Y0 (EUR/mo) | Y2 10× (EUR/mo) |
|---|---|---|
| Hetzner | 7 | 25 (CCX23/33) |
| R2 storage hot | 3 | 15 |
| R2 storage cold | 1 | 5 |
| R2 ops | <1 | 2 |
| Domain | 1 | 1 |
| Resend | 0 | 0 or 20 (paid tier ~20€) |
| Cloudflare | 0 | 0 |
| GlitchTip | 0 | 0 |
| **Total** | **~12** | **~50–70** |

Both within `CON-001` (80–100 EUR ceiling).

---

## 7. Plan defect list (output of this phase)

Each defect: ID · severity (Critical/High/Medium/Low) · description · proposed remedy · target slice or doc edit.

| ID | Sev | Description | Remedy | Target |
|---|---|---|---|---|
| D-01 | High | OAuth-only users have no recoverable email pathway if they lose Google access | Provide self-serve "set password" flow for OAuth-only accounts, gated by a fresh OAuth login | Amend `FR-AUTH-005` AC; add S-13.1 |
| D-02 | High | Email re-binding (user changes email) wasn't specified in Phase 1 | Add `FR-AUTH-010` (Change email with new-address verification + audit) | `01_requirements.md` change-request |
| D-03 | High | Article and profile slugs case-collide with reserved slugs only for `contributor_profiles`; items also need a global slug reservation per-author | Add `slug_reserved` enforcement also on item slugs per-author and on global routes | `03_data_model.md` note |
| D-04 | High | `attachments.role='video_primary'` for `video_kind='hosted'` but enum currently missing `video_thumbnail` for embed cover override | Add `video_thumbnail` to attachment_role enum | `03_data_model.md` |
| D-05 | High | View event endpoint can be abused as an open-redirect to inflate counts; need stricter origin check + sample rate-limit | Add `Origin` check + RL 30/min/user on view events | `FR-VIEW-001` AC |
| D-06 | High | Audit log retention default 365 d conflicts with right-to-erasure 30 d cap for PII fields in audit entries | Distinguish: audit entries retained 365 d but actor PII pseudonymized at erasure (SP-5 already implies this) — make explicit in `FR-LEG-004` AC | requirements |
| D-07 | Medium | No mechanism for Contributor to designate a *successor* on revocation/erasure if collaborators want to keep content visible | Explicitly: revoked contributor's content is admin's call (FR-ROLE-005); add admin option "reassign authorship to NDSC house account" | `FR-ROLE-005` AC clarification |
| D-08 | Medium | "Self-revoke contributor" + "delete content" combined with hosted video implies bulk R2 delete + CF cache purge — needs idempotent multi-step job | Add S-72.1 job spec | `05_implementation_plan.md` |
| D-09 | Medium | Embed video provider's privacy implications (YouTube cookies) not addressed in cookie consent | Use "click-to-play" placeholder until user consents to third-party cookies | `FR-LEG-003` AC; S-33 |
| D-10 | Medium | Search across drafts must NOT include drafts for non-author users | Query filter `state='published' OR author_id=:me OR role='admin'` enforced via repository | S-41 unit test |
| D-11 | Medium | Workshop with no recording yet but past date — admin queue should show as "missing recording" | Add admin queue entry kind `workshop.recording_missing` | S-60 |
| D-12 | Medium | Comments thread on tombstoned items should be archived but not visible | Hide comments when parent item is tombstoned | S-45 |
| D-13 | Medium | Right-to-erasure of a Contributor needs to handle outstanding cert recipients — certs survive (data about a different person) but issuer info must redact admin identity if admin themselves are erased | Issued admin id pseudonymized after erasure; cert verification page shows "Issued by NDSC Lab (admin record redacted)" | SP-5 wording; `FR-CERT-002` AC |
| D-14 | Medium | Cookie consent banner needed before *any* analytics event including in-house view tracking; if user denies analytics, view events are NOT recorded | Make per-user view tracking gated on `cookie_consents.analytics=true` | `FR-VIEW-001` AC; `FR-LEG-003` |
| D-15 | Medium | NFR-SEC-014 audit-chain HMAC chain breaks on legitimate pseudonymization (erasure mutates rows) | Replace HMAC-of-row with HMAC-of-canonical-non-PII-projection; pseudonymization rewrites only PII columns leaving the canonical projection intact | `02_architecture.md` §4.3 |
| D-16 | Low | Tags merge UNIQUE conflict when source tag was on item already having dest tag | Use `INSERT ... ON CONFLICT DO NOTHING; DELETE source rows` | S-37 |
| D-17 | Low | `daily_*_aggregates` need backfill if aggregator job is missed | Add idempotent reaggregate window of 7 days | S-43 |
| D-18 | Low | Profile photo upload missing rate-limit | Add 1 upload/min/user | S-23 |
| D-19 | Low | Forgot-password endpoint can be used to time-side-channel valid emails (Argon2 dominates but not always) | Always perform a dummy Argon2 verify even when account not found | S-12 |
| D-20 | Low | Cert verification of revoked + tampered PDF: order of checks should be revoked first to prevent enumeration via timing | Check revoked before sig verify | S-55 |

**Severity acceptance:** Critical: 0. High: 6 — all addressed in Phase 6. Medium/Low: addressed via slice amendments.

---

## 8. Verification conclusion

Design is suitable to meet requirements once the defect list §7 is applied. No fundamental rework required; Phase 6 is a delta-only revision.

---

## 9. Change log

| Date | Change |
|---|---|
| 2026-05-13 | v1.0. |
