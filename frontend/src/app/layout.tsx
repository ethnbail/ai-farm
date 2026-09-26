import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "@/components/ui";
import { LiveEventsProvider } from "@/hooks/use-live-events";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Farm · A place to grow",
  description: "Your paper agents and local opportunities, in one calm place.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <header className="border-b border-line">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-6 sm:px-10">
            <Link
              href="/"
              className="flex items-center gap-3 text-xl font-semibold"
            >
              <span className="rounded-xl bg-green p-2 text-cream">
                <Icon />
              </span>
              AI Farm
            </Link>
            <span className="text-xs font-medium uppercase tracking-widest text-muted">
              PAPER TRADING <span className="mx-2">/</span> Phase 04
            </span>
          </div>
        </header>
        <main
          id="main"
          className="mx-auto max-w-7xl px-6 py-10 sm:px-10 sm:py-14"
        >
          <LiveEventsProvider>{children}</LiveEventsProvider>
        </main>
        <footer className="mx-auto flex max-w-7xl flex-wrap justify-between gap-3 px-6 pb-8 text-xs text-muted sm:px-10">
          <p>AI Farm · Small beginnings, thoughtful growth.</p>
          <p>Development preview · Paper funds only</p>
        </footer>
      </body>
    </html>
  );
}
