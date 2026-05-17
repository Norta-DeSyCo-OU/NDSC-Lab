<!-- markdownlint-disable MD013 MD024 MD033 -->
# 03 — Data Model

| Project | NDSC Lab |
|---|---|
| Document version | 1.0 |
| Date frozen | 2026-05-13 |
| Phase | 2 — Architecture & Data Model Design |
| Inputs | `01_requirements.md` v1.0, `02_architecture.md` v1.0 |

> Storage paradigm is fixed by Phase 1 in spirit ("Postgres-friendly"); specific Postgres version chosen in `04_tech_stack.md`. Conventions: all PKs are ULID (sortable, no-collision, public-safe). All timestamps `timestamptz`. All money omitted (deferred). Soft-deletes via `deleted_at timestamptz NULL` where called for.

---

## 1. Storage paradigm per concern

| Concern | Store | Why |
|---|---|---|
| Relational entities (users, items, comments, ...) | Postgres 16 | Strong consistency, FTS, rich constraints, single-vendor simplicity. |
| Sessions | Redis | TTL, fast read on every request. |
| Rate-limit counters | Redis | TTL + atomic INCR. |
| Job queue | Redis (RQ/Dramatiq) | One fewer moving part vs RabbitMQ. |
| Object blobs (videos, files, photos, PDFs, exports) | Cloudflare R2 (S3 API) | Cheap egress (zero to CF CDN), durable. |
| Search index | Postgres FTS (GIN) | Sufficient for v1 scale; no Elastic to operate. |
| Backups | R2 cold bucket (separate IAM) | Off-host durability + cheap. |
| Metrics | Prometheus TSDB (local) | Self-contained. |
| Logs | stdout → Loki (optional) | Lightweight; keep on host. |

---

## 2. ERD overview (high level)

```
                            ┌──────────────────────────┐
                            │ User                     │
                            └────┬────────┬────────────┘
                                 │1       │1
                ┌────────────────┘        └────────────────┐
                │N                                         │N
       ┌────────▼──────┐                          ┌────────▼────────┐
       │ Item (author) │                          │ Comment         │
       └──────┬────────┘                          └─────────────────┘
              │1
              │N
       ┌──────▼───────┐
       │ Attachment   │
       └──────────────┘

User 1..1 ContributorProfile (when role=contributor)
ContributorProfile 1..N ProfileSection
ContributorProfile 1..N Collection
Collection N..M Item via CollectionItem (ordered)
Collection 1..N CourseCompletionCriterion (when is_course)
User × Course → UserCourseProgress (1..1)
User × Course → Certificate (0..N)
Item N..M Tag via ItemTag
Item N..M Category via ItemCategory
User 1..N RawViewEvent
RawViewEvent → aggregated nightly into DailyItemAggregate, DailyContributorAggregate, DailyCategoryAggregate
Workshop N..M ContributorProfile via WorkshopSpeaker
Workshop 0..1 Item (post-event recording link)
```

---

## 3. Entity catalog

For each: purpose, fields, key constraints, indexes, invariants.

### 3.1 Identity & Access

#### `users`

| Field | Type | Notes |
|---|---|---|
| `id` | ulid PK | |
| `email` | citext UNIQUE NOT NULL | citext for case-insensitive uniqueness |
| `email_verified_at` | timestamptz NULL | |
| `display_name` | text NULL | required for contributors |
| `role` | enum `user_role` ('user','contributor','admin') NOT NULL DEFAULT 'user' | |
| `state` | enum `user_state` ('pending_verify','active','banned','deleted') | |
| `password_hash` | text NULL | NULL when OAuth-only |
| `password_changed_at` | timestamptz NULL | |
| `mfa_secret` | bytea NULL | reserved (FR-AUTH-009) |
| `mfa_enabled_at` | timestamptz NULL | reserved |
| `age_confirmed_at` | timestamptz NOT NULL | |
| `tos_version` | text NOT NULL | references `legal_documents.version` |
| `cookie_consent_version` | text NOT NULL | |
| `scope_id` | ulid NULL | reserved for future per-department scoping |
| `created_at` | timestamptz NOT NULL DEFAULT now() | |
| `deleted_at` | timestamptz NULL | |

