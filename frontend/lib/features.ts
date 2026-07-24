/**
 * Feature API layer — connects the GenAI panels to the FastAPI backend
 * (endpoints under /api/v1). Every call maps the backend snake_case shapes to
 * the frontend camelCase types and falls back to the supplied mock data when the
 * backend is unreachable or NEXT_PUBLIC_DEMO_MODE=true — so the UI never breaks.
 */
import { api } from "@/lib/api";
import type {
  Product,
  Recommendation,
  ContentVariant,
  AuditStep,
  RoadmapWeek,
} from "@/lib/mock-data";

const DEMO = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

// --- backend wire shapes -------------------------------------------------
type BackendProduct = {
  id: string; name: string; brand: string; category: string; platform: string;
  price_vnd: number; rating: number; reviews: number; similarity: number;
  image_hue?: number; image_url?: string | null;
};
type BackendRec = Omit<BackendProduct, "id" | "image_hue"> & { product_id: string; reason: string };
type BackendVariant = {
  platform: string; title: string; body: string; predicted_ctr: number; rationale: string;
};

function mapProduct(p: BackendProduct): Product {
  return {
    id: p.id, name: p.name, brand: p.brand,
    category: p.category as Product["category"],
    platform: p.platform as Product["platform"],
    priceVnd: p.price_vnd, rating: p.rating, reviews: p.reviews,
    similarity: p.similarity, imageHue: p.image_hue ?? 215,
    imageUrl: p.image_url ?? "", description: "",
  };
}

async function post<T>(path: string, body: unknown): Promise<T | null> {
  if (DEMO) return null;
  try {
    const env = await api.post<T>(path, body);
    return env.data as T;
  } catch {
    return null;
  }
}

async function get<T>(path: string): Promise<T | null> {
  if (DEMO) return null;
  try {
    const env = await api.get<T>(path);
    return env.data as T;
  } catch {
    return null;
  }
}

// --- #03 Personal Shopper -------------------------------------------------
export async function shopperProducts(
  query: string, topK: number, fallback: Product[],
): Promise<{ products: Product[]; live: boolean }> {
  const data = await get<{ products: BackendProduct[] }>(
    `/personal-shopper/products?query=${encodeURIComponent(query)}&top_k=${topK}`,
  );
  if (!data?.products?.length) return { products: fallback, live: false };
  return { products: data.products.map(mapProduct), live: true };
}

// --- #11 Recsys -----------------------------------------------------------
export async function recsysRecommend(
  signals: Record<string, string>, topK: number, fallback: Recommendation[],
): Promise<{ items: Recommendation[]; live: boolean; model?: string }> {
  const data = await post<{ items: BackendRec[]; model: string }>(
    "/recsys/", { signals, top_k: topK },
  );
  if (!data?.items?.length) return { items: fallback, live: false };
  const items = data.items.map((r) => ({
    ...mapProduct({ ...r, id: r.product_id }), reason: r.reason,
  }));
  return { items, live: true, model: data.model };
}

// --- #09 Content Generator ------------------------------------------------
export async function contentGenerate(
  productName: string, features: string, platforms: string[], fallback: ContentVariant[],
): Promise<{ variants: ContentVariant[]; live: boolean }> {
  const data = await post<{ variants: BackendVariant[] }>(
    "/content-generator/", { product_name: productName, features, platforms },
  );
  if (!data?.variants?.length) return { variants: fallback, live: false };
  const variants = data.variants.map((v) => ({
    platform: v.platform as ContentVariant["platform"],
    title: v.title, body: v.body, predictedCtr: v.predicted_ctr, rationale: v.rationale,
  }));
  return { variants, live: true };
}

// --- #01 Review Sentiment -------------------------------------------------
export type Sentiment = { sentiment: "positive" | "neutral" | "negative"; confidence: number; reason: string };

export async function analyzeSentiment(text: string, rating?: number): Promise<Sentiment | null> {
  return post<Sentiment>("/review-sentiment/", { text, rating: rating ?? null });
}

// --- #05 Fake Review ------------------------------------------------------
export type FakeVerdict = { is_fake: boolean; confidence: number; signals: string[]; reason: string };

export async function detectFake(text: string, rating?: number, category?: string): Promise<FakeVerdict | null> {
  return post<FakeVerdict>("/fake-review/", { text, rating: rating ?? null, category: category ?? null });
}

