import Link from "next/link";
import { apiUrl } from "@/lib/api";

type Profile = {
  user_id: string;
  slug: string;
  bio_md: string | null;
  affiliation: string | null;
  orcid: string | null;
  links: { label: string; url: string }[] | null;
  contacts: { kind: "email" | "phone"; value: string; label: string | null }[] | null;
  photo_url: string | null;
};

type Section = {
  id: string;
  title: string;
  body_md: string | null;
  position: number;
};

type Item = {
  id: string;
  title: string;
  type: string;
  summary: string | null;
  published_at: string | null;
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

async function fetchProfile(slug: string): Promise<Profile | null> {
  const r = await fetch(apiUrl(`/c/${encodeURIComponent(slug)}`), { cache: "no-store" });
  if (!r.ok) return null;
  return (await r.json()) as Profile;
}

async function fetchSections(slug: string): Promise<Section[]> {
  const r = await fetch(apiUrl(`/c/${encodeURIComponent(slug)}/sections`), {
    cache: "no-store",
  });
  if (!r.ok) return [];
  return (await r.json()) as Section[];
}

async function fetchItems(uid: string): Promise<Item[]> {
  const r = await fetch(apiUrl(`/items?contributor=${uid}&limit=50`), { cache: "no-store" });
  if (!r.ok) return [];
  return (await r.json()) as Item[];
}

async function fetchSeries(uid: string): Promise<Series[]> {
  const r = await fetch(apiUrl(`/collections?contributor=${uid}&limit=50`), { cache: "no-store" });
  if (!r.ok) return [];
  return (await r.json()) as Series[];
}

async function fetchWorkshops(uid: string): Promise<Workshop[]> {
  const r = await fetch(apiUrl(`/workshops`), { cache: "no-store" });
  if (!r.ok) return [];
  const all = (await r.json()) as Workshop[];
  return all.filter((w) => w.speakers.includes(uid));
}

async function fetchSeriesItemIds(seriesIds: string[]): Promise<Set<string>> {
  // Union of item ids across this contributor's series. n+1 small fetches —
  // fine for typical contributor cardinalities; batch via a dedicated endpoint
  // later if performance becomes an issue.
  const ids = new Set<string>();
  await Promise.all(
    seriesIds.map(async (id) => {
      try {
        const r = await fetch(apiUrl(`/collections/${id}`), { cache: "no-store" });
        if (!r.ok) return;
        const d = (await r.json()) as { items: { item_id: string }[] };
        for (const it of d.items ?? []) ids.add(it.item_id);
      } catch {
        /* swallow */
      }
    }),
  );
  return ids;
}

const TYPE_LABEL: Record<string, string> = {
  video: "Video",
  article: "Article",
  teaching_material: "Teaching material",
};

export default async function ContributorPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ tab?: string }>;
}) {
  const { slug } = await params;
  const sp = await searchParams;
  const tab = (sp.tab as "series" | "workshops" | "content" | undefined) ?? "series";

  const profile = await fetchProfile(slug);
  if (!profile) {
    return (
      <div className="max-w-3xl mx-auto">
        <h1 className="text-2xl font-bold">Not found</h1>
        <p className="text-sm text-[var(--color-fg-muted)] mt-2">
          No contributor with slug <code>{slug}</code>.
        </p>
      </div>
    );
  }

  const [items, series, workshops, customSections] = await Promise.all([
    fetchItems(profile.user_id),
    fetchSeries(profile.user_id),
    fetchWorkshops(profile.user_id),
    fetchSections(slug),
  ]);
  const seriesItemIds = await fetchSeriesItemIds(series.map((c) => c.id));
  const looseItems = items.filter((it) => !seriesItemIds.has(it.id));

  const upcoming = workshops.filter((w) => Date.parse(w.starts_at) >= Date.now());
  const past = workshops.filter((w) => Date.parse(w.starts_at) < Date.now());

  function tabHref(t: "series" | "workshops" | "content") {
    return `/c/${encodeURIComponent(slug)}?tab=${t}`;
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Intro */}
      <header className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-4 min-w-0">
            {profile.photo_url && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={profile.photo_url}
                alt={`Profile photo of ${profile.slug}`}
                width={96}
                height={96}
                className="w-24 h-24 rounded-full object-cover border border-[var(--color-brand-blue-4)] shrink-0"
              />
            )}
            <div className="min-w-0">
              <h1 className="text-3xl font-bold">{profile.slug}</h1>
              {profile.affiliation && (
                <p className="text-[var(--color-fg-muted)] text-sm mt-1">{profile.affiliation}</p>
              )}
              {profile.orcid && (
                <p className="text-xs text-[var(--color-fg-muted)] mt-1">
                  ORCID:{" "}
                  <a
                    href={`https://orcid.org/${profile.orcid}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[var(--color-brand-cyan)] underline"
                  >
                    {profile.orcid}
                  </a>
                </p>
              )}
            </div>
          </div>
          {profile.links && profile.links.length > 0 && (
            <ul className="flex gap-3 text-sm flex-wrap justify-end">
              {profile.links.map((l) => (
                <li key={l.url}>
                  <a
                    href={l.url}
                    target="_blank"
                    rel="noopener noreferrer nofollow"
                    className="text-[var(--color-brand-cyan)] underline"
                  >
                    {l.label}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </div>

        {profile.bio_md && (
          <div className="text-sm whitespace-pre-wrap text-[var(--color-fg-muted)]">
            {profile.bio_md}
          </div>
        )}

        {profile.contacts && profile.contacts.length > 0 && (
          <section aria-labelledby="contacts-h" className="pt-1">
            <h2 id="contacts-h" className="text-sm font-semibold mb-1">
              Contacts
            </h2>
            <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
              {profile.contacts.map((c, i) => (
                <li key={i}>
                  <span className="text-[var(--color-fg-muted)]">
                    {c.label ? `${c.label}: ` : c.kind === "email" ? "✉ " : "☎ "}
                  </span>
                  <a
                    href={c.kind === "email" ? `mailto:${c.value}` : `tel:${c.value}`}
                    className="text-[var(--color-brand-cyan)] underline"
                  >
                    {c.value}
                  </a>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* At-a-glance counters */}
        <div className="flex gap-4 text-xs text-[var(--color-fg-muted)] pt-1">
          <span>{series.length} series</span>
          <span>·</span>
          <span>{workshops.length} workshops</span>
          <span>·</span>
          <span>{items.length} items total</span>
        </div>
      </header>

      {/* Content section with subsection tabs */}
      <section className="space-y-4" aria-labelledby="content-h">
        <h2 id="content-h" className="text-xl font-bold">
          Content
        </h2>

        <nav
          role="tablist"
          aria-label="Sections"
          className="flex flex-wrap gap-1 border-b border-[var(--color-brand-blue-4)]"
        >
          {(
            [
              ["series", `Series (${series.length})`],
              ["workshops", `Workshops (${workshops.length})`],
              ["content", `Other content (${looseItems.length})`],
            ] as const
          ).map(([t, label]) => {
            const active = tab === t;
            return (
              <Link
                key={t}
                href={tabHref(t)}
                role="tab"
                aria-selected={active}
                className={
                  "px-3 py-2 text-sm -mb-px border-b-2 " +
                  (active
                    ? "border-[var(--color-brand-cyan)] text-[var(--color-brand-cyan)]"
                    : "border-transparent text-[var(--color-fg-muted)] hover:text-[var(--color-fg-base)]")
                }
              >
                {label}
              </Link>
            );
          })}
        </nav>

        {tab === "series" && (
          <div className="space-y-3">
            {series.length === 0 ? (
              <p className="text-sm text-[var(--color-fg-muted)] py-6 text-center border border-dashed border-[var(--color-brand-blue-4)] rounded">
                No lecture series yet.
              </p>
            ) : (
              <ul className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {series.map((c) => (
                  <li
                    key={c.id}
                    className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded-lg p-4 hover:border-[var(--color-brand-cyan)] transition-colors"
                  >
                    <Link href={`/collections/${c.id}`} className="block">
                      <span className="text-xs uppercase tracking-wide text-[var(--color-brand-cyan)]">
                        {c.is_course ? "course" : "series"}
                      </span>
                      <h3 className="font-semibold mt-1 mb-2">{c.title}</h3>
                      {c.description_md && (
                        <p className="text-sm text-[var(--color-fg-muted)] line-clamp-3 whitespace-pre-wrap">
                          {c.description_md}
                        </p>
                      )}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            <p className="text-xs">
              <Link
                href={`/series?contributor=${encodeURIComponent(profile.user_id)}`}
                className="text-[var(--color-brand-cyan)] underline"
              >
                Open in full Lecture series browser →
              </Link>
            </p>
          </div>
        )}

        {tab === "workshops" && (
          <div className="space-y-4">
            {workshops.length === 0 ? (
              <p className="text-sm text-[var(--color-fg-muted)] py-6 text-center border border-dashed border-[var(--color-brand-blue-4)] rounded">
                No workshops yet.
              </p>
            ) : (
              <>
                <section aria-labelledby="up-h">
                  <h3 id="up-h" className="font-semibold mb-2 text-[var(--color-brand-cyan)]">
                    Upcoming
                  </h3>
                  {upcoming.length === 0 ? (
                    <p className="text-sm text-[var(--color-fg-muted)]">No upcoming.</p>
                  ) : (
                    <ul className="space-y-2">
                      {upcoming.map((w) => (
                        <WorkshopRow key={w.id} w={w} />
                      ))}
                    </ul>
                  )}
                </section>
                <section aria-labelledby="past-h">
                  <h3 id="past-h" className="font-semibold mb-2 text-[var(--color-brand-cyan)]">
                    Past
                  </h3>
                  {past.length === 0 ? (
                    <p className="text-sm text-[var(--color-fg-muted)]">No past.</p>
                  ) : (
                    <ul className="space-y-1 text-sm">
                      {past.map((w) => (
                        <li key={w.id}>
                          <time
                            dateTime={w.starts_at}
                            className="text-[var(--color-fg-muted)] mr-2"
                          >
                            {new Date(w.starts_at).toLocaleDateString()}
                          </time>
                          <span>{w.title}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              </>
            )}
          </div>
        )}

        {tab === "content" && (
          <div className="space-y-3">
            <p className="text-xs text-[var(--color-fg-muted)]">
              Standalone items — not part of any lecture series. Items inside a series appear under that series.
            </p>
            {looseItems.length === 0 ? (
              <p className="text-sm text-[var(--color-fg-muted)] py-6 text-center border border-dashed border-[var(--color-brand-blue-4)] rounded">
                No standalone items.
              </p>
            ) : (
              <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {looseItems.map((it) => (
                  <li
                    key={it.id}
                    className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded p-3 hover:border-[var(--color-brand-cyan)] transition-colors"
                  >
                    <Link href={`/items/${it.id}`} className="block">
                      <span className="text-xs uppercase tracking-wide text-[var(--color-brand-cyan)]">
                        {TYPE_LABEL[it.type] ?? it.type}
                      </span>
                      <h3 className="font-semibold mt-1">{it.title}</h3>
                      {it.summary && (
                        <p className="text-sm text-[var(--color-fg-muted)] line-clamp-2 mt-1">
                          {it.summary}
                        </p>
                      )}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            <p className="text-xs">
              <Link
                href={`/discover?contributor=${encodeURIComponent(profile.user_id)}`}
                className="text-[var(--color-brand-cyan)] underline"
              >
                See all items by this contributor in Discover →
              </Link>
            </p>
          </div>
        )}
      </section>

      {customSections.length > 0 && (
        <section className="space-y-4" aria-labelledby="custom-h">
          <h2 id="custom-h" className="text-xl font-bold">
            More
          </h2>
          {customSections.map((sec) => (
            <article
              key={sec.id}
              className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded-lg p-4"
            >
              <h3 className="font-semibold text-lg">{sec.title}</h3>
              {sec.body_md && (
                <p className="text-sm whitespace-pre-wrap mt-2">{sec.body_md}</p>
              )}
            </article>
          ))}
        </section>
      )}
    </div>
  );
}

function WorkshopRow({ w }: { w: Workshop }) {
  return (
    <li className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded p-3">
      <h4 className="font-semibold">{w.title}</h4>
      <p className="text-xs text-[var(--color-fg-muted)] mt-1">
        <time dateTime={w.starts_at}>{new Date(w.starts_at).toLocaleString()}</time> —{" "}
        <time dateTime={w.ends_at}>{new Date(w.ends_at).toLocaleString()}</time>
      </p>
      <p className="text-xs mt-1">{w.is_online ? "Online" : (w.location ?? "TBA")}</p>
      {w.registration_url && (
        <a
          className="inline-block mt-1 text-xs text-[var(--color-brand-cyan)] underline"
          href={w.registration_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          Register ↗
        </a>
      )}
    </li>
  );
}
