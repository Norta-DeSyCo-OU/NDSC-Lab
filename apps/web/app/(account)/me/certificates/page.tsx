"use client";

import { useEffect, useState } from "react";
import { apiGet, ApiError } from "@/lib/api";
import { Alert } from "@/components/Alert";

type Cert = {
  id: string;
  collection_id: string;
  issued_at: string;
  revoked_at: string | null;
  signing_key_id: string;
};

export const dynamic = "force-dynamic";

export default function MyCerts() {
  const [rows, setRows] = useState<Cert[]>([]);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    apiGet<Cert[]>("/me/certificates")
      .then(setRows)
      .catch((e) => setErr(e instanceof ApiError ? e.code : String(e)));
  }, []);

  return (
    <section className="max-w-2xl mx-auto space-y-4">
      <header>
        <h1 className="text-2xl font-bold">My certificates</h1>
        <p className="text-sm text-[var(--color-fg-muted)]">
          Ed25519-signed PDFs. Anyone can verify them at <code>/verify/&lt;id&gt;</code>.
        </p>
      </header>

      {err && <Alert kind="error">{err}</Alert>}

      <ul className="space-y-2">
        {rows.map((c) => (
          <li
            key={c.id}
            className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded p-3 flex flex-wrap items-baseline gap-3 justify-between"
          >
            <div>
              <div className="font-mono text-xs">{c.id}</div>
              <div className="text-xs text-[var(--color-fg-muted)]">
                Issued {new Date(c.issued_at).toLocaleDateString()} · key {c.signing_key_id}
              </div>
            </div>
            <div className="space-x-2 text-sm">
              {c.revoked_at ? (
                <span className="text-red-400">Revoked</span>
              ) : (
                <a
                  href={`/verify/${c.id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-2 py-1 border border-[var(--color-brand-blue-2)] rounded inline-block text-xs"
                >
                  Verify
                </a>
              )}
            </div>
          </li>
        ))}
        {rows.length === 0 && !err && (
          <li className="text-sm text-[var(--color-fg-muted)] py-6 text-center border border-dashed border-[var(--color-brand-blue-4)] rounded">
            No certificates yet.
          </li>
        )}
      </ul>
    </section>
  );
}