// --- #17 Seller Coach -----------------------------------------------------
export async function sellerCoach(
  fallback: { overall: number; audit: AuditStep[]; roadmap: RoadmapWeek[] },
): Promise<{ overall: number; audit: AuditStep[]; roadmap: RoadmapWeek[]; live: boolean }> {
  const data = await post<{ overall: number; audit: AuditStep[]; roadmap: RoadmapWeek[] }>(
    "/seller-coach/", {},
  );
  if (!data?.audit?.length) return { ...fallback, live: false };
  return { overall: data.overall, audit: data.audit, roadmap: data.roadmap, live: true };
}

// --- #02 Dynamic Pricing ----------------------------------------------------
export type PricingResult = {
  recommended_price: number; low: number; high: number;
  category_median: number; sample_size: number; rationale: string;
};

export async function recommendPrice(
  productName: string, category: string, currentPrice?: number,
): Promise<PricingResult | null> {
  return post<PricingResult>("/dynamic-pricing/", {
    product_name: productName, category, current_price: currentPrice ?? null,
  });
}

// --- #04 Churn Prediction ---------------------------------------------------
export type ChurnResult = {
  churn_risk: number; risk_band: "low" | "medium" | "high";
  drivers: string[]; retention_action: string;
};

export async function scoreChurn(input: {
  recencyDays: number; frequencyOrders: number; sessionsLastMonth: number;
  cartAbandonRate: number; trend: "declining" | "stable" | "growing";
}): Promise<ChurnResult | null> {
  return post<ChurnResult>("/churn/", {
    recency_days: input.recencyDays, frequency_orders: input.frequencyOrders,
    sessions_last_month: input.sessionsLastMonth, cart_abandon_rate: input.cartAbandonRate,
    trend: input.trend,
  });
}

// --- Customer Journey Intelligence (Track 1, Đề 2 — bonus) ----------------
export type JourneyEventType = "search" | "click" | "view" | "cart" | "purchase" | "livestream";
export type JourneyEventInput = { type: JourneyEventType; category?: string; query?: string };
export type NextAction = "checkout" | "add_to_cart" | "compare" | "keep_browsing" | "leave";
export type FunnelStage = "awareness" | "consideration" | "intent" | "purchase";
export type JourneyResult = {
  will_purchase: boolean; purchase_probability: number;
  predicted_next_action: NextAction; next_action_label: string;
  funnel_stage: FunnelStage; engagement_score: number; nudge: string;
  top_category: string | null; category_breakdown: Record<string, number>;
  recommended_products: BackendProduct[]; reasoning: string;
};
export type JourneyResultMapped = Omit<JourneyResult, "recommended_products"> & { recommended_products: Product[] };

export async function analyzeJourney(events: JourneyEventInput[]): Promise<JourneyResultMapped | null> {
  const data = await post<JourneyResult>("/journey/", { events });
  if (!data) return null;
  return { ...data, recommended_products: data.recommended_products.map(mapProduct) };
}

// --- #10 Return/Refund Prediction ------------------------------------------
export type ReturnResult = { return_risk: number; risk_band: "low" | "medium" | "high"; drivers: string[]; action: string };

export async function scoreReturn(input: {
  category: string; priceVnd: number; isNewCustomer: boolean; sizeRelated: boolean;
  discountPct: number; reviewsRead: number;
}): Promise<ReturnResult | null> {
  return post<ReturnResult>("/return-prediction/", {
    category: input.category, price_vnd: input.priceVnd, is_new_customer: input.isNewCustomer,
    size_related: input.sizeRelated, discount_pct: input.discountPct, reviews_read: input.reviewsRead,
  });
}

// --- #15 Post-purchase Regret Predictor ------------------------------------
export type RegretResult = {
  regret_risk: number; risk_band: "low" | "medium" | "high"; drivers: string[]; reassurance_message: string;
};

export async function scoreRegret(input: {
  decisionTimeSeconds: number; revisitCount: number; purchaseHour: number; priceVnd: number; usedDiscount: boolean;
}): Promise<RegretResult | null> {
  return post<RegretResult>("/regret/", {
    decision_time_seconds: input.decisionTimeSeconds, revisit_count: input.revisitCount,
    purchase_hour: input.purchaseHour, price_vnd: input.priceVnd, used_discount: input.usedDiscount,
  });
}

