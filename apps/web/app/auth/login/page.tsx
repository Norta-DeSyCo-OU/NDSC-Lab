"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiPost, ApiError } from "@/lib/api";
import { setMe, type Me } from "@/lib/useMe";
import { Field } from "@/components/Field";
import { Alert } from "@/components/Alert";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const me = await apiPost<Me>("/auth/login", { email, password });
      setMe(me);
      router.push("/");
    } catch (e) {
      const code = e instanceof ApiError ? e.code : "unknown";
      setErr(
        code === "invalid_credentials"
          ? "Wrong email or password."
          : code === "rate_limited"
            ? "Too many attempts. Try again in 15 minutes."
            : code === "csrf_failed"
              ? "Session expired. Refresh the page and try again."
              : `Sign in failed (${code}).`,
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="max-w-md mx-auto">
      <h1 className="text-2xl font-bold mb-6">Sign in</h1>
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <Field
          label="Email"
          type="email"
          value={email}
          onChange={setEmail}
          required
          autoComplete="email"
        />
        <Field
          label="Password"
          type="password"
          value={password}
          onChange={setPassword}
          required
          autoComplete="current-password"
        />
        {err && <Alert kind="error">{err}</Alert>}
        <button
          type="submit"
          disabled={busy}
          className="w-full py-2 bg-[var(--color-brand-cyan)] text-black rounded font-medium disabled:opacity-60"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
        <p className="text-sm text-center text-[var(--color-fg-muted)]">
          <a href="/auth/forgot">Forgot password?</a> ·{" "}
          <a href="/auth/signup">Create account</a>
        </p>
      </form>
    </section>
  );
}
