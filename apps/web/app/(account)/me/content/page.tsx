"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiGet, ApiError } from "@/lib/api";
import { useMe } from "@/lib/useMe";
import { Alert } from "@/components/Alert";

type MyItem = {
  id: string;
  type: string;
  title: string;
  slug: string;
  state: string;
  summary: string | null;
  published_at: string | null;
  updated_at: string;
};

export const dynamic = "force-dynamic";

export default function MyContent() {
  const { me } = useMe();
  const [items, setItems] = useState<MyItem[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("");

  async function load() {
    try {
      const url = filter ? `/me/items?state=${filter}&limit=200` : "/me/items?limit=200";
      setItems(await apiGet<MyItem[]>(url));
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : String(e));
    }
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  if (me && me.role === "user") {
    return (
      <Alert kind="warn">
        Apply to become a contributor first. <Link href="/me/contributor">Apply</Link>.
      </Alert>
    );
  }

  return (
    <section className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">My content</h1>
        <div className="flex gap-2 items-center">
          <label className="text-sm">
            Filter:{" "}
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="px-2 py-1 rounded bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)] text-sm"
            >
              <option value="">All</option>
              <option value="draft">Draft</option>
              <option value="pending_review">Pending review</option>
              <option value="published">Published</option>
              <option value="tombstoned">Tombstoned</option>
            </select>
          </label>
          <Link
            href="/me/content/new"
            className="px-3 py-1 bg-[var(--color-brand-cyan)] text-black rounded text-sm font-medium"
          >
            + New
          </Link>
        </div>
      </header>

      {err && <Alert kind="error">{err}</Alert>}

      <ul className="space-y-2">
        {items.map((i) => (
          <li
            key={i.id}
            className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded p-3 flex flex-wrap gap-3 items-baseline justify-between"
          >
            <div className="min-w-0">
              <div className="text-xs uppercase tracking-wide text-[var(--color-brand-cyan)]">
                {i.type.replace("_", " ")}
              </div>
              <Link href={`/me/content/${i.id}/edit`} className="font-semibold">
                {i.title}
              </Link>
              {i.summary && (
                <p className="text-xs text-[var(--color-fg-muted)] mt-1 line-clamp-1">
                  {i.summary}
                </p>
              )}
            </div>
            <div className="text-xs space-x-2">
              <span
                className={
                  i.state === "published"
                    ? "text-emerald-400"
                    : i.state === "pending_review"
                      ? "text-yellow-400"
                      : i.state === "tombstoned"
                        ? "text-red-400"
                        : "text-[var(--color-fg-muted)]"
                }
              >
                {i.state}
              </span>
              <Link
                href={`/me/content/${i.id}/edit`}
                className="px-2 py-1 border border-[var(--color-brand-blue-2)] rounded inline-block"
              >
                Edit
              </Link>
              {i.state === "published" && (
                <Link
                  href={`/items/${i.id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-2 py-1 border border-[var(--color-brand-blue-2)] rounded inline-block"
                >
                  View
                </Link>
              )}
            </div>
          </li>
        ))}
        {items.length === 0 && (
          <li className="text-sm text-[var(--color-fg-muted)] py-6 text-center border border-dashed border-[var(--color-brand-blue-4)] rounded">
            No items yet.{" "}
            <Link href="/me/content/new" className="text-[var(--color-brand-cyan)]">
              Create your first
            </Link>
            .
          </li>
        )}
      </ul>
    </section>
  );
}