// --- #08 Sentiment-driven Inventory Alert ----------------------------------
export type InventoryAlertResult = {
  is_trending: boolean; trend_score: number; days_of_stock_left: number;
  alert_level: "none" | "watch" | "urgent"; recommended_restock_qty: number; reason: string;
};

export async function checkInventoryAlert(input: {
  productName: string; socialMentions7d: number; socialSentiment: number; currentStock: number; avgDailySales: number;
}): Promise<InventoryAlertResult | null> {
  return post<InventoryAlertResult>("/inventory-alert/", {
    product_name: input.productName, social_mentions_7d: input.socialMentions7d,
    social_sentiment: input.socialSentiment, current_stock: input.currentStock, avg_daily_sales: input.avgDailySales,
  });
}

// --- #16 Supply Chain Disruption Early Warning -----------------------------
export type DisruptionAlert = {
  title: string; region: string; severity: "low" | "medium" | "high";
  estimated_delay_days: number; contingency: string;
};
export type SupplyChainResult = { alerts: DisruptionAlert[]; overall_risk: "low" | "medium" | "high"; summary: string };

export async function checkSupplyChain(region: string, category: string): Promise<SupplyChainResult | null> {
  return post<SupplyChainResult>("/supply-chain/", { region, category });
}

// --- #14 AI Negotiation Bot cho B2B -----------------------------------------
export type NegotiationResult = {
  decision: "accept" | "counter" | "reject"; counter_price_vnd: number | null; message: string; round: number;
};

export async function negotiate(input: {
  productName: string; listPriceVnd: number; minPriceVnd: number; buyerOfferVnd: number; round: number;
}): Promise<NegotiationResult | null> {
  return post<NegotiationResult>("/negotiation/", {
    product_name: input.productName, list_price_vnd: input.listPriceVnd, min_price_vnd: input.minPriceVnd,
    buyer_offer_vnd: input.buyerOfferVnd, round: input.round,
  });
}

// --- Shared category type (Thời trang / Mỹ phẩm / Phụ kiện) ----------------
export type Category = "Thời trang" | "Mỹ phẩm" | "Phụ kiện";

// --- Product Knowledge — vì sao doanh số thay đổi --------------------------
export type ProductKnowledgeResult = {
  sales_change_pct: number;
  direction: "up" | "down" | "flat";
  drivers: { factor: string; direction: "up" | "down"; impact: "low" | "medium" | "high" }[];
  promotion_effectiveness: string;
  explanation: string;
};

export async function analyzeProductKnowledge(input: {
  product: string;
  category: Category;
  sales_prev: number;
  sales_curr: number;
  price_change_pct?: number;
  promotion_active?: boolean;
  competitor_promo?: boolean;
  stock_status?: "ok" | "low" | "out";
  traffic_change_pct?: number;
}): Promise<ProductKnowledgeResult | null> {
  return post<ProductKnowledgeResult>("/product-knowledge/", input);
}

// --- Market Intelligence — phân tích đối thủ & giá -------------------------
export type MarketIntelligenceResult = {
  position: "cheaper" | "parity" | "pricier";
  recommended_action: "hold" | "match_price" | "undercut" | "differentiate";
  recommended_price_vnd: number;
  price_floor_vnd: number;
  margin_pct_at_recommended: number;
  competitor_effective_price_vnd: number;
  reasoning: string;
};

export async function analyzeMarketIntelligence(input: {
  our_product: string;
  category: Category;
  our_price_vnd: number;
  our_cost_vnd: number;
  competitor_name: string;
  competitor_price_vnd: number;
  competitor_discount_pct?: number;
  min_margin_pct?: number;
}): Promise<MarketIntelligenceResult | null> {
  return post<MarketIntelligenceResult>("/market-intelligence/", input);
}

// --- Creator Performance — hiệu quả KOL/KOC --------------------------------
export type CreatorItemInput = {
  creator: string;
  content_type: "video" | "livestream" | "post";
  views: number;
  engagements: number;
  attributed_sales_vnd: number;
};
export type CreatorPerformanceResult = {
  best_content_type: "video" | "livestream" | "post";
  recommended_creator: string;
  top_creators: {
    creator: string;
    content_type: string;
    total_sales_vnd: number;
    sales_per_1k_views: number;
    engagement_rate_pct: number;
  }[];
  insight: string;
};

