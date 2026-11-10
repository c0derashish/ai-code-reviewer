import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import Logo from "./Logo";
import HeroBackground from "../landing/HeroBackground";
import ProfileMenu from "../settings/ProfileMenu";
import SettingsMenu from "../settings/SettingsMenu";

type PageShellProps = {
  title: string;
  children: ReactNode;
};

export default function PageShell({ title, children }: PageShellProps) {
  return (
    <div className="relative flex min-h-full flex-col bg-base text-main">
      <HeroBackground />

      <header className="sticky top-0 z-30 flex shrink-0 items-center justify-between gap-3 px-5 py-3 sm:px-8">
        {/* glass layer sits behind, so the menus can blur too */}
        <div
          aria-hidden="true"
          className="glass-panel pointer-events-none absolute inset-0 -z-10 border-b [--glass-alpha:75%]"
        />
        <Link to="/" aria-label="Back to landing page">
          <Logo />
        </Link>
        <div className="flex items-center gap-2">
          <ProfileMenu />
          <SettingsMenu />
        </div>
      </header>

      <main className="relative z-10 mx-auto w-full max-w-5xl flex-1 px-5 py-8 sm:px-8">
        <h1 className="mb-6 text-2xl font-semibold">{title}</h1>
        {children}
      </main>
    </div>
  );
}