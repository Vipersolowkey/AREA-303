"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, Star, ShoppingBag, CheckCircle2, Loader2, PackageOpen } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { getStoreProduct, type StoreProduct } from "@/lib/features";
import { trackEvent } from "@/lib/journey-track";
import { StoreImage } from "@/components/store/store-image";
import { StoreProductCard } from "@/components/store/store-product-card";

const VND = new Intl.NumberFormat("vi-VN", {
  style: "currency",
  currency: "VND",
  maximumFractionDigits: 0,
});

export default function StoreDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id;

  const [product, setProduct] = useState<StoreProduct | null>(null);
  const [similar, setSimilar] = useState<StoreProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [ordered, setOrdered] = useState(false);

  useEffect(() => {
    if (!id) return;
    let alive = true;
    setLoading(true);
    getStoreProduct(id).then((res) => {
      if (!alive) return;
      const p = res?.product ?? null;
      setProduct(p);
      setSimilar(res?.similar ?? []);
      setLoading(false);
      if (p) trackEvent("view", { category: p.category });
    });
    return () => {
      alive = false;
    };
  }, [id]);

  if (loading) {
    return (
      <div className="grid place-items-center rounded-3xl border border-border bg-surface py-24 text-text-muted">
        <Loader2 className="h-6 w-6 animate-spin" />
        <p className="mt-3 text-sm">Đang tải sản phẩm…</p>
      </div>
    );
  }

  if (!product) {
    return (
      <div className="grid place-items-center rounded-3xl border border-border bg-surface py-24 text-center">
        <PackageOpen className="h-8 w-8 text-text-dim" />
        <p className="mt-3 text-lg font-extrabold">Không tìm thấy sản phẩm</p>
        <Link href="/shop/store" className="mt-4 inline-flex items-center gap-1.5 font-bold text-accent">
          <ArrowLeft className="h-4 w-4" /> Về cửa hàng
        </Link>
      </div>
    );
  }

  const attributes = Object.entries(product.attributes ?? {});

  return (
    <div className="space-y-8">
      <Link href="/shop/store" className="inline-flex items-center gap-1.5 text-sm font-bold text-accent">
        <ArrowLeft className="h-4 w-4" /> Về cửa hàng
      </Link>

      <div className="grid gap-8 md:grid-cols-2">
        {/* Image */}
        <div className="group">
          <StoreImage name={product.name} category={product.category} src={product.image_url} iconClassName="h-1/4 w-1/4" />
        </div>

        {/* Info */}
        <div className="space-y-4">
          <div>
            <Badge variant="info">{product.category}</Badge>
            <h1 className="mt-2 text-2xl font-extrabold tracking-tight">{product.name}</h1>
            <div className="mt-1 text-sm uppercase tracking-wider text-text-dim">{product.brand}</div>
          </div>

          <div className="flex items-baseline gap-1.5">
            <span className="mono text-3xl font-extrabold text-text" data-tnum>
              {VND.format(product.price_vnd).replace(/\s*₫/g, "")}
            </span>
            <span className="mono text-base text-text-dim">₫</span>
          </div>

          <div className="flex items-center gap-1.5 text-sm text-text-muted">
            <Star className="h-4 w-4 fill-warning stroke-warning" />
            <span className="mono text-text">{product.rating.toFixed(1)}</span>
            <span className="mono text-text-dim">({product.reviews.toLocaleString()} đánh giá)</span>
          </div>

          {attributes.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {attributes.map(([k, v]) => (
                <span
                  key={k}
                  className="inline-flex items-center gap-1 rounded-full border border-border bg-bg-alt px-3 py-1 text-xs text-text-muted"
                >
                  <span className="text-text-dim">{k}:</span>
                  <span className="font-semibold text-text">{v}</span>
                </span>
              ))}
            </div>
          )}

          <div className="text-2xs uppercase tracking-wider text-text-dim">
            SKU <span className="mono text-text-muted">{product.sku}</span>
          </div>

          {ordered ? (
            <div className="inline-flex items-center gap-2 rounded-2xl border border-success/40 bg-success/10 px-4 py-3 text-sm font-bold text-success">
              <CheckCircle2 className="h-5 w-5" /> Đã đặt hàng!
            </div>
          ) : (
            <div className="flex flex-wrap gap-3 pt-2">
              <button
                type="button"
                onClick={() => trackEvent("cart", { category: product.category })}
                className="inline-flex items-center gap-2 rounded-2xl border border-accent/40 bg-accent/10 px-5 py-2.5 text-sm font-bold text-accent transition-colors hover:bg-accent hover:text-white"
              >
                <ShoppingBag className="h-4 w-4" /> Thêm vào giỏ
              </button>
              <button
                type="button"
                onClick={() => {
                  trackEvent("purchase", { category: product.category });
                  setOrdered(true);
                }}
                className="inline-flex items-center gap-2 rounded-2xl bg-accent px-5 py-2.5 text-sm font-bold text-white transition-transform hover:-translate-y-0.5"
              >
                Mua ngay
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Similar products */}
      {similar.length > 0 && (
        <section>
          <h2 className="mb-4 text-lg font-extrabold">Sản phẩm tương tự</h2>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            {similar.map((p) => (
              <StoreProductCard key={p.id} product={p} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
