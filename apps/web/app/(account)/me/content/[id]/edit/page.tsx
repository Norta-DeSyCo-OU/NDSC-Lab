"use client";

import { use, useEffect, useState } from "react";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { Field } from "@/components/Field";
import { Alert } from "@/components/Alert";
import { MarkdownPreview } from "@/components/MarkdownPreview";
import { AttachmentManager } from "@/components/AttachmentManager";

type Item = {
  id: string;
  type: string;
  title: string;
  slug: string;
  state: string;
  summary: string | null;
  body_html: string | null;
  license: string;
  published_at: string | null;
};

export const dynamic = "force-dynamic";

export default function EditItemPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [it, setIt] = useState<Item | null>(null);
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [body, setBody] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState(false);
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const i = await apiGet<Item>(`/items/${id}`);
      setIt(i);
      setTitle(i.title);
      setSummary(i.summary ?? "");
      // body_html is server-rendered; we need raw md — fetch via /me/items + a body field on read.
      // For now use body_html stripped (rough), but show edit warning if missing.
      // TODO: add /items/{id}/raw endpoint for owners.
      setBody(""); // user re-writes if missing
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : String(e));
    }
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function save() {
    setErr(null);
    setOk(false);
    setBusy(true);
    try {
      const csrf = csrfCookie();
      const r = await fetch(`/api/items/${id}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify({
          title: title || null,
          summary: summary || null,
          body_md: body || null,
        }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error((data as { detail?: string }).detail ?? `${r.status}`);
      setOk(true);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function submitReview() {
    try {
      await apiPost(`/items/${id}/submit`, {});
      await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : String(e));
    }
  }

  if (!it)
    return (
      <p role="status" aria-live="polite" className="text-sm text-[var(--color-fg-muted)]">
        Loading…
      </p>
    );

  return (
    <section className="max-w-3xl mx-auto space-y-5">
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Edit item</h1>
          <p className="text-xs text-[var(--color-fg-muted)]">
            State: <code>{it.state}</code> · Type: <code>{it.type}</code>
          </p>
        </div>
        {it.state === "published" && (
          <a
            href={`/items/${it.id}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm underline"
          >
            View public page ↗
          </a>
        )}
      </header>

      {it.state !== "draft" && (
        <Alert kind="warn">
          This item is in state <code>{it.state}</code>. Editing may be limited until it returns to
          draft.
        </Alert>
      )}

      <Field label="Title" value={title} onChange={setTitle} required minLength={3} />
      <Field label="Summary" value={summary} onChange={setSummary} />

      <div className="space-y-1">
        <label htmlFor="body" className="block text-sm">
          Body (Markdown)
        </label>
        <textarea
          id="body"
          rows={14}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Paste your Markdown here. Leave empty to keep current body."
          className="w-full px-3 py-2 rounded bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)] font-mono text-sm"
        />
        <p className="text-xs text-[var(--color-fg-muted)]">
          For privacy, the editor does not pre-fill the saved Markdown back into the textarea. Leave
          empty to keep the current body; rewrite to replace it.
        </p>
      </div>

      {body && <MarkdownPreview value={body} />}

      {it.body_html && (
        <details className="border border-[var(--color-brand-blue-4)] rounded">
          <summary className="px-3 py-2 cursor-pointer text-sm text-[var(--color-fg-muted)]">
            Show current rendered body
          </summary>
          <div
            className="prose prose-invert max-w-none px-3 py-2"
            dangerouslySetInnerHTML={{ __html: it.body_html }}
          />
        </details>
      )}

      {ok && <Alert kind="success">Saved.</Alert>}
      {err && <Alert kind="error">{err}</Alert>}

      <AttachmentManager
        itemId={it.id}
        defaultRole={
          it.type === "video"
            ? "video_primary"
            : it.type === "teaching_material"
              ? "teaching_material_file"
              : "article_attachment"
        }
        allowedRoles={
          it.type === "video"
            ? ["video_primary"]
            : it.type === "teaching_material"
              ? ["teaching_material_file"]
              : ["article_attachment"]
        }
      />

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={save}
          disabled={busy}
          className="px-4 py-2 border border-[var(--color-brand-blue-2)] rounded disabled:opacity-60"
        >
          {busy ? "Saving…" : "Save"}
        </button>
        {it.state === "draft" && (
          <button
            type="button"
            onClick={submitReview}
            className="px-4 py-2 bg-[var(--color-brand-cyan)] text-black rounded font-medium"
          >
            Submit for review
          </button>
        )}
      </div>
    </section>
  );
}

function csrfCookie(): string {
  const m = document.cookie.match(/(?:^|; )ndsc_csrf=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}
