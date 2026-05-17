import Link from "next/link";
import { apiUrl } from "@/lib/api";

type RecentItem = {
  id: string;
  type: string;
  title: string;
  summary: string | null;
  published_at: string | null;
  author_slug: string | null;
  author_display_name: string | null;
};

async function fetchRecent(): Promise<RecentItem[]> {
  const r = await fetch(apiUrl(`/items?limit=6`), { cache: "no-store" });
  if (!r.ok) return [];
  return (await r.json()) as RecentItem[];
}

export default async function HomePage() {
  const recent = await fetchRecent();

  return (
    <div className="space-y-12">
      <section className="py-12">
        <h1 className="text-4xl md:text-5xl font-bold tracking-tight">
          Engineering <span className="text-[var(--color-brand-cyan)]">decentralized intelligent socio-technical systems</span>.
        </h1>
        <p className="mt-6 max-w-2xl text-lg text-[var(--color-fg-muted)]">
          NDSC Lab — a research-and-practice community curated by Norta DeSyCo OU. Lectures,
          articles, and teaching material on DAOs, tokenomics, ZKP, AI agents, multi-agent
          systems, blockchain infrastructure, decentralized identity, trusted AI, M2M economies,
          IoT coordination, and DeFi.
        </p>
        <div className="mt-8 flex gap-3">
          <Link
            href="/discover"
            className="px-5 py-2 bg-[var(--color-brand-cyan)] text-black rounded font-medium hover:opacity-90"
          >
            Browse content
          </Link>
          <Link
            href="/auth/signup"
            className="px-5 py-2 border border-[var(--color-brand-blue-2)] rounded hover:border-[var(--color-brand-cyan)]"
          >
            Create an account
          </Link>
        </div>
      </section>

      {recent.length > 0 && (
        <section aria-labelledby="recent-h" className="space-y-4">
          <div className="flex items-baseline justify-between">
            <h2 id="recent-h" className="text-2xl font-bold">Recent content</h2>
            <Link
              href="/discover"
              className="text-sm text-[var(--color-brand-cyan)] underline"
            >
              See all →
            </Link>
          </div>
          <ul className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {recent.map((it) => (
              <li
                key={it.id}
                className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded-lg p-4 hover:border-[var(--color-brand-cyan)] transition-colors"
              >
                <Link href={`/items/${it.id}`} className="block">
                  <span className="text-xs uppercase tracking-wide text-[var(--color-brand-cyan)]">
                    {it.type.replace("_", " ")}
                  </span>
                  <h3 className="font-semibold mt-1 mb-2">{it.title}</h3>
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
        </section>
      )}

      <section aria-labelledby="cats-h" className="space-y-4">
        <h2 id="cats-h" className="text-2xl font-bold">Categories</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[
            { h: "Lectures", t: "Video lectures from researchers and practitioners across the NDSC community.", q: "video" },
            { h: "Articles", t: "Long-form writing on governance, tokenomics, ZKP, agents, M2M economies, DeFi.", q: "article" },
            { h: "Workshops", t: "Hands-on sessions on decentralized identity, MAS, IoT coordination.", q: "" },
          ].map((c) => (
            <Link
              key={c.h}
              href={c.q ? `/discover?type=${c.q}` : "/workshops"}
              className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] p-5 rounded-lg hover:border-[var(--color-brand-cyan)] transition-colors"
            >
              <h3 className="font-semibold text-[var(--color-brand-cyan)] mb-2">{c.h}</h3>
              <p className="text-sm text-[var(--color-fg-muted)]">{c.t}</p>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
