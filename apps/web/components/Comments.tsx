"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useMe } from "@/lib/useMe";
import { Alert } from "@/components/Alert";

type Comment = {
  id: string;
  item_id: string;
  author_id: string;
  parent_id: string | null;
  body_md: string;
  body_html: string;
  state: string;
  created_at: string;
  updated_at: string;
};

export function Comments({ itemId }: { itemId: string }) {
  const { me } = useMe();
  const [rows, setRows] = useState<Comment[]>([]);
  const [text, setText] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      setRows(await apiGet<Comment[]>(`/items/${itemId}/comments?limit=100`));
    } catch (e) {
      setRows([]);
    }
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [itemId]);

  async function post(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await apiPost(`/items/${itemId}/comments`, { body_md: text });
      setText("");
      await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function del(c: Comment) {
    if (!confirm("Delete this comment?")) return;
    try {
      const csrf = csrfCookie();
      const r = await fetch(`/api/comments/${c.id}`, {
        method: "DELETE",
        credentials: "include",
        headers: { "X-CSRF-Token": csrf },
      });
      if (!r.ok) throw new Error(`${r.status}`);
      await load();
    } catch (e) {
      alert(String(e));
    }
  }

  return (
    <section aria-labelledby="comments-h" className="mt-10 border-t border-[var(--color-brand-blue-4)] pt-6 space-y-4">
      <h2 id="comments-h" className="text-xl font-semibold">
        Discussion
      </h2>

      {me ? (
        <form onSubmit={post} className="space-y-2">
          <label htmlFor="comment-body" className="sr-only">
            Write a comment
          </label>
          <textarea
            id="comment-body"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Markdown supported. Be civil."
            rows={3}
            required
            maxLength={5000}
            className="w-full px-3 py-2 rounded bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)]"
          />
          {err && <Alert kind="error">{err}</Alert>}
          <button
            type="submit"
            disabled={busy || !text.trim()}
            className="px-3 py-1 bg-[var(--color-brand-cyan)] text-black rounded text-sm font-medium disabled:opacity-60"
          >
            {busy ? "Posting…" : "Post"}
          </button>
        </form>
      ) : (
        <p className="text-sm text-[var(--color-fg-muted)]">
          <a href="/auth/login">Sign in</a> to participate.
        </p>
      )}

      <ul className="space-y-3">
        {rows.map((c) => (
          <li
            key={c.id}
            className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded p-3 space-y-1"
          >
            <div className="text-xs text-[var(--color-fg-muted)] flex justify-between">
              <span className="font-mono">{c.author_id.slice(0, 8)}…</span>
              <time dateTime={c.created_at}>
                {new Date(c.created_at).toLocaleString()}
              </time>
            </div>
            <div
              className="prose prose-invert prose-sm max-w-none text-sm"
              dangerouslySetInnerHTML={{ __html: c.body_html }}
            />
            {me && (me.id === c.author_id || me.role === "admin") && (
              <button
                type="button"
                onClick={() => del(c)}
                className="text-xs text-red-400"
              >
                Delete
              </button>
            )}
          </li>
        ))}
        {rows.length === 0 && (
          <li className="text-sm text-[var(--color-fg-muted)]">No comments yet.</li>
        )}
      </ul>
    </section>
  );
}

function csrfCookie(): string {
  const m = document.cookie.match(/(?:^|; )ndsc_csrf=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}
