"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiPost, ApiError } from "@/lib/api";
import { useMe } from "@/lib/useMe";

function csrfCookie(): string {
  const m = document.cookie.match(/(?:^|; )ndsc_csrf=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

export function AdminItemActions({
  itemId,
  state,
}: {
  itemId: string;
  state: string;
}) {
  const { me } = useMe();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  if (!me || me.role !== "admin") return null;

  async function unpublish() {
    if (!confirm("Unpublish this item? It returns to draft and is hidden from the public.")) return;
    setBusy(true);
    setErr(null);
    try {
      await apiPost(`/admin/items/${itemId}/unpublish`, {});
      router.refresh();
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function del() {
    if (
      !confirm(
        "Permanently tombstone this item? It will be hidden from search and the public, and the action is logged in the audit trail.",
      )
    )
      return;
    setBusy(true);
    setErr(null);
    try {
      const r = await fetch(`/api/admin/items/${itemId}`, {
        method: "DELETE",
        credentials: "include",
        headers: { "X-CSRF-Token": csrfCookie() },
      });
      if (!r.ok) throw new Error(`${r.status}`);
      router.push("/discover");
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside
      aria-label="Admin moderation"
      className="border border-yellow-500/60 bg-[var(--color-bg-panel)] rounded p-3 flex flex-wrap items-center justify-between gap-3"
    >
      <div className="text-xs">
        <strong className="text-yellow-300">Admin moderation</strong>{" "}
        <span className="text-[var(--color-fg-muted)]">
          · current state: <code>{state}</code>
        </span>
      </div>
      <div className="flex gap-2">
        {state === "published" && (
          <button
            type="button"
            onClick={unpublish}
            disabled={busy}
            className="text-xs px-3 py-1 border border-[var(--color-brand-blue-2)] rounded disabled:opacity-60"
          >
            {busy ? "Working…" : "Unpublish"}
          </button>
        )}
        {state !== "tombstoned" && (
          <button
            type="button"
            onClick={del}
            disabled={busy}
            className="text-xs px-3 py-1 border border-red-500 text-red-300 rounded disabled:opacity-60"
          >
            {busy ? "Working…" : "Delete"}
          </button>
        )}
      </div>
      {err && (
        <p className="basis-full text-xs text-red-300" role="alert">
          {err}
        </p>
      )}
    </aside>
  );
}
