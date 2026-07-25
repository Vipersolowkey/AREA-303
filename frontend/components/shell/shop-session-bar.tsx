"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Activity, X } from "lucide-react";
import { getTracked, clearTracked, JOURNEY_EVENT, type TrackedEvent } from "@/lib/journey-track";

/** Floating pill showing the shopper's live tracked session, with a shortcut to
 * analyse it in the seller Customer Journey panel. */
export function ShopSessionBar() {
  const [events, setEvents] = useState<TrackedEvent[]>([]);

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
      <div className="flex items-center gap-3 rounded-2xl border border-accent/40 bg-surface/95 px-4 py-3 shadow-soft backdrop-blur">
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-accent/15 text-accent">
          <Activity className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-bold text-text">Phiên của bạn · {events.length} hành động</div>
          <div className="truncate text-2xs text-text-muted">{summary}</div>
        </div>
        <Link
          href="/seller/customer-journey"
          className="shrink-0 rounded-full bg-accent px-3 py-1.5 text-xs font-bold text-white transition-transform hover:-translate-y-0.5"
        >
          Phân tích →
        </Link>
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
