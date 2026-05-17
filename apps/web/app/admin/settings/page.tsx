"use client";

import { useEffect, useState } from "react";
import { apiGet, ApiError } from "@/lib/api";
import { Alert } from "@/components/Alert";

const KEYS = [
  { key: "view.video_min_s", label: "Video view threshold (s)", type: "number" },
  { key: "view.article_min_s", label: "Article view threshold (s)", type: "number" },
  { key: "view.article_scroll_min", label: "Article scroll min (0..1)", type: "number" },
  { key: "view.dedup_window_s", label: "View dedup window (s)", type: "number" },
  { key: "upload.max_video_bytes", label: "Max video upload (bytes)", type: "number" },
  { key: "upload.max_video_duration_s", label: "Max video duration (s)", type: "number" },
  { key: "upload.max_file_bytes", label: "Max file upload (bytes)", type: "number" },
  { key: "registration.open", label: "Registration open (true/false)", type: "boolean" },
  { key: "audit.retention_days", label: "Audit log retention (days)", type: "number" },
  { key: "age.min_years", label: "Minimum age (years)", type: "number" },
  { key: "default.license", label: "Default license code", type: "string" },
];

type Row = { key: string; label: string; type: string; value: string; pending: string };

export default function SettingsPage() {
  const [rows, setRows] = useState<Row[]>(
    KEYS.map((k) => ({ ...k, value: "", pending: "" })),
  );
  const [err, setErr] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const next: Row[] = [];
      for (const k of KEYS) {
        try {
          const r = await apiGet<{ key: string; value: unknown }>(`/admin/settings/${k.key}`);
          next.push({ ...k, value: String(r.value), pending: String(r.value) });
        } catch (e) {
          if (e instanceof ApiError && e.status === 404) {
            next.push({ ...k, value: "", pending: "" });
          } else {
            next.push({ ...k, value: "(error)", pending: "" });
          }
        }
      }
      setRows(next);
    })();
  }, []);

  async function save(row: Row) {
    setErr(null);
    setInfo(null);
    let parsed: unknown = row.pending;
    if (row.type === "number") parsed = Number(row.pending);
    if (row.type === "boolean") parsed = row.pending === "true";
    try {
      const csrf = csrfCookie();
      const r = await fetch(`/api/admin/settings/${row.key}`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify({ value: parsed }),
      });
      if (!r.ok) throw new Error(`${r.status}`);
      setRows((rs) => rs.map((x) => (x.key === row.key ? { ...x, value: row.pending } : x)));
      setInfo(`Saved ${row.key}`);
    } catch (e) {
      setErr(`Failed to save ${row.key}: ${String(e)}`);
    }
  }

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold">Platform settings</h1>
        <p className="text-sm text-[var(--color-fg-muted)]">
          Per-platform tunables. Empty rows mean "use code default" until set.
        </p>
      </header>

      {err && <Alert kind="error">{err}</Alert>}
      {info && <Alert kind="success">{info}</Alert>}

      <div className="space-y-2">
        {rows.map((r) => (
          <div
            key={r.key}
            className="flex flex-wrap items-center gap-3 border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded p-3"
          >
            <div className="min-w-[14rem]">
              <div className="text-sm">{r.label}</div>
              <div className="text-xs font-mono text-[var(--color-fg-muted)]">{r.key}</div>
            </div>
            <input
              value={r.pending}
              onChange={(e) =>
                setRows((rs) =>
                  rs.map((x) => (x.key === r.key ? { ...x, pending: e.target.value } : x)),
                )
              }
              placeholder={r.value || "(unset)"}
              className="flex-1 px-2 py-1 rounded bg-[var(--color-bg-base)] border border-[var(--color-brand-blue-4)]"
            />
            <button
              type="button"
              onClick={() => save(r)}
              disabled={r.pending === r.value}
              className="text-xs px-3 py-1 bg-[var(--color-brand-cyan)] text-black rounded font-medium disabled:opacity-60"
            >
              Save
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

function csrfCookie(): string {
  const m = document.cookie.match(/(?:^|; )ndsc_csrf=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}
