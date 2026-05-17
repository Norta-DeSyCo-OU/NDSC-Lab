"use client";

import { useEffect, useState } from "react";
import { apiGet, ApiError } from "@/lib/api";
import { Alert } from "@/components/Alert";
import { FilePicker } from "@/components/FilePicker";

type Attachment = {
  id: string;
  role: string;
  mime: string;
  bytes: number;
  state: string;
  r2_key: string;
};

const ROLE_LABEL: Record<string, string> = {
  video_primary: "Video file (hosted)",
  article_attachment: "Article attachment (PDF/image/etc.)",
  teaching_material_file: "Teaching material file",
  profile_photo: "Profile photo",
};

// Browsers' file pickers filter by **either** MIME or file extension — many
// platforms (macOS Finder, Windows Explorer) only honor extensions reliably,
// and `.mov` is often reported as `application/octet-stream` so a pure MIME
// allowlist hides the file in the picker. Always include both.
const ALLOWED_MIMES_BY_ROLE: Record<string, string> = {
  video_primary: "video/*,.mp4,.mov,.m4v,.webm,.mkv,.qt",
  article_attachment:
    "application/pdf,application/zip,image/png,image/jpeg,image/webp,text/plain,text/markdown,text/csv,.pdf,.zip,.png,.jpg,.jpeg,.webp,.txt,.md,.csv",
  teaching_material_file:
    "application/pdf,application/zip,application/x-7z-compressed,application/vnd.openxmlformats-officedocument.presentationml.presentation,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown,text/csv,.pdf,.zip,.7z,.pptx,.docx,.txt,.md,.csv",
  profile_photo: "image/*,.png,.jpg,.jpeg,.webp",
};

