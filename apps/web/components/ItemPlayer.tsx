"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { useMe } from "@/lib/useMe";

type Attachment = {
  id: string;
  role: string;
  mime: string | null;
  bytes: number | null;
  state: string;
  stream_url: string;
};

const YT_RE = /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([A-Za-z0-9_-]{11})/;
const VIMEO_RE = /vimeo\.com\/(?:video\/)?(\d+)/;

function embedSrc(externalUrl: string | null): string | null {
  if (!externalUrl) return null;
  const yt = YT_RE.exec(externalUrl);
  if (yt) return `https://www.youtube-nocookie.com/embed/${yt[1]}`;
  const vm = VIMEO_RE.exec(externalUrl);
  if (vm) return `https://player.vimeo.com/video/${vm[1]}`;
  // Panopto and other allowlisted hosts can be added here.
  return null;
}

/**
 * Gate shown to anonymous visitors in place of the consumable payload
 * (video player, downloadable files). Item metadata + article body stay
 * public; only the payload sits behind login. Mirrors the server-side
 * gate in `uploads.stream_attachment` — this is UX, not the security
 * boundary (the API still 401s an anonymous stream request).
 */
function LoginGate({ message }: { message: string }) {
  const pathname = usePathname();
  const next = encodeURIComponent(pathname || "/");
  return (
    <div className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded-lg p-8 text-center space-y-4">
      <div>
        <p className="font-semibold">{message}</p>
        <p className="text-sm text-[var(--color-fg-muted)] mt-1">
          This content is available to registered members. Creating an account is free.
        </p>
      </div>
      <div className="flex gap-2 justify-center">
        <a
          href={`/auth/login?next=${next}`}
          className="px-4 py-2 bg-[var(--color-brand-cyan)] text-black rounded text-sm font-medium"
        >
          Log in
        </a>
        <a
          href={`/auth/signup?next=${next}`}
          className="px-4 py-2 border border-[var(--color-brand-blue-4)] rounded text-sm"
        >
          Sign up
        </a>
      </div>
    </div>
  );
}

function PlayerSkeleton() {
  return (
    <div className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded p-4 text-sm text-[var(--color-fg-muted)]">
      Loading…
    </div>
  );
}

/**
 * Renders the appropriate player for an item:
 * - hosted video: `<video controls>` pointing to /api/uploads/<id>/stream
 *   (HTTP-Range proxied through the api → R2/MinIO).
 * - embed video: cookie-light embed if recognized; otherwise click-to-play
 *   placeholder linking to the external URL (D-09 third-party cookie consent).
 * - teaching material: lists downloadable attachments.
 *
 * Consumable payload (video playback, file downloads, embed players) is
 * gated behind login; anonymous visitors get a `<LoginGate>` instead.
 */
