import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import Logo from "../common/Logo";
import SettingsMenu from "../settings/SettingsMenu";
import HeroBackground from "../landing/HeroBackground";

type AuthLayoutProps = {
  title: string;
  subtitle: string;
  children: ReactNode;
  footer: ReactNode;
};

export default function AuthLayout({ title, subtitle, children, footer }: AuthLayoutProps) {
  return (
    <div className="relative flex min-h-full flex-col bg-base text-main">
      <HeroBackground />

      <header className="relative z-20 flex items-center justify-between px-5 py-4 sm:px-8">
        <Link to="/" aria-label="Back to landing page">
          <Logo />
        </Link>
        <SettingsMenu />
      </header>

      <main className="relative z-10 flex flex-1 items-center justify-center px-4 py-8">
        <div className="glass-panel w-full max-w-md rounded-xl border p-6 shadow-2xl [--glass-alpha:65%] sm:p-8">
          <div className="mb-6">
            <h1 className="text-2xl font-semibold">{title}</h1>
            <p className="mt-1 text-sm text-muted">{subtitle}</p>
          </div>

          {children}

          <div className="mt-6 border-t border-line pt-4 text-center text-sm text-muted">
            {footer}
          </div>
        </div>
      </main>
    </div>
  );
}