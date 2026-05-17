"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { Alert } from "@/components/Alert";

export const dynamic = "force-dynamic";

type Status = {
  enabled: boolean;
  limit: number;
  window_s: number;
  cooldown_s: number;
  current_count: number;
  cooldown_active: boolean;
  cooldown_remaining_s: number;
};

type AuditRow = {
  id: number;
  ts: string | null;
  actor_user_id: string | null;
  action: string;
  payload: Record<string, unknown> | null;
};

function csrfCookie(): string {
  const m = document.cookie.match(/(?:^|; )ndsc_csrf=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

function fmtSeconds(s: number): string {
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min`;
  return `${Math.floor(m / 60)} h ${m % 60} min`;
}

export default function SecurityPage() {
  const [status, setStatus] = useState<Status | null>(null);
  const [events, setEvents] = useState<AuditRow[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Editable knobs (saved one at a time via PUT /admin/settings/{key}).
  const [limit, setLimit] = useState<number>(20);
  const [windowS, setWindowS] = useState<number>(7200);
  const [cooldownS, setCooldownS] = useState<number>(1800);

  async function load() {
    try {
      const s = await apiGet<Status>("/admin/signup-flood");
      setStatus(s);
      setLimit(s.limit);
      setWindowS(s.window_s);
      setCooldownS(s.cooldown_s);
      const rows = await apiGet<AuditRow[]>(
        "/admin/audit-log?action=security.signup_flood_triggered&limit=20",
      );
      setEvents(rows);
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : String(e));
    }
  }
  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, []);

  async function setSetting(key: string, value: unknown) {
    const csrf = csrfCookie();
    const r = await fetch(`/api/admin/settings/${key}`, {
      method: "PUT",
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
      body: JSON.stringify({ value }),
    });
    if (!r.ok) throw new Error(`${r.status}`);
  }

  async function toggleEnabled() {
    if (!status) return;
    setBusy(true);
    setErr(null);
    setInfo(null);
    try {
      await setSetting("signup_flood.enabled", !status.enabled);
      setInfo(status.enabled ? "Signup flood control disabled." : "Signup flood control enabled.");
      await load();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function saveKnobs(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    setInfo(null);
    try {
      await setSetting("signup_flood.limit", Math.max(1, Math.floor(limit)));
      await setSetting("signup_flood.window_s", Math.max(60, Math.floor(windowS)));
      await setSetting("signup_flood.cooldown_s", Math.max(60, Math.floor(cooldownS)));
      setInfo("Thresholds saved.");
      await load();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function clearCooldown() {
    if (
      !confirm(
        "Clear the current signup cooldown? Subsequent signup attempts will be accepted again.",
      )
    )
      return;
    setBusy(true);
    setErr(null);
    setInfo(null);
    try {
      await apiPost("/admin/signup-flood/clear", {});
      setInfo("Cooldown cleared.");
      await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (!status)
    return (
      <p role="status" aria-live="polite" className="text-sm text-[var(--color-fg-muted)]">
        Loading security status…
      </p>
    );

  const trippedColor = status.cooldown_active
    ? "text-red-300"
    : status.current_count > status.limit * 0.75
      ? "text-yellow-300"
      : "text-emerald-300";

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">Security</h1>
        <p className="text-sm text-[var(--color-fg-muted)] mt-1">
          Signup-flood control + alert log. Trips a global cooldown when more than{" "}
          <code>limit</code> signup attempts arrive within <code>window</code>.
        </p>
      </header>

      {err && <Alert kind="error">{err}</Alert>}
      {info && <Alert kind="success">{info}</Alert>}

      <section
        aria-labelledby="state-h"
        className="border border-[var(--color-brand-blue-4)] rounded p-4 space-y-3 bg-[var(--color-bg-panel)]"
      >
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <h2 id="state-h" className="font-semibold">
            Current state
          </h2>
          <span
            className={
              "text-xs px-2 py-0.5 rounded border " +
              (status.enabled
                ? "border-[var(--color-brand-cyan)] text-[var(--color-brand-cyan)]"
                : "border-red-500 text-red-300")
            }
          >
            {status.enabled ? "ENABLED" : "DISABLED"}
          </span>
        </div>

        <dl className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
          <div>
            <dt className="text-xs text-[var(--color-fg-muted)]">Signups in window</dt>
            <dd className={"text-2xl font-bold " + trippedColor}>
              {status.current_count}{" "}
              <span className="text-sm font-normal text-[var(--color-fg-muted)]">
                / {status.limit}
              </span>
            </dd>
          </div>
          <div>
            <dt className="text-xs text-[var(--color-fg-muted)]">Window</dt>
            <dd className="font-mono">{fmtSeconds(status.window_s)}</dd>
          </div>
          <div>
            <dt className="text-xs text-[var(--color-fg-muted)]">Cooldown</dt>
            <dd className="font-mono">
              {status.cooldown_active
                ? `${fmtSeconds(status.cooldown_remaining_s)} remaining`
                : "inactive"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-[var(--color-fg-muted)]">Cooldown length</dt>
            <dd className="font-mono">{fmtSeconds(status.cooldown_s)}</dd>
          </div>
        </dl>

        <div className="flex flex-wrap gap-2 pt-2">
          <button
            type="button"
            onClick={toggleEnabled}
            disabled={busy}
            className={
              "px-3 py-1 rounded text-sm font-medium border " +
              (status.enabled
                ? "border-red-500 text-red-300"
                : "border-[var(--color-brand-cyan)] text-[var(--color-brand-cyan)]")
            }
          >
            {status.enabled ? "Disable flood control" : "Enable flood control"}
          </button>
          {status.cooldown_active && (
            <button
              type="button"
              onClick={clearCooldown}
              disabled={busy}
              className="px-3 py-1 bg-[var(--color-brand-cyan)] text-black rounded text-sm font-medium"
            >
              Release cooldown
            </button>
          )}
        </div>
      </section>

      <section
        aria-labelledby="thresh-h"
        className="border border-[var(--color-brand-blue-4)] rounded p-4 space-y-3 bg-[var(--color-bg-panel)]"
      >
        <h2 id="thresh-h" className="font-semibold">
          Thresholds
        </h2>
        <form
          onSubmit={saveKnobs}
          className="grid grid-cols-1 sm:grid-cols-3 gap-3 items-end"
        >
          <label className="text-sm">
            <span className="block text-xs text-[var(--color-fg-muted)] mb-1">
              Limit (signups)
            </span>
            <input
              type="number"
              min={1}
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              className="w-full px-2 py-1 rounded bg-[var(--color-bg-base)] border border-[var(--color-brand-blue-4)]"
            />
          </label>
          <label className="text-sm">
            <span className="block text-xs text-[var(--color-fg-muted)] mb-1">
              Window (seconds)
            </span>
            <input
              type="number"
              min={60}
              value={windowS}
              onChange={(e) => setWindowS(Number(e.target.value))}
              className="w-full px-2 py-1 rounded bg-[var(--color-bg-base)] border border-[var(--color-brand-blue-4)]"
            />
          </label>
          <label className="text-sm">
            <span className="block text-xs text-[var(--color-fg-muted)] mb-1">
              Cooldown (seconds)
            </span>
            <input
              type="number"
              min={60}
              value={cooldownS}
              onChange={(e) => setCooldownS(Number(e.target.value))}
              className="w-full px-2 py-1 rounded bg-[var(--color-bg-base)] border border-[var(--color-brand-blue-4)]"
            />
          </label>
          <button
            type="submit"
            disabled={busy}
            className="sm:col-span-3 justify-self-start px-4 py-2 bg-[var(--color-brand-cyan)] text-black rounded font-medium disabled:opacity-60"
          >
            Save thresholds
          </button>
        </form>
        <p className="text-xs text-[var(--color-fg-muted)]">
          Defaults: 20 signups / 2 h window / 30 min cooldown. Saved in
          <code> platform_settings</code>; runtime picks them up on the next signup hit.
        </p>
      </section>

      <section
        aria-labelledby="evt-h"
        className="border border-[var(--color-brand-blue-4)] rounded p-4 space-y-2 bg-[var(--color-bg-panel)]"
      >
        <h2 id="evt-h" className="font-semibold">
          Recent flood alerts
        </h2>
        {events.length === 0 ? (
          <p className="text-xs text-[var(--color-fg-muted)]">
            None yet. Each time the limiter trips, an entry appears here and in the audit log.
          </p>
        ) : (
          <ul className="text-xs space-y-1 font-mono">
            {events.map((e) => (
              <li key={e.id} className="flex flex-wrap gap-3">
                <time className="text-[var(--color-fg-muted)]">{e.ts}</time>
                <span>
                  count={(e.payload as { count?: number })?.count} / limit=
                  {(e.payload as { limit?: number })?.limit}, cooldown=
                  {(e.payload as { cooldown_s?: number })?.cooldown_s} s
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </section>
  );
}