export function ItemPlayer({
  itemId,
  itemType,
  videoKind,
  externalUrl,
}: {
  itemId: string;
  itemType: "article" | "video" | "teaching_material";
  videoKind: string | null;
  externalUrl: string | null;
}) {
  // `null` = SSR / fetch in flight, `[]` = fetched and empty.
  const [atts, setAtts] = useState<Attachment[] | null>(null);
  const [revealEmbed, setRevealEmbed] = useState(false);
  const { me, loading: meLoading } = useMe();
  const authed = !!me;

  useEffect(() => {
    fetch(`/api/items/${itemId}/attachments`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : []))
      .then((rows: Attachment[]) => setAtts(rows ?? []))
      .catch(() => setAtts([]));
  }, [itemId]);

  // Defensive: video item with no video_kind = misconfigured metadata.
  if (itemType === "video" && !videoKind) {
    return (
      <div className="border border-yellow-500 bg-[var(--color-bg-panel)] rounded p-6 text-center text-sm">
        <p className="text-yellow-300 font-semibold">Video source not configured</p>
        <p className="text-[var(--color-fg-muted)] mt-1">
          This video item is missing its source kind. Edit the item and choose either
          &quot;Hosted upload&quot; or &quot;Embed URL&quot;.
        </p>
      </div>
    );
  }

  // ---- Content gate: video playback requires login --------------------------
  if (itemType === "video") {
    if (meLoading) return <PlayerSkeleton />;
    if (!authed) return <LoginGate message="Log in to watch this video." />;
  }

  if (itemType === "video" && videoKind === "embed") {
    if (!externalUrl) {
      return (
        <div className="border border-yellow-500 bg-[var(--color-bg-panel)] rounded p-6 text-center text-sm">
          <p className="text-yellow-300 font-semibold">No external video URL set</p>
          <p className="text-[var(--color-fg-muted)] mt-1">
            The author selected &quot;Embed&quot; for this item but did not provide a YouTube /
            Vimeo / Panopto URL. If you are the author, edit this item to either set the URL or
            switch the source to &quot;Hosted upload&quot; and upload a file.
          </p>
        </div>
      );
    }
    const src = embedSrc(externalUrl);
    if (!src) {
      return (
        <div className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded p-6 text-center">
          <p className="text-sm text-[var(--color-fg-muted)]">External video link:</p>
          <a
            href={externalUrl ?? "#"}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[var(--color-brand-cyan)] underline"
          >
            {externalUrl}
          </a>
        </div>
      );
    }
    if (!revealEmbed) {
      return (
        <button
          type="button"
          onClick={() => setRevealEmbed(true)}
          className="w-full aspect-video border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded flex items-center justify-center hover:border-[var(--color-brand-cyan)]"
          aria-label="Load the third-party video player"
        >
          <span className="text-sm">
            <strong>▶ Play</strong>
            <br />
            <span className="text-xs text-[var(--color-fg-muted)]">
              Loads the external player (sets third-party cookies)
            </span>
          </span>
        </button>
      );
    }
    return (
      <div className="aspect-video">
        <iframe
          src={src}
          title="Video"
          className="w-full h-full rounded border border-[var(--color-brand-blue-4)]"
          allow="autoplay; fullscreen; picture-in-picture"
          allowFullScreen
        />
      </div>
    );
  }

  if (itemType === "video" && videoKind === "hosted") {
    if (atts === null) {
      return (
        <div className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded p-4 text-sm text-[var(--color-fg-muted)]">
          Loading video…
        </div>
      );
    }
    // Prefer the web-friendly H.264 MP4 sibling. The original (`video_primary`)
    // may be `.mov`/`.mkv`/`.webm` — most browsers refuse `video/quicktime`
    // and Firefox refuses H.265-in-MP4. The worker transcodes anything that
    // needs it to a clean MP4 with `role='video_transcoded'`; fall back to
    // the original only if no transcode exists (already MP4 or still running).
    const transcoded = atts.find(
      (a) => a.role === "video_transcoded" && a.state === "clean",
    );
    const primary = atts.find(
      (a) => a.role === "video_primary" && a.state === "clean",
    );
    const pick = transcoded ?? primary;
    if (!pick) {
      // No clean source yet — original may still be scanning, or transcode
      // may be in flight after a quarantine. Either way, retry later.
      const anyPrimary = atts.find((a) => a.role === "video_primary");
      const stillScanning = anyPrimary?.state === "scanning";
      return (
        <div className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded p-4 text-sm text-[var(--color-fg-muted)]">
          {stillScanning
            ? "The video is still being scanned for malware. Refresh in a moment."
            : anyPrimary
              ? "The video is being transcoded to a web-friendly format. Refresh in a moment."
              : "No video file uploaded yet."}
        </div>
      );
    }
    // Some browsers strict-match the `type` attribute and skip sources whose
    // declared MIME they don't support. For QuickTime/Matroska fall back to
    // `video/mp4` (the stream endpoint rewrites the response Content-Type to
    // `video/mp4` for transcoded assets; for the rare case of serving the
    // original, omit the type so the browser sniffs the container).
    const sourceType =
      pick.role === "video_transcoded"
        ? "video/mp4"
        : pick.mime && pick.mime.startsWith("video/") && pick.mime !== "video/quicktime"
          ? pick.mime
          : undefined;
    return (
      <video
        controls
        preload="metadata"
        className="w-full rounded border border-[var(--color-brand-blue-4)]"
      >
        {sourceType ? (
          <source src={pick.stream_url} type={sourceType} />
        ) : (
          <source src={pick.stream_url} />
        )}
        Your browser does not support the video tag.
      </video>
    );
  }

  if (itemType === "teaching_material") {
    if (meLoading) return <PlayerSkeleton />;
    if (!authed) return <LoginGate message="Log in to download this teaching material." />;
    const files = (atts ?? []).filter(
      (a) => a.role === "teaching_material_file" && a.state === "clean",
    );
    return (
      <section
        aria-labelledby="files-h"
        className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded p-4 space-y-2"
      >
        <h2 id="files-h" className="font-semibold">
          Files
        </h2>
        {files.length === 0 ? (
          <p className="text-sm text-[var(--color-fg-muted)]">
            {externalUrl ? (
              <>
                External:{" "}
                <a href={externalUrl} target="_blank" rel="noopener noreferrer">
                  {externalUrl}
                </a>
              </>
            ) : (
              "No files yet (scanning may still be running)."
            )}
          </p>
        ) : (
          <ul className="space-y-1 text-sm">
            {files.map((f) => (
              <li key={f.id}>
                <a
                  href={f.stream_url}
                  className="text-[var(--color-brand-cyan)] underline"
                  rel="noopener noreferrer"
                >
                  {f.mime ?? "file"} ({humanBytes(f.bytes ?? 0)})
                </a>
              </li>
            ))}
          </ul>
        )}
      </section>
    );
  }

  // article — show downloadable attachments below the body, if any.
  const arts = (atts ?? []).filter((a) => a.role === "article_attachment" && a.state === "clean");
  if (arts.length === 0) return null;
  if (meLoading) return <PlayerSkeleton />;
  if (!authed) return <LoginGate message="Log in to download the attachments for this article." />;
  return (
    <section className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded p-4 space-y-2">
      <h2 className="font-semibold text-sm">Attachments</h2>
      <ul className="space-y-1 text-sm">
        {arts.map((a) => (
          <li key={a.id}>
            <a href={a.stream_url} target="_blank" rel="noopener noreferrer">
              {a.mime ?? "file"} ({humanBytes(a.bytes ?? 0)})
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}

function humanBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}
