"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import { Alert } from "@/components/Alert";

type Counts = {
  pending_review_items: number;
  pending_applications: number;
  open_takedowns: number;
  open_comment_reports: number;
  open_cert_suggestions: number;
};

export default function AdminDashboard() {
  const [counts, setCounts] = useState<Counts | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    apiGet<Counts>("/admin/queue/counts")
      .then(setCounts)
      .catch((e) => setErr(String(e?.code ?? e)));
  }, []);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">Admin dashboard</h1>
        <p className="text-sm text-[var(--color-fg-muted)]">
          Open work across queues. Click a tile to act on it.
        </p>
      </header>
      {err && <Alert kind="error">{err}</Alert>}
      <ul className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {[
          {
            label: "Items pending review",
            n: counts?.pending_review_items,
            href: "/admin/queue?tab=items",
          },
          {
            label: "Contributor applications",
            n: counts?.pending_applications,
            href: "/admin/queue?tab=apps",
          },
          {
            label: "Open takedowns",
            n: counts?.open_takedowns,
            href: "/admin/queue?tab=takedowns",
          },
          {
            label: "Open comment reports",
            n: counts?.open_comment_reports,
            href: "/admin/queue?tab=reports",
          },
          {
            label: "Cert suggestions",
            n: counts?.open_cert_suggestions,
            href: "/admin/certificates",
          },
        ].map((t) => (
          <li key={t.label}>
            <Link
              href={t.href}
              className="block border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded-lg p-5 hover:border-[var(--color-brand-cyan)] transition-colors"
            >
              <div className="text-xs uppercase tracking-wide text-[var(--color-fg-muted)]">
                {t.label}
              </div>
              <div className="text-3xl font-bold mt-2 text-[var(--color-brand-cyan)]">
                {t.n ?? "—"}
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
