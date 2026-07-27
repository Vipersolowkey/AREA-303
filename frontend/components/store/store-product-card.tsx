"use client";

import Link from "next/link";
import { Star, ShoppingBag } from "lucide-react";
import { StoreImage } from "@/components/store/store-image";
import type { StoreProduct } from "@/lib/features";

const VND = new Intl.NumberFormat("vi-VN", {
  style: "currency",
  currency: "VND",
  maximumFractionDigits: 0,
});

/** Catalog card used both in the storefront grid and the "similar" section. */
export function StoreProductCard({
  product,
  onClick,
  onCart,
}: {
  product: StoreProduct;
  /** Fired when the buyer navigates into the product (grid → detail). */
  onClick?: () => void;
  /** Fired by "Thêm vào giỏ"; when omitted the button is hidden. */
  onCart?: () => void;
}) {
  return (
    <Link
      href={`/shop/store/${product.id}`}
      onClick={onClick}
      className="group flex flex-col gap-2 rounded-2xl border border-border bg-surface p-3 transition-all hover:-translate-y-0.5 hover:shadow-soft"
    >
      <StoreImage name={product.name} category={product.category} src={product.image_url} />

      <div className="min-w-0">
        <div className="truncate text-sm font-semibold text-text group-hover:text-accent" title={product.name}>
          {product.name}
        </div>
        <div className="truncate text-2xs uppercase tracking-wider text-text-dim">{product.brand}</div>
      </div>

      <div className="flex items-baseline gap-1.5">
        <span className="mono text-base font-semibold text-text" data-tnum>
          {VND.format(product.price_vnd).replace(/\s*₫/g, "")}
        </span>
        <span className="mono text-2xs text-text-dim">₫</span>
      </div>

      <div className="flex items-center gap-1 text-2xs text-text-muted">
        <Star className="h-3 w-3 fill-warning stroke-warning" />
        <span className="mono text-text">{product.rating.toFixed(1)}</span>
        <span className="mono text-text-dim">({product.reviews.toLocaleString()})</span>
      </div>

      {onCart && (
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onCart();
          }}
          className="mt-1 inline-flex items-center justify-center gap-1.5 rounded-xl border border-accent/40 bg-accent/10 px-3 py-1.5 text-xs font-bold text-accent transition-colors hover:bg-accent hover:text-white"
        >
          <ShoppingBag className="h-3.5 w-3.5" /> Thêm vào giỏ
        </button>
      )}
    </Link>
  );
}
