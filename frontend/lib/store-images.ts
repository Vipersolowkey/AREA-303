/**
 * Storefront demo imagery — "lấy tạm hình shop khác để demo".
 * Maps a product name + category to an English Unsplash keyword (same tag logic
 * as components/genai/product-card.tsx `imageTag()`), then to an Unsplash URL.
 * A matching lucide icon is exposed for the graceful fallback when a photo fails.
 */
import {
  Palette, Droplet, Sparkles, SprayCan, ShoppingBag, Footprints, Glasses,
  Watch, Shirt, Flower2, Package, HardHat, Minus, Wind, type LucideIcon,
} from "lucide-react";

/** One precise English keyword per product so the photo matches the item type. */
export function imageKeyword(name: string, category: string): string {
  const n = `${name} ${category}`.toLowerCase();
  const has = (...ks: string[]) => ks.some((k) => n.includes(k));
  if (has("son", "lipstick", "môi", "tint", "velvet")) return "lipstick";
  if (has("serum", "tinh chất", "vitamin c", "niacinamide", "bha", "aha", "retinol")) return "serum,skincare";
  if (has("mặt nạ", "mask")) return "face mask";
  if (has("kem", "cream", "dưỡng", "lotion", "toner", "rửa mặt", "sữa rửa", "cushion", "chống nắng")) return "skincare,cosmetics";
  if (has("nước hoa", "perfume", "fragrance")) return "perfume";
  if (has("túi", "tote", "balo", "ví", "handbag", "bag")) return "handbag,bag";
  if (has("giày", "sneaker", "dép", "sandal", "boot", "shoe")) return "sneakers,shoes";
  if (has("kính", "glasses", "sunglass")) return "sunglasses";
  if (has("đồng hồ", "watch")) return "watch";
  if (has("váy", "đầm", "dress", "midi")) return "dress";
  if (has("quần", "jean", "denim")) return "jeans";
  if (has("áo thun", "tshirt", "tee")) return "tshirt";
  if (has("áo", "khoác", "hoodie", "jacket", "shirt")) return "jacket,clothing";
  if (has("mũ", "nón", "hat", "cap")) return "hat";
  if (has("thắt lưng", "belt")) return "belt";
  if (has("khăn", "scarf")) return "scarf";
  if (category === "Mỹ phẩm") return "cosmetics";
  if (category === "Phụ kiện") return "accessory";
  return "fashion";
}

export function imageUrl(name: string, category: string): string {
  const keyword = imageKeyword(name, category);
  return `https://source.unsplash.com/400x400/?${encodeURIComponent(keyword)}`;
}

/** Fallback icon (shown if the photo fails to load) matched to the keyword. */
export function iconForKeyword(keyword: string): LucideIcon {
  const map: Record<string, LucideIcon> = {
    "lipstick": Palette,
    "serum,skincare": Droplet,
    "face mask": Sparkles,
    "skincare,cosmetics": Droplet,
    "perfume": SprayCan,
    "handbag,bag": ShoppingBag,
    "sneakers,shoes": Footprints,
    "sunglasses": Glasses,
    "watch": Watch,
    "dress": Shirt,
    "jeans": Shirt,
    "tshirt": Shirt,
    "jacket,clothing": Shirt,
    "hat": HardHat,
    "belt": Minus,
    "scarf": Wind,
    "cosmetics": Flower2,
    "accessory": Package,
    "fashion": Shirt,
  };
  return map[keyword] ?? Shirt;
}
