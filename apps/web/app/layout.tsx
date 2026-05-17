import "./globals.css";
import type { Metadata, Viewport } from "next";
import { ThemeProvider } from "next-themes";
import { Nav } from "@/components/Nav";
import { CookieBanner } from "@/components/CookieBanner";

export const metadata: Metadata = {
  title: { default: "NDSC Lab", template: "%s — NDSC Lab" },
  description:
    "Research and engineering on decentralized intelligent socio-technical systems — DAOs, ZKP, AI agents, M2M economies, DeFi.",
  applicationName: "NDSC Lab",
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#0a0f1e" },
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}>
          <a
            href="#main"
            className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:bg-[var(--color-brand-cyan)] focus:text-black focus:px-3 focus:py-1 focus:rounded z-40"
          >
            Skip to content
          </a>
          <Nav />
          <main id="main" className="max-w-6xl mx-auto px-4 py-8">
            {children}
          </main>
          <footer
            className="mt-16 border-t border-[var(--color-brand-blue-4)] py-8 text-sm text-[var(--color-fg-muted)]"
            aria-label="Site footer"
          >
            <div className="max-w-6xl mx-auto px-4 flex flex-wrap gap-4 justify-between">
              <span>© Norta DeSyCo OU — NDSC Lab</span>
              <nav aria-label="Legal and verification" className="flex gap-4 flex-wrap">
                <a href="/legal/terms">Terms</a>
                <a href="/legal/privacy">Privacy</a>
                <a href="/legal/takedown">Takedown</a>
                <a href="/verify">Verify a certificate</a>
              </nav>
            </div>
          </footer>
          <CookieBanner />
        </ThemeProvider>
      </body>
    </html>
  );
}
