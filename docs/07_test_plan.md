<!-- markdownlint-disable MD013 MD024 -->
# 07 — Test Plan & Validation

| Project | NDSC Lab |
|---|---|
| Document version | 1.0 |
| Date | 2026-05-13 |
| Phase | 8 — Testing & validation |
| Inputs | All previous phase docs |

> Every requirement (FR/NFR/CON) is mapped to at least one test layer. Pre-launch gate: all Critical/High defects from Phase 5 closed, every requirement signed off by sponsor (UAT) or explicitly waived.

---

## 1. Test layers

| Layer | Tooling | Scope |
|---|---|---|
| Unit | pytest, vitest | Pure logic: policy, sanitization, dedup math, signer, HMAC chain. |
| Integration | pytest + testcontainers (PG + Redis + MinIO + ClamAV) | API endpoints with real dependencies. |
| Contract | OpenAPI schema diff against prior version | Detect breaking API changes. |
| End-to-end | Playwright (headed in CI on Chromium + WebKit) | Every user-visible flow. |
| Accessibility | axe-core via Playwright + manual screen-reader pass (NVDA + VoiceOver) | WCAG 2.2 AA. |
| Security (SAST) | Semgrep + ruff S rules + gitleaks | CI gate on every PR. |
| Security (deps) | pip-audit + npm audit + Trivy | CI gate. |
| Security (DAST) | OWASP ZAP baseline | Nightly on staging. |
| Performance / load | k6 | Synthetic load on staging. |
| Chaos / failure | docker network partition + container kill | Quarterly drill. |
| Backup/restore | Manual runbook | Quarterly drill. |
| UAT | Sponsor scripted walkthrough | Per requirement. |

---

## 2. Requirement → test coverage (selected; full matrix in CSV)

| Req | Unit | Integration | E2E | Other |
|---|---|---|---|---|
| FR-AUTH-001 signup | `test_argon2.py`, `test_signup_validation` | full signup flow w/ email-stub | Playwright `signup.spec.ts` | DAST on `/auth/signup` |
| FR-AUTH-003 login | `test_argon2.py`, lockout unit | login + lockout integration | login.spec.ts | DAST |
| FR-AUTH-005 reset | token consume unit | full reset flow | reset.spec.ts | DAST |
| FR-AUTH-007 lockout | unit on counter math | integration with real Redis | — | — |
| FR-AUTH-008 age check | schema unit | — | signup form rejects unchecked age | — |
| FR-ROLE-* policy | `test_policy.py` per rule | per-role × per-endpoint sweep | admin promote contributor.spec.ts | — |
| FR-CONTENT state machine | unit on transitions | publish-without-clean-attachment rejected | author publishes; admin approves; cdn purges | — |
| FR-VIDEO-001 upload | tus unit | tus + R2 + ClamAV integration | upload-large-video.spec.ts | k6 upload load |
| FR-COM-001 comment | unit | rate-limit + sanitize integration | comment.spec.ts | XSS DAST cases |
| FR-VIEW-001 view event | unit dedup + threshold | end-to-end view counted across pageload | — | k6 view-event load |
| FR-VIEW-007 admin only | policy unit | integration: user 403 | — | — |
| FR-CERT-001..6 | `test_cert.py` sign/verify/tamper | issue + revoke + verify integration | issue-cert.spec.ts + verify.spec.ts | — |
| FR-LEG-004 erasure | unit on pseudonymization | full erasure flow + post-state check | settings.spec.ts | post-state PII grep |
| FR-LEG-005 export | unit on zip build | full export flow + zip contents | export.spec.ts | — |
| NFR-PERF-001 page load | — | — | Lighthouse CI | k6 |
| NFR-PERF-005 concurrency | — | — | — | k6 sustained 100 VUs |
| NFR-AVAIL-003 RPO | — | — | — | restore drill |
| NFR-AVAIL-004 RTO | — | — | — | restore drill |
| NFR-SEC-001 Argon2 | hash params unit | — | — | — |
| NFR-SEC-002 TLS | — | — | — | testssl.sh manual |
| NFR-SEC-003 CSP | — | header integration | E2E asserts CSP header | ZAP CSP rule |
| NFR-SEC-007 virus scan | unit on attach state machine | infected file rejected | upload-eicar.spec.ts | — |
| NFR-SEC-009 DDoS | — | — | — | curl from non-CF IP fails |
| NFR-SEC-010 rate limit | unit | integration sweep | — | k6 burst |
| NFR-SEC-014 audit chain | HMAC roll-forward unit + tamper test | integration: chain breaks after manual UPDATE | — | — |
| NFR-A11Y-001 WCAG 2.2 AA | — | — | axe on every page | screen-reader manual |
| NFR-MAINT-005 CI | — | — | — | green pipeline |

---

## 3. UAT script (sponsor sign-off)

For every numbered requirement, the sponsor runs:

1. Trigger described in AC.
2. Observe the AC outcomes.
3. Mark "passed" / "failed" / "waived" with comment.

UAT spreadsheet template generated from `01_requirements.md` (auto-gen). Stored in `ops/uat/uat_v1.csv` after launch.

---

## 4. Test results — current (Phase 7 scaffold)

| Suite | Status |
|---|---|
| Backend Python syntax (`ast.parse` on every file) | **PASS** (42/42 files OK) |
| Argon2 hash/verify roundtrip | scaffolded; runnable with `cd apps/api && pip install -e ".[dev]" && pytest tests/test_argon2.py` |
| Policy table — all roles × all actions | scaffolded; runnable as above |
| Certificate sign + verify + tamper detection | scaffolded; runnable as above |
| Frontend type-check | scaffolded; runnable with `cd apps/web && npm install && npm run type-check` |
| CI workflow (`.github/workflows/ci.yml`) | declared with gates: ruff, mypy, pytest, next build, gitleaks, Semgrep, Trivy |

---

## 5. Pre-launch checklist

- [ ] All Critical/High defects from `06_verification.md` closed.
- [ ] Backup restore drill executed; RTO < 4 h documented.
- [ ] Origin firewall verified (`curl` from non-CF IP fails).
- [ ] HSTS header present in prod responses; domain submitted to HSTS preload list.
- [ ] CSP report-only ⇒ enforced (no console errors on key pages).
- [ ] Cookie consent banner mandatory before any analytics event recorded.
- [ ] DKIM + SPF + DMARC validated for outbound email domain.
- [ ] axe-core: 0 critical issues on home, signup, login, item, profile, verify pages.
- [ ] k6 100 concurrent users: P95 < 800 ms, error rate < 0.1%.
- [ ] Sentry/GlitchTip wired; test exception captured.
- [ ] Prometheus + Grafana scraping API metrics; alert rules firing on synthetic 5xx.
- [ ] UptimeRobot monitor active on `/healthz`.
- [ ] Cert: issue + verify + revoke + tamper all green in integration.
- [ ] Right-to-erasure runbook tested end-to-end on a test account.
- [ ] Data export ZIP verified to include all user data.
- [ ] ToS + Privacy Policy reviewed by Norta DeSyCo OU counsel.
- [ ] DMCA contact + form live.
- [ ] DNS + TLS + Cloudflare WAF rules deployed.
- [ ] Rollback plan rehearsed.

---

## 6. Change log

| Date | Change |
|---|---|
| 2026-05-13 | v1.0. |
