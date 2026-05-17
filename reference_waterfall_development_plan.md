<!-- markdownlint-disable MD024 -->
# Reference Waterfall Development Plan

> Reusable methodology for developing production-ready software systems from scratch. Generalized — contains no project-specific facts. Copy this file into every new project and instantiate its phases in that project's `CLAUDE.md`.

---

## 0. Philosophy

This methodology adapts the classical **waterfall** lifecycle (Royce 1970 / DoD-STD-2167A) with two modern additions:

- **Verification before code** (Phase 5) — a formal/lightweight audit of the design against the requirements before any implementation begins.
- **A revision loop between design and implementation** (Phase 6) — explicitly permitting one backward pass so a single late-discovered design flaw does not torpedo the project.

Everything else is strictly sequential. Each phase produces a versioned artifact that becomes the input to the next phase. **Do not begin a phase until the previous phase's artifact is complete and approved.**

This buys: traceability of every line of code back to a requirement; the ability to audit security/scalability properties before they are baked in; and a documentation set that can survive team turnover.

The cost: less flexibility once Phase 7 begins. Mitigate this by being thorough in Phases 1–5, and by allowing the Phase 6 revision step.

---

## Phase 1 — Requirements Elicitation

### Goal

Produce a complete, unambiguous, testable requirements specification — split into **functional**, **non-functional**, and **constraints**.

### Activities

