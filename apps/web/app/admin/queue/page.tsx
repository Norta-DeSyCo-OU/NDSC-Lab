"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { Alert } from "@/components/Alert";

export const dynamic = "force-dynamic";

type PendingItem = {
  id: string;
  title: string;
  author_id: string;
  author_email: string;
  type: string;
  submitted_at: string | null;
};

type Application = {
  id: string;
  user_id: string;
  user_email: string;
  motivation: string;
  links: Record<string, unknown> | null;
  state: string;
  created_at: string;
};

type Takedown = {
  id: string;
  complainant_name: string;
  complainant_email: string;
  target_url: string;
  sworn_statement: string;
  state: string;
  created_at: string;
};

type Tab = "items" | "content" | "workshops" | "apps" | "takedowns";

const TAB_LABEL: Record<Tab, string> = {
  items: "Pending review",
  content: "All content",
  workshops: "Workshops",
  apps: "Applications",
  takedowns: "Takedowns",
};

export default function QueuePage() {
  return (
    <Suspense fallback={<p>Loading…</p>}>
      <Queue />
    </Suspense>
  );
}

function Queue() {
  const sp = useSearchParams();
  const router = useRouter();
  const initialTab = (sp.get("tab") as Tab) ?? "items";
  const [tab, setTab] = useState<Tab>(initialTab);

  function setActive(t: Tab) {
    setTab(t);
    router.replace(`/admin/queue?tab=${t}`);
  }

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Queue</h1>
        <nav role="tablist" aria-label="Queue sections" className="flex gap-1 flex-wrap">
          {(["items", "content", "workshops", "apps", "takedowns"] as Tab[]).map((t) => (
            <button
              key={t}
              type="button"
              role="tab"
              aria-selected={tab === t}
              onClick={() => setActive(t)}
              className={`px-3 py-1 rounded text-sm ${
                tab === t
                  ? "bg-[var(--color-brand-cyan)] text-black"
                  : "border border-[var(--color-brand-blue-4)]"
              }`}
            >
              {TAB_LABEL[t]}
            </button>
          ))}
        </nav>
      </header>

      {tab === "items" && <ItemsPanel />}
      {tab === "content" && <ContentPanel />}
      {tab === "workshops" && <WorkshopsPanel />}
      {tab === "apps" && <ApplicationsPanel />}
      {tab === "takedowns" && <TakedownsPanel />}
    </div>
  );
}

function ItemsPanel() {
  const [items, setItems] = useState<PendingItem[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const load = async () => {
    try {
      setItems(await apiGet<PendingItem[]>("/admin/items/pending?limit=100"));
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : String(e));
    }
  };
  useEffect(() => {
    load();
  }, []);

  async function approve(id: string) {
    if (!confirm("Approve & publish?")) return;
    try {
      await apiPost(`/admin/items/${id}/approve`, {});
      await load();
    } catch (e) {
      alert(e instanceof ApiError ? e.code : String(e));
    }
  }
  async function reject(id: string) {
    if (!confirm("Reject (returns to draft state)?")) return;
    try {
      await apiPost(`/admin/items/${id}/unpublish`, {});
      await load();
    } catch (e) {
      alert(e instanceof ApiError ? e.code : String(e));
    }
  }
  async function del(id: string) {
    if (!confirm("Tombstone permanently?")) return;
    try {
      const r = await fetch(`/api/admin/items/${id}`, {
        method: "DELETE",
        credentials: "include",
        headers: { "X-CSRF-Token": csrfCookie() },
      });
      if (!r.ok) throw new Error(`${r.status}`);
      await load();
    } catch (e) {
      alert(String(e));
    }
  }

  return (
    <>
      {err && <Alert kind="error">{err}</Alert>}
      <ul className="space-y-2">
        {items.map((i) => (
          <li
            key={i.id}
            className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded p-4 flex flex-wrap gap-3 items-start justify-between"
          >
            <div>
              <div className="text-xs uppercase tracking-wide text-[var(--color-brand-cyan)]">
                {i.type.replace("_", " ")}
              </div>
              <a
                href={`/items/${i.id}`}
                className="font-semibold"
                target="_blank"
                rel="noopener noreferrer"
              >
                {i.title}
              </a>
              <div className="text-xs text-[var(--color-fg-muted)] mt-1">
                by {i.author_email} ·{" "}
                {i.submitted_at ? new Date(i.submitted_at).toLocaleString() : "—"}
              </div>
            </div>
            <div className="space-x-1">
              <button
                type="button"
                onClick={() => approve(i.id)}
                className="text-xs px-2 py-1 bg-[var(--color-brand-cyan)] text-black rounded font-medium"
              >
                Approve
              </button>
              <button
                type="button"
                onClick={() => reject(i.id)}
                className="text-xs px-2 py-1 border border-[var(--color-brand-blue-2)] rounded"
              >
                Reject
              </button>
              <button
                type="button"
                onClick={() => del(i.id)}
                className="text-xs px-2 py-1 border border-red-500 text-red-300 rounded"
              >
                Delete
              </button>
            </div>
          </li>
        ))}
        {items.length === 0 && (
          <li className="text-sm text-[var(--color-fg-muted)] py-6 text-center">
            No items pending review.
          </li>
        )}
      </ul>
    </>
  );
}

