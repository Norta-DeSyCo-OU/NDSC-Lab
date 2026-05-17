"use client";

import { useEffect, useState } from "react";
import { apiGet, ApiError } from "@/lib/api";
import { Alert } from "@/components/Alert";

type AuditRow = {
  id: number;
  ts: string;
  actor_user_id: string | null;
  action: string;
  target_type: string;
  target_id: string;
  payload: Record<string, unknown> | null;
};

export default function AuditPage() {
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [actor, setActor] = useState("");
  const [action, setAction] = useState("");
  const [targetType, setTargetType] = useState("");
  const [targetId, setTargetId] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    setBusy(true);
    setErr(null);
    try {
      const params = new URLSearchParams();
      if (actor) params.set("actor_user_id", actor);
      if (action) params.set("action", action);
      if (targetType) params.set("target_type", targetType);
      if (targetId) params.set("target_id", targetId);
      params.set("limit", "200");
      const data = await apiGet<AuditRow[]>(`/admin/audit-log?${params.toString()}`);
      setRows(data);
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : String(e));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold">Audit log</h1>
        <p className="text-sm text-[var(--color-fg-muted)]">
          Append-only, HMAC-chained. Latest 200 rows.
        </p>
      </header>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          load();
        }}
        className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2 items-end"
        role="search"
      >
        <label>
          <span className="block text-xs text-[var(--color-fg-muted)] mb-1">Actor user ID</span>
          <input
            value={actor}
            onChange={(e) => setActor(e.target.value)}
            className="w-full px-2 py-1 rounded bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)] font-mono text-xs"
          />
        </label>
        <label>
          <span className="block text-xs text-[var(--color-fg-muted)] mb-1">Action</span>
          <input
            value={action}
            onChange={(e) => setAction(e.target.value)}
            placeholder="e.g. cert.issue"
            className="w-full px-2 py-1 rounded bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)]"
          />
        </label>
        <label>
          <span className="block text-xs text-[var(--color-fg-muted)] mb-1">Target type</span>
          <input
            value={targetType}
            onChange={(e) => setTargetType(e.target.value)}
            placeholder="e.g. user"
            className="w-full px-2 py-1 rounded bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)]"
          />
        </label>
        <label>
          <span className="block text-xs text-[var(--color-fg-muted)] mb-1">Target ID</span>
          <input
            value={targetId}
            onChange={(e) => setTargetId(e.target.value)}
            className="w-full px-2 py-1 rounded bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)] font-mono text-xs"
          />
        </label>
        <button
          type="submit"
          disabled={busy}
          className="px-3 py-1 bg-[var(--color-brand-cyan)] text-black rounded text-sm font-medium disabled:opacity-60"
        >
          {busy ? "…" : "Filter"}
        </button>
      </form>

      {err && <Alert kind="error">{err}</Alert>}

      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse font-mono">
          <thead className="text-[var(--color-fg-muted)] uppercase">
            <tr className="border-b border-[var(--color-brand-blue-4)]">
              <th className="text-left py-2 px-1">ID</th>
              <th className="text-left py-2 px-1">When</th>
              <th className="text-left py-2 px-1">Actor</th>
              <th className="text-left py-2 px-1">Action</th>
              <th className="text-left py-2 px-1">Target</th>
              <th className="text-left py-2 px-1">Payload</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-b border-[var(--color-brand-blue-4)]/50 align-top">
                <td className="py-1.5 px-1">{r.id}</td>
                <td className="py-1.5 px-1">{new Date(r.ts).toLocaleString()}</td>
                <td className="py-1.5 px-1 max-w-[18ch] truncate">{r.actor_user_id ?? "—"}</td>
                <td className="py-1.5 px-1 text-[var(--color-brand-cyan)]">{r.action}</td>
                <td className="py-1.5 px-1">
                  {r.target_type}:<br />
                  <span className="text-[var(--color-fg-muted)]">{r.target_id}</span>
                </td>
                <td className="py-1.5 px-1 max-w-[40ch] overflow-x-auto">
                  <pre className="text-[10px]">{JSON.stringify(r.payload, null, 0)}</pre>
                </td>
              </tr>
            ))}
            {rows.length === 0 && !busy && (
              <tr>
                <td colSpan={6} className="py-6 text-center text-[var(--color-fg-muted)]">
                  No entries.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
