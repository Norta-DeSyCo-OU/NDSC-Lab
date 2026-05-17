import Link from "next/link";
import { apiUrl } from "@/lib/api";

type CollectionDetail = {
  id: string;
  owner_user_id: string;
  owner_slug: string | null;
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

async function fetchCollection(id: string): Promise<CollectionDetail | null> {
  const r = await fetch(apiUrl(`/collections/${id}`), { cache: "no-store" });
  if (!r.ok) return null;
  return (await r.json()) as CollectionDetail;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const c = await fetchCollection(id);
  return { title: c?.title ?? "Collection" };
}

export default async function CollectionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const c = await fetchCollection(id);
  if (!c) {
    return (
      <section className="max-w-3xl mx-auto">
        <h1 className="text-2xl font-bold">Collection not found</h1>
        <p className="text-sm text-[var(--color-fg-muted)]">
          This collection does not exist or no items have been published yet.
        </p>
      </section>
    );
  }

  return (
    <article className="max-w-3xl mx-auto space-y-6">
      <header>
        <span className="text-xs uppercase tracking-wide text-[var(--color-brand-cyan)]">
          {c.is_course ? "Course" : "Lecture series"}
        </span>
        <h1 className="text-3xl font-bold mt-1">{c.title}</h1>
        <p className="text-xs text-[var(--color-fg-muted)] mt-2">
          by{" "}
          {c.owner_slug ? (
            <Link
              href={`/c/${encodeURIComponent(c.owner_slug)}`}
              className="text-[var(--color-brand-cyan)] underline"
            >
              {c.owner_slug}
            </Link>
          ) : (
            <span className="font-mono">{c.owner_user_id.slice(0, 8)}…</span>
          )}
          {" · "}
          <Link
            href={`/series?contributor=${encodeURIComponent(c.owner_user_id)}`}
            className="underline"
          >
            More series by this author
          </Link>
        </p>
        {c.description_md && (
          <p className="text-[var(--color-fg-muted)] mt-3 whitespace-pre-wrap">
            {c.description_md}
          </p>
        )}
      </header>

      {c.items.length === 0 ? (
        <p className="text-sm text-[var(--color-fg-muted)] py-6 text-center border border-dashed border-[var(--color-brand-blue-4)] rounded">
          No items in this collection yet.
        </p>
      ) : (
        <ol className="space-y-3 list-decimal pl-6">
          {c.items.map((it) => (
            <li
              key={it.id}
              className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded-lg p-4 hover:border-[var(--color-brand-cyan)] transition-colors"
            >
              <Link href={`/items/${it.id}`} className="block">
                <div className="text-xs uppercase tracking-wide text-[var(--color-brand-cyan)]">
                  {it.type.replace("_", " ")}
                </div>
                <h2 className="font-semibold mt-1">{it.title}</h2>
                {c.is_course && (
                  <div className="text-xs text-[var(--color-fg-muted)] mt-1">
                    {it.is_required_for_course ? "Required" : "Optional"}
                    {it.completion_rule && (
                      <>
                        {" "}· rule: <code>{JSON.stringify(it.completion_rule)}</code>
                      </>
                    )}
                  </div>
                )}
              </Link>
            </li>
          ))}
        </ol>
      )}
    </article>
  );
}
