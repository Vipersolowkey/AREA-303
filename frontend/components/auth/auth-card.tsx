"use client";

import Link from "next/link";
import { Sparkles } from "lucide-react";

/** Shared chrome for /login and /register so the two pages stay thin. */
export function AuthCard({
  title,
  subtitle,
  error,
  footer,
  children,
}: {
  title: string;
  subtitle: string;
  error?: string | null;
  footer: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <main className="relative grid min-h-screen place-items-center overflow-hidden px-4 py-12">
      <div className="glow-field">
        <div className="glow-blob left-[-10%] top-[-15%] h-[34rem] w-[34rem] bg-accent" />
        <div className="glow-blob right-[-5%] top-[-10%] h-[28rem] w-[28rem] bg-accent-2" />
      </div>

      <div className="relative w-full max-w-md">
        <Link href="/" className="mb-8 flex items-center justify-center gap-2">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-accent text-white">
            <Sparkles className="h-4 w-4" />
          </span>
          <span className="text-lg font-bold tracking-tight">Cellaxnet</span>
        </Link>

        <div className="card-surface rounded-lg border p-7">
          <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
          <p className="mt-1.5 text-sm text-text-muted">{subtitle}</p>

          {error && (
            <p className="mt-5 rounded-xl border border-danger/30 bg-danger/5 px-3.5 py-2.5 text-sm text-danger">
              {error}
            </p>
          )}

          <div className="mt-6">{children}</div>
        </div>

        <div className="mt-6 text-center text-sm text-text-muted">{footer}</div>
      </div>
    </main>
  );
}
