"use client";

import { useState } from "react";
import { Field } from "@/components/Field";
import { Alert } from "@/components/Alert";
import { FilePicker } from "@/components/FilePicker";

export const dynamic = "force-dynamic";

type VerifyResult = {
  cert_id: string;
  issued_at: string | null;
  revoked: boolean;
  recipient_display_name: string | null;
  issuer_label: string;
  valid: boolean | null;
};

export default function VerifyPage() {
  const [certId, setCertId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<VerifyResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setResult(null);
    if (!file || !certId) {
      setErr("Provide both a certificate ID and a PDF.");
      return;
    }
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("pdf", file);
      const r = await fetch(`/api/verify/${encodeURIComponent(certId)}`, {
        method: "POST",
        body: fd,
      });
      if (!r.ok) {
        const detail = (await r.json().catch(() => ({}))) as { detail?: string };
        setErr(detail.detail ?? "verification_failed");
        return;
      }
      setResult((await r.json()) as VerifyResult);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Verify a certificate</h1>
      <p className="text-sm text-[var(--color-fg-muted)] mb-6">
        Paste the certificate ID and upload the PDF. The signature is verified against the public
        key published at{" "}
        <a
          href="/api/.well-known/ndsc-cert-pubkey.json"
          target="_blank"
          rel="noopener noreferrer"
        >
          /.well-known/ndsc-cert-pubkey.json
        </a>
        .
      </p>
      <form onSubmit={onSubmit} className="space-y-4">
        <Field
          label="Certificate ID"
          value={certId}
          onChange={setCertId}
          required
          placeholder="e.g. 01H0123456789ABCDEFGHJKLMN"
        />
        <div className="space-y-1">
          <span className="block text-sm">
            PDF<span className="text-red-400 ml-1" aria-hidden>*</span>
          </span>
          <FilePicker
            id="pdf-input"
            accept="application/pdf,.pdf"
            file={file}
            onChange={setFile}
            buttonLabel="Choose PDF"
            placeholder="No PDF selected"
          />
        </div>
        {err && <Alert kind="error">{err}</Alert>}
        <button
          type="submit"
          disabled={busy}
          className="px-4 py-2 bg-[var(--color-brand-cyan)] text-black rounded font-medium disabled:opacity-60"
        >
          {busy ? "Verifying…" : "Verify"}
        </button>
      </form>
      {result && (
        <div
          role="status"
          aria-live="polite"
          className="mt-8 border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded-lg p-5 text-sm space-y-1"
        >
          <p>
            Signature:{" "}
            {result.valid === true ? (
              <span className="text-emerald-400 font-medium">VALID</span>
            ) : (
              <span className="text-red-400 font-medium">INVALID</span>
            )}
          </p>
          <p>Recipient: {result.recipient_display_name ?? "—"}</p>
          <p>Issuer: {result.issuer_label}</p>
          <p>Status: {result.revoked ? "Revoked" : "Active"}</p>
        </div>
      )}
    </section>
  );
}
