"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useMe } from "@/lib/useMe";
import { Alert } from "@/components/Alert";

type Collection = {
  id: string;
  slug: string;
  title: string;
  description_md: string | null;
  is_course: boolean;
};

export const dynamic = "force-dynamic";

export default function MyCollections() {
  const { me } = useMe();
  const [rows, setRows] = useState<Collection[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [isCourse, setIsCourse] = useState(false);
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      setRows(await apiGet<Collection[]>("/me/collections"));
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : String(e));
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await apiPost<Collection>("/collections", { title, is_course: isCourse });
      setTitle("");
      setIsCourse(false);
      await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (me && me.role === "user") {
    return (
      <Alert kind="warn">
        Collections (and lecture-series courses) require contributor access.{" "}
        <Link href="/me/contributor">Apply</Link>.
      </Alert>
    );
  }

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">My collections</h1>
        <p className="text-sm text-[var(--color-fg-muted)]">
          Group items into ordered sets. Toggle <em>Course</em> to enable per-item completion
          criteria and certificate-issuance suggestions.
        </p>
      </header>

      <form
        onSubmit={create}
        className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded p-4 space-y-3"
      >
        <h2 className="font-semibold">New collection</h2>
        <label className="block">
          <span className="block text-sm mb-1">Title</span>
          <input
            required
            minLength={3}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full px-3 py-2 rounded bg-[var(--color-bg-base)] border border-[var(--color-brand-blue-4)]"
          />
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={isCourse}
            onChange={(e) => setIsCourse(e.target.checked)}
          />
          <span>Mark as Course (enables completion criteria + certs)</span>
        </label>
        {err && <Alert kind="error">{err}</Alert>}
        <button
          type="submit"
          disabled={busy || title.length < 3}
          className="px-3 py-1 bg-[var(--color-brand-cyan)] text-black rounded text-sm font-medium disabled:opacity-60"
        >
          {busy ? "Creating…" : "Create"}
        </button>
      </form>

      <ul className="space-y-2">
        {rows.map((c) => (
          <li
            key={c.id}
            className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded p-3 flex flex-wrap items-baseline gap-3 justify-between"
          >
            <div className="min-w-0">
              <Link href={`/me/collections/${c.id}`} className="font-semibold">
                {c.title}
              </Link>
              <div className="text-xs text-[var(--color-fg-muted)]">
                <span className="font-mono">/c/{c.slug}</span>
                {c.is_course && (
                  <span className="ml-2 px-2 py-0.5 rounded bg-[var(--color-brand-blue-4)] text-[var(--color-brand-cyan)]">
                    Course
                  </span>
                )}
              </div>
            </div>
            <Link
              href={`/me/collections/${c.id}`}
              className="text-xs px-2 py-1 border border-[var(--color-brand-blue-2)] rounded"
            >
              Edit
            </Link>
          </li>
        ))}
        {rows.length === 0 && (
          <li className="text-sm text-[var(--color-fg-muted)] py-6 text-center border border-dashed border-[var(--color-brand-blue-4)] rounded">
            No collections yet. Create one above.
          </li>
        )}
      </ul>
    </section>
  );
}
