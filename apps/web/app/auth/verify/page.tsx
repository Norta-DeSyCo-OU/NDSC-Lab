import { apiUrl } from "@/lib/api";
import type { Metadata } from "next";

export const dynamic = "force-dynamic";

export const metadata: Metadata = { title: "Email verification" };

export default async function VerifyEmailPage({
  searchParams,
}: {
  searchParams: Promise<{ t?: string }>;
}) {
  const sp = await searchParams;
  if (!sp.t) {
    return (
      <section className="max-w-md mx-auto">
        <h1 className="text-2xl font-bold mb-3">Missing verification token</h1>
        <p className="text-sm text-[var(--color-fg-muted)]">
          The link is incomplete. Sign up again to receive a fresh verification email.
        </p>
      </section>
    );
  }
  const r = await fetch(apiUrl(`/auth/verify?t=${encodeURIComponent(sp.t)}`), {
    cache: "no-store",
  });
  const ok = r.ok;
  return (
    <section className="max-w-md mx-auto">
      <h1 className="text-2xl font-bold mb-3">
        {ok ? "Email confirmed" : "Verification failed"}
      </h1>
      <p className="text-sm text-[var(--color-fg-muted)]">
        {ok ? (
          <>
            You can now <a href="/auth/login">sign in</a>.
          </>
        ) : (
          "The link is invalid or has expired. Sign up again to receive a fresh verification email."
        )}
      </p>
    </section>
  );
}
