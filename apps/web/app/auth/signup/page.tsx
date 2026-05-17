"use client";

import { useState } from "react";
import { apiPost, ApiError } from "@/lib/api";
import { Field } from "@/components/Field";
import { Alert } from "@/components/Alert";

const TOS_V = "2026-05-13";
const COOKIE_V = "2026-05-13";

export default function SignupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [age, setAge] = useState(false);
  const [tos, setTos] = useState(false);
  const [analytics, setAnalytics] = useState(false);
  const [status, setStatus] = useState<"idle" | "ok" | "err">("idle");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (!tos || !age) {
      setErr("Please confirm your age (16+) and accept the Terms before continuing.");
      return;
    }
    if (password.length < 12) {
      setErr("Password must be at least 12 characters.");
      return;
    }
    setBusy(true);
    try {
      await apiPost("/auth/signup", {
        email,
        password,
        age_confirmed: age,
        tos_version: TOS_V,
        cookie_consent_version: COOKIE_V,
        analytics_opt_in: analytics,
      });
      setStatus("ok");
    } catch (e) {
      const code = e instanceof ApiError ? e.code : "unknown";
      const msg =
        code === "password_breached"
          ? "This password appeared in a known data breach. Pick a different one."
          : code === "rate_limited"
            ? "Too many sign-up attempts. Wait a few minutes."
            : `Sign-up failed (${code}).`;
      setErr(msg);
      setStatus("err");
    } finally {
      setBusy(false);
    }
  }

  if (status === "ok") {
    return (
      <section className="max-w-md mx-auto">
        <h1 className="text-2xl font-bold mb-3">Check your email</h1>
        <p className="text-sm text-[var(--color-fg-muted)]">
          If the address is registrable, we just sent a verification link (valid 24 h).
        </p>
      </section>
    );
  }

  return (
    <section className="max-w-md mx-auto">
      <h1 className="text-2xl font-bold mb-6">Create an account</h1>
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
          minLength={12}
          autoComplete="new-password"
          help="At least 12 characters. Checked against HaveIBeenPwned breaches."
        />
        <fieldset className="space-y-2 text-sm">
          <legend className="sr-only">Required confirmations</legend>
          <label className="flex items-start gap-2">
            <input
              type="checkbox"
              checked={age}
              onChange={(e) => setAge(e.target.checked)}
              required
            />
            <span>I confirm I am 16 years old or older.</span>
          </label>
          <label className="flex items-start gap-2">
            <input
              type="checkbox"
              checked={tos}
              onChange={(e) => setTos(e.target.checked)}
              required
            />
            <span>
              I accept the <a href="/legal/terms">Terms</a> and{" "}
              <a href="/legal/privacy">Privacy Policy</a>.
            </span>
          </label>
          <label className="flex items-start gap-2">
            <input
              type="checkbox"
              checked={analytics}
              onChange={(e) => setAnalytics(e.target.checked)}
            />
            <span>Allow anonymized view analytics (you can change this later).</span>
          </label>
        </fieldset>
        {err && <Alert kind="error">{err}</Alert>}
        <button
          type="submit"
          disabled={busy}
          className="w-full py-2 bg-[var(--color-brand-cyan)] text-black rounded font-medium disabled:opacity-60"
        >
          {busy ? "Creating account…" : "Create account"}
        </button>
        <p className="text-sm text-center text-[var(--color-fg-muted)]">
          Already have an account? <a href="/auth/login">Sign in</a>.
        </p>
      </form>
    </section>
  );
}
