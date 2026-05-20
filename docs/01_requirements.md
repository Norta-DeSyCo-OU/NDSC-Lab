<!-- markdownlint-disable MD013 MD024 -->
# 01 — Requirements Specification

| Project | NDSC Lab |
|---|---|
| Provider | Norta DeSyCo OU |
| Document version | 1.0 |
| Date frozen | 2026-05-13 |
| Phase | 1 — Requirements Elicitation (complete) |
| Author | Engineering, with sponsor input |

> This document is the authoritative requirements specification. Every downstream artifact (architecture, data model, tech stack, implementation plan, tests) must trace back to identifiers defined here. Changes after freeze require a change-request entry in `CLAUDE.md` §4.

---

## 1. Glossary

| Term | Definition |
|---|---|
| Platform | The NDSC Lab system as a whole. |
| User | A registered visitor with the Viewer role (default on signup). |
| Contributor | A User who has been granted permission to publish content and curate a public author page. |
| Admin | A User with full administrative permissions. Flat role — no super/moderator split. |
| Content Item (Item) | A single piece of published material: a Video, an Article, or a Teaching Material file/link. |
| Video Item | An Item whose primary medium is moving image. Can be hosted (uploaded) or embedded (external URL allowlisted). |
| Article | An Item authored on-platform as Markdown/WYSIWYG, optionally with attached PDFs, LaTeX (KaTeX), and code blocks (Shiki). |
| Teaching Material Item | An Item that is a downloadable file (PDF, slides, datasets, code archive, ZIP) or an external link. |
| Collection | A named, ordered set of Content Items grouped by a Contributor. |
| Course | A Collection subtype that has defined completion criteria and is eligible for certificate issuance. |
| Workshop | A scheduled event listing (date/time, abstract, speakers, registration link, optional post-event recording attachment). Speakers link to Contributor profiles. |
| Author Page | A Contributor's public profile page (bio, links, items, sections). |
| View | A counted impression. Definition is per-item-type and is admin-tunable (see FR-VIEW-002, FR-VIEW-003). |
| Certificate | A cryptographically signed PDF attesting that a named User completed a named Course on a given date, issued by an Admin. Verifiable via a public verification page. |
| RBAC | Role-Based Access Control. |
| FTS | Full-Text Search. |
| TOTP | Time-based One-Time Password (RFC 6238). |
| VC | Verifiable Credential (W3C standard). Out of scope for v1; architecture must remain VC-extensible. |
| CDN | Content Delivery Network (Cloudflare). |
| RPO / RTO | Recovery Point Objective / Recovery Time Objective. |

---

## 2. Stakeholders

| Stakeholder | Interest |
|---|---|
| Norta DeSyCo OU (sponsor / provider) | Owns and operates the platform; bears legal liability as ToS counterparty. |
| Admins (NDSC employees) | Manage platform content, contributors, comments, certificates, audit. |
| Contributors (researchers, industry practitioners) | Publish content, curate author page, gain visibility. |
| Users (community: researchers, students, practitioners) | Consume content, earn certificates, comment. |
| Sole maintainer (post-launch) | Operates, patches, monitors the platform alone. |

---

## 3. Scope

### 3.1 In scope (v1)

- Three-role RBAC (Admin, Contributor, User), global, hierarchical.
- Content types: Video (hosted + embedded), Article (Markdown/WYSIWYG + attachments), Teaching Material (file/link).
- Author pages with strict templates + extensible sections.
- Collections (flat list and Course subtype with completion criteria).
- Comments on all Item types.
- Per-user view tracking + per-item/per-contributor/per-category/time-series analytics (Admins only).
- Tags + admin-managed categories; FTS on articles + filter by contributor/tag/type/date.
- Certificates: admin-issued, Ed25519-signed PDF, public verification page.
- Workshops: event listings with metadata + speakers + optional recording.
- GDPR machinery: cookie consent, right-to-erasure, data export.
- Audit log.
- Dockerized deployment, dark + light theme, English-only, EU CDN, WCAG 2.2 AA.

### 3.2 Deferred (architecture must accommodate)

- **Payments / paywall** — `Item.paywall_config_id` nullable field reserved; null ⇒ free.
- **Live streaming** — `Video.kind` enum reserves `LIVE`; not implemented.
- **MFA** — auth module structured to plug TOTP in without schema migration.
- **Verifiable Credentials** — certificate issuer code factored to add a VC artifact alongside the PDF.
- **Multi-tenant / per-department admin scoping** — entities carry nullable `scope_id`; null ⇒ global.

### 3.3 Out of scope (v1, not planned)

- Quizzes, formal assessments other than admin-issued certificates.
- Ratings, reactions, bookmarks.
- Co-authoring on a single item.
- Edit history / content versioning.
- Native mobile applications.
- Video transcript search, auto-transcription, auto-transcoding to HLS adaptive bitrate.
- Multilingual UI (English only).
- Forums (comments only).
- On-platform workshop registration / RSVP (only external link).

---

## 4. Functional Requirements

Each requirement: `ID — Title — Description — Acceptance Criterion (AC) — Priority (M/S/C/W per MoSCoW) — Source`.

### 4.1 Authentication & accounts

