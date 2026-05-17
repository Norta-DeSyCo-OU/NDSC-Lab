import { apiUrl } from "@/lib/api";
import Link from "next/link";
import type { Metadata } from "next";
import { ContributorCTA } from "@/components/ContributorCTA";

export const metadata: Metadata = {
  title: "Lecture series",
  description: "Browse ordered lecture series and certificate-eligible courses on the NDSC platform.",
};

type Series = {
  id: string;
  owner_user_id: string;
  owner_slug: string | null;
  slug: string;
  title: string;
  description_md: string | null;
  is_course: boolean;
};

async function fetchSeries(params: URLSearchParams): Promise<Series[]> {
  const r = await fetch(apiUrl(`/collections?${params.toString()}`), { cache: "no-store" });
  if (!r.ok) return [];
  return (await r.json()) as Series[];
}

export default async function SeriesIndexPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; contributor?: string; course_only?: string }>;
}) {
  const sp = await searchParams;
  const params = new URLSearchParams();
  if (sp.q) params.set("q", sp.q);
  if (sp.contributor) params.set("contributor", sp.contributor);
  if (sp.course_only === "1") params.set("course_only", "true");
  params.set("limit", "60");

  const rows = await fetchSeries(params);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold">Lecture series</h1>
          <p className="text-sm text-[var(--color-fg-muted)] mt-1">
            Ordered playlists curated by contributors. Series marked as Courses are eligible for signed completion certificates.
          </p>
        </div>
        <ContributorCTA href="/me/collections" label="New lecture series" />
      </header>

      <form
        action="/series"
        method="GET"
        role="search"
        aria-label="Filter lecture series"
        className="flex flex-wrap gap-3"
      >
        <label htmlFor="q" className="sr-only">Search</label>
        <input
          id="q"
          name="q"
          type="search"
          placeholder="Search title or description…"
          defaultValue={sp.q ?? ""}
          className="flex-1 min-w-64 px-3 py-2 rounded bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)] focus:border-[var(--color-brand-cyan)] outline-none"
        />
        {sp.contributor && (
          <input type="hidden" name="contributor" value={sp.contributor} />
        )}
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            name="course_only"
            value="1"
            defaultChecked={sp.course_only === "1"}
          />
          Courses only
        </label>
        <button
          type="submit"
          className="px-4 py-2 bg-[var(--color-brand-cyan)] text-black rounded font-medium"
        >
          Apply
        </button>
        {(sp.q || sp.contributor || sp.course_only) && (
          <Link
            href="/series"
            className="px-4 py-2 border border-[var(--color-brand-blue-2)] rounded text-sm self-center"
          >
            Clear
          </Link>
        )}
      </form>

      {sp.contributor && (
        <p className="text-xs text-[var(--color-fg-muted)]">
          Filtered to contributor <code>{sp.contributor}</code>.{" "}
          <Link href="/series" className="underline">
            Remove filter
          </Link>
          .
        </p>
      )}

      {rows.length === 0 ? (
        <div className="text-sm text-[var(--color-fg-muted)] py-8 text-center border border-dashed border-[var(--color-brand-blue-4)] rounded space-y-2">
          <p>No series match these filters yet.</p>
          <p className="text-xs">
            Are you a contributor? Use the &quot;+ New lecture series&quot; button at the top, or go to{" "}
            <Link href="/me/collections" className="text-[var(--color-brand-cyan)] underline">
              /me/collections
            </Link>{" "}
            to create one.
          </p>
        </div>
      ) : (
        <ul className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {rows.map((c) => (
            <li
              key={c.id}
              className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded-lg p-4 hover:border-[var(--color-brand-cyan)] transition-colors"
            >
              <Link href={`/collections/${c.id}`} className="block">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-xs uppercase tracking-wide text-[var(--color-brand-cyan)]">
                    {c.is_course ? "course" : "series"}
                  </span>
                </div>
                <h2 className="font-semibold mt-1 mb-2">{c.title}</h2>
                {c.description_md && (
                  <p className="text-sm text-[var(--color-fg-muted)] line-clamp-3 whitespace-pre-wrap">
                    {c.description_md}
                  </p>
                )}
              </Link>
              <p className="text-xs mt-3 text-[var(--color-fg-muted)]">
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
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
