"use client";
/** A real client-side shopping cart (localStorage, shared across the Shop). */
export type CartItem = {
  id: string; name: string; brand: string; price_vnd: number; image_url: string; qty: number;
};

const KEY = "area303:cart";
export const CART_EVENT = "area303:cart";

function read(): CartItem[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as CartItem[]) : [];
  } catch {
    return [];
  }
}

function write(items: CartItem[]): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(KEY, JSON.stringify(items));
    window.dispatchEvent(new Event(CART_EVENT));
  } catch {
    /* ignore */
  }
}

export function getCart(): CartItem[] {
  return read();
}

export function addToCart(item: Omit<CartItem, "qty">, qty = 1): void {
  const items = read();
  const existing = items.find((i) => i.id === item.id);
  if (existing) existing.qty += qty;
  else items.push({ ...item, qty });
  write(items);
}

export function setQty(id: string, qty: number): void {
  const items = read().map((i) => (i.id === id ? { ...i, qty: Math.max(1, qty) } : i));
  write(items);
}

export function removeItem(id: string): void {
  write(read().filter((i) => i.id !== id));
}

export function clearCart(): void {
  write([]);
}

export function cartCount(): number {
  return read().reduce((n, i) => n + i.qty, 0);
}

export function cartTotal(): number {
  return read().reduce((s, i) => s + i.price_vnd * i.qty, 0);
}