| ID | Title | Description | AC | Pri | Src |
|---|---|---|---|---|---|
| FR-AUTH-001 | Email/password signup | A visitor can self-register with email + password. Email verification required before login. | (1) `POST /auth/signup` creates an unverified account and dispatches a verification email via Resend. (2) Account is `pending_verification` until link clicked within 24 h. (3) Password ≥ 12 chars, Argon2id-hashed with server pepper. | M | Q6, Q7 |
| FR-AUTH-002 | Google OAuth signup/login | A visitor can sign up or log in via Google OAuth 2.0 (OIDC). | (1) Account auto-verified on first successful OIDC flow. (2) Email scope only; no Workspace admin scopes. (3) Linkable to existing email account if email matches and user confirms. | M | Q7 |
| FR-AUTH-003 | Login | A verified User can log in and receive a session cookie. | (1) Session via secure HTTPOnly SameSite=Lax cookie. (2) 30-day rolling expiry, sliding renewal on activity. (3) CSRF token issued for state-changing requests. | M | Q7 |
| FR-AUTH-004 | Logout | A logged-in User can log out, invalidating the session server-side. | (1) Session record deleted from session store. (2) Cookie cleared in response. | M | Q7 |
| FR-AUTH-005 | Password reset | A User can request a password reset. | (1) Time-limited (1 h) single-use token. (2) Rate-limited to 5 / account / hour. (3) Always returns 200 regardless of email existence (account enumeration defense). | M | derived |
| FR-AUTH-006 | Breached-password check | New and changed passwords are checked against HIBP via k-anonymity API. | (1) Submission with > 0 hits rejected with clear message. (2) Network failure to HIBP is non-blocking (logged). | S | derived |
| FR-AUTH-007 | Account lockout | After 5 failed logins / IP / 15 min OR 10 / account / 15 min, lockout with exponential backoff. | (1) Lockout state persisted. (2) Admin can unlock from admin panel. | M | derived |
| FR-AUTH-008 | Age confirmation | Signup form requires confirmation that the user is ≥ 16 years old (GDPR EU threshold). | (1) Required checkbox at signup. (2) Server records timestamp + IP of confirmation. | M | Q39 |
| FR-AUTH-009 | MFA-ready architecture | Auth code is structured so TOTP MFA can be added later without schema migration. | (1) `mfa_secret` and `mfa_enabled_at` columns reserved nullable on User. (2) Login flow factored to allow inserting a TOTP challenge step. | S | derived |

### 4.2 Roles & permissions

| ID | Title | Description | AC | Pri | Src |
|---|---|---|---|---|---|
| FR-ROLE-001 | Three flat global roles | Admin, Contributor, User. Permissions inherit: Admin ⊇ Contributor ⊇ User. | (1) Single `role` column on User, enum-constrained. (2) Authorization layer enforces inheritance. | M | Q5, Q8 |
| FR-ROLE-002 | Contributor self-apply | A User can submit a Contributor application (motivation text, links). | (1) `POST /me/contributor-application`. (2) Creates a pending application visible in admin queue. (3) Applicant can edit their pending application until decision. | M | Q9 |
| FR-ROLE-003 | Admin grants Contributor | Admin reviews application and approves or rejects with optional comment. | (1) On approve, User's role atomically upgraded; notification email sent. (2) Reject reason stored; applicant may re-apply after 7 days. | M | Q9 |
| FR-ROLE-004 | Admin grants Contributor ad-hoc | Admin can promote any User to Contributor without an application. | (1) `POST /admin/users/{id}/role` with audit log entry. | M | Q9 |
| FR-ROLE-005 | Contributor self-revocation | A Contributor can revoke their own role; admin specifies content fate on revocation request. | (1) Self-revoke action triggers an admin review: tombstone-and-reassign-to-"Anonymous" OR hard-delete. (2) Admin choice executed atomically with role downgrade. | M | Q10, Q19 |
| FR-ROLE-006 | Admin revokes Contributor / bans User | Admin can demote any Contributor or ban any User. | (1) Audit log entry recorded. (2) Banned account loses session and cannot re-login. (3) Demoted Contributor's content fate handled per FR-ROLE-005. | M | Q6, Q32 |

### 4.3 Author pages (Contributor profile)

| ID | Title | Description | AC | Pri | Src |
|---|---|---|---|---|---|
| FR-PROFILE-001 | Public author page | Each Contributor has a public page at `/c/<slug>`. | (1) Slug unique, lowercase alphanumeric + dash, 3–40 chars. (2) Page renders without authentication. | M | Q23 |
| FR-PROFILE-002 | Editable profile fields | Contributor can edit: display name, bio (Markdown), photo (≤ 2 MB, image MIME), affiliation, ORCID, social links (Twitter/X, GitHub, LinkedIn, Mastodon, personal site), arbitrary custom external links (label + URL). | (1) All fields optional except display name and slug. (2) URL validation; HTTPS only on links. | M | Q23 |
| FR-PROFILE-003 | Custom URL slug | Contributor can change slug; old slug 301-redirects for 90 days. | (1) Slug change rate-limited to once per 30 days. (2) Reserved slugs ("admin","api","c","verify",...) blocked. | S | Q23 |
| FR-PROFILE-004 | Strict template + extensible sections | Page uses a fixed template; Contributor can add named sections and sub-sections, but cannot inject raw HTML. | (1) Section title + body (Markdown sanitized). (2) Drag-handle reorder. (3) Server sanitizes via allowlist (e.g., `rehype-sanitize`). | M | Q24 |
| FR-PROFILE-005 | Item listing on author page | Contributor's published Items are listed on their page, filterable by type and Collection. | (1) Default sort: most recent first. (2) Pagination 20/page. | M | Q23 |

