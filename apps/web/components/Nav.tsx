"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { useEffect, useRef, useState } from "react";
import {
  Sun,
  Moon,
  Menu,
  X,
  ChevronDown,
  LogOut,
  Shield,
  User as UserIcon,
  ExternalLink,
} from "lucide-react";
import { useMe, setMe, type Me } from "@/lib/useMe";
import { apiPost } from "@/lib/api";

const LINKS = [
  { href: "/series", label: "Lecture series" },
  { href: "/workshops", label: "Workshops" },
  { href: "/contributors", label: "Contributors" },
  { href: "/verify", label: "Verify" },
];

type MenuEntry = {
  href: string;
  label: string;
  hint?: string;
  external?: boolean;
  roles?: ("user" | "contributor" | "admin")[];
};

function profileMenuFor(me: Me): MenuEntry[] {
  const isContributor = me.role !== "user";
  const isAdmin = me.role === "admin";
  return [
    { href: "/me", label: "My account", hint: "Overview & data" },
    ...(isContributor
      ? [
          { href: "/me/profile", label: "Edit public profile", hint: "Photo, bio, links, contacts" },
          { href: "/me/content", label: "My content", hint: "Drafts and published items" },
          { href: "/me/collections", label: "My lecture series", hint: "Ordered playlists & courses" },
          { href: "/me/workshops", label: "My workshops", hint: "Schedule live sessions" },
        ]
      : []),
    { href: "/me/certificates", label: "My certificates", hint: "Issued course completions" },
    { href: "/me/security", label: "Security", hint: "Password, email" },
    ...(isAdmin
      ? [{ href: "/admin", label: "Admin console", hint: "Queue, users, security" }]
      : []),
    ...(me.profile_slug
      ? [
          {
            href: `/c/${me.profile_slug}`,
            label: "View my public page",
            hint: `/c/${me.profile_slug}`,
            external: true,
          },
        ]
      : []),
  ];
}

