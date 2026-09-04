"use client";

import { AlertTriangle, Database, Loader2, RefreshCw, ShieldCheck, Store } from "lucide-react";
import { Button } from "@/components/ui/button";

export function WorkspaceLoadingScreen({
  title = "Đang mở workspace của bạn",
  detail = "Hệ thống đang xác thực tài khoản và nạp dữ liệu cửa hàng.",
}: {
  title?: string;
  detail?: string;
}) {
  return (
    <main className="relative grid min-h-screen place-items-center overflow-hidden bg-bg px-6 text-text">
      <div className="glow-field z-0">
        <div className="glow-blob left-[-15%] top-[-20%] h-[30rem] w-[30rem] bg-accent" />
        <div className="glow-blob bottom-[-25%] right-[-10%] h-[28rem] w-[28rem] bg-accent-2" />
      </div>
      <section className="card-surface relative z-10 w-full max-w-lg rounded-2xl border p-7 text-center sm:p-10">
        <div className="mx-auto grid h-16 w-16 place-items-center rounded-2xl border-2 border-accent/35 bg-accent/10 text-accent shadow-[4px_4px_0_hsl(var(--accent)/0.16)]">
          <Store className="h-7 w-7" />
        </div>
        <h1 className="mt-6 font-doodle text-3xl font-bold tracking-tight">{title}</h1>
        <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-text-muted">{detail}</p>

        <div className="mx-auto mt-7 h-2 max-w-xs overflow-hidden rounded-full bg-surface-3">
          <div className="h-full w-2/3 animate-pulse rounded-full bg-accent" />
        </div>

        <div className="mt-7 grid gap-2 text-left text-xs text-text-muted sm:grid-cols-3">
          <div className="rounded-xl border border-border bg-surface-2 p-3">
            <ShieldCheck className="mb-2 h-4 w-4 text-success" />
            Xác thực phiên
          </div>
          <div className="rounded-xl border border-border bg-surface-2 p-3">
            <Database className="mb-2 h-4 w-4 text-accent" />
            Nạp workspace
          </div>
          <div className="rounded-xl border border-border bg-surface-2 p-3">
            <Loader2 className="mb-2 h-4 w-4 animate-spin text-accent-2" />
            Đồng bộ dữ liệu
          </div>
        </div>
      </section>
    </main>
  );
}

export function WorkspaceLoadErrorScreen({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <main className="relative grid min-h-screen place-items-center overflow-hidden bg-bg px-6 text-text">
      <div className="glow-field z-0">
        <div className="glow-blob left-[-15%] top-[-20%] h-[30rem] w-[30rem] bg-warning" />
        <div className="glow-blob bottom-[-25%] right-[-10%] h-[28rem] w-[28rem] bg-accent" />
      </div>
      <section className="card-surface relative z-10 w-full max-w-lg rounded-2xl border p-8 text-center sm:p-10">
        <div className="mx-auto grid h-16 w-16 place-items-center rounded-2xl border-2 border-warning/40 bg-warning/10 text-warning shadow-[4px_4px_0_hsl(var(--warning)/0.14)]">
          <AlertTriangle className="h-7 w-7" />
        </div>
        <h1 className="mt-6 font-doodle text-3xl font-bold tracking-tight">
          Chưa nạp được workspace
        </h1>
        <p className="mx-auto mt-3 max-w-sm text-sm leading-6 text-text-muted">{message}</p>
        <Button className="mt-7" onClick={onRetry}>
          <RefreshCw className="h-4 w-4" />
          Nạp lại workspace
        </Button>
      </section>
    </main>
  );
}