### 4.4 Content items — common

| ID | Title | Description | AC | Pri | Src |
|---|---|---|---|---|---|
| FR-CONTENT-001 | Create draft | A Contributor can create a draft Item of any type. | (1) Draft has full edit access by author. (2) Drafts are not publicly listed and not searchable. | M | Q17 |
| FR-CONTENT-002 | Edit draft | Author can edit own drafts unrestricted. | (1) Autosave every 30 s while editing. | M | Q17 |
| FR-CONTENT-003 | Preview draft | Author can preview the draft as it will appear when published. | (1) Preview URL is signed and only valid for the author + admins. | M | Q17 |
| FR-CONTENT-004 | Submit for review | Author submits draft for admin approval. | (1) `POST /items/{id}/submit`. (2) Locks editing while in `pending_review`. (3) Admins notified. | M | Q17 |
| FR-CONTENT-005 | Admin approves / rejects publication | Admin reviews submitted Item and approves (publishes) or rejects (returns to draft with comment). | (1) Action logged in audit log with comment. (2) Author notified. | M | Q17 |
| FR-CONTENT-006 | Admin auto-publish | Admin-authored Items skip review and publish immediately. | (1) Admin can also force-publish any submitted Item bypassing further review. | M | Q17 |
| FR-CONTENT-007 | Unpublish / delete | Author can unpublish own published Item (returns to draft). Admin can unpublish or hard-delete any Item. | (1) Hard-delete removes blob from R2 within 24 h. (2) Soft-delete keeps record for audit. | M | derived |
| FR-CONTENT-008 | Tags | Author can add tags (free or from suggestion list). | (1) Tag normalized lowercase, trimmed, 1–32 chars. (2) Max 10 tags per Item. | M | Q15 |
| FR-CONTENT-009 | Admin-managed categories | Each Item belongs to ≥ 1 admin-defined Category. | (1) Admin CRUD on Category taxonomy. (2) Items missing a Category cannot be published. | M | Q15 |
| FR-CONTENT-010 | License selection | Author chooses a license per Item from a predefined list (CC-BY 4.0 default, CC-BY-SA, CC-BY-NC, CC0, "All rights reserved"). | (1) License displayed on Item page. (2) License changeable post-publication; old views retain license at view-time. | M | Q21 |
| FR-CONTENT-011 | Payment-ready field | Each Item has a nullable `paywall_config_id` field, currently always null. | (1) Schema includes the field. (2) Application code branches treat `null` as free. | C | Q3 |

### 4.5 Video items

| ID | Title | Description | AC | Pri | Src |
|---|---|---|---|---|---|
| FR-VIDEO-001 | Hosted video upload | A Contributor can upload a video file when admin-permitted. | (1) Resumable upload (tus protocol). (2) Default ceiling 2 GB, 4 h duration; per-contributor admin-tunable. (3) Mime allowlist: mp4, webm, mov. | M | Q11 |
| FR-VIDEO-002 | Hosted video storage + streaming | Uploaded videos stored on R2; streamed via Cloudflare CDN with HTTP range requests. | (1) Direct streaming, no transcoding v1. (2) Signed URLs with TTL 1 h. | M | Q11, Q53 |
| FR-VIDEO-003 | Embedded video | A Contributor can embed an external video by URL. | (1) Host allowlist: YouTube, Vimeo, Panopto. (2) Server-side oEmbed lookup for thumbnail/title. | M | Q11 |
| FR-VIDEO-004 | Admin can disable hosted video per contributor | Admin can toggle "hosted upload allowed" and "embed-only mode" per Contributor. | (1) Existing hosted videos remain accessible. (2) New hosted uploads rejected when disabled. | M | Q11 |
| FR-VIDEO-005 | Video kind enum reserves LIVE | Database enum for video kind includes `LIVE` (unused v1). | (1) Migration creates enum. (2) Application rejects writes with `LIVE`. | C | Q3 |

### 4.6 Articles

| ID | Title | Description | AC | Pri | Src |
|---|---|---|---|---|---|
| FR-ART-001 | Markdown/WYSIWYG editor | Author writes article in a Markdown-backed WYSIWYG editor (e.g., TipTap). | (1) Source stored as Markdown; sanitized HTML cached. | M | Q12 |
| FR-ART-002 | Math (KaTeX) | LaTeX expressions rendered via KaTeX. | (1) `$inline$` and `$$block$$` supported. | M | Q12 |
| FR-ART-003 | Code blocks (Shiki) | Syntax-highlighted code blocks via Shiki. | (1) Common languages enabled. (2) Copy-button. | M | Q12 |
| FR-ART-004 | PDF/DOCX attach | Author can attach files (PDF up to 50 MB inline-rendered via PDF.js, DOCX downloadable). | (1) PDF rendered inline + download link. (2) DOCX download only. | M | Q12 |
| FR-ART-005 | External link content | Article can be a pointer to an external URL (open-graph preview rendered). | (1) URL validated, allowlisted schemes (https). | M | Q12 |

### 4.7 Teaching material

