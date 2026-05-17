"use client";

import { useState } from "react";
import { apiPost, ApiError } from "@/lib/api";
import { Field } from "@/components/Field";
import { Alert } from "@/components/Alert";

export default function DangerZone() {
  const [pwd, setPwd] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (confirm !== "DELETE") {
      setErr('Type "DELETE" exactly to confirm.');
      return;
    }
    setErr(null);
    setBusy(true);
    try {
      const r = await apiPost<{ state: string; grace_until: string }>("/me/erasure", {
        password: pwd,
      });
      setInfo(
        `Erasure scheduled. State=${r.state}. Grace ends ${new Date(r.grace_until).toLocaleString()}. ` +
          `Cancel from this page within the grace window.`,
      );
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    try {
      await apiPost("/me/erasure/cancel", {});
      setInfo("Erasure cancelled.");
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : String(e));
    }
  }

  return (
    <section className="max-w-md mx-auto space-y-4">
      <header>
        <h1 className="text-2xl font-bold text-red-400">Delete my account</h1>
        <p className="text-sm text-[var(--color-fg-muted)]">
          Schedules permanent deletion of your account and all your content. A 7-day grace window
          lets you cancel. After 30 days, audit-log references to you are pseudonymized.
        </p>
      </header>

      <form onSubmit={onSubmit} className="space-y-3">
        <Field
          label="Current password"
          type="password"
          value={pwd}
          onChange={setPwd}
          required
          help="Leave blank only if you signed up with Google (a fresh Google re-auth is required first)."
        />
        <Field
          label='Type "DELETE" to confirm'
          value={confirm}
          onChange={setConfirm}
          required
        />
        {info && <Alert kind="success">{info}</Alert>}
        {err && <Alert kind="error">{err}</Alert>}
        <div className="flex flex-wrap gap-3">
          <button
            type="submit"
            disabled={busy}
            className="px-4 py-2 bg-red-500 text-white rounded font-medium disabled:opacity-60"
          >
            {busy ? "Scheduling…" : "Schedule deletion"}
          </button>
          <button
            type="button"
            onClick={cancel}
            className="px-4 py-2 border border-[var(--color-brand-blue-2)] rounded"
          >
            Cancel pending deletion
          </button>
        </div>
      </form>
    </section>
  );
}
