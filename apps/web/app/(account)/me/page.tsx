"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { setMe, useMe } from "@/lib/useMe";
import { Alert } from "@/components/Alert";

export const dynamic = "force-dynamic";

export default function MePage() {
  const { me, loading, refresh } = useMe();
  const [err, setErr] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !me) {
      // Probably an expired session.
    }
  }, [loading, me]);

  async function logout() {
    try {
      await apiPost("/auth/logout", {});
    } catch {}
    setMe(null);
    window.location.href = "/";
  }

  async function requestExport() {
    try {
      const r = await apiPost<{ id: string; state: string }>("/me/export", {});
      setInfo(`Export queued (${r.state}). You will receive an email when ready.`);
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : "failed");
    }
  }

  if (loading)
    return (
      <p role="status" aria-live="polite" className="text-sm text-[var(--color-fg-muted)]">
        Loading…
      </p>
    );
  if (!me)
    return (
      <section className="max-w-md mx-auto">
        <h1 className="text-2xl font-bold mb-3">Sign in required</h1>
        <p className="text-sm text-[var(--color-fg-muted)]">
          <Link href="/auth/login">Sign in</Link> to manage your account.
        </p>
      </section>
    );

  return (
    <section className="max-w-3xl mx-auto space-y-6">
      <header>
        <h1 className="text-2xl font-bold">My account</h1>
        <p className="text-sm text-[var(--color-fg-muted)]">
          Signed in as <strong>{me.email}</strong> ·{" "}
          <span className="capitalize">{me.role}</span>
        </p>
      </header>

      {info && <Alert kind="success">{info}</Alert>}
      {err && <Alert kind="error">{err}</Alert>}

      <nav aria-label="Account areas" className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <SectionLink
          href="/me/security"
          title="Security"
          desc="Change password, change email."
        />
        {me.role !== "user" && (
          <SectionLink
            href="/me/profile"
            title="Public profile"
            desc="Edit your contributor page (slug, bio, links)."
          />
        )}
        {me.role !== "user" && (
          <SectionLink
            href="/me/content"
            title="My content"
            desc="Drafts, submitted, published items. Upload videos and files from each item's edit page."
          />
        )}
        {me.role !== "user" && (
          <SectionLink
            href="/me/collections"
            title="Collections & courses"
            desc="Group items into ordered lecture series. Mark as Course for certificate-eligible completion criteria."
          />
        )}
        {me.role !== "user" && (
          <SectionLink
            href="/me/workshops"
            title="Workshops"
            desc="Schedule live or in-person sessions; appear on /workshops once approved."
          />
        )}
        <SectionLink
          href="/me/certificates"
          title="My certificates"
          desc="View and download your issued certificates."
        />
        {me.role === "user" && (
          <SectionLink
            href="/me/contributor"
            title="Become a contributor"
            desc="Apply to publish your own content."
          />
        )}
        {me.role === "contributor" && (
          <SectionLink
            href="/me/contributor"
            title="Contributor"
            desc="Application status, self-revoke."
          />
        )}
        {me.role === "admin" && (
          <SectionLink
            href="/admin"
            title="Admin"
            desc="Queues, users, settings, audit log."
          />
        )}
      </nav>

      <section className="border-t border-[var(--color-brand-blue-4)] pt-4 space-y-3">
        <h2 className="font-semibold">Data &amp; account</h2>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={requestExport}
            className="px-3 py-1 border border-[var(--color-brand-blue-2)] rounded text-sm"
          >
            Export my data
          </button>
          <Link
            href="/me/danger"
            className="px-3 py-1 border border-red-500 text-red-300 rounded text-sm"
          >
            Delete my account
          </Link>
          <button
            type="button"
            onClick={logout}
            className="px-3 py-1 border border-[var(--color-brand-blue-2)] rounded text-sm ml-auto"
          >
            Sign out
          </button>
        </div>
      </section>
    </section>
  );
}

function SectionLink({ href, title, desc }: { href: string; title: string; desc: string }) {
  return (
    <Link
      href={href}
      className="block border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded-lg p-4 hover:border-[var(--color-brand-cyan)] transition-colors"
    >
      <h3 className="font-semibold text-[var(--color-brand-cyan)]">{title}</h3>
      <p className="text-xs text-[var(--color-fg-muted)] mt-1">{desc}</p>
    </Link>
  );
}