| ID | Title | Description | AC | Pri | Src |
|---|---|---|---|---|---|
| FR-TM-001 | File upload | Author can upload files (PDF, PPT/PPTX, ZIP, datasets, code archives, common code MIMEs). | (1) Default 200 MB per file ceiling; admin-tunable. (2) MIME allowlist + extension allowlist. | M | Q13 |
| FR-TM-002 | External link material | Author can post an external link (Zenodo, GitHub, etc.) as a Teaching Material Item. | (1) https only; preview where supported. | M | Q13 |
| FR-TM-003 | Quota | Per-contributor storage quota default 20 GB; admin-tunable. | (1) Soft-warning at 80%. (2) New uploads rejected over hard limit. | M | derived |

### 4.8 Collections & Courses

| ID | Title | Description | AC | Pri | Src |
|---|---|---|---|---|---|
| FR-COL-001 | Create collection | Contributor creates a named, ordered Collection of own Items. | (1) Title, description (Markdown), cover image. (2) Drag-reorder. | M | Q14 |
| FR-COL-002 | Course subtype | Collection can be flagged "Course" with per-item completion criteria. | (1) Per item: required ✓, "completed when" rule (video ≥ X% watched, article ≥ Y% scrolled, file downloaded). | M | new |
| FR-COL-003 | Per-user progress | For each User × Course, system tracks per-item completion state. | (1) Computed from view events. (2) Visible to the User on the Course page. | M | new |
| FR-COL-004 | Course completion detection | When a User satisfies all required items' criteria, the system marks the Course "completed" for that User. | (1) Event raised. (2) Suggestion appears in admin Certificate Issuance queue. | M | new |

### 4.9 Certificates

| ID | Title | Description | AC | Pri | Src |
|---|---|---|---|---|---|
| FR-CERT-001 | Ed25519 server keypair | Platform holds an Ed25519 signing keypair in secrets store, rotatable. | (1) Public key published at `/.well-known/ndsc-cert-pubkey.json`. (2) Key rotation supported with multi-key verification window. | M | new |
| FR-CERT-002 | Admin issues certificate | An Admin can issue a Certificate for any User × Course (suggested by FR-COL-004 or ad-hoc). | (1) Cert record has unique ID, User, Course, issued-at, issuing-admin. (2) PDF generated server-side with cert ID + QR code linking to verification URL. (3) PDF detached-signed with Ed25519; signature embedded in PDF metadata. | M | new |
| FR-CERT-003 | User downloads certificate | Issued User sees a "My certificates" page and can download the PDF. | (1) Notification email on issuance. | M | new |
| FR-CERT-004 | Public verification page | `/verify/<cert-id>` shows the cert record + verifies the PDF signature on upload. | (1) GET shows DB record. (2) POST PDF re-verifies signature against current and previous public keys. | M | new |
| FR-CERT-005 | Revocation | Admin can revoke a Certificate. | (1) Revocation flag visible on verification page. | S | new |
| FR-CERT-006 | VC-extensible architecture | Issuer code factored so a W3C VC can be produced alongside the PDF without redesign. | (1) Separate `signer` service with pluggable artifact producers. | C | Q3 |

### 4.10 Comments

| ID | Title | Description | AC | Pri | Src |
|---|---|---|---|---|---|
| FR-COM-001 | Post comment | Any authenticated User/Contributor/Admin can comment on any published Item. | (1) Markdown sanitized. (2) Max 5000 chars. (3) Rate limit 5/min/user. | M | Q19 |
| FR-COM-002 | Edit / delete own comment | Author can edit (within 15 min) or delete own comment. | (1) Edited flag shown. (2) Delete is soft + audit-logged. | M | Q19 |
| FR-COM-003 | Admin moderation | Admin can delete any comment and ban any commenter. | (1) Deletion reason stored. (2) Item-page hides removed comments. | M | Q19 |
| FR-COM-004 | Report comment | User can report a comment; goes to admin queue. | (1) Reporter, reason, item, ts captured. | S | Q32 |

### 4.11 View tracking & analytics

| ID | Title | Description | AC | Pri | Src |
|---|---|---|---|---|---|
| FR-VIEW-001 | Per-user view events | Each Item view emits an event (User ID, Item ID, type, ts, session). | (1) Event stored in raw_events table. (2) Async pipeline aggregates into daily/weekly/monthly per-item, per-contributor, per-category counts. | M | Q26, Q27 |
| FR-VIEW-002 | Video view definition | A "view" is counted when watch duration ≥ N seconds (default 10, admin-tunable). | (1) Client emits heartbeats; server validates threshold. | M | Q28 |
| FR-VIEW-003 | Article view definition | A "view" is counted when ≥ 5 s on page AND ≥ 25% scrolled (admin-tunable). | (1) Client emits engagement event; server applies threshold. | M | Q28 |
| FR-VIEW-004 | De-duplication | Same user + same item within 30 min = 1 view. | (1) Idempotency at aggregation stage. | M | derived |
| FR-VIEW-005 | Admin dashboard | Admin sees total/per-item/per-contributor/per-category/time-series views. | (1) Charts + CSV export. (2) Configurable date range. | M | Q26, Q29 |
| FR-VIEW-006 | Analytics retention | Raw events retained 90 days; aggregates retained indefinitely. | (1) Daily job purges raw events older than 90 days. | M | Q31 |
| FR-VIEW-007 | No public view counts | View counts are NOT shown to Users or Contributors. | (1) API endpoints restrict analytics responses to Admin. | M | Q29 |

### 4.12 Search & discovery

