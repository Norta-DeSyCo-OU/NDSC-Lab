"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type Series = {
  id: string;
  title: string;
  is_course: boolean;
  owner_slug: string | null;
};

export function ItemSeriesBadge({ itemId }: { itemId: string }) {
  const [rows, setRows] = useState<Series[] | null>(null);

  useEffect(() => {
    fetch(`/api/items/${itemId}/collections`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : []))
      .then((d: Series[]) => setRows(d ?? []))
      .catch(() => setRows([]));
  }, [itemId]);

  if (!rows || rows.length === 0) return null;
  return (
    <p className="text-xs text-[var(--color-fg-muted)] mt-2">
      Part of:&nbsp;
      {rows.map((c, i) => (
        <span key={c.id}>
          {i > 0 && <span> · </span>}
          <Link
            href={`/collections/${c.id}`}
            className="text-[var(--color-brand-cyan)] underline"
          >
            {c.title}
            {c.is_course && <span className="ml-1 text-[var(--color-fg-muted)]">(course)</span>}
          </Link>
        </span>
      ))}
    </p>
  );
}
