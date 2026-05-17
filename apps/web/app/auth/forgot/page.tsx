"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import { Field } from "@/components/Field";

export default function ForgotPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await apiPost("/auth/forgot", { email });
    } finally {
      setBusy(false);
      setSent(true);
    }
  }

  if (sent)
    return (
      <section className="max-w-md mx-auto">
        <h1 className="text-2xl font-bold mb-3">Check your email</h1>
        <p className="text-sm text-[var(--color-fg-muted)]">
          If the address has an account, you&apos;ll receive a reset link (valid 1 h).
        </p>
      </section>
    );

  return (
    <section className="max-w-md mx-auto">
      <h1 className="text-2xl font-bold mb-6">Reset password</h1>
      <form onSubmit={onSubmit} className="space-y-4">
        <Field
          label="Email"
          type="email"
          value={email}
          onChange={setEmail}
          required
          autoComplete="email"
          placeholder="email@example.com"
        />
        <button
          type="submit"
          disabled={busy}
          className="w-full py-2 bg-[var(--color-brand-cyan)] text-black rounded font-medium disabled:opacity-60"
        >
          {busy ? "Sending…" : "Send reset link"}
        </button>
      </form>
    </section>
  );
}