Indexes: `email`, `(state, role)`, `(created_at)`.

Invariants:

- `state='active'` ⇒ `email_verified_at IS NOT NULL`.
- `role IN ('contributor','admin')` ⇒ `display_name IS NOT NULL`.
- `password_hash IS NULL` ⇒ at least one row in `oauth_identities`.

#### `oauth_identities`

| Field | Type |
|---|---|
| `id` | ulid PK |
| `user_id` | ulid FK → users(id) ON DELETE CASCADE |
| `provider` | enum `oauth_provider` ('google') |
| `subject` | text NOT NULL |
| `created_at` | timestamptz |

Unique `(provider, subject)`.

#### `sessions` (Redis)

Stored in Redis, not Postgres. Key: `session:<sid>` (sid = 32-byte random base64url). Value JSON: `{user_id, csrf, created_at, last_seen, ip, ua}`. TTL 30 d (slide on touch).

#### `login_attempts`

For lockout + forensics.

| Field | Type |
|---|---|
| `id` | bigserial |
| `email_lower` | citext |
| `ip` | inet |
| `success` | bool |
| `created_at` | timestamptz |

Indexes: `(email_lower, created_at)`, `(ip, created_at)`.

Retention: 90 d (job purge).

#### `role_transitions`

| Field | Type |
|---|---|
| `id` | ulid PK |
| `user_id` | ulid FK |
| `from_role` | enum |
| `to_role` | enum |
| `actor_user_id` | ulid FK |
| `reason` | text |
| `created_at` | timestamptz |

#### `contributor_applications`

| Field | Type |
|---|---|
| `id` | ulid PK |
| `user_id` | ulid FK |
| `motivation` | text |
| `links` | jsonb |
| `state` | enum ('pending','approved','rejected','withdrawn') |
| `decision_actor_id` | ulid FK NULL |
| `decision_reason` | text NULL |
| `created_at` | timestamptz |
| `decided_at` | timestamptz NULL |

#### `tos_acceptances`

| Field | Type |
|---|---|
| `id` | ulid PK |
| `user_id` | ulid FK |
| `tos_version` | text |
| `accepted_at` | timestamptz |
| `ip` | inet |

#### `cookie_consents`

| Field | Type |
|---|---|
| `id` | ulid PK |
| `user_id` | ulid FK NULL |  ← also support anon by session cookie ID |
| `anon_id` | text NULL |
| `essential` | bool NOT NULL DEFAULT true |
| `analytics` | bool NOT NULL DEFAULT false |
| `version` | text |
| `created_at` | timestamptz |

### 3.2 Content

#### `items`

| Field | Type | Notes |
|---|---|---|
| `id` | ulid PK | |
| `author_id` | ulid FK users(id) | |
| `type` | enum `item_type` ('video','article','teaching_material') | |
| `video_kind` | enum `video_kind` ('hosted','embed','live') NULL | non-null when type=video; 'live' reserved (FR-VIDEO-005) |
| `title` | text NOT NULL | |
| `slug` | text NOT NULL | unique per author |
| `summary` | text NULL | |
| `body_md` | text NULL | for articles |
| `body_html_cached` | text NULL | sanitized; invalidate on update |
| `external_url` | text NULL | for embed/external |
| `license` | enum `content_license` ('cc-by-4.0','cc-by-sa-4.0','cc-by-nc-4.0','cc0-1.0','arr') DEFAULT 'cc-by-4.0' | FR-CONTENT-010 |
| `paywall_config_id` | ulid NULL | FR-CONTENT-011 (reserved) |
| `state` | enum `item_state` ('draft','pending_review','published','tombstoned') | |
| `published_at` | timestamptz NULL | |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |
| `deleted_at` | timestamptz NULL | |
| `search_vector` | tsvector | generated stored: weight(A,title) + weight(B,summary) + weight(C,body) |

