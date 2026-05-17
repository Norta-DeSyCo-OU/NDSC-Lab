import { apiUrl } from "@/lib/api";
import Link from "next/link";
import type { Metadata } from "next";
import { ContributorCTA } from "@/components/ContributorCTA";

export const metadata: Metadata = {
  title: "Discover",
  description: "Browse lectures, articles, and teaching material on decentralized intelligent socio-technical systems.",
};

type Item = {
  id: string;
  author_id: string;
  author_slug: string | null;
  author_display_name: string | null;
  type: string;
  title: string;
  slug: string;
  state: string;
  summary: string | null;
  published_at: string | null;
};

async function fetchItems(q?: string, type?: string, contributor?: string): Promise<Item[]> {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (type) params.set("type", type);
  if (contributor) params.set("contributor", contributor);
  params.set("limit", "30");
  const r = await fetch(apiUrl(`/items?${params.toString()}`), { cache: "no-store" });
  if (!r.ok) return [];
  return (await r.json()) as Item[];
}

export default async function DiscoverPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; type?: string; contributor?: string }>;
}) {
  const sp = await searchParams;
  const items = await fetchItems(sp.q, sp.type, sp.contributor);

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold">Discover</h1>
          <p className="text-sm text-[var(--color-fg-muted)] mt-1">
            Lectures, articles, and teaching material from the NDSC community.
          </p>
        </div>
        <ContributorCTA href="/me/content/new" label="New item" />
      </header>

      <form
        action="/discover"
        method="GET"
        role="search"
        aria-label="Search content"
        className="flex flex-wrap gap-3"
      >
        <label htmlFor="q" className="sr-only">
          Search
        </label>
        <input
          id="q"
          name="q"
          type="search"
          placeholder="Search titles and bodies…"
          defaultValue={sp.q ?? ""}
          className="flex-1 min-w-64 px-3 py-2 rounded bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)] focus:border-[var(--color-brand-cyan)] outline-none"
        />
        <label htmlFor="type" className="sr-only">
          Filter by type
        </label>
        <select
          id="type"
          name="type"
          defaultValue={sp.type ?? ""}
          className="px-3 py-2 rounded bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)] focus:border-[var(--color-brand-cyan)] outline-none"
        >
          <option value="">All types</option>
          <option value="video">Video</option>
          <option value="article">Article</option>
          <option value="teaching_material">Material</option>
        </select>
        {sp.contributor && (
          <input type="hidden" name="contributor" value={sp.contributor} />
        )}
        <button
          type="submit"
          className="px-4 py-2 bg-[var(--color-brand-cyan)] text-black rounded font-medium"
        >
          Search
        </button>
        {(sp.q || sp.type || sp.contributor) && (
          <Link
            href="/discover"
            className="px-4 py-2 border border-[var(--color-brand-blue-2)] rounded text-sm self-center"
          >
            Clear
          </Link>
        )}
      </form>

      {sp.contributor && (
        <p className="text-xs text-[var(--color-fg-muted)]">
          Filtered to contributor <code>{sp.contributor}</code>.{" "}
          <Link href="/discover" className="underline">
            Remove filter
          </Link>
          .
        </p>
      )}

      {items.length === 0 ? (
        <p className="text-sm text-[var(--color-fg-muted)] py-8 text-center border border-dashed border-[var(--color-brand-blue-4)] rounded">
          {sp.q || sp.type || sp.contributor
            ? "No results match your filters. Try clearing them."
            : "No content has been published yet. Check back soon."}
        </p>
      ) : (
        <ul className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {items.map((it) => (
            <li
              key={it.id}
              className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded-lg p-4 hover:border-[var(--color-brand-cyan)] transition-colors"
            >
              <Link href={`/items/${it.id}`} className="block">
                <span className="text-xs uppercase tracking-wide text-[var(--color-brand-cyan)]">
                  {it.type.replace("_", " ")}
                </span>
                <h2 className="font-semibold mt-1 mb-2">{it.title}</h2>
                {it.summary && (
                  <p className="text-sm text-[var(--color-fg-muted)] line-clamp-3">{it.summary}</p>
                )}
              </Link>
              <p className="mt-3 text-xs text-[var(--color-fg-muted)]">
                {it.author_slug ? (
                  <Link
                    href={`/c/${encodeURIComponent(it.author_slug)}`}
                    className="text-[var(--color-brand-cyan)] underline"
                  >
                    {it.author_display_name || it.author_slug}
                  </Link>
                ) : (
                  <span>{it.author_display_name ?? "Contributor"}</span>
                )}
                {it.published_at && (
                  <>
                    {" · "}
                    <time dateTime={it.published_at}>
                      {new Date(it.published_at).toLocaleDateString()}
                    </time>
                  </>
                )}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
