import { apiUrl } from "@/lib/api";
import type { Metadata } from "next";
import { ContributorCTA } from "@/components/ContributorCTA";

export const metadata: Metadata = {
  title: "Workshops",
  description: "Upcoming and past NDSC Lab workshops.",
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

async function fetchWorkshops(): Promise<Workshop[]> {
  const r = await fetch(apiUrl(`/workshops`), { cache: "no-store" });
  if (!r.ok) return [];
  return (await r.json()) as Workshop[];
}

export default async function WorkshopsPage() {
  const ws = await fetchWorkshops();
  const now = Date.now();
  const upcoming = ws.filter((w) => Date.parse(w.starts_at) >= now);
  const past = ws.filter((w) => Date.parse(w.starts_at) < now);

  return (
    <div className="space-y-10">
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="text-3xl font-bold">Workshops</h1>
        <ContributorCTA href="/me/workshops" label="New workshop" />
      </header>

      <section aria-labelledby="upcoming-h">
        <h2 id="upcoming-h" className="text-xl font-semibold mb-3 text-[var(--color-brand-cyan)]">
          Upcoming
        </h2>
        {upcoming.length === 0 ? (
          <p className="text-sm text-[var(--color-fg-muted)]">No upcoming workshops.</p>
        ) : (
          <ul className="space-y-3">
            {upcoming.map((w) => (
              <li
                key={w.id}
                className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded p-4"
              >
                <h3 className="font-semibold">{w.title}</h3>
                <p className="text-xs text-[var(--color-fg-muted)] mt-1">
                  <time dateTime={w.starts_at}>{new Date(w.starts_at).toLocaleString()}</time> —{" "}
                  <time dateTime={w.ends_at}>{new Date(w.ends_at).toLocaleString()}</time>
                </p>
                <p className="text-xs mt-1">{w.is_online ? "Online" : (w.location ?? "TBA")}</p>
                {w.registration_url && (
                  <a
                    className="inline-block mt-2 text-sm"
                    href={w.registration_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Register ↗
                  </a>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="past-h">
        <h2 id="past-h" className="text-xl font-semibold mb-3 text-[var(--color-brand-cyan)]">
          Past
        </h2>
        {past.length === 0 ? (
          <p className="text-sm text-[var(--color-fg-muted)]">No past workshops.</p>
        ) : (
          <ul className="space-y-2">
            {past.map((w) => (
              <li key={w.id} className="text-sm">
                <time dateTime={w.starts_at} className="text-[var(--color-fg-muted)] mr-2">
                  {new Date(w.starts_at).toLocaleDateString()}
                </time>
                <span>{w.title}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
