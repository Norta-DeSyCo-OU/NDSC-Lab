import { apiUrl } from "@/lib/api";

type VerifyResponse = {
  cert_id: string;
  issued_at: string | null;
  revoked: boolean;
  recipient_display_name: string | null;
  issuer_label: string;
};

async function fetchVerify(id: string): Promise<VerifyResponse | null> {
  try {
    const r = await fetch(apiUrl(`/verify/${id}`), { cache: "no-store" });
    if (!r.ok) return null;
    return (await r.json()) as VerifyResponse;
  } catch {
    return null;
  }
}

export default async function VerifyByIdPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const data = await fetchVerify(id);

  if (!data) {
    return (
      <div className="max-w-2xl mx-auto">
        <h1 className="text-2xl font-bold mb-4">Certificate not found</h1>
        <p className="text-sm text-[var(--color-fg-muted)]">
          No certificate with ID <code>{id}</code> was found in our records.
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Certificate verification</h1>
      <div className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded-lg p-6 space-y-3">
        <dl className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-sm">
          <dt className="text-[var(--color-fg-muted)]">Certificate ID</dt>
          <dd className="sm:col-span-2 font-mono">{data.cert_id}</dd>
          <dt className="text-[var(--color-fg-muted)]">Recipient</dt>
          <dd className="sm:col-span-2">{data.recipient_display_name ?? "—"}</dd>
          <dt className="text-[var(--color-fg-muted)]">Issued</dt>
          <dd className="sm:col-span-2">{data.issued_at ?? "—"}</dd>
          <dt className="text-[var(--color-fg-muted)]">Issuer</dt>
          <dd className="sm:col-span-2">{data.issuer_label}</dd>
          <dt className="text-[var(--color-fg-muted)]">Status</dt>
          <dd className="sm:col-span-2">
            {data.revoked ? (
              <span className="text-red-400">Revoked</span>
            ) : (
              <span className="text-emerald-400">Valid record</span>
            )}
          </dd>
        </dl>
        <p className="text-xs text-[var(--color-fg-muted)] pt-2">
          To cryptographically verify a downloaded PDF, upload it on the{" "}
          <a href="/verify">Verify page</a>.
        </p>
      </div>
    </div>
  );
}