Indexes:

- UNIQUE `(author_id, slug)`.
- `(state, published_at desc)`.
- GIN `search_vector` (FR-SEARCH-001).
- `(author_id, type, published_at desc)`.

Invariants:

- `state='published'` ⇒ `published_at IS NOT NULL`.
- For `type='video'` with `video_kind='hosted'`: at least one attachment of role `video_primary` and state `clean`.
- For `type='article'`: `body_md IS NOT NULL`.

#### `attachments`

For uploaded blobs (video files, article PDFs, teaching material files, profile photos, certificate PDFs).

| Field | Type |
|---|---|
| `id` | ulid PK |
| `owner_user_id` | ulid FK |
| `item_id` | ulid FK NULL | nullable: certificate PDFs aren't items |
| `role` | enum `attachment_role` ('video_primary','article_attachment','teaching_material_file','profile_photo','certificate_pdf','data_export_zip') |
| `r2_key` | text NOT NULL UNIQUE |
| `bytes` | bigint |
| `mime` | text |
| `checksum_sha256` | bytea |
| `state` | enum `attachment_state` ('uploading','scanning','clean','quarantined','deleted') |
| `scanned_at` | timestamptz NULL |
| `created_at` | timestamptz |

Indexes: `(state)`, `(item_id)`, `(owner_user_id, role)`.

Quota enforcement: trigger on INSERT checks per-user sum of clean+scanning bytes against `contributor_tunables.storage_quota_bytes`.

#### `tags`

| Field | Type |
|---|---|
| `id` | ulid PK |
| `name` | text UNIQUE NOT NULL | normalized lower-trimmed |

#### `categories` (admin-managed)

| Field | Type |
|---|---|
| `id` | ulid PK |
| `slug` | text UNIQUE |
| `name` | text |
| `parent_id` | ulid NULL FK self |

#### `item_tags`, `item_categories`

Join tables, PK `(item_id, tag_id)` / `(item_id, category_id)`.

#### `review_submissions`

| Field | Type |
|---|---|
| `id` | ulid PK |
| `item_id` | ulid FK |
| `submitted_by` | ulid FK |
| `state` | enum ('pending','approved','rejected') |
| `decision_actor_id` | ulid NULL |
| `decision_reason` | text NULL |
| `created_at`, `decided_at` | timestamptz |

### 3.3 Curation

#### `contributor_profiles`

1:1 with users where role ∈ {contributor, admin-who-publishes}.

| Field | Type |
|---|---|
| `user_id` | ulid PK FK users(id) |
| `slug` | citext UNIQUE NOT NULL |
| `bio_md` | text |
| `photo_attachment_id` | ulid FK NULL |
| `affiliation` | text |
| `orcid` | text |
| `links` | jsonb | array of `{label, url}`; URLs https only |
| `created_at`, `updated_at` | timestamptz |

Reserved slugs blocked: see `slug_reserved` table.

#### `profile_sections` (ordered, hierarchical)

| Field | Type |
|---|---|
| `id` | ulid PK |
| `profile_user_id` | ulid FK |
| `parent_section_id` | ulid FK NULL self | for subsections |
| `position` | int NOT NULL | sibling ordering |
| `title` | text |
| `body_md` | text |

Indexes: `(profile_user_id, parent_section_id, position)`.

#### `collections`

| Field | Type |
|---|---|
| `id` | ulid PK |
| `owner_user_id` | ulid FK |
| `slug` | text |
| `title` | text |
| `description_md` | text |
| `cover_attachment_id` | ulid NULL FK |
| `is_course` | bool NOT NULL DEFAULT false | |
| `created_at`, `updated_at` | timestamptz |

