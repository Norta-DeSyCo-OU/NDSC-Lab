"use client";

import Link from "next/link";
import { useMe } from "@/lib/useMe";

/**
 * Renders a "Create new …" call-to-action only for contributors and admins.
 * Hidden for anonymous and plain-user roles.
 */
export function ContributorCTA({
  href,
  label,
  rolesAllowed = ["contributor", "admin"],
}: {
  href: string;
  label: string;
  rolesAllowed?: string[];
}) {
  const { me } = useMe();
  if (!me || !rolesAllowed.includes(me.role)) return null;
  return (
    <Link
      href={href}
      className="inline-flex items-center px-4 py-2 bg-[var(--color-brand-cyan)] text-black rounded font-medium text-sm hover:opacity-90"
    >
      + {label}
    </Link>
  );
}
