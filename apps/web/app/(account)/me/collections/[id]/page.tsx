"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { apiGet, apiPost, apiPut, ApiError } from "@/lib/api";
import { Alert } from "@/components/Alert";

type CollectionDetail = {
  id: string;
  slug: string;
  title: string;
  description_md: string | null;
  is_course: boolean;
  items: {
    id: string;
    title: string;
    type: string;
    state: string;
    position: number;
    is_required_for_course: boolean;
    completion_rule: Record<string, unknown> | null;
  }[];
};

type MyItem = { id: string; title: string; type: string; state: string };

export const dynamic = "force-dynamic";

function csrf(): string {
  const m = document.cookie.match(/(?:^|; )ndsc_csrf=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

export default function CollectionEdit({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [coll, setColl] = useState<CollectionDetail | null>(null);
  const [myItems, setMyItems] = useState<MyItem[]>([]);
  const [pickItem, setPickItem] = useState("");
  const [pickRequired, setPickRequired] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const c = await apiGet<CollectionDetail>(`/collections/${id}`);
      setColl(c);
      const items = await apiGet<MyItem[]>("/me/items?limit=200");
      // Only allow attaching items NOT already in the collection.
      const inSet = new Set(c.items.map((it) => it.id));
      setMyItems(items.filter((i) => !inSet.has(i.id)));
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : String(e));
    }
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function addItem() {
    if (!pickItem) return;
    setErr(null);
    setBusy(true);
    try {
      await apiPost(`/collections/${id}/items`, {
        item_id: pickItem,
        position: coll?.items.length ?? 0,
        is_required_for_course: pickRequired,
      });
      setPickItem("");
      await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.code : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function removeItem(item_id: string) {
    if (!confirm("Remove from collection?")) return;
    try {
      const r = await fetch(`/api/collections/${id}/items/${item_id}`, {
        method: "DELETE",
        credentials: "include",
        headers: { "X-CSRF-Token": csrf() },
      });
      if (!r.ok) throw new Error(`${r.status}`);
      await load();
    } catch (e) {
      setErr(String(e));
    }
  }

  async function toggleCourse() {
    if (!coll) return;
    try {
      const r = await fetch(`/api/collections/${id}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf() },
        body: JSON.stringify({ is_course: !coll.is_course }),
      });
      if (!r.ok) throw new Error(`${r.status}`);
      await load();
    } catch (e) {
      setErr(String(e));
    }
  }

  async function reorder(nextIds: string[]) {
    if (!coll) return;
    const prev = coll.items;
    // Optimistic update so the UI reacts immediately, then reconcile from server.
    setColl({
      ...coll,
      items: nextIds
        .map((id) => prev.find((p) => p.id === id))
        .filter((x): x is CollectionDetail["items"][number] => !!x)
        .map((it, i) => ({ ...it, position: i })),
    });
    setErr(null);
    try {
      await apiPut(`/collections/${id}/items/order`, { item_ids: nextIds });
      await load();
    } catch (e) {
      // Roll back optimistic order on failure.
      setColl({ ...coll, items: prev });
      setErr(e instanceof ApiError ? e.code : String(e));
    }
  }

  function moveItem(index: number, delta: -1 | 1) {
    if (!coll) return;
    const next = coll.items.map((it) => it.id);
    const j = index + delta;
    if (j < 0 || j >= next.length) return;
    [next[index], next[j]] = [next[j], next[index]];
    reorder(next);
  }

  async function setRule(item_id: string, rule: Record<string, unknown>) {
    try {
      const r = await fetch(`/api/collections/${id}/items/${item_id}/rule`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf() },
        body: JSON.stringify({ rule }),
      });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        throw new Error((j as { detail?: string }).detail ?? `${r.status}`);
      }
      setInfo("Rule saved.");
      await load();
    } catch (e) {
      setErr(String(e));
    }
  }

  if (!coll)
    return (
      <p role="status" aria-live="polite" className="text-sm text-[var(--color-fg-muted)]">
        Loading…
      </p>
    );

  return (
    <section className="space-y-6">
      <header className="flex flex-wrap items-baseline gap-3 justify-between">
        <div>
          <h1 className="text-2xl font-bold">{coll.title}</h1>
          <p className="text-sm text-[var(--color-fg-muted)]">
            Public page:{" "}
            <Link href={`/collections/${coll.id}`} target="_blank" rel="noopener noreferrer">
              /collections/{coll.id}
            </Link>
            {" "}·{" "}
            <button
              type="button"
              onClick={toggleCourse}
              className={
                "ml-2 px-2 py-0.5 rounded text-xs " +
                (coll.is_course
                  ? "bg-[var(--color-brand-cyan)] text-black"
                  : "border border-[var(--color-brand-blue-4)]")
              }
            >
              {coll.is_course ? "Course" : "Make Course"}
            </button>
          </p>
        </div>
        <Link href="/me/collections" className="text-sm underline">
          ← All collections
        </Link>
      </header>

      {info && <Alert kind="success">{info}</Alert>}
      {err && <Alert kind="error">{err}</Alert>}

      <section
        aria-labelledby="add-h"
        className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded p-4 space-y-2"
      >
        <h2 id="add-h" className="font-semibold">
          Add an item
        </h2>
        <div className="flex flex-wrap gap-2 items-end">
          <label className="flex-1 min-w-64">
            <span className="block text-xs text-[var(--color-fg-muted)] mb-1">My items</span>
            <select
              value={pickItem}
              onChange={(e) => setPickItem(e.target.value)}
              className="w-full px-2 py-1 rounded bg-[var(--color-bg-base)] border border-[var(--color-brand-blue-4)] text-sm"
            >
              <option value="">— pick one —</option>
              {myItems.map((i) => (
                <option key={i.id} value={i.id}>
                  [{i.type}] {i.title} ({i.state})
                </option>
              ))}
            </select>
          </label>
          {coll.is_course && (
            <label className="flex items-center gap-1 text-sm">
              <input
                type="checkbox"
                checked={pickRequired}
                onChange={(e) => setPickRequired(e.target.checked)}
              />
              Required for course
            </label>
          )}
          <button
            type="button"
            disabled={!pickItem || busy}
            onClick={addItem}
            className="px-3 py-1 bg-[var(--color-brand-cyan)] text-black rounded text-sm font-medium disabled:opacity-60"
          >
            {busy ? "Adding…" : "Add"}
          </button>
        </div>
        <p className="text-xs text-[var(--color-fg-muted)]">
          You can only add items you authored. Create new items at{" "}
          <Link href="/me/content/new">/me/content/new</Link>.
        </p>
      </section>

      <section aria-labelledby="items-h" className="space-y-2">
        <h2 id="items-h" className="font-semibold">
          Items in this collection
        </h2>
        {coll.items.length === 0 ? (
          <p className="text-sm text-[var(--color-fg-muted)] py-6 text-center border border-dashed border-[var(--color-brand-blue-4)] rounded">
            No items yet.
          </p>
        ) : (
          <ol className="space-y-2 list-decimal pl-6">
            {coll.items.map((it, idx) => (
              <li
                key={it.id}
                className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded p-3 space-y-2"
              >
                <div className="flex flex-wrap items-baseline gap-3 justify-between">
                  <div className="flex items-start gap-2">
                    <div className="flex flex-col -mt-1" aria-label="Reorder">
                      <button
                        type="button"
                        onClick={() => moveItem(idx, -1)}
                        disabled={idx === 0}
                        aria-label={`Move "${it.title}" up`}
                        title="Move up"
                        className="px-1 leading-none text-[var(--color-brand-cyan)] disabled:opacity-30 disabled:cursor-not-allowed"
                      >
                        ▲
                      </button>
                      <button
                        type="button"
                        onClick={() => moveItem(idx, 1)}
                        disabled={idx === coll.items.length - 1}
                        aria-label={`Move "${it.title}" down`}
                        title="Move down"
                        className="px-1 leading-none text-[var(--color-brand-cyan)] disabled:opacity-30 disabled:cursor-not-allowed"
                      >
                        ▼
                      </button>
                    </div>
                    <div>
                      <div className="text-xs uppercase tracking-wide text-[var(--color-brand-cyan)]">
                        {it.type.replace("_", " ")} · {it.state}
                      </div>
                      <Link href={`/me/content/${it.id}/edit`} className="font-semibold">
                        {it.title}
                      </Link>
                      {coll.is_course && (
                        <span className="ml-2 text-xs text-[var(--color-fg-muted)]">
                          {it.is_required_for_course ? "Required" : "Optional"}
                        </span>
                      )}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => removeItem(it.id)}
                    className="text-xs px-2 py-1 border border-red-500 text-red-300 rounded"
                  >
                    Remove
                  </button>
                </div>
                {coll.is_course && (
                  <CourseRuleEditor
                    itemType={it.type}
                    current={it.completion_rule}
                    onSave={(rule) => setRule(it.id, rule)}
                  />
                )}
              </li>
            ))}
          </ol>
        )}
      </section>
    </section>
  );
}

function CourseRuleEditor({
  itemType,
  current,
  onSave,
}: {
  itemType: string;
  current: Record<string, unknown> | null;
  onSave: (rule: Record<string, unknown>) => void;
}) {
  const [pct, setPct] = useState(() => {
    if (current && typeof current["video_pct"] === "number") return current["video_pct"] as number;
    if (current && typeof current["article_scroll_pct"] === "number")
      return current["article_scroll_pct"] as number;
    return itemType === "video" ? 0.9 : 0.9;
  });
  const [fileDl, setFileDl] = useState<boolean>(
    !!(current && (current as Record<string, unknown>)["file_downloaded"]),
  );

  function save() {
    if (itemType === "video") onSave({ video_pct: pct });
    else if (itemType === "article") onSave({ article_scroll_pct: pct });
    else onSave({ file_downloaded: fileDl });
  }

  return (
    <div className="text-xs text-[var(--color-fg-muted)] border-t border-[var(--color-brand-blue-4)] pt-2 flex flex-wrap items-center gap-2">
      <span className="font-semibold">Completion rule:</span>
      {itemType === "video" && (
        <label className="flex items-center gap-1">
          Watched ≥
          <input
            type="number"
            min={0}
            max={1}
            step={0.05}
            value={pct}
            onChange={(e) => setPct(Number(e.target.value))}
            className="w-16 px-1 rounded bg-[var(--color-bg-base)] border border-[var(--color-brand-blue-4)]"
          />
          (0–1)
        </label>
      )}
      {itemType === "article" && (
        <label className="flex items-center gap-1">
          Scrolled ≥
          <input
            type="number"
            min={0}
            max={1}
            step={0.05}
            value={pct}
            onChange={(e) => setPct(Number(e.target.value))}
            className="w-16 px-1 rounded bg-[var(--color-bg-base)] border border-[var(--color-brand-blue-4)]"
          />
          (0–1)
        </label>
      )}
      {itemType === "teaching_material" && (
        <label className="flex items-center gap-1">
          <input
            type="checkbox"
            checked={fileDl}
            onChange={(e) => setFileDl(e.target.checked)}
          />
          Mark complete when file is downloaded
        </label>
      )}
      <button
        type="button"
        onClick={save}
        className="px-2 py-1 border border-[var(--color-brand-blue-2)] rounded"
      >
        Save rule
      </button>
      {current && (
        <code className="font-mono">{JSON.stringify(current)}</code>
      )}
    </div>
  );
}