UNIQUE `(owner_user_id, slug)`.

#### `collection_items`

| Field | Type |
|---|---|
| `collection_id` | ulid FK |
| `item_id` | ulid FK |
| `position` | int |
| `is_required_for_course` | bool DEFAULT true | matters only when collection.is_course |
| PK | `(collection_id, item_id)` |

UNIQUE `(collection_id, position)`.

#### `course_completion_criteria`

Per collection-item, only when course.

| Field | Type |
|---|---|
| `collection_id` | ulid FK |
| `item_id` | ulid FK |
| `rule` | jsonb | `{"video_pct":0.9}` or `{"article_scroll_pct":0.9}` or `{"file_downloaded":true}` |
| PK | `(collection_id, item_id)` |

#### `user_course_progress`

| Field | Type |
|---|---|
| `user_id` | ulid FK |
| `collection_id` | ulid FK |
| `item_id` | ulid FK |
| `state` | enum ('in_progress','completed') |
| `progress` | jsonb | `{"max_watched_s": 432, "max_scroll_pct": 0.91}` |
| `completed_at` | timestamptz NULL |
| PK | `(user_id, collection_id, item_id)` |

Plus rollup view `user_course_state(user_id, collection_id, state)`.

#### `workshops`

| Field | Type |
|---|---|
| `id` | ulid PK |
| `title` | text |
| `slug` | text UNIQUE |
| `abstract_md` | text |
| `starts_at` | timestamptz |
| `ends_at` | timestamptz |
| `location` | text NULL |
| `is_online` | bool |
| `registration_url` | text NULL |
| `recording_item_id` | ulid FK NULL |
| `state` | enum item_state | reuses item-state machine |
| `created_at`, `updated_at` | timestamptz |

#### `workshop_speakers`

| Field | Type |
|---|---|
| `workshop_id` | ulid FK |
| `contributor_user_id` | ulid FK |
| `position` | int |
| PK | `(workshop_id, contributor_user_id)` |

### 3.4 Comments

#### `comments`

| Field | Type |
|---|---|
| `id` | ulid PK |
| `item_id` | ulid FK |
| `author_id` | ulid FK |
| `parent_id` | ulid NULL FK self | reply (single level v1) |
| `body_md` | text |
| `state` | enum ('visible','deleted','hidden_by_admin') |
| `created_at`, `updated_at`, `deleted_at` | timestamptz |

Indexes: `(item_id, created_at)`, `(author_id, created_at)`.

#### `comment_reports`

| Field | Type |
|---|---|
| `id` | ulid PK |
| `comment_id` | ulid FK |
| `reporter_id` | ulid FK NULL |
| `reason` | text |
| `state` | enum ('open','closed','actioned') |
| `decided_by` | ulid NULL |
| `decided_at` | timestamptz NULL |

### 3.5 Analytics

#### `raw_view_events`

| Field | Type |
|---|---|
| `id` | bigserial |
| `user_id` | ulid FK |
| `item_id` | ulid FK |
| `item_type` | enum item_type |
| `category_id` | ulid NULL | denormalized for fast aggregation |
| `contributor_user_id` | ulid | denormalized author |
| `view_session_uuid` | uuid | client-emitted |
| `qualifying_ts` | timestamptz | when threshold crossed |
| `data` | jsonb | `{watched_s, scroll_pct, ua_fp}` |

Partitioned by `qualifying_ts` (monthly). Indexes: `(item_id, qualifying_ts)`, `(contributor_user_id, qualifying_ts)`, `(category_id, qualifying_ts)`.

Retention: 90 d (FR-VIEW-006); partition drop monthly.

#### `daily_item_aggregates`

| Field | Type |
|---|---|
| `day` | date |
| `item_id` | ulid |
| `views` | int |
| PK | `(day, item_id)` |

