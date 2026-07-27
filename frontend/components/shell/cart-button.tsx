"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ShoppingCart } from "lucide-react";
import { cartCount, CART_EVENT } from "@/lib/cart";

export function CartButton() {
  const [count, setCount] = useState(0);
  useEffect(() => {
    const sync = () => setCount(cartCount());
    sync();
    window.addEventListener(CART_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(CART_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  return (
    <Link
      href="/shop/cart"
      aria-label="Giỏ hàng"
      className="relative grid h-10 w-10 place-items-center rounded-2xl border border-border text-text-muted transition-colors hover:border-text hover:text-text"
    >
      <ShoppingCart className="h-4 w-4" />
      {count > 0 && (
        <span className="absolute -right-1.5 -top-1.5 grid min-h-[18px] min-w-[18px] place-items-center rounded-full bg-accent px-1 text-2xs font-bold text-white">
          {count}
        </span>
      )}
    </Link>
  );
}
