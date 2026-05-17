"use client";

import { Suspense, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { apiPost, ApiError } from "@/lib/api";
import { Field } from "@/components/Field";
import { Alert } from "@/components/Alert";

export const dynamic = "force-dynamic";

export default function ResetPage() {
  return (
    <Suspense fallback={<p className="max-w-md mx-auto">Loading…</p>}>
      <ResetForm />
    </Suspense>
  );
}

function ResetForm() {
  const sp = useSearchParams();
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const token = sp.get("t") ?? "";

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await apiPost("/auth/reset", { token, password });
      router.push("/auth/login");
    } catch (e) {
      const code = e instanceof ApiError ? e.code : "unknown";
      setErr(
        code === "invalid_token"
          ? "The reset link is invalid or has expired. Request a new one."
          : code === "password_breached"
            ? "This password appeared in a known data breach. Pick a different one."
            : `Reset failed (${code}).`,
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="max-w-md mx-auto">
      <h1 className="text-2xl font-bold mb-6">Set new password</h1>
      <form onSubmit={onSubmit} className="space-y-4">
        <Field
          label="New password"
          type="password"
          value={password}
          onChange={setPassword}
          required
          minLength={12}
          autoComplete="new-password"
          help="At least 12 characters."
        />
        {err && <Alert kind="error">{err}</Alert>}
        <button
          type="submit"
          disabled={busy}
          className="w-full py-2 bg-[var(--color-brand-cyan)] text-black rounded font-medium disabled:opacity-60"
        >
          {busy ? "Resetting…" : "Reset password"}
        </button>
      </form>
    </section>
  );
}