| ID | Title | Description | AC | Pri | Src |
|---|---|---|---|---|---|
| FR-SEARCH-001 | Full-text article search | Postgres FTS over article title + body. | (1) Sub-300 ms P95 at v1 scale. (2) Stemmed English. | M | Q16 |
| FR-SEARCH-002 | Filters | Combinable filters: contributor, tag, category, type, date range. | (1) Returns paginated results. | M | Q16 |
| FR-SEARCH-003 | Sort | Sort by relevance, date, view-count (admin only for view-count sort). | (1) Default relevance for queries, date for browse. | M | Q16 |

### 4.13 Workshops

| ID | Title | Description | AC | Pri | Src |
|---|---|---|---|---|---|
| FR-WS-001 | Workshop listing | Public page lists upcoming + past workshops. | (1) Sort by date. (2) Filter past/upcoming. | M | Q2 |
| FR-WS-002 | Workshop record | Workshop has: title, abstract (Markdown), start ts, end ts, location/online, external registration URL, speakers (≥ 1 Contributor reference). | (1) Speakers link to their Contributor pages. | M | Q2 |
| FR-WS-003 | Post-event recording attachment | Workshop can optionally attach one Video Item as the recording. | (1) Linked Video must be published. | M | Q2 |
| FR-WS-004 | Admin/Contributor create | Workshops can be created by Contributors (subject to admin approval) or Admins. | (1) Same approval flow as Items. | M | derived |

### 4.14 Admin capabilities

| ID | Title | Description | AC | Pri | Src |
|---|---|---|---|---|---|
| FR-ADMIN-001 | Content CRUD on any Item | Admin can CRUD any Item regardless of author. | (1) Audit-logged. | M | Q32 |
| FR-ADMIN-002 | User management | Admin can list, search, ban/unban, delete (right-to-erasure), force password reset, change role, and unlock locked accounts. | (1) Bulk actions available. | M | Q32 |
| FR-ADMIN-003 | Audit log viewer | Admin can view + filter + export the audit log. | (1) Filters: actor, action, target, date range. (2) CSV export. | M | Q32 |
| FR-ADMIN-004 | Site-wide announcements | Admin can publish a banner shown to all users until dismissed. | (1) Severity (info/warning/critical). (2) Per-user dismissal recorded. | M | Q32 |
| FR-ADMIN-005 | Email template management | Admin can edit subjects + bodies of transactional emails. | (1) Sandboxed templating (no arbitrary code). (2) Test-send to admin's own email. | M | Q32 |
| FR-ADMIN-006 | Reports queue | Admin sees a unified queue: Contributor applications, content review, comment reports, takedown requests, certificate suggestions. | (1) Per-queue counters in nav. | M | Q32 |
| FR-ADMIN-007 | Theme customization | Admin can switch a small set of theme variables (primary accent, dark/light default). | (1) Live preview. | S | Q32 |
| FR-ADMIN-008 | Per-contributor tunables | Admin sets per-contributor: storage quota, hosted-video allowed, embed-only mode, max video duration. | (1) Defaults inherited from platform settings. | M | Q11, Q13 |
| FR-ADMIN-009 | Platform settings | Admin edits platform tunables: view thresholds, max file sizes, allowed MIME types, default license, audit retention, registration open/closed, age threshold. | (1) Changes audit-logged. | M | Q11, Q13, Q28, Q41 |
| FR-ADMIN-010 | Tag/category management | Admin CRUD on categories; can merge or rename tags. | (1) Merge re-points all references atomically. | M | Q15 |

### 4.15 Legal & lifecycle

| ID | Title | Description | AC | Pri | Src |
|---|---|---|---|---|---|
| FR-LEG-001 | ToS + Privacy Policy pages | Platform publishes ToS and Privacy Policy authored by/for Norta DeSyCo OU; versioned. | (1) `/legal/terms` and `/legal/privacy`. (2) Each user signup records the accepted version. (3) Material changes prompt re-acceptance. | M | Q56 |
| FR-LEG-002 | DMCA / takedown form | Public form `/legal/takedown` posts to admin queue. | (1) Required fields: complainant identity, URL, sworn statement, contact. (2) Admin SLA 48 h. | M | Q22 |
| FR-LEG-003 | Cookie consent | Granular cookie banner: essential always on; analytics opt-in. | (1) Compliant with ePrivacy Directive. (2) Choice persisted, revisitable in user settings. | M | Q30 |
| FR-LEG-004 | Right-to-erasure | User can delete own account + all data from settings. | (1) Hard-delete within 30 days. (2) Pseudonymization of legally retained records (audit log) within 30 days. | M | Q30 |
| FR-LEG-005 | Data export | User can export their data (profile + content + view history + comments + certificates) as a ZIP. | (1) Self-serve from settings. (2) Generated async; email link when ready. | M | Q30 |

---

## 5. Non-Functional Requirements

### 5.1 Performance

| ID | Requirement | Target | AC | Pri |
|---|---|---|---|---|
| NFR-PERF-001 | Page load P95 (CDN-cached, EU/NA) | ≤ 800 ms | Synthetic monitor in EU + NA samples every 5 min, P95 weekly. | M |
| NFR-PERF-002 | Page load P95 (cold) | ≤ 1.5 s | Same monitor, cold-cache requests. | M |
| NFR-PERF-003 | Video first-frame | ≤ 3 s on 25 Mbps connection | Lighthouse-equivalent measurement on representative video. | M |
| NFR-PERF-004 | Search P95 | ≤ 300 ms server time at 50k articles | Load test. | M |
| NFR-PERF-005 | Concurrent users | 100 concurrent active sessions at launch, design headroom to 500. | Load test. | M |

