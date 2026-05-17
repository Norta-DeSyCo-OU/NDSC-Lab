"use client";

// metadata is exposed via a `head.tsx` sibling so this client component
// can still set its own title via document.title — but we rely on the
// layout template; client pages can also set <title> via the document.
import { useState, useEffect } from "react";
import { apiPost, ApiError } from "@/lib/api";
import { Field } from "@/components/Field";
import { Alert } from "@/components/Alert";

export default function TakedownPage() {
  const [form, setForm] = useState({
    complainant_name: "",
    complainant_email: "",
    complainant_address: "",
    target_url: "",
    sworn_statement: "",
  });
  const [status, setStatus] = useState<"idle" | "ok" | "err">("idle");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    document.title = "Takedown — NDSC Lab";
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await apiPost("/legal/takedown", form);
      setStatus("ok");
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : "unknown");
      setStatus("err");
    } finally {
      setBusy(false);
    }
  }

  if (status === "ok") {
    return (
      <section className="max-w-2xl mx-auto">
        <h1 className="text-2xl font-bold mb-3">Takedown submitted</h1>
        <p className="text-sm text-[var(--color-fg-muted)]">
          We received your request. Our admins review within 48 hours. You will be contacted at the
          email you provided.
        </p>
      </section>
    );
  }

  return (
    <section className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-3">Takedown / DMCA request</h1>
      <p className="text-sm text-[var(--color-fg-muted)] mb-6">
        Use this form to report content you believe infringes your rights. You must include a sworn
        statement and verifiable contact information.
      </p>
      <form onSubmit={onSubmit} className="space-y-4">
        <Field
          label="Your full name"
          value={form.complainant_name}
          onChange={(v) => setForm({ ...form, complainant_name: v })}
          required
          autoComplete="name"
        />
        <Field
          label="Email"
          type="email"
          value={form.complainant_email}
          onChange={(v) => setForm({ ...form, complainant_email: v })}
          required
          autoComplete="email"
        />
        <Field
          label="Mailing address"
          value={form.complainant_address}
          onChange={(v) => setForm({ ...form, complainant_address: v })}
          autoComplete="street-address"
        />
        <Field
          label="URL of the content"
          type="url"
          value={form.target_url}
          onChange={(v) => setForm({ ...form, target_url: v })}
          required
        />
        <div className="space-y-1">
          <label htmlFor="sworn" className="block text-sm">
            Sworn statement<span className="text-red-400 ml-1" aria-hidden>*</span>
          </label>
          <textarea
            id="sworn"
            required
            minLength={20}
            value={form.sworn_statement}
            onChange={(e) => setForm({ ...form, sworn_statement: e.target.value })}
            rows={6}
            aria-describedby="sworn-help"
            className="w-full px-3 py-2 rounded bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)] focus:border-[var(--color-brand-cyan)] outline-none"
          />
          <p id="sworn-help" className="text-xs text-[var(--color-fg-muted)]">
            Include: a description of the work, a good-faith statement that the use is
            unauthorized, and an acknowledgement of perjury liability.
          </p>
        </div>
        {err && <Alert kind="error">{err}</Alert>}
        <button
          type="submit"
          disabled={busy}
          className="px-4 py-2 bg-[var(--color-brand-cyan)] text-black rounded font-medium disabled:opacity-60"
        >
          {busy ? "Submitting…" : "Submit"}
        </button>
      </form>
    </section>
  );
}