Plus `daily_contributor_aggregates` and `daily_category_aggregates` analogously.

Aggregates retained indefinitely (FR-VIEW-006).

#### `cert_completion_suggestions`

Pre-computed admin queue entry when a user finishes a course.

| Field | Type |
|---|---|
| `id` | ulid PK |
| `user_id` | ulid FK |
| `collection_id` | ulid FK |
| `created_at` | timestamptz |
| `state` | enum ('open','issued','dismissed') |

### 3.6 Certification

#### `signing_keys`

| Field | Type |
|---|---|
| `id` | ulid PK |
| `key_id` | text UNIQUE | shortid embedded in PDFs |
| `algo` | text | 'ed25519' |
| `public_key_pem` | text |
| `private_key_ref` | text | reference to env-injected secret; private bytes never stored in DB |
| `state` | enum ('active','retired') |
| `created_at`, `retired_at` | timestamptz |

#### `certificates`

| Field | Type |
|---|---|
| `id` | ulid PK | also the public cert ID |
| `user_id` | ulid FK |
| `collection_id` | ulid FK |  ← course
| `issued_by_admin_id` | ulid FK |
| `issued_at` | timestamptz |
| `signing_key_id` | text FK signing_keys(key_id) |
| `signature_b64` | text |
| `pdf_attachment_id` | ulid FK attachments |
| `revoked_at` | timestamptz NULL |
| `revoke_reason` | text NULL |

Public verify endpoint reads this.

### 3.7 Admin & audit

#### `audit_log`

Append-only, hash-chained (NFR-SEC-014).

| Field | Type |
|---|---|
| `id` | bigserial |
| `ts` | timestamptz |
| `actor_user_id` | ulid FK NULL |
| `actor_ip` | inet |
| `actor_ua` | text |
| `action` | text | dotted, e.g., `item.publish`, `user.role.grant` |
| `target_type` | text |
| `target_id` | text |
| `payload` | jsonb |
| `prev_hmac` | bytea NULL |
| `hmac` | bytea NOT NULL |

Indexes: `(ts)`, `(actor_user_id, ts)`, `(action, ts)`, `(target_type, target_id, ts)`.

Retention: default 365 d (FR-ADMIN-003); platform setting can extend.

#### `platform_settings`

KV table.

| Field | Type |
|---|---|
| `key` | text PK |
| `value` | jsonb |
| `updated_by` | ulid |
| `updated_at` | timestamptz |

Initial keys: `view.video_min_s`, `view.article_min_s`, `view.article_scroll_min`, `view.dedup_window_s`, `upload.max_video_bytes`, `upload.max_video_duration_s`, `upload.max_file_bytes`, `upload.mime_allowlist`, `registration.open`, `audit.retention_days`, `age.min_years`, `default.license`, `theme.primary`, `theme.default_mode`.

#### `contributor_tunables`

| Field | Type |
|---|---|
| `user_id` | ulid PK FK |
| `storage_quota_bytes` | bigint |
| `hosted_video_allowed` | bool |
| `embed_only` | bool |
| `max_video_duration_s` | int |
| `updated_by`, `updated_at` | |

#### `announcements`

| Field | Type |
|---|---|
| `id` | ulid PK |
| `severity` | enum ('info','warning','critical') |
| `body_md` | text |
| `starts_at`, `ends_at` | timestamptz |
| `created_by` | ulid |

#### `announcement_dismissals`

| Field | Type |
|---|---|
| `announcement_id` | ulid FK |
| `user_id` | ulid FK |
| `dismissed_at` | timestamptz |
| PK | (announcement_id, user_id) |

#### `email_templates`

| Field | Type |
|---|---|
| `key` | text PK | e.g., `auth.verify`, `cert.issued`, `legal.takedown.complainant` |
| `subject` | text |
| `body_mjml` | text | MJML or plain template (sandboxed) |
| `updated_by`, `updated_at` | |