### 5.2 Availability & recovery

| ID | Requirement | Target | AC | Pri |
|---|---|---|---|---|
| NFR-AVAIL-001 | Monthly uptime | ≥ 99.0% | Uptime monitor (UptimeRobot/Better-Stack free). | M |
| NFR-AVAIL-002 | Maintenance window | Sundays 02:00–04:00 UTC, advertised 7 d prior | Maintenance banner shown. | M |
| NFR-AVAIL-003 | RPO | ≤ 24 h | Daily Postgres dump uploaded to R2 (separate bucket, separate credentials). | M |
| NFR-AVAIL-004 | RTO | ≤ 4 h | Documented + quarterly drill. | M |
| NFR-AVAIL-005 | Backup retention | 30 days encrypted | Lifecycle rule on R2. | M |

### 5.3 Security

| ID | Requirement | AC | Pri |
|---|---|---|---|
| NFR-SEC-001 | Argon2id password hashing with server-side pepper | Library: `argon2` with parameters memory ≥ 64 MB, ops ≥ 3, parallelism 1. | M |
| NFR-SEC-002 | TLS 1.2+ only, HSTS preload | Mozilla "intermediate" cipher suite, HSTS `max-age=63072000; includeSubDomains; preload`. | M |
| NFR-SEC-003 | Strict CSP | `default-src 'self'`, allowlist for Cloudflare CDN, R2, embed video hosts. Nonce-based for inline scripts. | M |
| NFR-SEC-004 | CSRF tokens | Double-submit cookie + same-site Lax. | M |
| NFR-SEC-005 | Authorization checks centralized | Single policy module (e.g., oso/casbin or hand-rolled), called from every mutating endpoint. | M |
| NFR-SEC-006 | Input validation | Schema validation (Zod/Pydantic) at API boundary on every endpoint. | M |
| NFR-SEC-007 | Upload virus scan | ClamAV (Docker sidecar) scans every uploaded file before publication; quarantine on hit; notify admin. | M |
| NFR-SEC-008 | Signed-URL access to R2 | All blob reads use 1 h TTL signed URLs; no public-bucket reads. | M |
| NFR-SEC-009 | DDoS / WAF | Cloudflare in front with managed WAF rules. | M |
| NFR-SEC-010 | Rate limiting | Auth endpoints 5/IP/15min, 10/account/15min; password reset 5/account/hour; comments 5/user/min; generic 100/min/IP. | M |
| NFR-SEC-011 | Secret management | Secrets injected via env at container start; never written to logs; gitleaks gate in CI. | M |
| NFR-SEC-012 | Dependency hygiene | CI runs SAST (Semgrep), dep audit (`npm audit` / `pip-audit`), container scan (Trivy), secret scan (gitleaks) on every PR. | M |
| NFR-SEC-013 | Threat model maintained | STRIDE table in `06_verification.md` covers each protocol and dataflow crossing a trust boundary. | M |
| NFR-SEC-014 | Audit-log integrity | Audit log append-only; integrity check via per-row HMAC chain. | S |

### 5.4 Privacy & compliance

| ID | Requirement | AC | Pri |
|---|---|---|---|
| NFR-PRIV-001 | GDPR-compliant | Lawful basis recorded per processing purpose. DPA-style register maintained. | M |
| NFR-PRIV-002 | EU data residency | All PII stored in EU region (Hetzner Falkenstein/Nuremberg, R2 EU jurisdictional). | M |
| NFR-PRIV-003 | EU Accessibility Act | EAA-equivalent (WCAG 2.2 AA) compliant from launch (timing aligned with EAA enforcement). | M |
| NFR-PRIV-004 | Data minimisation | Only collect: email, optional display name, optional profile fields, content authored, view events. No location beyond IP-truncated. | M |
| NFR-PRIV-005 | PII encryption at rest | DB at rest via volume encryption; R2 server-side encryption. | M |
| NFR-PRIV-006 | Pseudonymization on deletion | Audit log entries de-link from user via pseudonym after right-to-erasure. | M |
| NFR-PRIV-007 | Privacy disclosure of view tracking | Privacy Policy explicitly discloses per-user view tracking. | M |

### 5.5 Accessibility

| ID | Requirement | AC | Pri |
|---|---|---|---|
| NFR-A11Y-001 | WCAG 2.2 AA compliance | Automated axe-core + manual screen reader pass (NVDA + VoiceOver). | M |
| NFR-A11Y-002 | Keyboard navigation | All flows operable without a mouse. | M |
| NFR-A11Y-003 | Color contrast | All text meets 4.5:1 normal / 3:1 large per WCAG. Theme tokens audited. | M |
| NFR-A11Y-004 | Video accessibility | Player supports captions (when contributor provides VTT); keyboard-controllable. | M |
| NFR-A11Y-005 | Reduced motion | Respect `prefers-reduced-motion`. | S |

### 5.6 UX / branding

| ID | Requirement | AC | Pri |
|---|---|---|---|
| NFR-UX-001 | Visual identity matches `nortadesyco.xyz` | Color tokens per `CLAUDE.md §1.3`. Design system in code (CSS variables / Tailwind theme). | M |
| NFR-UX-002 | Dark default, light toggle | Theme preference persisted per user. | M |
| NFR-UX-003 | Responsive | Mobile (≥ 360 px), tablet, desktop layouts; no horizontal scroll except in code blocks. | M |
| NFR-UX-004 | English-only | All UI strings in EN. Translation infra not built; string table extractable for future i18n. | M |