function csrfCookie(): string {
  const m = document.cookie.match(/(?:^|; )ndsc_csrf=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

function humanBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export function AttachmentManager({
  itemId,
  defaultRole,
  allowedRoles,
}: {
  itemId: string;
  defaultRole: string;
  allowedRoles: string[];
}) {
  const [rows, setRows] = useState<Attachment[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [role, setRole] = useState(defaultRole);
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState<number | null>(null);

  async function load() {
    try {
      setRows(await apiGet<Attachment[]>(`/uploads/by-item/${itemId}`));
    } catch (e) {
      setRows([]);
      if (e instanceof ApiError && e.status === 403) {
        setErr("You don't own this item.");
      }
    }
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [itemId]);

  async function _ensureCsrf(): Promise<string> {
    let tok = csrfCookie();
    if (tok) return tok;
    await fetch("/api/csrf", { credentials: "include" });
    tok = csrfCookie();
    return tok;
  }

  async function onUpload(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setInfo(null);
    if (!file) {
      setErr("Pick a file first.");
      return;
    }
    setBusy(true);
    setProgress(0);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("item_id", itemId);
      fd.append("role", role);
      const csrf = await _ensureCsrf();
      // XHR for progress events.
      const result = await new Promise<{ attachment_id: string; state: string }>(
        (resolve, reject) => {
          const xhr = new XMLHttpRequest();
          xhr.open("POST", "/api/uploads/simple");
          xhr.withCredentials = true;
          xhr.setRequestHeader("X-CSRF-Token", csrf);
          xhr.upload.onprogress = (ev) => {
            if (ev.lengthComputable) setProgress((ev.loaded / ev.total) * 100);
          };
          xhr.onload = () => {
            let data: { attachment_id?: string; state?: string; detail?: unknown } = {};
            try {
              data = JSON.parse(xhr.responseText);
            } catch {
              /* non-JSON body — fall through */
            }
            if (xhr.status >= 200 && xhr.status < 300 && data.attachment_id) {
              resolve(data as { attachment_id: string; state: string });
            } else {
              const detail =
                typeof data.detail === "string"
                  ? data.detail
                  : data.detail
                    ? JSON.stringify(data.detail)
                    : `HTTP ${xhr.status}`;
              reject(new Error(detail));
            }
          };
          xhr.onerror = () => reject(new Error("network_error"));
          xhr.send(fd);
        },
      );
      setInfo(`Uploaded. Attachment ${result.attachment_id} → state=${result.state} (ClamAV scan running).`);
      setFile(null);
      setProgress(null);
      await load();
    } catch (e) {
      setErr(String(e));
      setProgress(null);
    } finally {
      setBusy(false);
    }
  }

  async function del(a: Attachment) {
    if (!confirm(`Delete ${a.r2_key.split("/").pop()}?`)) return;
    try {
      const csrf = csrfCookie();
      const r = await fetch(`/api/uploads/${a.id}`, {
        method: "DELETE",
        credentials: "include",
        headers: { "X-CSRF-Token": csrf },
      });
      if (!r.ok) throw new Error(`${r.status}`);
      await load();
    } catch (e) {
      setErr(String(e));
    }
  }

  return (
    <section
      aria-labelledby="att-h"
      className="border border-[var(--color-brand-blue-4)] rounded p-4 space-y-3 bg-[var(--color-bg-panel)]"
    >
      <h2 id="att-h" className="font-semibold">
        Attachments
      </h2>
      <form onSubmit={onUpload} className="flex flex-wrap gap-2 items-end" encType="multipart/form-data">
        <label>
          <span className="block text-xs text-[var(--color-fg-muted)] mb-1">Type</span>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="px-2 py-1 rounded bg-[var(--color-bg-base)] border border-[var(--color-brand-blue-4)] text-sm"
          >
            {allowedRoles.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABEL[r] ?? r}
              </option>
            ))}
          </select>
        </label>
        <div>
          <span className="block text-xs text-[var(--color-fg-muted)] mb-1">File</span>
          <FilePicker
            id={`att-file-${itemId}`}
            accept={ALLOWED_MIMES_BY_ROLE[role] ?? ""}
            file={file}
            onChange={setFile}
            buttonLabel="Choose file"
            disabled={busy}
          />
        </div>
        <button
          type="submit"
          disabled={busy || !file}
          aria-disabled={busy || !file}
          className="px-3 py-1.5 bg-[var(--color-brand-cyan)] text-black rounded text-sm font-medium disabled:opacity-60"
        >
          {busy ? "Uploading…" : file ? "Upload" : "Pick a file first"}
        </button>
        {progress !== null && (
          <progress
            value={progress}
            max={100}
            className="w-full"
            aria-label="Upload progress"
          />
        )}
      </form>
      <p className="text-xs text-[var(--color-fg-muted)]">
        Streamed in 8 MB chunks; no fixed upper bound (storage quota and your
        network speed are the only practical limits). ClamAV scans every file
        before publication. Videos in non-MP4 formats (e.g. <code>.mov</code>,{" "}
        <code>.webm</code>) are auto-converted to a web-friendly MP4 in the
        background. If the picker hides your file, change the picker filter to{" "}
        <em>&quot;All files&quot;</em>.
      </p>

      {err && <Alert kind="error">{err}</Alert>}
      {info && <Alert kind="success">{info}</Alert>}

      <ul className="space-y-1 text-sm">
        {rows.map((a) => (
          <li
            key={a.id}
            className="border border-[var(--color-brand-blue-4)]/50 rounded px-3 py-2 flex flex-wrap items-baseline justify-between gap-2"
          >
            <div className="min-w-0">
              <div className="font-mono text-xs truncate">{a.r2_key.split("/").pop()}</div>
              <div className="text-xs text-[var(--color-fg-muted)]">
                {ROLE_LABEL[a.role] ?? a.role} · {a.mime} · {humanBytes(a.bytes)}
              </div>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span
                className={
                  a.state === "clean"
                    ? "text-emerald-400"
                    : a.state === "quarantined"
                      ? "text-red-400"
                      : "text-yellow-400"
                }
              >
                {a.state}
              </span>
              <button
                type="button"
                onClick={() => del(a)}
                className="text-red-400 underline"
              >
                Delete
              </button>
            </div>
          </li>
        ))}
        {rows.length === 0 && (
          <li className="text-xs text-[var(--color-fg-muted)]">No attachments yet.</li>
        )}
      </ul>
    </section>
  );
}
