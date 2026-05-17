import Link from "next/link";
import { apiUrl } from "@/lib/api";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Contributors",
  description: "Browse contributors publishing on the NDSC Lab platform.",
};

type Contributor = {
  user_id: string;
  slug: string;
  affiliation: string | null;
  bio_md: string | null;
  display_name: string | null;
  photo_url: string | null;
};

async function fetchContributors(q?: string): Promise<Contributor[]> {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  params.set("limit", "120");
  const r = await fetch(apiUrl(`/contributors?${params.toString()}`), { cache: "no-store" });
  if (!r.ok) return [];
  return (await r.json()) as Contributor[];
}

export default async function ContributorsPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const sp = await searchParams;
  const rows = await fetchContributors(sp.q);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-3xl font-bold">Contributors</h1>
        <p className="text-sm text-[var(--color-fg-muted)] mt-1">
          Researchers and practitioners publishing lectures, articles, teaching material, and workshops on NDSC Lab.
        </p>
      </header>

      <form
        action="/contributors"
        method="GET"
        role="search"
        aria-label="Search contributors"
        className="flex flex-wrap gap-3"
      >
        <label htmlFor="q" className="sr-only">
          Search contributors
        </label>
        <input
          id="q"
          name="q"
          type="search"
          placeholder="Search name, slug, affiliation, bio…"
          defaultValue={sp.q ?? ""}
          className="flex-1 min-w-64 px-3 py-2 rounded bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)] focus:border-[var(--color-brand-cyan)] outline-none"
        />
        <button
          type="submit"
          className="px-4 py-2 bg-[var(--color-brand-cyan)] text-black rounded font-medium"
        >
          Search
        </button>
        {sp.q && (
          <Link
            href="/contributors"
            className="px-4 py-2 border border-[var(--color-brand-blue-2)] rounded text-sm self-center"
          >
            Clear
          </Link>
        )}
      </form>

      {rows.length === 0 ? (
        <p className="text-sm text-[var(--color-fg-muted)] py-8 text-center border border-dashed border-[var(--color-brand-blue-4)] rounded">
          {sp.q
            ? "No contributors match this search."
            : "No contributors with a public profile yet."}
        </p>
      ) : (
        <ul className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {rows.map((c) => (
            <li
              key={c.user_id}
              className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded-lg p-4 hover:border-[var(--color-brand-cyan)] transition-colors"
            >
              <Link href={`/c/${encodeURIComponent(c.slug)}`} className="block">
                <div className="flex items-center gap-3">
                  {c.photo_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={c.photo_url}
                      alt=""
                      width={56}
                      height={56}
                      className="w-14 h-14 rounded-full object-cover border border-[var(--color-brand-blue-4)] shrink-0"
                    />
                  ) : (
                    <div
                      aria-hidden
                      className="w-14 h-14 rounded-full bg-[var(--color-bg-base)] border border-[var(--color-brand-blue-4)] flex items-center justify-center text-xs text-[var(--color-fg-muted)] shrink-0"
                    >
                      {(c.display_name || c.slug).slice(0, 2).toUpperCase()}
                    </div>
                  )}
                  <div className="min-w-0">
                    <h2 className="font-semibold truncate">{c.display_name || c.slug}</h2>
                    {c.display_name && (
                      <p className="text-xs text-[var(--color-brand-cyan)] truncate">@{c.slug}</p>
                    )}
                    {c.affiliation && (
                      <p className="text-xs text-[var(--color-fg-muted)] truncate">
                        {c.affiliation}
                      </p>
                    )}
                  </div>
                </div>
                {c.bio_md && (
                  <p className="text-sm text-[var(--color-fg-muted)] mt-3 line-clamp-3 whitespace-pre-wrap">
                    {c.bio_md}
                  </p>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
