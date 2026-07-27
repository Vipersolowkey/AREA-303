"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { imageUrl, imageKeyword, iconForKeyword } from "@/lib/store-images";

/**
 * Storefront product image with a graceful fallback: if the demo Unsplash photo
 * fails to load, we hide the <img> and show a soft gradient tile with a lucide
 * icon matched to the product type — so a card never looks broken.
 */
export function StoreImage({
  name,
  category,
  src: srcProp,
  className,
  iconClassName = "h-1/3 w-1/3",
}: {
  name: string;
  category: string;
  /** Real backend image URL; falls back to a keyword image, then an icon. */
  src?: string;
  className?: string;
  iconClassName?: string;
}) {
  const [broken, setBroken] = useState(false);
  const keyword = imageKeyword(name, category);
  const Icon = iconForKeyword(keyword);
  const src = srcProp?.trim() || imageUrl(name, category);

  return (
    <div
      className={cn(
        "relative grid aspect-square w-full place-items-center overflow-hidden rounded-xl border border-border",
        className,
      )}
      style={{ background: "linear-gradient(135deg, hsl(215 62% 92%), hsl(247 66% 84%))" }}
    >
      {!broken ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt={name}
          loading="lazy"
          onError={() => setBroken(true)}
          className="absolute inset-0 h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
        />
      ) : (
        <Icon className={iconClassName} strokeWidth={1.5} style={{ color: "hsl(215 45% 38%)" }} />
      )}
    </div>
  );
}
