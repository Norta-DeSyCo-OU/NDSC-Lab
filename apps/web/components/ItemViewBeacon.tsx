"use client";

import { useEffect } from "react";

const KEY = "ndsc.cookieConsent";

function hasAnalyticsConsent(): boolean {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return false;
    return !!JSON.parse(raw).analytics;
  } catch {
    return false;
  }
}

function uuidv4(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

async function csrfToken(): Promise<string> {
  const m = document.cookie.match(/(?:^|; )ndsc_csrf=([^;]+)/);
  if (m) return decodeURIComponent(m[1]);
  await fetch("/api/csrf", { credentials: "include" });
  const m2 = document.cookie.match(/(?:^|; )ndsc_csrf=([^;]+)/);
  return m2 ? decodeURIComponent(m2[1]) : "";
}

/**
 * Records a per-user view event when:
 * - the user accepted analytics in the cookie banner, AND
 * - for articles: ≥5 s on page AND ≥25 % scrolled,
 * - for videos: ≥10 s "watched" approximation (time on page used as a proxy
 *   until a real player is wired in).
 */
export function ItemViewBeacon({
  itemId,
  itemType,
}: {
  itemId: string;
  itemType: "article" | "video" | "teaching_material";
}) {
  useEffect(() => {
    if (!hasAnalyticsConsent()) return;
    const viewSessionUuid = uuidv4();
    const start = Date.now();
    let maxScroll = 0;
    let fired = false;

    const onScroll = () => {
      const h = document.documentElement;
      const denom = Math.max(1, h.scrollHeight - h.clientHeight);
      const pct = h.scrollTop / denom;
      if (pct > maxScroll) maxScroll = pct;
    };
    window.addEventListener("scroll", onScroll, { passive: true });

    const tryFire = async () => {
      if (fired) return;
      const watched = (Date.now() - start) / 1000;
      const ok =
        itemType === "video"
          ? watched >= 10
          : watched >= 5 && maxScroll >= 0.25;
      if (!ok) return;
      fired = true;
      try {
        const csrf = await csrfToken();
        await fetch("/api/events/view", {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
          body: JSON.stringify({
            item_id: itemId,
            item_type: itemType,
            view_session_uuid: viewSessionUuid,
            watched_s: watched,
            scroll_pct: maxScroll,
          }),
        });
      } catch {
        // best-effort; analytics may be blocked
      }
    };

    const interval = window.setInterval(tryFire, 2500);
    const onLeave = () => {
      void tryFire();
    };
    window.addEventListener("beforeunload", onLeave);

    return () => {
      window.clearInterval(interval);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("beforeunload", onLeave);
      void tryFire();
    };
  }, [itemId, itemType]);

  return null;
}