#### `slug_reserved`

| Field | Type |
|---|---|
| `slug` | citext PK |

Seeded with `admin`, `api`, `c`, `verify`, `legal`, `me`, `auth`, `assets`, ...

### 3.8 Legal & privacy

#### `legal_documents`

| Field | Type |
|---|---|
| `id` | ulid PK |
| `kind` | enum ('tos','privacy') |
| `version` | text UNIQUE per kind |
| `effective_at` | timestamptz |
| `body_md` | text |
| `material_change` | bool | if true, users must re-accept |

#### `takedown_requests`

| Field | Type |
|---|---|
| `id` | ulid PK |
| `complainant_name` | text |
| `complainant_email` | text |
| `complainant_address` | text |
| `target_url` | text |
| `target_item_id` | ulid FK NULL | resolved by admin |
| `sworn_statement` | text |
| `state` | enum ('open','closed_tombstoned','closed_rejected') |
| `decision_actor_id` | ulid NULL |
| `decision_reason` | text NULL |
| `created_at`, `decided_at` | timestamptz |

#### `erasure_requests`

| Field | Type |
|---|---|
| `id` | ulid PK |
| `user_id` | ulid FK |
| `state` | enum ('pending','executing','completed','cancelled') |
| `eta_at` | timestamptz | now()+30d hard ceiling |
| `grace_until` | timestamptz | now()+7d |
| `created_at`, `completed_at` | timestamptz |

#### `data_export_requests`

| Field | Type |
|---|---|
| `id` | ulid PK |
| `user_id` | ulid FK |
| `state` | enum ('pending','building','ready','expired') |
| `zip_attachment_id` | ulid FK NULL |
| `presigned_url_expires_at` | timestamptz |
| `created_at`, `built_at` | timestamptz |

### 3.9 Notifications

#### `outbound_emails`

| Field | Type |
|---|---|
| `id` | ulid PK |
| `to_email` | citext |
| `template_key` | text |
| `payload` | jsonb |
| `state` | enum ('queued','sent','failed','bounced') |
| `resend_id` | text NULL |
| `retry_count` | int |
| `created_at`, `sent_at` | timestamptz |

#### `email_events` (webhook from Resend)

| Field | Type |
|---|---|
| `id` | bigserial |
| `outbound_email_id` | ulid FK |
| `type` | text | delivered, bounced, complained, opened |
| `payload` | jsonb |
| `ts` | timestamptz |

#### `in_app_notifications`

| Field | Type |
|---|---|
| `id` | ulid PK |
| `user_id` | ulid FK |
| `kind` | text |
| `body_md` | text |
| `link_url` | text |
| `read_at` | timestamptz NULL |
| `created_at` | timestamptz |

---

## 4. Indexing intent (summary)

Beyond per-entity indexes above:

- All FK columns have B-tree index.
- All `(user_id, created_at desc)` paginations have composite index.
- `items.search_vector` GIN.
- `audit_log` BRIN on `ts` if volume justifies it; B-tree otherwise.
- `raw_view_events` partitioned by month + B-tree per partition.

---

## 5. Invariants (DB-enforced)

1. Email uniqueness (citext unique).
2. Author of an Item must exist and be active.
3. Item state machine enforced via CHECK + trigger: cannot transition from `tombstoned` to anything; cannot publish without an associated `clean` attachment when type=video&kind=hosted.
4. Per-user storage quota enforced via trigger.
5. Audit-log row insert is the only allowed write (`UPDATE`, `DELETE` blocked by GRANT).
6. Erasure-requested user's writes are blocked at app layer; grace period elapsed deletions are atomic.

---

## 6. Migration strategy

- Tool: Alembic (Python) or sqlx-cli — pick in `04_tech_stack.md`.
- Migrations reversible.
- Every PR with schema change ships migration up + down + a forward-compatibility note (whether old code can run on new schema).
- Initial migration `0001_init.sql` creates everything in §3.

