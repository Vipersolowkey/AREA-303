import {
  LayoutDashboard,
  Star,
  Tag,
  ShoppingBag,
  UserMinus,
  TrendingUp,
  Image as ImageIcon,
  MessageSquare,
  PenLine,
  RotateCcw,
  Sparkles,
  ScanFace,
  Heart,
  Users2,
  BadgePercent,
  Truck,
  GraduationCap,
  Route,
  Brain,
  Swords,
  Users,
  Lightbulb,
  Bot,
  ClipboardCheck,
  Network,
  Store,
  type LucideIcon,
} from "lucide-react";

/**
 * Navigation contract — 17 e-commerce AI/ML features for AREA-303.
 *
 * Slug suffix is the canonical id; appears on every nav row right-aligned in mono.
 * Section groups mirror the day-by-day build plan in the project README.
 */
export type AppKind = "seller" | "shop";

export type NavItem = {
  id: string; // canonical feature id e.g. "01", "17"
  slug: string;
  label: string;
  href: string;
  icon: LucideIcon;
  app: AppKind; // which of the two apps this feature belongs to
  section: "commerce" | "intelligence" | "creator" | "operations" | "demand";
  category:
    | "NLP"
    | "Time Series"
    | "Computer Vision"
    | "Generative AI"
    | "Behavioral AI";
  owner: "TL" | "DA" | "FS" | "D1" | "D2";
};

