"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Activity, X } from "lucide-react";
import { getTracked, clearTracked, JOURNEY_EVENT, type TrackedEvent } from "@/lib/journey-track";
import { useAuth } from "@/lib/auth-context";
import { useMounted } from "@/lib/hooks/use-mounted";

/** Floating pill showing the shopper's live tracked session, with a shortcut to
 * analyse it in the seller Customer Journey panel. */
export function ShopSessionBar() {
  const [events, setEvents] = useState<TrackedEvent[]>([]);
  const { isAdmin } = useAuth();
  const mounted = useMounted();

  useEffect(() => {
    const sync = () => setEvents(getTracked());
    sync();
    window.addEventListener(JOURNEY_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(JOURNEY_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  if (events.length === 0) return null;

  const kinds = events.reduce<Record<string, number>>((a, e) => {
    a[e.type] = (a[e.type] ?? 0) + 1;
    return a;
  }, {});
  const summary = Object.entries(kinds)
    .map(([k, n]) => `${n} ${({ search: "tìm", click: "click", view: "xem", cart: "giỏ", purchase: "mua", livestream: "live" } as Record<string, string>)[k] ?? k}`)
    .join(" · ");

  return (
    <div className="fixed bottom-4 left-1/2 z-40 w-[calc(100%-2rem)] max-w-md -translate-x-1/2">
      <div className="flex items-center gap-3 rounded-2xl border border-border bg-surface px-4 py-3 shadow-soft">
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-accent/10 text-accent">
          <Activity className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium text-text">Phiên của bạn · {events.length} hành động</div>
          <div className="truncate text-2xs text-text-muted">{summary}</div>
        </div>
        {/* Third seller entry point — the session summary stays visible to
            every shopper, but only an admin gets the link into the portal. */}
        {mounted && isAdmin && (
          <Link
            href="/seller/customer-journey"
            className="shrink-0 rounded-full bg-accent/10 px-3 py-1.5 text-xs font-semibold text-accent"
          >
            Phân tích →
          </Link>
        )}
        <button
          onClick={() => clearTracked()}
          aria-label="Xóa phiên"
          className="shrink-0 text-text-dim transition-colors hover:text-danger"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
