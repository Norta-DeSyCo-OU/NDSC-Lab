"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { Alert } from "@/components/Alert";

type Cert = {
  id: string;
  user_id: string;
  user_email: string;
  collection_id: string;
  collection_title: string | null;
  issued_at: string;
  revoked_at: string | null;
};

export default function CertsPage() {
  const [rows, setRows] = useState<Cert[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [issuing, setIssuing] = useState(false);
  const [form, setForm] = useState({ user_id: "", collection_id: "", course_title: "" });

  async function load() {
    try {
      setRows(await apiGet<Cert[]>("/admin/certificates?limit=200"));
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : String(e));
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function issue(e: React.FormEvent) {
    e.preventDefault();
    setIssuing(true);
    try {
      await apiPost("/admin/certificates", form);
      setForm({ user_id: "", collection_id: "", course_title: "" });
      await load();
    } catch (e) {
      alert(e instanceof ApiError ? e.code : String(e));
    } finally {
      setIssuing(false);
    }
  }

  async function revoke(id: string) {
    const reason = prompt("Reason for revocation (shown on verifier page):");
    if (!reason) return;
    try {
      await apiPost(`/admin/certificates/${id}/revoke`, { reason });
      await load();
    } catch (e) {
      alert(e instanceof ApiError ? e.code : String(e));
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">Certificates</h1>
        <p className="text-sm text-[var(--color-fg-muted)]">
          Ed25519-signed PDFs verifiable at <code>/verify/&lt;id&gt;</code>.
        </p>
      </header>

      <section className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded p-4">
        <h2 className="font-semibold mb-3">Issue a certificate</h2>
        <form onSubmit={issue} className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 items-end">
          <label>
            <span className="block text-xs text-[var(--color-fg-muted)] mb-1">Recipient user ID</span>
            <input
              required
              value={form.user_id}
              onChange={(e) => setForm({ ...form, user_id: e.target.value })}
              placeholder="01H..."
              className="w-full px-2 py-1 rounded bg-[var(--color-bg-base)] border border-[var(--color-brand-blue-4)] font-mono text-xs"
            />
          </label>
          <label>
            <span className="block text-xs text-[var(--color-fg-muted)] mb-1">Collection ID</span>
            <input
              required
              value={form.collection_id}
              onChange={(e) => setForm({ ...form, collection_id: e.target.value })}
              placeholder="01H..."
              className="w-full px-2 py-1 rounded bg-[var(--color-bg-base)] border border-[var(--color-brand-blue-4)] font-mono text-xs"
            />
          </label>
          <label>
            <span className="block text-xs text-[var(--color-fg-muted)] mb-1">Course title</span>
            <input
              required
              value={form.course_title}
              onChange={(e) => setForm({ ...form, course_title: e.target.value })}
              className="w-full px-2 py-1 rounded bg-[var(--color-bg-base)] border border-[var(--color-brand-blue-4)]"
            />
          </label>
          <div className="sm:col-span-2 md:col-span-3 text-right">
            <button
              type="submit"
              disabled={issuing}
              className="px-3 py-1 bg-[var(--color-brand-cyan)] text-black rounded text-sm font-medium disabled:opacity-60"
            >
              {issuing ? "Issuing…" : "Issue"}
            </button>
          </div>
        </form>
      </section>

      {err && <Alert kind="error">{err}</Alert>}

      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead className="text-[var(--color-fg-muted)] text-xs uppercase">
            <tr className="border-b border-[var(--color-brand-blue-4)]">
              <th className="text-left py-2 px-1">Cert ID</th>
              <th className="text-left py-2 px-1">Recipient</th>
              <th className="text-left py-2 px-1">Course</th>
              <th className="text-left py-2 px-1">Issued</th>
              <th className="text-left py-2 px-1">Status</th>
              <th className="text-right py-2 px-1">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-b border-[var(--color-brand-blue-4)]/50">
                <td className="py-2 px-1 font-mono text-xs">{r.id}</td>
                <td className="py-2 px-1">{r.user_email}</td>
                <td className="py-2 px-1">{r.collection_title ?? r.collection_id}</td>
                <td className="py-2 px-1 text-xs text-[var(--color-fg-muted)]">
                  {new Date(r.issued_at).toLocaleString()}
                </td>
                <td className="py-2 px-1">
                  {r.revoked_at ? (
                    <span className="text-red-400">revoked</span>
                  ) : (
                    <span className="text-emerald-400">valid</span>
                  )}
                </td>
                <td className="py-2 px-1 text-right space-x-1">
                  <a
                    href={`/api/admin/certificates/${r.id}/pdf`}
                    className="text-xs px-2 py-1 border border-[var(--color-brand-blue-2)] rounded inline-block"
                  >
                    PDF
                  </a>
                  <a
                    href={`/verify/${r.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs px-2 py-1 border border-[var(--color-brand-blue-2)] rounded inline-block"
                  >
                    Verify
                  </a>
                  {!r.revoked_at && (
                    <button
                      type="button"
                      onClick={() => revoke(r.id)}
                      className="text-xs px-2 py-1 border border-red-500 text-red-300 rounded"
                    >
                      Revoke
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={6} className="py-6 text-center text-[var(--color-fg-muted)]">
                  No certificates issued.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
