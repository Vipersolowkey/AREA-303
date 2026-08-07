"use client";

import Link from "next/link";
import { Star, ShoppingBag } from "lucide-react";
import { StoreImage } from "@/components/store/store-image";
import { isOutOfStock, type StoreProduct } from "@/lib/features";
import { cn } from "@/lib/utils";

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
  const soldOut = isOutOfStock(product);
  // Only warn when we know the number and it's genuinely low — `stock: null`
  // means the level is unknown, which must not read as scarcity.
  const lowStock = !soldOut && product.stock !== null && product.stock <= 5;

  return (
    <Link
      href={`/shop/store/${product.id}`}
      onClick={onClick}
      className="group flex flex-col gap-3"
    >
      <div className="relative">
        <StoreImage
          name={product.name}
          category={product.category}
          src={product.image_url}
          className={cn("rounded-xl", soldOut && "opacity-50")}
        />
        {soldOut && (
          <span className="absolute left-2 top-2 rounded-full bg-text px-2.5 py-1 text-2xs font-semibold text-bg">
            Hết hàng
          </span>
        )}
        {lowStock && (
          <span className="absolute left-2 top-2 rounded-full bg-warning px-2.5 py-1 text-2xs font-semibold text-white">
            Còn {product.stock}
          </span>
        )}
      </div>

      <div className="min-w-0">
        <div className="truncate text-2xs uppercase tracking-wider text-text-dim">{product.brand}</div>
        <div className="mt-0.5 truncate text-sm text-text" title={product.name}>
          {product.name}
        </div>
      </div>

      <div className="flex items-center justify-between">
        <span className="mono text-sm text-text" data-tnum>
          {VND.format(product.price_vnd).replace(/\s*₫/g, "")}₫
        </span>
        <div className="flex items-center gap-1 text-2xs text-text-muted">
          <Star className="h-3 w-3 fill-warning stroke-warning" />
          <span className="mono text-text">{product.rating.toFixed(1)}</span>
        </div>
      </div>

      {onCart && (
        <button
          type="button"
          disabled={soldOut}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onCart();
          }}
          className="mt-1 inline-flex items-center justify-center gap-1.5 rounded-full border border-border-strong px-3 py-2 text-xs font-semibold text-text transition-colors hover:border-accent hover:bg-accent/5 hover:text-accent disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-border-strong disabled:hover:bg-transparent disabled:hover:text-text"
        >
          <ShoppingBag className="h-3.5 w-3.5" /> {soldOut ? "Hết hàng" : "Thêm vào giỏ"}
        </button>
      )}
    </Link>
  );
}
