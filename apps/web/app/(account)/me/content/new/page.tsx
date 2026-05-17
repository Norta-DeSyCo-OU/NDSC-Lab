"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { apiPost, ApiError } from "@/lib/api";
import { Field } from "@/components/Field";
import { Alert } from "@/components/Alert";
import { MarkdownPreview } from "@/components/MarkdownPreview";
import { AttachmentManager } from "@/components/AttachmentManager";

const LICENSES = [
  ["cc-by-4.0", "CC BY 4.0 (default)"],
  ["cc-by-sa-4.0", "CC BY-SA 4.0"],
  ["cc-by-nc-4.0", "CC BY-NC 4.0"],
  ["cc0-1.0", "CC0 1.0 (public domain)"],
  ["arr", "All rights reserved"],
] as const;

type Step = "meta" | "files";

export default function NewItemPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("meta");
  const [createdId, setCreatedId] = useState<string | null>(null);
  const [type, setType] = useState<"article" | "video" | "teaching_material">("article");
  // Default to "hosted" — most users want to upload their own file. Embed is
  // for already-public YouTube/Vimeo content.
  const [videoKind, setVideoKind] = useState<"hosted" | "embed">("hosted");
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [body, setBody] = useState("");
  const [externalUrl, setExternalUrl] = useState("");
  const [license, setLicense] = useState<string>("cc-by-4.0");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  function needsFiles(): boolean {
    if (type === "video" && videoKind === "hosted") return true;
    if (type === "teaching_material") return true;
    if (type === "article") return false;
    return false;
  }

  async function saveDraft() {
    setErr(null);
    setInfo(null);
    setBusy(true);
    try {
      const payload: Record<string, unknown> = {
        type,
        title,
        summary: summary || null,
        body_md: body || null,
        external_url: externalUrl || null,
        license,
      };
      if (type === "video") payload.video_kind = videoKind;
      const created = await apiPost<{ id: string }>("/items", payload);
      setCreatedId(created.id);
      if (needsFiles()) {
        setStep("files");
        setInfo(
          'Draft saved. Upload your file(s) below. When done, click "Submit for review" or "Go to full editor".',
        );
      } else {
        // No files needed (article / embed video) — go straight to edit page.
        router.push(`/me/content/${created.id}/edit`);
      }
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function submitForReview() {
    if (!createdId) return;
    setBusy(true);
    try {
      await apiPost(`/items/${createdId}/submit`, {});
      router.push(`/me/content/${createdId}/edit`);
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : String(e));
    } finally {
      setBusy(false);
    }
  }

  const attachmentRole =
    type === "video"
      ? "video_primary"
      : type === "teaching_material"
        ? "teaching_material_file"
        : "article_attachment";

  return (
    <section className="max-w-3xl mx-auto space-y-5">
      <header>
        <h1 className="text-2xl font-bold">New item</h1>
        <p className="text-sm text-[var(--color-fg-muted)]">
          {step === "meta"
            ? "Step 1 — fill the metadata, then save. If your item needs a file (hosted video / teaching material), the uploader appears next."
            : "Step 2 — upload your file(s). They go through ClamAV before becoming public."}
        </p>
      </header>

      {step === "meta" && (
        <>
          <fieldset className="space-y-3 border border-[var(--color-brand-blue-4)] rounded p-4">
            <legend className="text-sm px-2">Type</legend>
            <div className="flex flex-wrap gap-3 text-sm">
              {(
                [
                  ["article", "Article"],
                  ["video", "Video"],
                  ["teaching_material", "Teaching material"],
                ] as const
              ).map(([v, l]) => (
                <label key={v} className="flex items-center gap-1">
                  <input
                    type="radio"
                    name="type"
                    checked={type === v}
                    onChange={() => setType(v)}
                  />
                  {l}
                </label>
              ))}
            </div>
            {type === "video" && (
              <div className="flex flex-wrap gap-3 text-sm">
                <span className="text-[var(--color-fg-muted)]">Source:</span>
                {(
                  [
                    ["embed", "Embed (YouTube/Vimeo/Panopto URL)"],
                    ["hosted", "Hosted upload (file)"],
                  ] as const
                ).map(([v, l]) => (
                  <label key={v} className="flex items-center gap-1">
                    <input
                      type="radio"
                      name="video_kind"
                      checked={videoKind === v}
                      onChange={() => setVideoKind(v)}
                    />
                    {l}
                  </label>
                ))}
              </div>
            )}
          </fieldset>

          <Field label="Title" value={title} onChange={setTitle} required minLength={3} />
          <Field label="Summary (1 sentence)" value={summary} onChange={setSummary} />

          {type === "video" && videoKind === "embed" && (
            <Field
              label="Video URL (YouTube / Vimeo / Panopto)"
              type="url"
              value={externalUrl}
              onChange={setExternalUrl}
            />
          )}
          {type === "teaching_material" && (
            <Field
              label="External link (optional)"
              type="url"
              value={externalUrl}
              onChange={setExternalUrl}
              help="Leave empty if you will attach a file in step 2."
            />
          )}

          {(type === "article" || type === "video") && (
            <div className="space-y-1">
              <label htmlFor="body" className="block text-sm">
                Body (Markdown)
              </label>
              <textarea
                id="body"
                rows={14}
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder="# Hello world&#10;&#10;Write Markdown. **Bold**, *italic*, `code`, [links](https://…)."
                className="w-full px-3 py-2 rounded bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)] font-mono text-sm"
              />
            </div>
          )}

          {body && <MarkdownPreview value={body} />}

          <div className="space-y-1">
            <label htmlFor="license" className="block text-sm">
              License
            </label>
            <select
              id="license"
              value={license}
              onChange={(e) => setLicense(e.target.value)}
              className="px-2 py-1 rounded bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)]"
            >
              {LICENSES.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </div>

          {err && <Alert kind="error">{err}</Alert>}

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={saveDraft}
              disabled={busy || title.trim().length < 3}
              className="px-4 py-2 bg-[var(--color-brand-cyan)] text-black rounded font-medium disabled:opacity-60"
            >
              {busy
                ? "Saving…"
                : needsFiles()
                  ? "Save draft & continue to files →"
                  : "Save draft"}
            </button>
          </div>
        </>
      )}

      {step === "files" && createdId && (
        <>
          {info && <Alert kind="success">{info}</Alert>}
          {err && <Alert kind="error">{err}</Alert>}

          <AttachmentManager
            itemId={createdId}
            defaultRole={attachmentRole}
            allowedRoles={[attachmentRole]}
          />

          <div className="flex flex-wrap gap-3 pt-2">
            <button
              type="button"
              onClick={submitForReview}
              disabled={busy}
              className="px-4 py-2 bg-[var(--color-brand-cyan)] text-black rounded font-medium disabled:opacity-60"
            >
              {busy ? "Submitting…" : "Submit for review"}
            </button>
            <Link
              href={`/me/content/${createdId}/edit`}
              className="px-4 py-2 border border-[var(--color-brand-blue-2)] rounded"
            >
              Go to full editor
            </Link>
          </div>

          <p className="text-xs text-[var(--color-fg-muted)]">
            Tip: you can always re-open this item later at{" "}
            <Link href={`/me/content/${createdId}/edit`}>
              /me/content/{createdId}/edit
            </Link>
            .
          </p>
        </>
      )}
    </section>
  );
}
