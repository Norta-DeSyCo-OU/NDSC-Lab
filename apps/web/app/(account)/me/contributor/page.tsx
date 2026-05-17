"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useMe } from "@/lib/useMe";
import { Field } from "@/components/Field";
import { Alert } from "@/components/Alert";

type AppStatus = {
  id: string | null;
  state: string | null;
  motivation: string | null;
  decision_reason: string | null;
  created_at: string | null;
};

export default function ContributorPage() {
  const { me, refresh } = useMe();
  const [app, setApp] = useState<AppStatus | null>(null);
  const [motivation, setMotivation] = useState("");
  const [links, setLinks] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState(false);
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      setApp(await apiGet<AppStatus>("/me/contributor-application"));
    } catch (e) {
      setApp(null);
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function apply(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setOk(false);
    setBusy(true);
    try {
      const linksObj = links.trim()
        ? Object.fromEntries(
            links.split(/\r?\n/).map((l) => l.split(/\s*=\s*|\s*:\s*/, 2)).filter((p) => p.length === 2),
          )
        : null;
      await apiPost("/me/contributor-application", { motivation, links: linksObj });
      setOk(true);
      await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function revoke() {
    const fate = prompt(
      "Content fate on revocation? Type one of: tombstone, reassign_house, delete",
      "tombstone",
    );
    if (!fate) return;
    try {
      await apiPost("/me/contributor/revoke", { confirm: true, content_fate: fate });
      refresh();
      window.location.href = "/me";
    } catch (e) {
      alert(e instanceof ApiError ? e.code : String(e));
    }
  }

  if (!me) return <p className="text-sm">Sign in required.</p>;

  if (me.role === "contributor") {
    return (
      <section className="max-w-2xl mx-auto space-y-4">
        <h1 className="text-2xl font-bold">Contributor</h1>
        <Alert kind="success">You are a contributor. Curate your page at <a href="/me/profile">/me/profile</a>.</Alert>
        <button
          type="button"
          onClick={revoke}
          className="px-3 py-1 border border-red-500 text-red-300 rounded text-sm"
        >
          Revoke contributor role
        </button>
      </section>
    );
  }

  if (me.role === "admin") {
    return (
      <section className="max-w-2xl mx-auto space-y-3">
        <h1 className="text-2xl font-bold">Contributor</h1>
        <p className="text-sm">As admin, you already have contributor permissions implicitly.</p>
      </section>
    );
  }

  return (
    <section className="max-w-2xl mx-auto space-y-6">
      <header>
        <h1 className="text-2xl font-bold">Become a contributor</h1>
        <p className="text-sm text-[var(--color-fg-muted)]">
          Tell us who you are and what you would publish. Admins review applications and respond by
          email.
        </p>
      </header>

      {app && app.state === "pending" && (
        <Alert kind="info">
          Application submitted on {new Date(app.created_at!).toLocaleString()}. Awaiting review.
        </Alert>
      )}
      {app && app.state === "rejected" && (
        <Alert kind="warn">
          Application rejected{app.decision_reason ? `: ${app.decision_reason}` : ""}. You may
          re-apply after 7 days.
        </Alert>
      )}

      <form onSubmit={apply} className="space-y-3">
        <div className="space-y-1">
          <label htmlFor="motivation" className="block text-sm">
            Motivation<span className="text-red-400 ml-1" aria-hidden>*</span>
          </label>
          <textarea
            id="motivation"
            required
            minLength={20}
            value={motivation}
            onChange={(e) => setMotivation(e.target.value)}
            rows={5}
            className="w-full px-3 py-2 rounded bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)]"
          />
          <p className="text-xs text-[var(--color-fg-muted)]">
            What you intend to publish, your background, links to prior work.
          </p>
        </div>
        <div className="space-y-1">
          <label htmlFor="links" className="block text-sm">
            Links (optional, one per line, <code>label = url</code>)
          </label>
          <textarea
            id="links"
            value={links}
            onChange={(e) => setLinks(e.target.value)}
            rows={3}
            placeholder={"orcid = https://orcid.org/0000-0000-0000-0000\nsite = https://example.com"}
            className="w-full px-3 py-2 rounded bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)] font-mono text-xs"
          />
        </div>
        {ok && <Alert kind="success">Application submitted.</Alert>}
        {err && <Alert kind="error">{err}</Alert>}
        <button
          type="submit"
          disabled={busy}
          className="px-4 py-2 bg-[var(--color-brand-cyan)] text-black rounded font-medium disabled:opacity-60"
        >
          {busy ? "Submitting…" : "Apply"}
        </button>
      </form>
    </section>
  );
}
