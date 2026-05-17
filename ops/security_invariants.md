# Security invariants (checked per release)

These are the security properties promised by the design (`docs/06_verification.md` §3). Re-verify before every release.

| ID | Property | How verified |
|---|---|---|
| SP-1 | Role monotonicity within a request. | Integration test: actor role taken once at request start; mutation does not change it mid-request. |
| SP-2 | Write authorization (default-deny). | Integration test sweep: each role × each mutating endpoint; unauthorized combos must return 403. |
| SP-3 | Audit completeness for the AUDITED action set. | Integration test asserts an `audit_log` row appears for each AUDITED action invocation. |
| SP-4 | Audit log is append-only. | `app_user` PG role granted INSERT/SELECT only; UPDATE/DELETE blocked at DB. Manual check `\dp audit_log`. |
| SP-5 | Erasure terminality. | Integration test: after running erasure for a user, scan all tables for the user's email; expect zero matches. |
| SP-6 | Cert authenticity. | Unit test on signer + integration test on `/verify`. |
| SP-7 | Origin firewall (no direct origin access). | Manual check: `curl` to origin IP from non-CF must fail. |
| SP-8 | PII residency in EU. | Manual: Hetzner region = FSN1/NBG1; R2 jurisdiction = EU. |