### 5.7 Observability

| ID | Requirement | AC | Pri |
|---|---|---|---|
| NFR-OBS-001 | Structured logs | JSON logs with request-id, user-id (when present), trace-id. | M |
| NFR-OBS-002 | Metrics | Prometheus-format metrics endpoint; key metrics: req/s, latency histograms, error rate, queue depth, R2 ops, view-event rate. | M |
| NFR-OBS-003 | Error monitoring | Self-hosted GlitchTip (Sentry-compatible) or free Sentry tier (≤ 5k events/mo). | M |
| NFR-OBS-004 | Uptime monitoring | External monitor (UptimeRobot or Better-Stack free) on `/healthz` every 60 s. | M |
| NFR-OBS-005 | Alerting | Email + (optional) Telegram bot alerts on: 5xx rate > 1%/5min, latency P95 > 2× target/5min, healthcheck down, disk > 80%. | M |
| NFR-OBS-006 | Dashboards | Grafana (self-hosted, Docker) with default app dashboard. | S |

### 5.8 Maintainability

| ID | Requirement | AC | Pri |
|---|---|---|---|
| NFR-MAINT-001 | Dockerized | Whole platform runs via `docker compose up` on a clean Ubuntu host. | M |
| NFR-MAINT-002 | Portable | Deployable to any docker host (Hetzner, AWS EC2, on-prem) with config-only changes. | M |
| NFR-MAINT-003 | Documentation | README for run/deploy/backup/restore; ADR per non-obvious decision; OpenAPI for HTTP API. | M |
| NFR-MAINT-004 | Test coverage | Unit ≥ 70% on application code; integration tests on every API endpoint; e2e for each user-visible flow. | M |
| NFR-MAINT-005 | CI gates | PR cannot merge unless: lint, type-check, unit + integration tests, Semgrep, gitleaks, Trivy, dep audit all green. | M |
| NFR-MAINT-006 | Migrations | Versioned, reversible Postgres migrations. | M |
| NFR-MAINT-007 | Sole-operator runbook | Every operational task (rotate key, restore backup, ban user, rotate secret) has a documented runbook. | M |

---

## 6. Constraints

| ID | Constraint | Rationale | Pri |
|---|---|---|---|
| CON-001 | Infrastructure budget: 20–30 EUR/mo nominal, 80–100 EUR/mo ceiling | Sole-operator project, sponsor's budget. | M |
| CON-002 | Hosting on Hetzner + Cloudflare R2 + Cloudflare CDN | Phase 1 vendor decision. | M |
| CON-003 | Dockerized + self-hostable anywhere | Portability requirement for sponsor flexibility. | M |
| CON-004 | English only at launch | Sponsor decision. | M |
| CON-005 | Free / free-tier 3rd-party services only | Resend free, GlitchTip self-host or Sentry free tier, UptimeRobot free, ClamAV. | M |
| CON-006 | EU data residency | GDPR. | M |
| CON-007 | Solo maintainer | All operational tasks must be solo-runnable in < 30 min/week steady-state. | M |
| CON-008 | No MFA at v1 | Sponsor decision (override on engineering recommendation). Architecture remains MFA-extensible (FR-AUTH-009). | M |
| CON-009 | No native mobile app | Sponsor decision. | M |
| CON-010 | GDPR + EU Accessibility Act + WCAG 2.2 AA compliance | Legal. | M |

---

## 7. Out-of-scope / Deferred

See §3.2 (deferred, architecture-ready) and §3.3 (not planned). Any future addition requires a change request.

---

## 8. Traceability anchors

Every downstream phase document must reference these IDs. The reverse-traceability matrix in `06_verification.md` will list, for each ID, which architectural element + slice + test covers it.

## 9. Change log

| Date | Change | Source |
|---|---|---|
| 2026-05-13 | v1.0 frozen. | Sponsor sign-off via session of 2026-05-13. |
| 2026-05-13 | v1.1 Phase 6 amendments (D-01..D-20). See §10. | Phase 5/6. |

---

## 10. v1.1 amendments (Phase 6, defects D-01..D-20)

### FR-AUTH-005 (amended; D-01)

Add AC: For users with `password_hash IS NULL` (OAuth-only), a "Set password" flow is available behind a fresh re-OIDC step.

### FR-AUTH-010 (new; D-02)

Change email: logged-in user submits new email + current password (or fresh OAuth); confirmation link to new address; both addresses notified; audit-logged. Priority M.

### FR-ROLE-005 (amended; D-07)

On Contributor revocation/erasure with retention, additional option **"reassign authorship to NDSC house account"** rendering "by NDSC Lab".

### FR-CERT-002 (amended; D-13)

If issuing admin is erased, verification shows "Issued by NDSC Lab (admin record redacted)"; cert remains valid.

### FR-LEG-003 (amended; D-09, D-14)

(a) Until user opts into analytics, no per-user view event recorded. (b) Embedded videos render as click-to-play placeholder until user consents to third-party cookies.

### FR-VIEW-001 (amended; D-05, D-14)

Origin/Referer check; per-user RL 30/min; event accepted only if `cookie_consents.analytics=true`.

