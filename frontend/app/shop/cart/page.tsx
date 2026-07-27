"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowLeft, Minus, Plus, Trash2, ShoppingCart, CheckCircle2 } from "lucide-react";
import {
  getCart, setQty, removeItem, clearCart, cartTotal, cartCount, CART_EVENT, type CartItem,
} from "@/lib/cart";
import { trackEvent } from "@/lib/journey-track";
import { StoreImage } from "@/components/store/store-image";

const VND = new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND", maximumFractionDigits: 0 });
const fmt = (n: number) => VND.format(n).replace(/\s*₫/g, "") + "₫";

export default function CartPage() {
  const [items, setItems] = useState<CartItem[]>([]);
  const [ordered, setOrdered] = useState<{ count: number; total: number } | null>(null);

  useEffect(() => {
    const sync = () => setItems(getCart());
    sync();
    window.addEventListener(CART_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(CART_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  function checkout() {
    if (items.length === 0) return;
    // Multi-item purchase: one purchase event per item (feeds Journey), then clear.
    items.forEach(() => trackEvent("purchase"));
    setOrdered({ count: cartCount(), total: cartTotal() });
    clearCart();
  }

  if (ordered) {
    return (
      <div className="grid place-items-center rounded-3xl border border-success/40 bg-success/5 py-20 text-center">
        <CheckCircle2 className="h-10 w-10 text-success" />
        <p className="mt-4 text-xl font-extrabold">Đặt hàng thành công!</p>
        <p className="mt-1 text-text-muted">
          {ordered.count} sản phẩm · tổng <span className="mono font-bold text-text">{fmt(ordered.total)}</span>
        </p>
        <Link href="/shop/store" className="mt-5 inline-flex items-center gap-1.5 rounded-2xl bg-accent px-5 py-2.5 font-bold text-white">
          Tiếp tục mua sắm
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShoppingCart className="h-6 w-6 text-accent" />
          <h1 className="text-2xl font-extrabold tracking-tight">Giỏ hàng</h1>
        </div>
        <Link href="/shop/store" className="inline-flex items-center gap-1.5 text-sm font-bold text-accent">
          <ArrowLeft className="h-4 w-4" /> Về cửa hàng
        </Link>
      </div>

      {items.length === 0 ? (
        <div className="grid place-items-center rounded-3xl border border-border bg-surface py-20 text-center">
          <ShoppingCart className="h-8 w-8 text-text-dim" />
          <p className="mt-3 text-lg font-extrabold">Giỏ hàng trống</p>
          <p className="mt-1 text-text-muted">Vào cửa hàng chọn vài món nhé!</p>
          <Link href="/shop/store" className="mt-4 inline-flex items-center gap-1.5 rounded-2xl bg-accent px-5 py-2.5 font-bold text-white">
            Đi mua sắm
          </Link>
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Items */}
          <div className="space-y-3 lg:col-span-2">
            {items.map((it) => (
              <div key={it.id} className="flex gap-4 rounded-2xl border border-border bg-surface p-3">
                <div className="w-24 shrink-0">
                  <StoreImage name={it.name} category="" src={it.image_url} iconClassName="h-1/3 w-1/3" />
                </div>
                <div className="flex min-w-0 flex-1 flex-col">
                  <Link href={`/shop/store/${it.id}`} className="truncate text-sm font-semibold text-text hover:text-accent">
                    {it.name}
                  </Link>
                  <div className="truncate text-2xs uppercase tracking-wider text-text-dim">{it.brand}</div>
                  <div className="mono mt-1 text-sm font-semibold text-text">{fmt(it.price_vnd)}</div>
                  <div className="mt-auto flex items-center gap-3 pt-2">
                    <div className="inline-flex items-center overflow-hidden rounded-lg border border-border">
                      <button onClick={() => setQty(it.id, it.qty - 1)} className="grid h-8 w-8 place-items-center text-text-muted hover:text-text" aria-label="Giảm">
                        <Minus className="h-3.5 w-3.5" />
                      </button>
                      <span className="mono w-8 text-center text-sm text-text">{it.qty}</span>
                      <button onClick={() => setQty(it.id, it.qty + 1)} className="grid h-8 w-8 place-items-center text-text-muted hover:text-text" aria-label="Tăng">
                        <Plus className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    <button onClick={() => removeItem(it.id)} className="inline-flex items-center gap-1 text-2xs text-text-dim hover:text-danger">
                      <Trash2 className="h-3.5 w-3.5" /> Xóa
                    </button>
                  </div>
                </div>
                <div className="mono shrink-0 self-center text-sm font-bold text-text">{fmt(it.price_vnd * it.qty)}</div>
              </div>
            ))}
          </div>

          {/* Summary */}
          <div className="h-fit rounded-2xl border border-border bg-surface p-5">
            <div className="text-sm font-extrabold text-text">Tóm tắt đơn</div>
            <div className="mt-3 flex justify-between text-sm text-text-muted">
              <span>Số lượng</span><span className="mono text-text">{cartCount()} sản phẩm</span>
            </div>
            <div className="mt-2 flex justify-between text-sm text-text-muted">
              <span>Tạm tính</span><span className="mono text-text">{fmt(cartTotal())}</span>
            </div>
            <div className="mt-3 flex items-baseline justify-between border-t border-border pt-3">
              <span className="font-bold text-text">Tổng cộng</span>
              <span className="mono text-lg font-extrabold text-accent">{fmt(cartTotal())}</span>
            </div>
            <button
              onClick={checkout}
              className="mt-4 w-full rounded-2xl bg-accent px-5 py-3 text-sm font-bold text-white transition-transform hover:-translate-y-0.5"
            >
              Thanh toán ({cartCount()} món)
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