// Two apps: `shop` = buyer storefront, `seller` = seller portal.
// href = /<app>/<slug>. `implemented` features (below) render a live panel.
export const NAV_ITEMS: NavItem[] = [
  // --- SHOP (buyer-facing) ---
  { id: "ST", slug: "store",            label: "Cửa hàng",           href: "/shop/store",            icon: Store,         app: "shop",   section: "commerce",     category: "Behavioral AI",   owner: "FS" },
  { id: "03", slug: "personal-shopper", label: "Personal Shopper",   href: "/shop/personal-shopper", icon: ShoppingBag,   app: "shop",   section: "commerce",     category: "Generative AI",   owner: "FS" },
  { id: "11", slug: "recsys",           label: "For You (RecSys)",   href: "/shop/recsys",           icon: Sparkles,      app: "shop",   section: "commerce",     category: "Generative AI",   owner: "FS" },
  { id: "07", slug: "visual-search",    label: "Visual Search",      href: "/shop/visual-search",    icon: ImageIcon,     app: "shop",   section: "commerce",     category: "Computer Vision", owner: "DA" },
  { id: "12", slug: "virtual-tryon",    label: "Virtual Try-On",     href: "/shop/virtual-tryon",    icon: ScanFace,      app: "shop",   section: "commerce",     category: "Computer Vision", owner: "DA" },

  // --- SELLER (seller portal) ---
  { id: "AI", slug: "copilot",          label: "AI Copilot",         href: "/seller/copilot",          icon: Bot,             app: "seller", section: "intelligence", category: "Generative AI",   owner: "TL" },
  { id: "BR", slug: "daily-briefing",   label: "Hôm nay cần làm gì",  href: "/seller/daily-briefing",   icon: ClipboardCheck,  app: "seller", section: "intelligence", category: "Generative AI",   owner: "TL" },
  { id: "01", slug: "review-intelligence", label: "Review Intelligence", href: "/seller/review-intelligence", icon: Star, app: "seller", section: "intelligence", category: "NLP", owner: "DA" },
  { id: "02", slug: "dynamic-pricing",  label: "Dynamic Pricing",    href: "/seller/dynamic-pricing",  icon: Tag,           app: "seller", section: "commerce",     category: "Time Series",     owner: "TL" },
  { id: "04", slug: "churn",            label: "Churn Radar",        href: "/seller/churn",            icon: UserMinus,     app: "seller", section: "intelligence", category: "Behavioral AI",   owner: "TL" },
  { id: "06", slug: "demand-forecast",  label: "Demand Forecast",    href: "/seller/demand-forecast",  icon: TrendingUp,    app: "seller", section: "intelligence", category: "Time Series",     owner: "DA" },
  { id: "10", slug: "return-predict",   label: "Return Predict",     href: "/seller/return-predict",   icon: RotateCcw,     app: "seller", section: "intelligence", category: "Behavioral AI",   owner: "DA" },
  { id: "13", slug: "emotion-sale",     label: "Flash Sale AI",      href: "/seller/emotion-sale",     icon: Heart,         app: "seller", section: "intelligence", category: "Behavioral AI",   owner: "D1" },
  { id: "50", slug: "segmentation",     label: "Customer Segmentation", href: "/seller/segmentation",     icon: Users2,        app: "seller", section: "intelligence", category: "Behavioral AI",   owner: "D1" },
  { id: "15", slug: "regret-predict",   label: "Regret Predict",     href: "/seller/regret-predict",   icon: BadgePercent,  app: "seller", section: "intelligence", category: "Behavioral AI",   owner: "D1" },
  { id: "09", slug: "content-generator",label: "Content Generator",  href: "/seller/content-generator",icon: PenLine,       app: "seller", section: "creator",      category: "Generative AI",   owner: "FS" },
  { id: "17", slug: "seller-coach",     label: "Seller Coach",       href: "/seller/seller-coach",     icon: GraduationCap, app: "seller", section: "creator",      category: "Generative AI",   owner: "FS" },
  { id: "08", slug: "sentiment-alert",  label: "Sentiment Alert",    href: "/seller/sentiment-alert",  icon: MessageSquare, app: "seller", section: "creator",      category: "NLP",              owner: "D1" },
  { id: "16", slug: "supply-chain",     label: "Supply Chain",       href: "/seller/supply-chain",     icon: Truck,         app: "seller", section: "operations",   category: "Time Series",     owner: "TL" },
  { id: "18", slug: "product-knowledge",    label: "Product Knowledge",   href: "/seller/product-knowledge",    icon: Brain,     app: "seller", section: "intelligence", category: "Generative AI", owner: "TL" },
  { id: "19", slug: "market-intelligence",  label: "Market Intelligence", href: "/seller/market-intelligence",  icon: Swords,    app: "seller", section: "intelligence", category: "Generative AI", owner: "TL" },
  { id: "20", slug: "creator-performance",  label: "Creator Performance", href: "/seller/creator-performance",  icon: Users,     app: "seller", section: "creator",      category: "Generative AI", owner: "TL" },
  { id: "21", slug: "decision-intelligence",label: "Decision Intelligence",href:"/seller/decision-intelligence",icon: Lightbulb, app: "seller", section: "intelligence", category: "Generative AI", owner: "TL" },
  { id: "22", slug: "product-graph",       label: "Product Graph",       href: "/seller/product-graph",        icon: Network,   app: "seller", section: "intelligence", category: "Generative AI", owner: "TL" },

  // --- Bonus (Track 1 official brief, not part of the 17-idea brainstorm) ---
  { id: "T1-2", slug: "customer-journey", label: "Customer Journey",  href: "/seller/customer-journey", icon: Route,         app: "seller", section: "intelligence", category: "Behavioral AI",   owner: "FS" },
];

/** Features that have a live, wired panel (vs. a placeholder). */
export const IMPLEMENTED = new Set<string>([
  "personal-shopper", "recsys", "content-generator", "seller-coach",
  "review-intelligence", "dynamic-pricing", "churn", "customer-journey",
  "return-predict", "regret-predict", "sentiment-alert", "supply-chain",
  "emotion-sale", "segmentation",
  "product-knowledge", "market-intelligence", "creator-performance", "decision-intelligence",
  "product-graph",
  "copilot", "daily-briefing",
]);

