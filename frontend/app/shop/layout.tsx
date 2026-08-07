import { ShopShell } from "@/components/shell/shop-shell";

// No theme override any more: /shop and /seller share the single token set in
// globals.css so the two apps read as one product.
export default function ShopLayout({ children }: { children: React.ReactNode }) {
  return <ShopShell>{children}</ShopShell>;
}
