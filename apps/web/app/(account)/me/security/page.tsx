"use client";

import { useState } from "react";
import { apiPost, ApiError } from "@/lib/api";
import { Field } from "@/components/Field";
import { Alert } from "@/components/Alert";

export default function SecurityPage() {
  return (
    <section className="max-w-md mx-auto space-y-8">
      <header>
        <h1 className="text-2xl font-bold">Security</h1>
        <p className="text-sm text-[var(--color-fg-muted)]">
          Manage password and email. Changes are audit-logged.
        </p>
      </header>
      <PasswordForm />
      <EmailForm />
    </section>
  );
}

function PasswordForm() {
  const [cur, setCur] = useState("");
  const [next, setNext] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setOk(false);
    setBusy(true);
    try {
      await apiPost("/me/password", { current_password: cur, new_password: next });
      setOk(true);
      setCur("");
      setNext("");
    } catch (e) {
      const code = e instanceof ApiError ? e.code : "unknown";
      setErr(
        code === "current_password_required"
          ? "Current password is wrong."
          : code === "password_breached"
            ? "This password appeared in a known data breach."
            : code === "recent_oauth_required"
              ? "Sign in again with Google, then come back to set a password."
              : `Could not change password (${code}).`,
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-3 border border-[var(--color-brand-blue-4)] p-4 rounded">
      <h2 className="font-semibold">Change password</h2>
      <Field
        label="Current password"
        type="password"
        value={cur}
        onChange={setCur}
        autoComplete="current-password"
        help="Leave blank only if your account has no password yet (Google sign-in)."
      />
      <Field
        label="New password"
        type="password"
        value={next}
        onChange={setNext}
        required
        minLength={12}
        autoComplete="new-password"
        help="At least 12 characters. Checked against HaveIBeenPwned."
      />
      {ok && <Alert kind="success">Password changed.</Alert>}
      {err && <Alert kind="error">{err}</Alert>}
      <button
        type="submit"
        disabled={busy}
        className="px-4 py-2 bg-[var(--color-brand-cyan)] text-black rounded font-medium disabled:opacity-60"
      >
        {busy ? "Saving…" : "Change password"}
      </button>
    </form>
  );
}

function EmailForm() {
  const [email, setEmail] = useState("");
  const [pwd, setPwd] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setOk(false);
    setBusy(true);
    try {
      await apiPost("/me/email", { new_email: email, current_password: pwd });
      setOk(true);
      setEmail("");
      setPwd("");
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : "unknown");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-3 border border-[var(--color-brand-blue-4)] p-4 rounded">
      <h2 className="font-semibold">Change email</h2>
      <Field
        label="New email"
        type="email"
        value={email}
        onChange={setEmail}
        required
        autoComplete="email"
      />
      <Field
        label="Current password"
        type="password"
        value={pwd}
        onChange={setPwd}
        autoComplete="current-password"
        help="Leave blank if signed in via Google (you'll need a recent Google re-auth)."
      />
      {ok && (
        <Alert kind="success">
          Check the new email for a confirmation link. Old email is notified.
        </Alert>
      )}
      {err && <Alert kind="error">{err}</Alert>}
      <button
        type="submit"
        disabled={busy}
        className="px-4 py-2 bg-[var(--color-brand-cyan)] text-black rounded font-medium disabled:opacity-60"
      >
        {busy ? "Sending…" : "Request change"}
      </button>
    </form>
  );
}
