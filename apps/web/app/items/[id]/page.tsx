import { headers } from "next/headers";
import { apiUrl } from "@/lib/api";
import { Comments } from "@/components/Comments";
import { ItemViewBeacon } from "@/components/ItemViewBeacon";
import { ItemPlayer } from "@/components/ItemPlayer";
import { AdminItemActions } from "@/components/AdminItemActions";
import { ItemSeriesBadge } from "@/components/ItemSeriesBadge";

type Item = {
  id: string;
  author_id: string;
  author_slug: string | null;
  author_display_name: string | null;
  type: "article" | "video" | "teaching_material";
  title: string;
  slug: string;
  state: string;
  summary: string | null;
  body_html: string | null;
  license: string;
  published_at: string | null;
  video_kind: string | null;
  external_url: string | null;
};

async function fetchItem(id: string): Promise<Item | null> {
  // Forward the caller's session cookie so the backend can apply the
  // owner / admin draft-read policy. Without this the SSR fetch hits the
  // backend as anonymous and items in `pending_review`/`draft` return 404,
  // so admins reviewing the queue cannot open the item page at all.
  const h = await headers();
  const cookie = h.get("cookie") ?? "";
  const r = await fetch(apiUrl(`/items/${id}`), {
    cache: "no-store",
    headers: cookie ? { Cookie: cookie } : undefined,
  });
  if (!r.ok) return null;
  return (await r.json()) as Item;
}

export default async function ItemPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const item = await fetchItem(id);
  if (!item) {
    return (
      <section className="max-w-3xl mx-auto">
        <h1 className="text-2xl font-bold">Not found</h1>
        <p className="text-sm text-[var(--color-fg-muted)]">
          This content does not exist or is not published.
        </p>
      </section>
    );
  }

  return (
    <article className="max-w-3xl mx-auto space-y-6">
      <header>
        <span className="text-xs uppercase tracking-wide text-[var(--color-brand-cyan)]">
          {item.type.replace("_", " ")}
        </span>
        <h1 className="text-3xl font-bold mt-1">{item.title}</h1>
        {item.summary && <p className="text-[var(--color-fg-muted)] mt-2">{item.summary}</p>}
        <p className="mt-3 text-xs text-[var(--color-fg-muted)]">
          by{" "}
          {item.author_slug ? (
            <a
              href={`/c/${encodeURIComponent(item.author_slug)}`}
              className="text-[var(--color-brand-cyan)] underline"
            >
              {item.author_display_name || item.author_slug}
            </a>
          ) : (
            <span>{item.author_display_name ?? "Anonymous contributor"}</span>
          )}
          {item.published_at && (
            <>
              {" · "}
              <time dateTime={item.published_at}>
                Published {new Date(item.published_at).toLocaleDateString()}
              </time>
            </>
          )}
        </p>
      </header>

      <ItemSeriesBadge itemId={item.id} />

      <AdminItemActions itemId={item.id} state={item.state} />

      {(item.type === "video" || item.type === "teaching_material") && (
        <ItemPlayer
          itemId={item.id}
          itemType={item.type}
          videoKind={item.video_kind}
          externalUrl={item.external_url}
        />
      )}

      {item.body_html && (
        <div
          className="prose prose-invert max-w-none"
          // Server-sanitized via nh3 before reaching client (NFR-SEC-006).
          dangerouslySetInnerHTML={{ __html: item.body_html }}
        />
      )}

      {item.type === "article" && (
        <ItemPlayer
          itemId={item.id}
          itemType={item.type}
          videoKind={null}
          externalUrl={null}
        />
      )}

      <footer className="pt-6 border-t border-[var(--color-brand-blue-4)] text-xs text-[var(--color-fg-muted)]">
        License: <code>{item.license}</code>
      </footer>

      <Comments itemId={item.id} />
      <ItemViewBeacon itemId={item.id} itemType={item.type} />
    </article>
  );
}
