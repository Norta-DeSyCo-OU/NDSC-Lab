"use client";

import { useEffect, useRef, useState } from "react";

type Consent = { essential: true; analytics: boolean; version: string };
const VERSION = "2026-05-13";
const KEY = "ndsc.cookieConsent";

export function CookieBanner() {
  const [shown, setShown] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(KEY);
      if (!raw) setShown(true);
      else {
        const c = JSON.parse(raw) as Consent;
        if (c.version !== VERSION) setShown(true);
      }
    } catch {
      setShown(true);
    }
  }, []);

  useEffect(() => {
    if (shown) ref.current?.focus();
  }, [shown]);

  const persist = (analytics: boolean) => {
    const c: Consent = { essential: true, analytics, version: VERSION };
    localStorage.setItem(KEY, JSON.stringify(c));
    setShown(false);
  };

  if (!shown) return null;

  return (
    <div
      ref={ref}
      role="region"
      aria-label="Cookie consent"
      tabIndex={-1}
      className="fixed bottom-4 left-4 right-4 md:max-w-3xl md:left-1/2 md:-translate-x-1/2 bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)] text-[var(--color-fg)] p-4 rounded-lg shadow-lg z-50"
    >
      <p className="text-sm mb-3">
        We use essential cookies to operate this site. With your consent, we also count per-user
        views to understand which content is useful. See our{" "}
        <a href="/legal/privacy">Privacy Policy</a>.
      </p>
      <div className="flex flex-wrap gap-2 justify-end">
        <button
          type="button"
          onClick={() => persist(false)}
          className="px-3 py-1 border border-[var(--color-brand-blue-2)] rounded text-sm"
        >
          Essential only
        </button>
        <button
          type="button"
          onClick={() => persist(true)}
          className="px-3 py-1 bg-[var(--color-brand-cyan)] text-black rounded text-sm font-medium"
        >
          Accept all
        </button>
      </div>
    </div>
  );
}
