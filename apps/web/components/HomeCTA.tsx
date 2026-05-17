"use client";

import Link from "next/link";
import { useMe } from "@/lib/useMe";

export function HomeCTA() {
  const { me, loading } = useMe();
  if (loading) {
    // Reserve space so the layout doesn't jump.
    return <div className="mt-8 h-10" aria-hidden />;
  }
  return (
    <div className="mt-8 flex flex-wrap gap-3">
      <Link
        href="/discover"
        className="px-5 py-2 bg-[var(--color-brand-cyan)] text-black rounded font-medium hover:opacity-90"
      >
        Browse content
      </Link>
      {me ? (
        <>
          <Link
            href="/me"
            className="px-5 py-2 border border-[var(--color-brand-blue-2)] rounded hover:border-[var(--color-brand-cyan)]"
          >
            My account
          </Link>
          <span className="self-center text-sm text-[var(--color-fg-muted)]">
            Signed in as <strong className="text-[var(--color-fg)]">{me.email}</strong>
            {me.role !== "user" && (
              <span className="ml-2 px-2 py-0.5 rounded text-xs bg-[var(--color-brand-blue-4)] capitalize">
                {me.role}
              </span>
            )}
          </span>
        </>
      ) : (
        <Link
          href="/auth/signup"
          className="px-5 py-2 border border-[var(--color-brand-blue-2)] rounded hover:border-[var(--color-brand-cyan)]"
        >
          Create an account
        </Link>
      )}
    </div>
  );
}