export function navForApp(app: AppKind): NavItem[] {
  return NAV_ITEMS.filter((i) => i.app === app);
}

export const SUBTITLE: Record<string, string> = {
  "copilot": "Hỏi bất cứ điều gì — agent tự chọn công cụ",
  "daily-briefing": "Việc ưu tiên theo tác động doanh thu",
  "personal-shopper": "Chat mua sắm — RAG retrieval trên catalog, gợi ý sản phẩm phù hợp với nhu cầu & ngân sách.",
  "recsys": "Gợi ý For You theo hồ sơ mua sắm của bạn — độ khớp, khoảng giá và lý do từng sản phẩm.",
  "content-generator": "Sinh tiêu đề + mô tả listing tối ưu cho Shopee · Tiki · TikTok Shop.",
  "seller-coach": "Audit shop theo 5 trục + lộ trình cải thiện 4 tuần.",
  "review-intelligence": "Phân loại cảm xúc (tiếng Việt + tiếng Anh) và phát hiện review giả / seeding cùng lúc, để ưu tiên xử lý và không bị đánh lừa bởi rating ảo.",
  "dynamic-pricing": "Đề xuất giá bán cạnh tranh dựa trên trung vị các sản phẩm cùng danh mục.",
  "churn": "Dự đoán nguy cơ khách hàng rời bỏ (RFM heuristic) + hành động giữ chân đề xuất.",
  "customer-journey": "Mô phỏng hành trình mua sắm (xem / giỏ hàng / mua / livestream) để dự đoán hành động tiếp theo — Đề 2, Track 1.",
  "return-predict": "Dự đoán nguy cơ hoàn trả đơn hàng dựa trên giá trị, giảm giá, và hồ sơ khách hàng.",
  "regret-predict": "Dự đoán khả năng khách hối hận sau khi mua và tự động gửi nội dung trấn an phù hợp.",
  "sentiment-alert": "Kết hợp buzz mạng xã hội với tồn kho để cảnh báo sớm trước khi sản phẩm viral gây hết hàng.",
  "supply-chain": "Cảnh báo sớm gián đoạn chuỗi cung ứng (bão, ùn tắc cảng) theo khu vực kho hàng.",
  "emotion-sale": "Phát hiện khách 'thích nhưng do dự' từ tín hiệu hành vi và kích hoạt ưu đãi cá nhân hoá đúng lúc.",
  "segmentation": "Phân nhóm khách hàng theo hành vi (persona) — dự đoán 1 trong 4 nhóm để target đúng đối tượng.",
  "product-knowledge": "Giải thích vì sao doanh số thay đổi — bóc tách các yếu tố tác động (giá, khuyến mãi, traffic, tồn kho).",
  "market-intelligence": "Phân tích đối thủ & giá — so sánh vị thế và đề xuất mức giá tối ưu không phá sàn lợi nhuận.",
  "creator-performance": "Đo hiệu quả KOL/KOC theo doanh số quy đổi, doanh số/1k view và tỷ lệ tương tác.",
  "decision-intelligence": "Học từ quyết định quá khứ để rút ra hành động nên lặp lại và thời điểm chạy ads tốt nhất.",
  "product-graph": "Quan hệ SKU/brand + sản phẩm tương tự",
};

export const NAV_SECTIONS: Array<{ id: NavItem["section"]; title: string }> = [
  { id: "commerce",    title: "Commerce" },
  { id: "intelligence",title: "Intelligence" },
  { id: "creator",     title: "Creator" },
  { id: "operations",  title: "Operations" },
];

export const SECTION_TITLES: Record<NavItem["section"], string> = {
  commerce: "Commerce",
  intelligence: "Intelligence",
  creator: "Creator",
  operations: "Operations",
  demand: "Demand",
};

/** Quick lookup by slug for the dynamic page fallback. */
export function findBySlug(slug: string): NavItem | undefined {
  return NAV_ITEMS.find((i) => i.slug === slug);
}