1. Stakeholder identification (who pays, who uses, who operates, who regulates).
2. Structured Q&A with the user/sponsor covering every category in §1.1 below.
3. Use-case enumeration (one per user role × major capability).
4. Acceptance criteria per requirement (so each becomes testable).
5. Glossary of domain terms (avoids drift in later phases).
6. Prioritization (MoSCoW: Must / Should / Could / Won't-this-release).

### 1.1 Standard elicitation question categories

Ask explicitly in **every** project — never assume:

- **Purpose & scope**: problem being solved; out-of-scope items; success metrics.
- **Users & roles**: who, with what permissions, in what numbers, on what devices.
- **Functional capabilities**: per role, what operations they perform.
- **Data**: what entities exist; relationships; ownership; retention; deletion semantics.
- **External integrations**: identity providers, payments, email/SMS, storage, analytics, CDNs.
- **Non-functional — performance**: expected concurrent users, latency budgets, throughput, peak vs. average.
- **Non-functional — scalability**: growth horizon (users, content volume); horizontal vs. vertical preference.
- **Non-functional — availability**: target uptime; planned vs. unplanned downtime tolerance; RTO/RPO.
- **Non-functional — security**: authentication mechanisms, authorization model, data classification, threat actors of concern, compliance (GDPR / HIPAA / SOC2 / PCI etc.), audit logging needs.
- **Non-functional — privacy**: PII handled, consent model, data residency, right-to-erasure.
- **Non-functional — accessibility**: WCAG level target, screen reader support, keyboard navigation.
- **Non-functional — internationalization**: locales, RTL, currency/date formats.
- **Non-functional — observability**: metrics, logs, traces, alerting expectations.
- **Non-functional — maintainability**: who maintains; expected change cadence; documentation depth.
- **UI/UX**: target visual style, reference sites, brand assets, responsive breakpoints, dark/light mode.
- **Deployment & operations**: target environments (on-prem / cloud / hybrid), CI/CD expectations, on-call model.
- **Budget & constraints**: cost ceilings on infra; licensing constraints (e.g., no GPL); preferred vendors.
- **Timeline & milestones**: hard deadlines; demo dates; soft vs. hard milestones.
- **Legal & contractual**: ToS, privacy policy, IP ownership of contributed content, DMCA/takedown process.

### Output

`docs/01_requirements.md` — numbered requirements (FR-001…, NFR-001…, CON-001…), each with a one-line description, acceptance criterion, priority, and source (which stakeholder said it).

### Exit criterion

User signs off on the requirements doc in writing (or in the conversation log). Requirements are frozen for Phase 2; later changes go through a change-request log.

---

## Phase 2 — Architecture & Data Model Design

### Goal

A coherent technical design that satisfies every requirement, before any technology is chosen.

### Activities

1. **Logical architecture**: bounded contexts / modules / services; their responsibilities; their interfaces.
2. **Physical architecture sketch** (technology-agnostic at this stage): client tier, edge, application tier, data tier, async/queue tier, observability tier, identity tier.
3. **Dynamic protocol designs** — one sequence diagram (or equivalent) per non-trivial protocol. Standard list to cover:
   - User registration & email verification
   - Authentication & session management (login, logout, refresh, MFA if applicable)
   - Authorization decision flow (role check, resource ownership)
   - Permission grant/revoke between roles
   - Content upload (incl. large-file flow if applicable)
   - Content publication / moderation
   - Content consumption + view-tracking
   - Search / discovery
   - Notification dispatch (email, in-app)
   - Background jobs (transcoding, indexing, etc.)
   - Backup & restore
   - Account deletion / data export (GDPR)
4. **Data model**: entities, attributes, relationships, cardinalities, invariants, indexing intent. Express as an ERD plus a written specification. State which storage *paradigm* each entity needs (relational, document, key-value, blob, search index) — still tech-agnostic.
5. **Cross-cutting concerns design**: auth model (RBAC/ABAC), audit log shape, soft-delete vs. hard-delete, event sourcing vs. CRUD, caching strategy, idempotency keys.
6. **NFR mapping**: state how each NFR is met by the architecture (e.g., "NFR-007 P95 < 200 ms → CDN + edge cache + read replicas").

### Output

- `docs/02_architecture.md` — components, protocols (with diagrams), NFR-to-design mapping.
- `docs/03_data_model.md` — ERD + per-entity spec + indexing/invariants.

### Exit criterion

Every requirement in `01_requirements.md` is traceable to one or more elements in the architecture/data model. Reverse-traceability matrix included.

---

## Phase 3 — Tech Stack Selection

### Goal

Pick concrete technologies that realize the Phase 2 design, with documented justification.

### Activities

1. For each architectural slot (frontend framework, backend framework, database, object storage, cache, queue, search, IdP, CDN, observability, CI/CD, hosting), list **at least two candidates**.
2. For each candidate, write **pros, cons, trade-offs** evaluated against the specific requirements (not in the abstract). Include: maturity, license, ecosystem, team familiarity, operational burden, cost model, lock-in.
3. **Ask the user** whenever a trade-off is non-obvious or hinges on a preference (budget, hosting environment, vendor lock-in tolerance, team skills).
4. Decide and **record the decision** with rationale.
5. Identify which technologies cross trust/security boundaries and will need security review in Phase 5.

### Output

`docs/04_tech_stack.md` — table of slot → chosen tech → rationale → rejected alternatives → known risks.

### Exit criterion

Every architectural slot has a chosen technology with written justification. User has resolved every flagged trade-off.

---

## Phase 4 — Detailed Implementation Plan

### Goal

Translate the design + stack into a sequenced execution plan that another engineer could pick up and run.

### Activities

1. **Work breakdown**: decompose into milestones, each milestone into vertical slices (a slice cuts through UI → API → data → tests and delivers one user-visible capability).
2. **Sequencing**: order slices to minimize rework and maximize early feedback. Foundation slices first (auth, base data model, CI, deployment skeleton), then domain capabilities.
3. **Per slice**: scope, dependencies, acceptance criteria, test plan, owner, estimate, risk level.
4. **Cross-cutting tracks** running in parallel: security hardening, observability, accessibility, performance budgets.
5. **Environments**: dev, staging, prod definitions; promotion criteria.
6. **CI/CD pipeline design**: stages, gates, required checks before merge and before deploy.
7. **Risk register**: top N risks with mitigation + contingency.
8. **Definition of Done** (project-wide): code reviewed, tested, documented, observability wired, security checklist passed.

### Output

`docs/05_implementation_plan.md` — milestone-by-milestone plan with slices, sequencing, CI/CD, risk register, DoD.

### Exit criterion

Every requirement and every architectural element is covered by at least one slice. No orphan requirements, no orphan slices.

---

## Phase 5 — Plan Verification & Audit

### Goal

Find design and plan defects **before** writing code. Cheaper to fix on paper than in production.

### Activities

1. **Requirements coverage audit**: forward and reverse traceability check.
2. **Threat model**: STRIDE per component; per dynamic protocol; per data flow crossing a trust boundary. List threats + mitigations + residual risk.
3. **Security property verification**:
   - Authentication: replay, fixation, brute-force, MFA bypass.
   - Authorization: privilege escalation, IDOR, confused deputy, role tampering.
   - Data: at-rest encryption, in-transit encryption, secret management, key rotation.
   - Input validation: injection (SQL/NoSQL/command/template/LDAP), SSRF, XXE, deserialization.
   - Output: XSS (stored/reflected/DOM), CSRF, open redirect, clickjacking.
   - Session: rotation, expiry, revocation, secure cookie flags.
   - Auditability: tamper-evident logs, retention.
   - Where useful, write the security property formally (e.g., "no Viewer principal can mutate any Content resource" — express in TLA+ / Alloy / Z3 for high-stakes systems).
4. **Scalability verification**:
   - Identify hot paths; estimate load; compute capacity (Little's Law / queueing).
   - Spot single points of failure / shared bottlenecks.
   - Validate the cache, partition, and replication strategy under projected growth.
5. **Failure mode analysis**: what breaks when each external dependency fails? Define degradation modes.
6. **Cost projection**: monthly cost at expected scale; cost at 10×.
7. **Plan defect list**: enumerate every gap found.

### Output

`docs/06_verification.md` — traceability matrix, threat model table, scalability analysis, FMEA, cost model, defect list.

### Exit criterion

All Critical and High defects from the defect list either have a fix queued for Phase 6, or are explicitly accepted (with documented rationale).

---

## Phase 6 — Plan Revision & Optimization

### Goal

Fold Phase 5 findings back into the design and plan. This is the **only** sanctioned backward pass.

### Activities

1. For each defect: amend the relevant doc (`02_architecture.md`, `03_data_model.md`, `04_tech_stack.md`, `05_implementation_plan.md`).
2. Re-run the traceability check after edits.
3. If any change is large enough to invalidate the threat model or scalability model, re-run that portion of Phase 5 on the changed area only.
4. **Freeze the design.** Further changes during Phase 7 require a written change-request entry in `CLAUDE.md` §4.

### Output

Updated Phase 2–5 artifacts. A `CHANGELOG` section at the bottom of each amended doc.

### Exit criterion

Design is frozen. Implementation may begin.

---

## Phase 7 — Implementation

### Goal

Build the system per the frozen plan.

### Activities

1. **Bootstrap**: repo, branch protections, CI skeleton, base scaffolding, environments, secret management, observability baseline. This is itself a slice.
2. **Execute slices in the planned order.** Each slice = a PR (or PR cluster) that ends green and deployable.
3. **Tests with code**: unit alongside the unit, integration alongside the seam, e2e for each user-visible capability — written *as part of the slice*, not after.
4. **Observability with code**: metrics, structured logs, traces wired at the time the code is written. Dashboards updated.
5. **Security checks gated in CI**: SAST, dependency scan, secret scan, container scan.
6. **Documentation with code**: ADRs for non-obvious decisions; READMEs for each module; OpenAPI / schema definitions kept current.
7. **Reviews**: every PR reviewed against the per-slice acceptance criteria and the project DoD.
8. **Demos at milestone boundaries** to the user/sponsor.

### Output

Working software in version control, deployable to all defined environments.

### Exit criterion

All planned slices are merged and deployed to staging. All DoD checks pass on every slice.

---

## Phase 8 — Testing & Validation

### Goal

Prove the system meets every requirement before production release.

### Activities

1. **Test inventory**: confirm coverage of every requirement; identify gaps.
2. **Test layers**:
   - **Unit** — pure logic, table-driven where applicable.
   - **Integration** — across module/service seams against real (or near-real) dependencies.
   - **Contract** — for any API consumed by another party.
   - **End-to-end** — user-flow level, in a staging environment.
   - **Accessibility** — automated (axe) + manual screen-reader pass at the target WCAG level.
   - **Security** — DAST, authenticated and unauthenticated; penetration test on critical flows; auth/authz fuzzing.
   - **Performance / load** — soak test, stress test, spike test against the NFRs; capture P50/P95/P99.
   - **Chaos / failure injection** — kill dependencies, verify degradation modes.
   - **Backup / restore drill** — restore from backup into a fresh environment; measure RTO/RPO actuals.
3. **UAT (User Acceptance Testing)**: the sponsor runs the system end-to-end against the original requirements. Sign-off is per requirement, not blanket.
4. **Pre-production hardening**: rate limits live, CSP tight, HSTS preload, error pages, robots/sitemap, legal pages, monitoring + alerting actually paging humans.
5. **Cutover plan**: data migration (if any), DNS, rollback plan, comms plan.
6. **Post-launch**: monitor SLOs for the first N days; record what surprised you for the next project's Phase 5.

### Output

- `docs/07_test_plan.md` — test inventory, results, defects, sign-offs.
- A go/no-go decision recorded in `CLAUDE.md` §4.

### Exit criterion

UAT signed off. All Critical/High defects fixed or explicitly waived. Cutover plan rehearsed.

---

## Cross-phase rules

1. **Ask the user** whenever you reach a decision that depends on preference, budget, business context, or risk tolerance — never silently choose.
2. **Update `CLAUDE.md`** at the start and end of each phase: tick the phase tracker, record locked decisions, log open questions.
3. **Every artifact is versioned in the repo** alongside the code, not in a separate wiki — so it cannot drift.
4. **One backward step is allowed** (Phase 5 → Phase 6 → re-freeze). Any further backward step requires explicit user authorization and a written change request.
5. **Traceability is non-negotiable**: every line of code traces to a slice, every slice traces to one or more requirements, every requirement has acceptance criteria.
6. **Production-ready means**: secured by default, observable by default, recoverable by default, documented by default, accessible by default. If any of those is missing, the system is not done.

---

## When to deviate

This methodology is heavyweight by design and is right when:

- The system must be secure, scalable, and maintainable from day one.
- Multiple developers, multiple stakeholders, or regulatory pressure exist.
- The cost of a late design defect is high (data integrity, security, money, lives).

It is overkill for:

- Prototypes intended to be thrown away.
- Single-author research scripts.
- Hackathon work.

For those cases, collapse Phases 1–6 into a single short design note, but **never skip Phase 5 entirely** — even a one-page threat model and a one-page scalability sketch saves more time than it costs.
