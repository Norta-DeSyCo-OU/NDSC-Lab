"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost, apiPatch, apiDelete, ApiError } from "@/lib/api";
import { Field } from "@/components/Field";
import { Alert } from "@/components/Alert";
import { FilePicker } from "@/components/FilePicker";

type Profile = {
  user_id: string;
  slug: string | null;
  display_name: string | null;
  bio_md: string | null;
  affiliation: string | null;
  orcid: string | null;
  links: { label: string; url: string }[] | null;
  contacts: { kind: "email" | "phone"; value: string; label: string | null }[] | null;
  photo_url: string | null;
  role: string;
};

type Contact = { kind: "email" | "phone"; value: string; label: string };

type Section = {
  id: string;
  title: string;
  body_md: string | null;
  position: number;
};

export const dynamic = "force-dynamic";

function csrfCookie(): string {
  const m = document.cookie.match(/(?:^|; )ndsc_csrf=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

export default function ProfileEditor() {
  const [p, setP] = useState<Profile | null>(null);
  const [slug, setSlug] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [bio, setBio] = useState("");
  const [aff, setAff] = useState("");
  const [orcid, setOrcid] = useState("");
  const [linksRows, setLinksRows] = useState<{ label: string; url: string }[]>([]);
  const [contactRows, setContactRows] = useState<Contact[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState(false);

  // Sections state
  const [sections, setSections] = useState<Section[]>([]);
  const [secTitle, setSecTitle] = useState("");
  const [secBody, setSecBody] = useState("");
  const [secPos, setSecPos] = useState<number>(0);
  const [secBusy, setSecBusy] = useState(false);
  const [secErr, setSecErr] = useState<string | null>(null);

  // Photo state
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoBusy, setPhotoBusy] = useState(false);
  const [photoErr, setPhotoErr] = useState<string | null>(null);
  const [photoBust, setPhotoBust] = useState<number>(Date.now());

  async function loadAll() {
    try {
      const prof = await apiGet<Profile>("/me/profile");
      setP(prof);
      setSlug(prof.slug ?? "");
      setDisplayName(prof.display_name ?? "");
      setBio(prof.bio_md ?? "");
      setAff(prof.affiliation ?? "");
      setOrcid(prof.orcid ?? "");
      setLinksRows((prof.links ?? []).map((l) => ({ label: l.label, url: l.url })));
      setContactRows(
        (prof.contacts ?? []).map((c) => ({
          kind: c.kind,
          value: c.value,
          label: c.label ?? "",
        })),
      );
      if (prof.role !== "user") {
        const secs = await apiGet<Section[]>("/me/profile/sections");
        setSections(secs);
      }
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : String(e));
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setOk(false);
    setBusy(true);
    try {
      const csrf = csrfCookie();
      const linksArr = linksRows
        .map((r) => ({ label: r.label.trim(), url: r.url.trim() }))
        .filter((r) => r.label && /^https?:\/\//i.test(r.url));
      const contactsArr = contactRows
        .map((c) => ({
          kind: c.kind,
          value: c.value.trim(),
          label: c.label.trim() || null,
        }))
        .filter((c) => c.value);
      const r = await fetch("/api/me/profile", {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify({
          slug: slug || null,
          display_name: displayName || null,
          bio_md: bio || null,
          affiliation: aff || null,
          orcid: orcid || null,
          links: linksArr,
          contacts: contactsArr,
        }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error((data as { detail?: string }).detail ?? `${r.status}`);
      setOk(true);
      setP(data as Profile);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function uploadPhoto(e: React.FormEvent) {
    e.preventDefault();
    if (!photoFile) return;
    setPhotoErr(null);
    setPhotoBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", photoFile);
      const csrf = csrfCookie();
      const r = await fetch("/api/me/profile/photo", {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRF-Token": csrf },
        body: fd,
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error((data as { detail?: string }).detail ?? `${r.status}`);
      setPhotoBust(Date.now());
      setPhotoFile(null);
      await loadAll();
    } catch (e) {
      setPhotoErr(String(e));
    } finally {
      setPhotoBusy(false);
    }
  }

  async function deletePhoto() {
    if (!confirm("Remove the current profile photo?")) return;
    setPhotoBusy(true);
    setPhotoErr(null);
    try {
      const csrf = csrfCookie();
      const r = await fetch("/api/me/profile/photo", {
        method: "DELETE",
        credentials: "include",
        headers: { "X-CSRF-Token": csrf },
      });
      if (!r.ok) throw new Error(`${r.status}`);
      setPhotoBust(Date.now());
      await loadAll();
    } catch (e) {
      setPhotoErr(String(e));
    } finally {
      setPhotoBusy(false);
    }
  }

  async function addSection(e: React.FormEvent) {
    e.preventDefault();
    if (!secTitle.trim()) return;
    setSecErr(null);
    setSecBusy(true);
    try {
      const created = await apiPost<Section>("/me/profile/sections", {
        title: secTitle,
        body_md: secBody || null,
        position: secPos,
      });
      setSections((rs) => [...rs, created].sort((a, b) => a.position - b.position));
      setSecTitle("");
      setSecBody("");
      setSecPos(sections.length + 1);
    } catch (e) {
      setSecErr(e instanceof ApiError ? e.code : String(e));
    } finally {
      setSecBusy(false);
    }
  }

  async function patchSection(id: string, fields: Partial<Section>) {
    try {
      const updated = await apiPatch<Section>(`/me/profile/sections/${id}`, fields);
      setSections((rs) =>
        rs.map((r) => (r.id === id ? updated : r)).sort((a, b) => a.position - b.position),
      );
    } catch (e) {
      setSecErr(e instanceof ApiError ? e.code : String(e));
    }
  }

  async function deleteSection(id: string) {
    if (!confirm("Delete this section?")) return;
    try {
      await apiDelete(`/me/profile/sections/${id}`);
      setSections((rs) => rs.filter((r) => r.id !== id));
    } catch (e) {
      setSecErr(e instanceof ApiError ? e.code : String(e));
    }
  }

  if (!p)
    return (
      <p role="status" aria-live="polite" className="text-sm text-[var(--color-fg-muted)]">
        Loading…
      </p>
    );
  if (p.role === "user")
    return (
      <Alert kind="warn">
        Apply to become a contributor first. <a href="/me/contributor">Apply</a>.
      </Alert>
    );

  return (
    <section className="max-w-3xl mx-auto space-y-8">
      <header>
        <h1 className="text-2xl font-bold">My public profile</h1>
        {p.slug && (
          <p className="text-sm text-[var(--color-fg-muted)]">
            Live at{" "}
            <a href={`/c/${p.slug}`} target="_blank" rel="noopener noreferrer">
              /c/{p.slug}
            </a>
          </p>
        )}
      </header>

      {/* Photo */}
      <section
        aria-labelledby="photo-h"
        className="border border-[var(--color-brand-blue-4)] rounded p-4 space-y-3 bg-[var(--color-bg-panel)]"
      >
        <h2 id="photo-h" className="font-semibold">
          Profile photo
        </h2>
        <div className="flex items-center gap-4">
          {p.photo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={`${p.photo_url}?v=${photoBust}`}
              alt={`Profile photo of ${p.slug}`}
              width={96}
              height={96}
              className="w-24 h-24 rounded-full object-cover border border-[var(--color-brand-blue-4)]"
            />
          ) : (
            <div className="w-24 h-24 rounded-full bg-[var(--color-bg-base)] border border-[var(--color-brand-blue-4)] flex items-center justify-center text-xs text-[var(--color-fg-muted)]">
              no photo
            </div>
          )}
          <form onSubmit={uploadPhoto} className="flex flex-wrap items-center gap-2">
            <FilePicker
              id="profile-photo-picker"
              accept="image/png,image/jpeg,image/webp,.png,.jpg,.jpeg,.webp"
              file={photoFile}
              onChange={setPhotoFile}
              buttonLabel="Choose image"
              placeholder="No image selected"
              disabled={photoBusy}
            />
            <button
              type="submit"
              disabled={!photoFile || photoBusy}
              className="px-3 py-1.5 bg-[var(--color-brand-cyan)] text-black rounded text-sm font-medium disabled:opacity-60"
            >
              {photoBusy ? "Uploading…" : photoFile ? "Upload photo" : "Pick a file first"}
            </button>
            {p.photo_url && (
              <button
                type="button"
                onClick={deletePhoto}
                disabled={photoBusy}
                className="px-3 py-1.5 border border-red-500 text-red-300 rounded text-sm"
              >
                Remove
              </button>
            )}
          </form>
        </div>
        <p className="text-xs text-[var(--color-fg-muted)]">
          PNG / JPEG / WEBP, up to 5 MB. Shown on your public page, contributor cards, and item bylines.
        </p>
        {photoErr && <Alert kind="error">{photoErr}</Alert>}
      </section>

      {/* Identity */}
      <section
        aria-labelledby="ident-h"
        className="border border-[var(--color-brand-blue-4)] rounded p-4 space-y-3 bg-[var(--color-bg-panel)]"
      >
        <h2 id="ident-h" className="font-semibold">
          Identity
        </h2>
        <form onSubmit={save} className="space-y-3">
          <div className="space-y-1">
            <label htmlFor="display-name" className="block text-sm">
              Display name
            </label>
            <input
              id="display-name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              maxLength={120}
              placeholder="e.g. Sowelu Avanzo"
              className="w-full px-3 py-2 rounded bg-[var(--color-bg-base)] border border-[var(--color-brand-blue-4)]"
            />
            <p className="text-xs text-[var(--color-fg-muted)]">
              Shown on the contributors directory, your public page header, and item bylines. Free-form (capitals, spaces, accents). Leave blank to fall back to your handle.
            </p>
          </div>

          <div className="space-y-1">
            <label htmlFor="slug" className="block text-sm">
              Page handle <span className="text-red-300">*</span>
            </label>
            <div className="flex flex-wrap items-center gap-1 text-sm">
              <span className="text-[var(--color-fg-muted)] font-mono">
                {typeof window !== "undefined" ? window.location.origin : ""}/c/
              </span>
              <input
                id="slug"
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                required
                placeholder="your-handle"
                className="flex-1 min-w-32 px-2 py-1 rounded bg-[var(--color-bg-base)] border border-[var(--color-brand-blue-4)] font-mono"
              />
            </div>
            <p className="text-xs text-[var(--color-fg-muted)]">
              This is the public web address of your profile on NDSC Lab, not an external URL. Lowercase letters, digits, dashes. External links (LinkedIn, GitHub, personal website…) go in the &quot;Social &amp; external links&quot; section below.
            </p>
          </div>

          <div className="space-y-1">
            <label htmlFor="bio" className="block text-sm">
              Bio (Markdown)
            </label>
            <textarea
              id="bio"
              rows={6}
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              className="w-full px-3 py-2 rounded bg-[var(--color-bg-base)] border border-[var(--color-brand-blue-4)]"
            />
          </div>
          <Field label="Affiliation" value={aff} onChange={setAff} placeholder="Norta DeSyCo OU" />
          <Field
            label="ORCID"
            value={orcid}
            onChange={setOrcid}
            placeholder="0000-0000-0000-0000"
          />

          <LinksEditor rows={linksRows} setRows={setLinksRows} />
          <ContactsEditor rows={contactRows} setRows={setContactRows} />

          {ok && <Alert kind="success">Profile saved.</Alert>}
          {err && <Alert kind="error">{err}</Alert>}
          <button
            type="submit"
            disabled={busy}
            className="px-4 py-2 bg-[var(--color-brand-cyan)] text-black rounded font-medium disabled:opacity-60"
          >
            {busy ? "Saving…" : "Save"}
          </button>
        </form>
      </section>

      {/* Custom sections */}
      <section
        aria-labelledby="sec-h"
        className="border border-[var(--color-brand-blue-4)] rounded p-4 space-y-3 bg-[var(--color-bg-panel)]"
      >
        <h2 id="sec-h" className="font-semibold">
          Custom sections
        </h2>
        <p className="text-xs text-[var(--color-fg-muted)]">
          Add free-form blocks to your public page (e.g. <em>Publications</em>, <em>Awards</em>, <em>Teaching</em>). Lower position numbers appear first.
        </p>

        {secErr && <Alert kind="error">{secErr}</Alert>}

        <ul className="space-y-3">
          {sections.map((sec) => (
            <SectionEditor
              key={sec.id}
              sec={sec}
              onPatch={(fields) => patchSection(sec.id, fields)}
              onDelete={() => deleteSection(sec.id)}
            />
          ))}
        </ul>

        <form
          onSubmit={addSection}
          className="border border-dashed border-[var(--color-brand-blue-4)] rounded p-3 space-y-2"
        >
          <h3 className="text-sm font-semibold">Add new section</h3>
          <div className="grid grid-cols-1 sm:grid-cols-[1fr_6rem] gap-2">
            <input
              type="text"
              value={secTitle}
              onChange={(e) => setSecTitle(e.target.value)}
              placeholder="Section title (e.g. Publications)"
              className="px-2 py-1 rounded bg-[var(--color-bg-base)] border border-[var(--color-brand-blue-4)] text-sm"
              required
            />
            <input
              type="number"
              value={secPos}
              onChange={(e) => setSecPos(Number(e.target.value))}
              aria-label="Position"
              className="px-2 py-1 rounded bg-[var(--color-bg-base)] border border-[var(--color-brand-blue-4)] text-sm"
              placeholder="Order"
            />
          </div>
          <textarea
            rows={4}
            value={secBody}
            onChange={(e) => setSecBody(e.target.value)}
            placeholder="Body (Markdown). Lists, links, formatting."
            className="w-full px-3 py-2 rounded bg-[var(--color-bg-base)] border border-[var(--color-brand-blue-4)] font-mono text-xs"
          />
          <button
            type="submit"
            disabled={secBusy || !secTitle.trim()}
            className="px-3 py-1 bg-[var(--color-brand-cyan)] text-black rounded text-sm font-medium disabled:opacity-60"
          >
            {secBusy ? "Adding…" : "Add section"}
          </button>
        </form>
      </section>
    </section>
  );
}

const LINK_PRESETS: { label: string; placeholder: string; match: RegExp }[] = [
  { label: "LinkedIn", placeholder: "https://www.linkedin.com/in/your-handle", match: /linkedin\.com/i },
  { label: "GitHub", placeholder: "https://github.com/your-handle", match: /github\.com/i },
  { label: "X (Twitter)", placeholder: "https://x.com/your-handle", match: /(twitter|x)\.com/i },
  { label: "Mastodon", placeholder: "https://mastodon.social/@you", match: /mastodon|@.+@.+/i },
  { label: "Bluesky", placeholder: "https://bsky.app/profile/you.bsky.social", match: /bsky\.app/i },
  { label: "Google Scholar", placeholder: "https://scholar.google.com/citations?user=…", match: /scholar\.google/i },
  { label: "ResearchGate", placeholder: "https://www.researchgate.net/profile/…", match: /researchgate/i },
  { label: "Website", placeholder: "https://example.com", match: /.*/ },
  { label: "YouTube", placeholder: "https://www.youtube.com/@you", match: /youtube\.com|youtu\.be/i },
];

function autoLabel(url: string): string {
  if (!url) return "";
  for (const p of LINK_PRESETS) {
    if (p.label === "Website") continue;
    if (p.match.test(url)) return p.label;
  }
  try {
    const u = new URL(url);
    return u.hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

function LinksEditor({
  rows,
  setRows,
}: {
  rows: { label: string; url: string }[];
  setRows: React.Dispatch<React.SetStateAction<{ label: string; url: string }[]>>;
}) {
  function update(i: number, patch: Partial<{ label: string; url: string }>) {
    setRows((rs) => rs.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }
  function remove(i: number) {
    setRows((rs) => rs.filter((_, idx) => idx !== i));
  }
  function addRow(preset?: { label: string; placeholder: string }) {
    setRows((rs) => [
      ...rs,
      preset ? { label: preset.label, url: "" } : { label: "", url: "" },
    ]);
  }

  return (
    <fieldset className="space-y-2 border border-[var(--color-brand-blue-4)] rounded p-3">
      <legend className="px-1 text-sm font-semibold">Social &amp; external links</legend>
      <p className="text-xs text-[var(--color-fg-muted)]">
        These appear at the top-right of your public page (e.g. LinkedIn, GitHub, your lab&apos;s website). Each row is one button on your profile.
      </p>

      <ul className="space-y-2">
        {rows.length === 0 && (
          <li className="text-xs text-[var(--color-fg-muted)] italic">
            No links yet. Add one below.
          </li>
        )}
        {rows.map((r, i) => {
          const detected = autoLabel(r.url);
          return (
            <li
              key={i}
              className="grid grid-cols-1 sm:grid-cols-[10rem_1fr_auto] gap-2 items-center"
            >
              <input
                value={r.label}
                onChange={(e) => update(i, { label: e.target.value })}
                placeholder={detected || "Label"}
                aria-label={`Link ${i + 1} label`}
                className="px-2 py-1 rounded bg-[var(--color-bg-base)] border border-[var(--color-brand-blue-4)] text-sm"
              />
              <input
                type="url"
                value={r.url}
                onChange={(e) => {
                  const url = e.target.value;
                  // Auto-fill label if user hasn't typed one yet.
                  if (!r.label.trim()) {
                    const guess = autoLabel(url);
                    if (guess) {
                      update(i, { url, label: guess });
                      return;
                    }
                  }
                  update(i, { url });
                }}
                placeholder="https://…"
                aria-label={`Link ${i + 1} URL`}
                className="px-2 py-1 rounded bg-[var(--color-bg-base)] border border-[var(--color-brand-blue-4)] text-sm font-mono"
              />
              <button
                type="button"
                onClick={() => remove(i)}
                aria-label={`Remove link ${i + 1}`}
                className="text-red-300 underline text-xs px-2"
              >
                Remove
              </button>
            </li>
          );
        })}
      </ul>

      <div className="flex flex-wrap gap-2 pt-2">
        <button
          type="button"
          onClick={() => addRow()}
          className="px-3 py-1 bg-[var(--color-brand-cyan)] text-black rounded text-sm font-medium"
        >
          + Add link
        </button>
        <div className="flex flex-wrap items-center gap-1 text-xs">
          <span className="text-[var(--color-fg-muted)]">Quick add:</span>
          {LINK_PRESETS.filter((p) => p.label !== "Website").map((p) => (
            <button
              key={p.label}
              type="button"
              onClick={() => addRow(p)}
              className="px-2 py-0.5 border border-[var(--color-brand-blue-2)] rounded hover:border-[var(--color-brand-cyan)]"
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>
    </fieldset>
  );
}

function ContactsEditor({
  rows,
  setRows,
}: {
  rows: Contact[];
  setRows: React.Dispatch<React.SetStateAction<Contact[]>>;
}) {
  function update(i: number, patch: Partial<Contact>) {
    setRows((rs) => rs.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }
  function remove(i: number) {
    setRows((rs) => rs.filter((_, idx) => idx !== i));
  }
  function add(kind: "email" | "phone") {
    setRows((rs) => [...rs, { kind, value: "", label: "" }]);
  }

  return (
    <fieldset className="space-y-2 border border-[var(--color-brand-blue-4)] rounded p-3">
      <legend className="px-1 text-sm font-semibold">Contacts</legend>
      <p className="text-xs text-[var(--color-fg-muted)]">
        Email addresses and phone numbers shown on your public page (e.g. work email, lab phone). Add as many as you need. Optional <em>label</em> appears in front (e.g. &quot;Work&quot;, &quot;Lab&quot;).
      </p>

      <ul className="space-y-2">
        {rows.length === 0 && (
          <li className="text-xs text-[var(--color-fg-muted)] italic">
            No contacts yet. Use the buttons below to add one.
          </li>
        )}
        {rows.map((c, i) => (
          <li
            key={i}
            className="grid grid-cols-1 sm:grid-cols-[6rem_8rem_1fr_auto] gap-2 items-center"
          >
            <select
              value={c.kind}
              onChange={(e) => update(i, { kind: e.target.value as "email" | "phone" })}
              aria-label={`Contact ${i + 1} kind`}
              className="px-2 py-1 rounded bg-[var(--color-bg-base)] border border-[var(--color-brand-blue-4)] text-sm"
            >
              <option value="email">Email</option>
              <option value="phone">Phone</option>
            </select>
            <input
              value={c.label}
              onChange={(e) => update(i, { label: e.target.value })}
              placeholder="Label (optional)"
              aria-label={`Contact ${i + 1} label`}
              className="px-2 py-1 rounded bg-[var(--color-bg-base)] border border-[var(--color-brand-blue-4)] text-sm"
            />
            <input
              type={c.kind === "email" ? "email" : "tel"}
              value={c.value}
              onChange={(e) => update(i, { value: e.target.value })}
              placeholder={c.kind === "email" ? "you@example.com" : "+1 555 0100"}
              aria-label={`Contact ${i + 1} value`}
              className="px-2 py-1 rounded bg-[var(--color-bg-base)] border border-[var(--color-brand-blue-4)] text-sm font-mono"
            />
            <button
              type="button"
              onClick={() => remove(i)}
              aria-label={`Remove contact ${i + 1}`}
              className="text-red-300 underline text-xs px-2"
            >
              Remove
            </button>
          </li>
        ))}
      </ul>

      <div className="flex flex-wrap gap-2 pt-2">
        <button
          type="button"
          onClick={() => add("email")}
          className="px-3 py-1 bg-[var(--color-brand-cyan)] text-black rounded text-sm font-medium"
        >
          + Add email
        </button>
        <button
          type="button"
          onClick={() => add("phone")}
          className="px-3 py-1 border border-[var(--color-brand-cyan)] text-[var(--color-brand-cyan)] rounded text-sm font-medium"
        >
          + Add phone
        </button>
      </div>
    </fieldset>
  );
}

function SectionEditor({
  sec,
  onPatch,
  onDelete,
}: {
  sec: Section;
  onPatch: (fields: Partial<Section>) => Promise<void>;
  onDelete: () => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(sec.title);
  const [body, setBody] = useState(sec.body_md ?? "");
  const [position, setPosition] = useState(sec.position);

  if (!editing) {
    return (
      <li className="border border-[var(--color-brand-blue-4)] rounded p-3 bg-[var(--color-bg-base)]">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="font-semibold">{sec.title}</h3>
          <div className="flex gap-2 text-xs">
            <span className="text-[var(--color-fg-muted)]">pos {sec.position}</span>
            <button type="button" onClick={() => setEditing(true)} className="underline">
              Edit
            </button>
            <button type="button" onClick={onDelete} className="text-red-300 underline">
              Delete
            </button>
          </div>
        </div>
        {sec.body_md && (
          <p className="text-sm text-[var(--color-fg-muted)] mt-1 whitespace-pre-wrap">
            {sec.body_md}
          </p>
        )}
      </li>
    );
  }
  return (
    <li className="border border-[var(--color-brand-cyan)] rounded p-3 space-y-2 bg-[var(--color-bg-base)]">
      <div className="grid grid-cols-1 sm:grid-cols-[1fr_6rem] gap-2">
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="px-2 py-1 rounded bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)] text-sm"
        />
        <input
          type="number"
          value={position}
          onChange={(e) => setPosition(Number(e.target.value))}
          className="px-2 py-1 rounded bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)] text-sm"
        />
      </div>
      <textarea
        rows={4}
        value={body}
        onChange={(e) => setBody(e.target.value)}
        className="w-full px-3 py-2 rounded bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)] font-mono text-xs"
      />
      <div className="flex gap-2">
        <button
          type="button"
          onClick={async () => {
            await onPatch({ title, body_md: body, position });
            setEditing(false);
          }}
          className="px-3 py-1 bg-[var(--color-brand-cyan)] text-black rounded text-sm font-medium"
        >
          Save
        </button>
        <button
          type="button"
          onClick={() => {
            setTitle(sec.title);
            setBody(sec.body_md ?? "");
            setPosition(sec.position);
            setEditing(false);
          }}
          className="px-3 py-1 border border-[var(--color-brand-blue-2)] rounded text-sm"
        >
          Cancel
        </button>
      </div>
    </li>
  );
}