function ApplicationsPanel() {
  const [apps, setApps] = useState<Application[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const load = async () => {
    try {
      setApps(await apiGet<Application[]>("/admin/applications?state=pending&limit=100"));
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : String(e));
    }
  };
  useEffect(() => {
    load();
  }, []);

  async function decide(id: string, approve: boolean) {
    const reason = prompt(approve ? "Approval note (optional):" : "Reason for rejection:");
    if (!approve && reason === null) return;
    try {
      await apiPost(`/admin/applications/${id}/decide`, { approve, reason });
      await load();
    } catch (e) {
      alert(e instanceof ApiError ? e.code : String(e));
    }
  }

  return (
    <>
      {err && <Alert kind="error">{err}</Alert>}
      <ul className="space-y-2">
        {apps.map((a) => (
          <li
            key={a.id}
            className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded p-4 space-y-2"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <div>
                <div className="font-semibold">{a.user_email}</div>
                <div className="text-xs text-[var(--color-fg-muted)]">
                  {new Date(a.created_at).toLocaleString()}
                </div>
              </div>
              <div className="space-x-1">
                <button
                  type="button"
                  onClick={() => decide(a.id, true)}
                  className="text-xs px-2 py-1 bg-[var(--color-brand-cyan)] text-black rounded font-medium"
                >
                  Approve
                </button>
                <button
                  type="button"
                  onClick={() => decide(a.id, false)}
                  className="text-xs px-2 py-1 border border-red-500 text-red-300 rounded"
                >
                  Reject
                </button>
              </div>
            </div>
            <p className="text-sm whitespace-pre-wrap">{a.motivation}</p>
            {a.links && Object.keys(a.links).length > 0 && (
              <pre className="text-xs bg-[var(--color-bg-base)] p-2 rounded overflow-x-auto">
                {JSON.stringify(a.links, null, 2)}
              </pre>
            )}
          </li>
        ))}
        {apps.length === 0 && (
          <li className="text-sm text-[var(--color-fg-muted)] py-6 text-center">
            No pending applications.
          </li>
        )}
      </ul>
    </>
  );
}

function TakedownsPanel() {
  const [items, setItems] = useState<Takedown[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const load = async () => {
    try {
      setItems(await apiGet<Takedown[]>("/admin/takedowns?state=open&limit=100"));
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : String(e));
    }
  };
  useEffect(() => {
    load();
  }, []);

  async function decide(id: string, action: "tombstone" | "reject") {
    const reason = prompt(
      action === "tombstone"
        ? "Tombstone target content — provide reason:"
        : "Reject takedown — provide reason for the complainant:",
    );
    if (!reason) return;
    try {
      await apiPost(`/admin/takedowns/${id}/decide`, { action, reason });
      await load();
    } catch (e) {
      alert(e instanceof ApiError ? e.code : String(e));
    }
  }

  return (
    <>
      {err && <Alert kind="error">{err}</Alert>}
      <ul className="space-y-2">
        {items.map((t) => (
          <li
            key={t.id}
            className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded p-4 space-y-2"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <div>
                <div className="font-semibold">{t.complainant_name}</div>
                <div className="text-xs text-[var(--color-fg-muted)]">
                  {t.complainant_email} · {new Date(t.created_at).toLocaleString()}
                </div>
              </div>
              <div className="space-x-1">
                <button
                  type="button"
                  onClick={() => decide(t.id, "tombstone")}
                  className="text-xs px-2 py-1 bg-red-500 text-white rounded font-medium"
                >
                  Tombstone
                </button>
                <button
                  type="button"
                  onClick={() => decide(t.id, "reject")}
                  className="text-xs px-2 py-1 border border-[var(--color-brand-blue-2)] rounded"
                >
                  Reject
                </button>
              </div>
            </div>
            <p className="text-sm">
              <span className="text-[var(--color-fg-muted)]">URL:</span>{" "}
              <a href={t.target_url} target="_blank" rel="noopener noreferrer">
                {t.target_url}
              </a>
            </p>
            <p className="text-sm whitespace-pre-wrap">{t.sworn_statement}</p>
          </li>
        ))}
        {items.length === 0 && (
          <li className="text-sm text-[var(--color-fg-muted)] py-6 text-center">
            No open takedowns.
          </li>
        )}
      </ul>
    </>
  );
}

