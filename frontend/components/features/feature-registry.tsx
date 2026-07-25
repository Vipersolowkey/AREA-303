"use client";

import type { ComponentType } from "react";
import { PersonalShopperPanel } from "./personal-shopper-panel";
import { RecsysPanel } from "./recsys-panel";
import { ContentGeneratorPanel } from "./content-generator-panel";
import { SellerCoachPanel } from "./seller-coach-panel";
import { ReviewSentimentPanel } from "./review-sentiment-panel";
import { FakeReviewPanel } from "./fake-review-panel";
import { DynamicPricingPanel } from "./dynamic-pricing-panel";
import { ChurnPanel } from "./churn-panel";
import { CustomerJourneyPanel } from "./customer-journey-panel";
import { ReturnPredictionPanel } from "./return-prediction-panel";
import { RegretPredictorPanel } from "./regret-predictor-panel";
import { InventoryAlertPanel } from "./inventory-alert-panel";
import { SupplyChainPanel } from "./supply-chain-panel";
import { NegotiationPanel } from "./negotiation-panel";
import { FlashSalePanel } from "./flash-sale-panel";
import { ProductKnowledgePanel } from "./product-knowledge-panel";
import { MarketIntelligencePanel } from "./market-intelligence-panel";
import { CreatorPerformancePanel } from "./creator-performance-panel";
import { DecisionIntelligencePanel } from "./decision-intelligence-panel";
import { ProductGraphPanel } from "./product-graph-panel";
import { CopilotPanel } from "./copilot-panel";
import { DailyBriefingPanel } from "./daily-briefing-panel";

/** Maps a feature slug to its live panel. Keep in sync with IMPLEMENTED in lib/nav. */
const PANELS: Record<string, ComponentType> = {
  copilot: CopilotPanel,
  "daily-briefing": DailyBriefingPanel,
  "personal-shopper": PersonalShopperPanel,
  recsys: RecsysPanel,
  "content-generator": ContentGeneratorPanel,
  "seller-coach": SellerCoachPanel,
  "review-analyzer": ReviewSentimentPanel,
  "fake-review": FakeReviewPanel,
  "dynamic-pricing": DynamicPricingPanel,
  churn: ChurnPanel,
  "customer-journey": CustomerJourneyPanel,
  "return-predict": ReturnPredictionPanel,
  "regret-predict": RegretPredictorPanel,
  "sentiment-alert": InventoryAlertPanel,
  "supply-chain": SupplyChainPanel,
  negotiation: NegotiationPanel,
  "emotion-sale": FlashSalePanel,
  "product-knowledge": ProductKnowledgePanel,
  "market-intelligence": MarketIntelligencePanel,
  "creator-performance": CreatorPerformancePanel,
  "decision-intelligence": DecisionIntelligencePanel,
  "product-graph": ProductGraphPanel,
};

export function FeaturePanel({ slug }: { slug: string }) {
  const Panel = PANELS[slug];
  return Panel ? <Panel /> : null;
}
