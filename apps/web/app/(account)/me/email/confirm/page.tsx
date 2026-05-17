import { apiUrl } from "@/lib/api";

export const dynamic = "force-dynamic";
export const metadata = { title: "Email change" };

export default async function ConfirmEmailChange({
  searchParams,
}: {
  searchParams: Promise<{ t?: string }>;
}) {
  const sp = await searchParams;
  if (!sp.t) {
    return (
      <section className="max-w-md mx-auto">
        <h1 className="text-2xl font-bold mb-3">Missing token</h1>
      </section>
    );
  }
  const r = await fetch(apiUrl(`/me/email/confirm?t=${encodeURIComponent(sp.t)}`), {
    cache: "no-store",
  });
  const ok = r.ok;
  return (
    <section className="max-w-md mx-auto">
      <h1 className="text-2xl font-bold mb-3">{ok ? "Email updated" : "Confirmation failed"}</h1>
      <p className="text-sm text-[var(--color-fg-muted)]">
        {ok
          ? "Your new email is now active. Sign in if needed."
          : "The link is invalid or has expired. Request a new change from Security."}
      </p>
    </section>
  );
}
