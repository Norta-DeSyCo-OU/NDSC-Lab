"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useMe } from "@/lib/useMe";
import { Alert } from "@/components/Alert";
import { Field } from "@/components/Field";

type Workshop = {
  id: string;
  title: string;
  slug: string;
  starts_at: string;
  ends_at: string;
  state: string;
  is_online: boolean;
  location: string | null;
  registration_url: string | null;
  speakers: string[];
};

export const dynamic = "force-dynamic";

export default function MyWorkshopsPage() {
  const { me } = useMe();
  const [rows, setRows] = useState<Workshop[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Form state
  const [title, setTitle] = useState("");
  const [abstract, setAbstract] = useState("");
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [isOnline, setIsOnline] = useState(true);
  const [location, setLocation] = useState("");
  const [regUrl, setRegUrl] = useState("");

  async function load() {
    try {
      setRows(await apiGet<Workshop[]>("/me/workshops"));
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : String(e));
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!me) return;
    setErr(null);
    setInfo(null);
    setBusy(true);
    try {
      const payload = {
        title,
        abstract_md: abstract || null,
        starts_at: new Date(startsAt).toISOString(),
        ends_at: new Date(endsAt).toISOString(),
        location: isOnline ? null : location || null,
        is_online: isOnline,
        registration_url: regUrl || null,
        speakers: [me.id],
      };
      await apiPost<Workshop>("/workshops", payload);
      setInfo(
        me.role === "admin"
          ? "Workshop published."
          : "Workshop submitted — admins will review and publish it.",
      );
      setTitle("");
      setAbstract("");
      setStartsAt("");
      setEndsAt("");
      setLocation("");
      setRegUrl("");
      await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (me && me.role === "user")
    return (
      <section className="max-w-md mx-auto">
        <h1 className="text-2xl font-bold mb-3">Contributor access required</h1>
        <p className="text-sm text-[var(--color-fg-muted)]">
          Only contributors and admins can host workshops.{" "}
          <Link href="/me/contributor">Apply to contribute</Link>.
        </p>
      </section>
    );

  return (
    <section className="max-w-3xl mx-auto space-y-6">
      <header>
        <h1 className="text-2xl font-bold">My workshops</h1>
        <p className="text-sm text-[var(--color-fg-muted)]">
          Schedule a workshop, talk, or seminar. Listings appear publicly at{" "}
          <Link href="/workshops">/workshops</Link> once approved.
        </p>
      </header>

      {info && <Alert kind="success">{info}</Alert>}
      {err && <Alert kind="error">{err}</Alert>}

      <form
        onSubmit={create}
        className="border border-[var(--color-brand-blue-4)] rounded p-4 space-y-3"
      >
        <h2 className="font-semibold">Create workshop</h2>
        <Field label="Title" value={title} onChange={setTitle} required minLength={3} />
        <div className="space-y-1">
          <label htmlFor="abstract" className="block text-sm">
            Abstract (Markdown, optional)
          </label>
          <textarea
            id="abstract"
            rows={5}
            value={abstract}
            onChange={(e) => setAbstract(e.target.value)}
            className="w-full px-3 py-2 rounded bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)] font-mono text-sm"
          />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <label className="text-sm">
            <span className="block mb-1">Starts</span>
            <input
              type="datetime-local"
              required
              value={startsAt}
              onChange={(e) => setStartsAt(e.target.value)}
              className="w-full px-2 py-1 rounded bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)]"
            />
          </label>
          <label className="text-sm">
            <span className="block mb-1">Ends</span>
            <input
              type="datetime-local"
              required
              value={endsAt}
              onChange={(e) => setEndsAt(e.target.value)}
              className="w-full px-2 py-1 rounded bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)]"
            />
          </label>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={isOnline}
            onChange={(e) => setIsOnline(e.target.checked)}
          />
          Online (no physical location)
        </label>
        {!isOnline && (
          <Field label="Location" value={location} onChange={setLocation} />
        )}
        <Field
          label="Registration URL (optional)"
          type="url"
          value={regUrl}
          onChange={setRegUrl}
        />
        <button
          type="submit"
          disabled={busy || !title || !startsAt || !endsAt}
          className="px-4 py-2 bg-[var(--color-brand-cyan)] text-black rounded font-medium disabled:opacity-60"
        >
          {busy ? "Saving…" : me?.role === "admin" ? "Publish" : "Submit for review"}
        </button>
      </form>

      <section aria-labelledby="mine-h" className="space-y-2">
        <h2 id="mine-h" className="font-semibold">
          Your workshops
        </h2>
        {rows.length === 0 && (
          <p className="text-sm text-[var(--color-fg-muted)]">
            None yet. Create one above.
          </p>
        )}
        <ul className="space-y-2">
          {rows.map((w) => (
            <li
              key={w.id}
              className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded p-3"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h3 className="font-semibold">{w.title}</h3>
                <span
                  className={
                    "text-xs " +
                    (w.state === "published"
                      ? "text-emerald-400"
                      : w.state === "pending_review"
                        ? "text-yellow-400"
                        : "text-[var(--color-fg-muted)]")
                  }
                >
                  {w.state}
                </span>
              </div>
              <p className="text-xs text-[var(--color-fg-muted)] mt-1">
                {new Date(w.starts_at).toLocaleString()} →{" "}
                {new Date(w.ends_at).toLocaleString()}
              </p>
              <p className="text-xs mt-1">
                {w.is_online ? "Online" : (w.location ?? "TBA")}
                {w.registration_url && (
                  <>
                    {" · "}
                    <a
                      href={w.registration_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[var(--color-brand-cyan)] underline"
                    >
                      Registration
                    </a>
                  </>
                )}
              </p>
            </li>
          ))}
        </ul>
      </section>
    </section>
  );
}