### FR-LEG-004 (clarified; D-06)

Erasure pseudonymizes audit-log actor identity references and truncates IP, but audit rows retained for audit-retention period.

### FR-CERT-004 (amended; D-20)

Verify checks `revoked_at IS NULL` before signature verify.

---

## 11. v1.2 additions (post-launch, surfaced during integration & E2E testing 2026-05-16)

### FR-CONTENT-012 (new)

Title: Author can read back the raw source of their own item.

Description: To make the in-app editor a complete authoring tool, the author of an item must be able to fetch the **raw** Markdown (or external URL, video_kind, etc.) of their own drafts and published items, not only the server-rendered HTML.

Sub-requirements:

- **FR-CONTENT-012a** — `GET /items/{id}/raw` returns `{body_md, external_url, video_kind, license, summary, title, slug, state, type}` for owner or admin only; non-owner non-admin gets 404 (no existence leak).
- **FR-CONTENT-012b** — Editor at `/me/content/[id]/edit` prefills the body textarea from FR-CONTENT-012a.
- **FR-CONTENT-012c** — `published` items remain editable by their author; PATCH updates body without changing visibility.

Priority: M. Source: integration test gap.

### FR-VIDEO-006 (new)

Title: Hosted videos must stream to the browser end-to-end.

Description: After a Contributor uploads a hosted video and an Admin publishes the item, any **authenticated** visitor (User / Contributor / Admin) MUST be able to play the video in-browser, with HTTP Range support so the browser can scrub. Anonymous visitors still see the item page (title, summary, byline, license, article body) but the consumable payload — video playback, file downloads, embed-video player — requires login. (Amended 2026-05-20: content gate, see §4 locked decision.)

Sub-requirements:

- **FR-VIDEO-006a** — `GET /items/{item_id}/attachments` returns the public-safe list (`clean` + `published` only); owner/admin see all states. Anonymous callers still receive the metadata list so the item page can render a "log in to watch" prompt.
- **FR-VIDEO-006b** — `GET /uploads/{attachment_id}/stream` streams the file with `Accept-Ranges: bytes`. Range → `206 Content-Range`. API proxies bytes from R2/MinIO. An attachment is streamable iff `state='clean'` AND `parent.state='published'` AND the requester is authenticated (any role: User/Contributor/Admin); owner/admin always (incl. preview while `scanning`). Anonymous → `401 login_required`; non-existent / unpublished / quarantined → `404` (no existence leak). `GET /uploads/{attachment_id}/url` (presigned URL) shares the identical authorization via one helper, so it cannot become a side door.
- **FR-VIDEO-006c** — Item page renders `<video controls>` for hosted videos, click-to-play iframe for embed videos (D-09), and downloadable file list for teaching material.
- **FR-VIDEO-006d** — Background `worker` container drains `queue:scan` (ClamAV) without operator intervention; included in `docker compose up`.

Priority: M. Source: end-to-end gap — users could upload but not watch.

### FR-VIDEO-007 (new)

Title: Auto-transcode non-MP4 hosted videos to a web-friendly format.

Description: Contributors record on phones / cameras that produce `.mov` (QuickTime container, often H.264 inside), `.webm`, `.mkv`, etc. Browsers (Chrome / Firefox / Edge) reject `video/quicktime` outright at the codec-discovery stage even when the inner codec is web-safe. Without transcoding, only Safari users see the video. The platform must automatically convert non-MP4 uploads into H.264/AAC MP4 with `+faststart` for universal browser playback.

Sub-requirements:

- **FR-VIDEO-007a** — `attachment_role` enum gains `video_transcoded` (migration `0003`). The original upload is preserved; the transcoded copy is stored as a sibling attachment on the same item.
- **FR-VIDEO-007b** — Worker picks up cleaned `video_primary` attachments whose MIME is not `video/mp4` and runs `ffmpeg -c:v libx264 -preset veryfast -crf 23 -c:a aac -movflags +faststart -f mp4`. Result is uploaded to R2 and a new `Attachment(role='video_transcoded', state='clean', mime='video/mp4')` row is inserted. Idempotent: skip if a `video_transcoded` already exists for the item.
- **FR-VIDEO-007c** — `ffmpeg` is installed in the api + worker images (`apt-get install ffmpeg` in `apps/api/Dockerfile`).
- **FR-VIDEO-007d** — Frontend `<ItemPlayer>` prefers the `video_transcoded` attachment over the raw `video_primary`. Falls back to original if transcoding hasn't completed yet, with a small inline note ("Converting in the background — refresh to retry").
- **FR-VIDEO-007e** — `GET /items/{id}/attachments` surfaces both attachments to anon (so the player can prefer `video_transcoded`); both must be `clean` to be listed publicly.

Acceptance criteria: (1) `.mov` upload via `/uploads/simple` is auto-detected by the worker after ClamAV clean, enqueued on `queue:transcode`. (2) Worker runs ffmpeg; a new `video_transcoded` row appears with `mime='video/mp4'`. (3) Public listing returns both. (4) Streaming the transcoded URL returns `Content-Type: video/mp4` and a body whose bytes 4-7 are the literal `ftyp` (ISO-BMFF marker). (5) An upload that is already `video/mp4` is **not** re-transcoded (idempotency).

Priority: M. Source: end-to-end testing with `.mov` revealed Chrome/Firefox cannot play QuickTime container even when codec is H.264.