export async function analyzeCreatorPerformance(input: {
  campaign_category: Category;
  items: CreatorItemInput[];
}): Promise<CreatorPerformanceResult | null> {
  return post<CreatorPerformanceResult>("/creator-performance/", input);
}

// --- Decision Intelligence — học từ quyết định quá khứ ----------------------
export type DecisionInput = {
  kind: "price" | "promo" | "ad" | "inventory";
  description: string;
  metric: "ROAS" | "sales_lift_pct" | "margin_pct" | "sell_through_pct";
  value: number;
  month?: number | null;
};
export type DecisionIntelligenceResult = {
  best_decision: { kind: string; description: string; metric: string; value: number };
  best_ad_month: number | null;
  recommended_action: string;
  reasoning: string;
};

export async function analyzeDecisionIntelligence(input: {
  situation: string;
  category: Category;
  decisions: DecisionInput[];
}): Promise<DecisionIntelligenceResult | null> {
  return post<DecisionIntelligenceResult>("/decision-intelligence/", input);
}

// --- AI Copilot — hỏi bất cứ điều gì, agent tự chọn công cụ ----------------
export type CopilotResult = {
  answer: string;
  skill_used: string;
  entity: string | null;
  impact_vnd: number | null;
  tool_result: Record<string, unknown>;
};

export async function askCopilot(question: string): Promise<CopilotResult | null> {
  return post<CopilotResult>("/copilot/ask", { question });
}

// --- AI Copilot Agent — multi-step, tự gọi nhiều công cụ --------------------
export type AgentStep = { tool: string; args: Record<string, unknown>; summary: string };
export type CopilotAgentResult = { answer: string; tools_used: string[]; steps: AgentStep[]; multi_step: boolean };

export async function askAgent(
  question: string,
  history: { role: "user" | "assistant"; content: string }[],
): Promise<CopilotAgentResult | null> {
  return post<CopilotAgentResult>("/copilot/agent", { question, history });
}

// --- Product Graph — quan hệ SKU/brand + sản phẩm tương tự (Đề 1) ----------
export type PGDriver = { factor: string; direction: "up" | "down"; impact: "low" | "medium" | "high" };
export type PGSimilar = { id: string; sku: string; name: string; brand: string; price_vnd: number; relation: string };
export type ProductGraphResult = {
  found: boolean;
  product: { id: string; sku: string; name: string; brand: string; category: string; price_vnd: number; cost_vnd: number; trend: string; stock_status: string } | null;
  sales: { sales_prev: number; sales_curr: number; change_pct: number; direction: "up" | "down" | "flat"; drivers: PGDriver[] } | null;
  similar_products: PGSimilar[];
  brand_siblings: string[];
  category_peers: number;
  promotions: { name: string; discount_pct: number; lift_pct: number; effectiveness: string }[];
  summary: string;
};

export async function exploreProductGraph(query: string): Promise<ProductGraphResult | null> {
  return post<ProductGraphResult>("/product-knowledge/graph", { query });
}

// --- Daily Briefing — hôm nay cần làm gì -----------------------------------
export type BriefingAction = {
  kind: "restock" | "reduce" | "reprice" | "investigate" | "promote";
  title: string;
  product: string;
  priority: "high" | "medium" | "low";
  impact_vnd: number;
  detail: string;
};
export type BriefingResult = {
  summary: string;
  total_impact_vnd: number;
  actions: BriefingAction[];
};

export async function getBriefing(): Promise<BriefingResult | null> {
  return get<BriefingResult>("/copilot/briefing");
}

// --- #13 Emotion-Aware Flash Sale Optimizer --------------------------------
export type FlashSaleResult = {
  hesitating: boolean; hesitation_score: number; trigger_now: boolean;
  suggested_discount_pct: number; message: string;
};

export async function analyzeHesitation(input: {
  dwellTimeSeconds: number; scrollDepthPct: number; revisitCount: number; cartOpenedNoPurchase: boolean; priceVnd: number;
}): Promise<FlashSaleResult | null> {
  return post<FlashSaleResult>("/flash-sale/", {
    dwell_time_seconds: input.dwellTimeSeconds, scroll_depth_pct: input.scrollDepthPct,
    revisit_count: input.revisitCount, cart_opened_no_purchase: input.cartOpenedNoPurchase, price_vnd: input.priceVnd,
  });
}