---

## 7. Reserved fields for deferred features

| Field | Defers | Reason |
|---|---|---|
| `users.scope_id` | per-dept admin scoping | architecture-ready |
| `users.mfa_secret`, `users.mfa_enabled_at` | MFA | architecture-ready (CON-008) |
| `items.paywall_config_id` | payments | architecture-ready (Q3) |
| `items.video_kind ∈ {live}` | live streaming | architecture-ready (Q3) |
| signer-service abstraction (no DB column) | W3C VC artifact | architecture-ready (FR-CERT-006) |

---

## 8. Forward traceability — schema → requirements

| Requirement group | Tables |
|---|---|
| FR-AUTH-* | users, oauth_identities, sessions(redis), login_attempts |
| FR-ROLE-* | users, role_transitions, contributor_applications |
| FR-PROFILE-* | contributor_profiles, profile_sections, slug_reserved |
| FR-CONTENT-* | items, attachments, tags, item_tags, categories, item_categories, review_submissions |
| FR-VIDEO-* | items.video_kind, attachments |
| FR-ART-*, FR-TM-* | items, attachments |
| FR-COL-* | collections, collection_items, course_completion_criteria, user_course_progress, cert_completion_suggestions |
| FR-CERT-* | signing_keys, certificates, attachments(certificate_pdf) |
| FR-COM-* | comments, comment_reports |
| FR-VIEW-* | raw_view_events, daily_*_aggregates |
| FR-SEARCH-* | items.search_vector |
| FR-WS-* | workshops, workshop_speakers |
| FR-ADMIN-* | audit_log, platform_settings, contributor_tunables, announcements, email_templates |
| FR-LEG-* | legal_documents, takedown_requests, erasure_requests, data_export_requests, cookie_consents |

---

## 9. Change log

| Date | Change |
|---|---|
| 2026-05-13 | v1.0. |
| 2026-05-13 | v1.1 Phase 6 revision: |

- **D-03**: extend `slug_reserved` enforcement to `items.slug` lookup. Application layer rejects any item slug matching a reserved slug for the author and any globally reserved route.
- **D-04**: add `video_thumbnail` to `attachment_role` enum.
- **D-15**: add generated column `audit_log.canon text generated always as (jsonb_build_object('action',action,'target_type',target_type,'target_id',target_id,'ts',extract(epoch from ts),'payload',payload - ARRAY['ip','ua','email']) ::text) stored`. HMAC chain over `canon`.
- **D-18**: introduce table `upload_rate_buckets(user_id, role, minute_bucket, count)` used by middleware to enforce per-role upload caps (profile photo 1/min, attachments 10/min, etc.) — alternatively implement entirely in Redis ZSET sliding windows.
- **D-13**: add `cert_admin_pseudonyms(original_admin_id, pseudonym_id, redacted_at)` lookup so verification page can display "redacted" while preserving referential integrity.
- **D-17**: aggregator job accepts a `--from <date> --to <date>` for idempotent re-aggregation; daily run aggregates last 7 days to absorb gaps.
- **D-12**: `items.state='tombstoned'` now hides comments at query layer regardless of comment state.

Schema delta (one migration `0002_phase6_amendments.sql`):

```sql
ALTER TYPE attachment_role ADD VALUE 'video_thumbnail';
ALTER TABLE audit_log ADD COLUMN canon text GENERATED ALWAYS AS (
  jsonb_build_object(
    'action', action,
    'target_type', target_type,
    'target_id', target_id,
    'ts_epoch', extract(epoch from ts),
    'payload_pruned', payload - 'ip' - 'ua' - 'email'
  )::text
) STORED;
CREATE TABLE cert_admin_pseudonyms (
  original_admin_id ulid PRIMARY KEY,
  pseudonym_id ulid NOT NULL,
  redacted_at timestamptz NOT NULL DEFAULT now()
);
```