type ContentItem = {
  id: string;
  title: string;
  type: string;
  state: string;
  author_id: string;
  author_email: string;
  summary: string | null;
  published_at: string | null;
  updated_at: string;
  created_at: string;
};

const STATE_FILTERS = [
  { v: "", l: "All (non-deleted)" },
  { v: "published", l: "Published" },
  { v: "pending_review", l: "Pending review" },
  { v: "draft", l: "Draft" },
  { v: "tombstoned", l: "Tombstoned (deleted)" },
];

function ContentPanel() {
  const [items, setItems] = useState<ContentItem[]>([]);
  const [state, setState] = useState<string>("published");
  const [q, setQ] = useState<string>("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setErr(null);
    setBusy(true);
    try {
      const params = new URLSearchParams();
      if (state) params.set("state", state);
      if (q) params.set("q", q);
      params.set("limit", "100");
      setItems(await apiGet<ContentItem[]>(`/admin/items?${params.toString()}`));
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : String(e));
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state]);

  async function unpublish(id: string) {
    if (!confirm("Unpublish (item returns to draft, hidden from public)?")) return;
    try {
      await apiPost(`/admin/items/${id}/unpublish`, {});
      await load();
    } catch (e) {
      alert(e instanceof ApiError ? e.code : String(e));
    }
  }
  async function del(id: string) {
    if (!confirm("Tombstone permanently? This hides the item, removes it from search, and cannot be undone via the UI.")) return;
    try {
      const r = await fetch(`/api/admin/items/${id}`, {
        method: "DELETE",
        credentials: "include",
        headers: { "X-CSRF-Token": csrfCookie() },
      });
      if (!r.ok) throw new Error(`${r.status}`);
      await load();
    } catch (e) {
      alert(String(e));
    }
  }

  return (
    <div className="space-y-3">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          load();
        }}
        className="flex flex-wrap gap-2 items-end"
      >
        <label className="text-sm">
          <span className="block text-xs text-[var(--color-fg-muted)] mb-1">State</span>
          <select
            value={state}
            onChange={(e) => setState(e.target.value)}
            className="px-2 py-1 rounded bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)]"
          >
            {STATE_FILTERS.map((s) => (
              <option key={s.v} value={s.v}>
                {s.l}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm flex-1 min-w-48">
          <span className="block text-xs text-[var(--color-fg-muted)] mb-1">Search title/summary</span>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="keyword…"
            className="w-full px-2 py-1 rounded bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)]"
          />
        </label>
        <button
          type="submit"
          disabled={busy}
          className="px-3 py-1 bg-[var(--color-brand-cyan)] text-black rounded text-sm font-medium disabled:opacity-60"
        >
          {busy ? "Loading…" : "Apply"}
        </button>
      </form>

      {err && <Alert kind="error">{err}</Alert>}

      <ul className="space-y-2">
        {items.map((i) => (
          <li
            key={i.id}
            className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded p-4 flex flex-wrap gap-3 items-start justify-between"
          >
            <div className="min-w-0">
              <div className="text-xs uppercase tracking-wide text-[var(--color-brand-cyan)] flex gap-2 items-center">
                <span>{i.type.replace("_", " ")}</span>
                <span
                  className={
                    i.state === "published"
                      ? "text-emerald-400"
                      : i.state === "tombstoned"
                        ? "text-red-400"
                        : "text-yellow-400"
                  }
                >
                  · {i.state}
                </span>
              </div>
              <a
                href={`/items/${i.id}`}
                className="font-semibold"
                target="_blank"
                rel="noopener noreferrer"
              >
                {i.title}
              </a>
              <div className="text-xs text-[var(--color-fg-muted)] mt-1">
                by {i.author_email} · updated {new Date(i.updated_at).toLocaleString()}
              </div>
              {i.summary && (
                <p className="text-xs text-[var(--color-fg-muted)] mt-1 line-clamp-2">
                  {i.summary}
                </p>
              )}
            </div>
            <div className="space-x-1 shrink-0">
              {i.state === "published" && (
                <button
                  type="button"
                  onClick={() => unpublish(i.id)}
                  className="text-xs px-2 py-1 border border-[var(--color-brand-blue-2)] rounded"
                >
                  Unpublish
                </button>
              )}
              {i.state !== "tombstoned" && (
                <button
                  type="button"
                  onClick={() => del(i.id)}
                  className="text-xs px-2 py-1 border border-red-500 text-red-300 rounded"
                >
                  Delete
                </button>
              )}
            </div>
          </li>
        ))}
        {items.length === 0 && !busy && (
          <li className="text-sm text-[var(--color-fg-muted)] py-6 text-center">
            No items match these filters.
          </li>
        )}
      </ul>
    </div>
  );
}

type WorkshopRow = {
  id: string;
  title: string;
  slug: string;
  state: string;
  starts_at: string;
  ends_at: string;
  is_online: boolean;
  location: string | null;
  registration_url: string | null;
};

function WorkshopsPanel() {
  const [rows, setRows] = useState<WorkshopRow[]>([]);
  const [state, setState] = useState<string>("pending_review");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setErr(null);
    setBusy(true);
    try {
      const params = new URLSearchParams();
      if (state) params.set("state", state);
      setRows(await apiGet<WorkshopRow[]>(`/admin/workshops?${params.toString()}`));
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : String(e));
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state]);

  async function approve(id: string) {
    if (!confirm("Approve & publish workshop?")) return;
    try {
      await apiPost(`/admin/workshops/${id}/approve`, {});
      await load();
    } catch (e) {
      alert(e instanceof ApiError ? e.code : String(e));
    }
  }
  async function unpublish(id: string) {
    if (!confirm("Unpublish workshop (returns to draft)?")) return;
    try {
      await apiPost(`/admin/workshops/${id}/unpublish`, {});
      await load();
    } catch (e) {
      alert(e instanceof ApiError ? e.code : String(e));
    }
  }
  async function del(id: string) {
    if (!confirm("Tombstone workshop permanently?")) return;
    try {
      const r = await fetch(`/api/admin/workshops/${id}`, {
        method: "DELETE",
        credentials: "include",
        headers: { "X-CSRF-Token": csrfCookie() },
      });
      if (!r.ok) throw new Error(`${r.status}`);
      await load();
    } catch (e) {
      alert(String(e));
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2 items-end">
        <label className="text-sm">
          <span className="block text-xs text-[var(--color-fg-muted)] mb-1">State</span>
          <select
            value={state}
            onChange={(e) => setState(e.target.value)}
            className="px-2 py-1 rounded bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)]"
          >
            <option value="">All (non-deleted)</option>
            <option value="pending_review">Pending review</option>
            <option value="published">Published</option>
            <option value="draft">Draft</option>
            <option value="tombstoned">Tombstoned</option>
          </select>
        </label>
      </div>

      {err && <Alert kind="error">{err}</Alert>}

      <ul className="space-y-2">
        {rows.map((w) => (
          <li
            key={w.id}
            className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded p-4 flex flex-wrap gap-3 items-start justify-between"
          >
            <div className="min-w-0">
              <div className="text-xs uppercase tracking-wide text-[var(--color-brand-cyan)]">
                workshop · <span className={w.state === "published" ? "text-emerald-400" : w.state === "pending_review" ? "text-yellow-400" : "text-[var(--color-fg-muted)]"}>{w.state}</span>
              </div>
              <h3 className="font-semibold">{w.title}</h3>
              <p className="text-xs text-[var(--color-fg-muted)] mt-1">
                {new Date(w.starts_at).toLocaleString()} → {new Date(w.ends_at).toLocaleString()}
              </p>
              <p className="text-xs mt-1">{w.is_online ? "Online" : (w.location ?? "TBA")}</p>
            </div>
            <div className="space-x-1 shrink-0">
              {w.state !== "published" && w.state !== "tombstoned" && (
                <button
                  type="button"
                  onClick={() => approve(w.id)}
                  className="text-xs px-2 py-1 bg-[var(--color-brand-cyan)] text-black rounded font-medium"
                >
                  Approve
                </button>
              )}
              {w.state === "published" && (
                <button
                  type="button"
                  onClick={() => unpublish(w.id)}
                  className="text-xs px-2 py-1 border border-[var(--color-brand-blue-2)] rounded"
                >
                  Unpublish
                </button>
              )}
              {w.state !== "tombstoned" && (
                <button
                  type="button"
                  onClick={() => del(w.id)}
                  className="text-xs px-2 py-1 border border-red-500 text-red-300 rounded"
                >
                  Delete
                </button>
              )}
            </div>
          </li>
        ))}
        {rows.length === 0 && !busy && (
          <li className="text-sm text-[var(--color-fg-muted)] py-6 text-center">
            No workshops match this filter.
          </li>
        )}
      </ul>
    </div>
  );
}

function csrfCookie(): string {
  const m = document.cookie.match(/(?:^|; )ndsc_csrf=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}