export function Nav() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);
  const [acctOpen, setAcctOpen] = useState(false);
  const pathname = usePathname();
  const { me } = useMe();
  const acctRef = useRef<HTMLDivElement>(null);
  const hoverTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => setMounted(true), []);
  useEffect(() => {
    setOpen(false);
    setAcctOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!acctOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (acctRef.current && !acctRef.current.contains(e.target as Node))
        setAcctOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setAcctOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [acctOpen]);

  function onMenuEnter() {
    if (hoverTimer.current) clearTimeout(hoverTimer.current);
    setAcctOpen(true);
  }
  function onMenuLeave() {
    if (hoverTimer.current) clearTimeout(hoverTimer.current);
    // Small grace period so jumping the cursor from button → panel doesn't close.
    hoverTimer.current = setTimeout(() => setAcctOpen(false), 120);
  }

  async function signOut() {
    try {
      await apiPost("/auth/logout", {});
    } catch {
      // ignore
    }
    setMe(null);
    window.location.href = "/";
  }

  return (
    <header className="border-b border-[var(--color-brand-blue-4)]/60 sticky top-0 backdrop-blur-md bg-[color-mix(in_oklab,var(--color-bg-base),transparent_25%)] z-30 supports-[backdrop-filter]:bg-[color-mix(in_oklab,var(--color-bg-base),transparent_40%)]">
      <nav
        aria-label="Primary"
        className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between gap-4"
      >
        <Link
          href="/"
          className="font-semibold tracking-wide text-[var(--color-brand-cyan)] hover:opacity-90 transition-opacity"
          aria-label="NDSC Lab home"
          style={{ textShadow: "0 0 18px color-mix(in oklab, var(--color-brand-cyan), transparent 60%)" }}
        >
          NDSC&nbsp;Lab
        </Link>

        <ul className="hidden md:flex items-center gap-1 text-sm">
          {LINKS.map((l) => {
            const active = pathname === l.href || pathname.startsWith(l.href + "/");
            return (
              <li key={l.href}>
                <Link
                  href={l.href}
                  aria-current={active ? "page" : undefined}
                  className={
                    "relative px-3 py-1.5 rounded-md transition-colors after:absolute after:left-3 after:right-3 after:-bottom-0.5 after:h-px after:transition-opacity " +
                    (active
                      ? "text-[var(--color-brand-cyan)] after:bg-[var(--color-brand-cyan)] after:opacity-100"
                      : "hover:text-[var(--color-brand-cyan)] after:bg-[var(--color-brand-cyan)] after:opacity-0 hover:after:opacity-60")
                  }
                >
                  {l.label}
                </Link>
              </li>
            );
          })}

          {me ? (
            <li>
              <div
                className="relative"
                ref={acctRef}
                onMouseEnter={onMenuEnter}
                onMouseLeave={onMenuLeave}
                onFocus={() => setAcctOpen(true)}
                onBlur={(e) => {
                  if (!e.currentTarget.contains(e.relatedTarget as Node))
                    setAcctOpen(false);
                }}
              >
                <button
                  type="button"
                  onClick={() => setAcctOpen((v) => !v)}
                  aria-expanded={acctOpen}
                  aria-haspopup="menu"
                  className="flex items-center gap-2 pl-1 pr-2.5 py-1 rounded-full border border-[var(--color-brand-blue-2)] hover:border-[var(--color-brand-cyan)] hover:shadow-[0_0_0_3px_color-mix(in_oklab,var(--color-brand-cyan),transparent_85%)] transition-all"
                >
                  {me.photo_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={me.photo_url}
                      alt=""
                      width={26}
                      height={26}
                      className="w-[26px] h-[26px] rounded-full object-cover ring-1 ring-[var(--color-brand-blue-4)]"
                    />
                  ) : (
                    <span
                      aria-hidden
                      className="w-[26px] h-[26px] rounded-full bg-[var(--color-bg-panel)] border border-[var(--color-brand-blue-4)] flex items-center justify-center"
                    >
                      {me.role === "admin" ? (
                        <Shield size={13} className="text-[var(--color-brand-cyan)]" />
                      ) : (
                        <UserIcon size={13} />
                      )}
                    </span>
                  )}
                  <span className="font-medium">My Profile</span>
                  <ChevronDown
                    size={14}
                    aria-hidden
                    className={
                      "transition-transform " + (acctOpen ? "rotate-180" : "")
                    }
                  />
                </button>

                <div
                  role="menu"
                  aria-hidden={!acctOpen}
                  className={
                    "absolute right-0 mt-2 w-72 origin-top-right rounded-lg border border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)]/95 backdrop-blur-md shadow-[0_8px_32px_-8px_rgba(0,0,0,0.6),0_0_0_1px_color-mix(in_oklab,var(--color-brand-cyan),transparent_85%)] py-2 text-sm transition-all " +
                    (acctOpen
                      ? "opacity-100 translate-y-0 visible pointer-events-auto"
                      : "opacity-0 -translate-y-1 invisible pointer-events-none")
                  }
                >
                  <div className="px-4 py-2 border-b border-[var(--color-brand-blue-4)]/60 flex items-center gap-3">
                    {me.photo_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={me.photo_url}
                        alt=""
                        width={38}
                        height={38}
                        className="w-[38px] h-[38px] rounded-full object-cover"
                      />
                    ) : (
                      <span
                        aria-hidden
                        className="w-[38px] h-[38px] rounded-full bg-[var(--color-bg-base)] border border-[var(--color-brand-blue-4)] flex items-center justify-center"
                      >
                        {me.role === "admin" ? (
                          <Shield size={18} className="text-[var(--color-brand-cyan)]" />
                        ) : (
                          <UserIcon size={18} />
                        )}
                      </span>
                    )}
                    <div className="min-w-0">
                      <div className="font-semibold truncate">
                        {me.display_name || me.email.split("@")[0]}
                      </div>
                      <div className="text-xs text-[var(--color-fg-muted)] truncate">
                        {me.email}
                      </div>
                      <div className="text-[10px] uppercase tracking-wider text-[var(--color-brand-cyan)] mt-0.5">
                        {me.role}
                      </div>
                    </div>
                  </div>

                  <ul className="py-1">
                    {profileMenuFor(me).map((it) => (
                      <li key={it.href}>
                        <Link
                          href={it.href}
                          role="menuitem"
                          target={it.external ? "_blank" : undefined}
                          rel={it.external ? "noopener noreferrer" : undefined}
                          className="flex items-start justify-between gap-3 px-4 py-2 hover:bg-[var(--color-bg-base)] focus:bg-[var(--color-bg-base)] focus:outline-none transition-colors"
                        >
                          <div className="min-w-0">
                            <div className="font-medium flex items-center gap-1">
                              {it.label}
                              {it.external && (
                                <ExternalLink
                                  size={12}
                                  aria-hidden
                                  className="text-[var(--color-fg-muted)]"
                                />
                              )}
                            </div>
                            {it.hint && (
                              <div className="text-xs text-[var(--color-fg-muted)] truncate">
                                {it.hint}
                              </div>
                            )}
                          </div>
                        </Link>
                      </li>
                    ))}
                    <li className="border-t border-[var(--color-brand-blue-4)]/60 mt-1 pt-1">
                      <button
                        type="button"
                        onClick={signOut}
                        role="menuitem"
                        className="flex items-center gap-2 w-full text-left px-4 py-2 hover:bg-[var(--color-bg-base)] text-red-300 transition-colors"
                      >
                        <LogOut size={14} aria-hidden /> Sign out
                      </button>
                    </li>
                  </ul>
                </div>
              </div>
            </li>
          ) : (
            <li>
              <Link
                href="/auth/login"
                className="ml-2 px-4 py-1.5 rounded-full border border-[var(--color-brand-cyan)] text-[var(--color-brand-cyan)] hover:bg-[var(--color-brand-cyan)] hover:text-black hover:shadow-[0_0_0_4px_color-mix(in_oklab,var(--color-brand-cyan),transparent_85%)] transition-all font-medium"
              >
                Sign in
              </Link>
            </li>
          )}

          <li>
            <button
              type="button"
              aria-label={
                mounted && resolvedTheme === "dark"
                  ? "Switch to light theme"
                  : "Switch to dark theme"
              }
              onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
              className="p-2 rounded-full hover:bg-[var(--color-bg-panel)] transition-colors"
            >
              {mounted ? (
                resolvedTheme === "dark" ? (
                  <Sun size={18} aria-hidden />
                ) : (
                  <Moon size={18} aria-hidden />
                )
              ) : (
                <span className="inline-block w-[18px] h-[18px]" />
              )}
            </button>
          </li>
        </ul>

        <button
          type="button"
          className="md:hidden p-1"
          aria-expanded={open}
          aria-controls="primary-nav-mobile"
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X size={20} aria-hidden /> : <Menu size={20} aria-hidden />}
        </button>
      </nav>

      {open && (
        <div
          id="primary-nav-mobile"
          className="md:hidden border-t border-[var(--color-brand-blue-4)] bg-[var(--color-bg-panel)]/95 backdrop-blur"
        >
          <ul className="flex flex-col gap-1 px-4 py-3 text-sm">
            {LINKS.map((l) => (
              <li key={l.href}>
                <Link href={l.href} className="block py-2">
                  {l.label}
                </Link>
              </li>
            ))}
            {me ? (
              <>
                <li className="border-t border-[var(--color-brand-blue-4)] mt-2 pt-2">
                  <div className="text-xs text-[var(--color-fg-muted)]">Signed in as</div>
                  <div className="font-semibold truncate">{me.email}</div>
                </li>
                {profileMenuFor(me).map((it) => (
                  <li key={it.href}>
                    <Link
                      href={it.href}
                      target={it.external ? "_blank" : undefined}
                      rel={it.external ? "noopener noreferrer" : undefined}
                      className="block py-2"
                    >
                      {it.label}
                    </Link>
                  </li>
                ))}
                <li>
                  <button
                    type="button"
                    onClick={signOut}
                    className="py-2 flex items-center gap-2 text-red-300"
                  >
                    <LogOut size={14} aria-hidden /> Sign out
                  </button>
                </li>
              </>
            ) : (
              <li>
                <Link
                  href="/auth/login"
                  className="block py-2 text-[var(--color-brand-cyan)]"
                >
                  Sign in
                </Link>
              </li>
            )}
            <li className="border-t border-[var(--color-brand-blue-4)] mt-2 pt-2">
              <button
                type="button"
                aria-label="Toggle theme"
                onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
                className="py-2 flex items-center gap-2"
              >
                {mounted ? (
                  resolvedTheme === "dark" ? (
                    <Sun size={16} aria-hidden />
                  ) : (
                    <Moon size={16} aria-hidden />
                  )
                ) : null}
                <span>Toggle theme</span>
              </button>
            </li>
          </ul>
        </div>
      )}
    </header>
  );
}
