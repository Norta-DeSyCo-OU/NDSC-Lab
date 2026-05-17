"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useMe } from "@/lib/useMe";
import { Alert } from "@/components/Alert";
import {
  LayoutDashboard,
  ListChecks,
  Users,
  ScrollText,
  Award,
  Settings,
  ShieldAlert,
} from "lucide-react";

const NAV = [
  { href: "/admin", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { href: "/admin/queue", label: "Queue", icon: ListChecks },
  { href: "/admin/users", label: "Users", icon: Users },
  { href: "/admin/certificates", label: "Certificates", icon: Award },
  { href: "/admin/security", label: "Security", icon: ShieldAlert },
  { href: "/admin/audit", label: "Audit log", icon: ScrollText },
  { href: "/admin/settings", label: "Settings", icon: Settings },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { me, loading } = useMe();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (!loading && (!me || me.role !== "admin")) {
      router.replace("/auth/login");
    }
  }, [me, loading, router]);

  if (loading) {
    return (
      <p role="status" aria-live="polite" className="text-sm text-[var(--color-fg-muted)]">
        Loading admin…
      </p>
    );
  }
  if (!me || me.role !== "admin") {
    return (
      <Alert kind="error">
        <ShieldAlert size={14} aria-hidden className="inline mr-1" /> Admin access required.
      </Alert>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-[200px_1fr] gap-6">
      <aside aria-label="Admin navigation">
        <nav className="border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)] rounded p-2 sticky top-20">
          <ul className="space-y-1">
            {NAV.map((n) => {
              const active = n.exact ? pathname === n.href : pathname.startsWith(n.href);
              const Icon = n.icon;
              return (
                <li key={n.href}>
                  <Link
                    href={n.href}
                    aria-current={active ? "page" : undefined}
                    className={`flex items-center gap-2 px-2 py-1.5 rounded text-sm ${
                      active
                        ? "bg-[var(--color-brand-blue-4)] text-[var(--color-brand-cyan)]"
                        : "hover:bg-[var(--color-brand-blue-4)]/40"
                    }`}
                  >
                    <Icon size={14} aria-hidden />
                    {n.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </aside>
      <section>{children}</section>
    </div>
  );
}
