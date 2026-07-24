"use client";

import { useState } from "react";
import { Search, MousePointerClick, Eye, ShoppingCart, CreditCard, Radio, Loader2, Sparkles, X, ArrowRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ProductCard } from "@/components/genai/product-card";
import { analyzeJourney, type JourneyEventInput, type JourneyResultMapped } from "@/lib/features";
import { cn } from "@/lib/utils";

const CATEGORIES = ["Thời trang", "Mỹ phẩm", "Phụ kiện"] as const;

const EVENT_TYPES = [
  { type: "search", label: "Tìm kiếm", icon: Search },
  { type: "click", label: "Click", icon: MousePointerClick },
  { type: "view", label: "Xem sản phẩm", icon: Eye },
  { type: "cart", label: "Thêm vào giỏ", icon: ShoppingCart },
  { type: "purchase", label: "Mua hàng", icon: CreditCard },
  { type: "livestream", label: "Xem livestream", icon: Radio },
] as const;

const NEXT_ACTION_STYLE: Record<string, { cls: string }> = {
  checkout: { cls: "text-success" },
  add_to_cart: { cls: "text-accent" },
  compare: { cls: "text-warning" },
  keep_browsing: { cls: "text-text" },
  leave: { cls: "text-danger" },
};

const FUNNEL_LABEL: Record<string, string> = {
  awareness: "Nhận biết", consideration: "Cân nhắc", intent: "Có ý định", purchase: "Đã mua",
};
const FUNNEL_ORDER = ["awareness", "consideration", "intent", "purchase"];

type Result = JourneyResultMapped;

export function CustomerJourneyPanel() {
  const [category, setCategory] = useState<(typeof CATEGORIES)[number]>("Mỹ phẩm");
  const [events, setEvents] = useState<JourneyEventInput[]>([
    { type: "search", category: "Mỹ phẩm", query: "serum vitamin c" },
    { type: "click", category: "Mỹ phẩm" },
    { type: "view", category: "Mỹ phẩm" },
    { type: "livestream", category: "Mỹ phẩm" },
    { type: "cart", category: "Mỹ phẩm" },
  ]);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState(false);

  function addEvent(type: JourneyEventInput["type"]) {
    setEvents((prev) => [...prev, { type, category }]);
    setResult(null);
    setError(false);
  }
  function removeEvent(i: number) {
    setEvents((prev) => prev.filter((_, idx) => idx !== i));
    setResult(null);
    setError(false);
  }

  async function run() {
    if (busy || !events.length) return;
    setBusy(true);
    setError(false);
    const r = await analyzeJourney(events);
    setError(r === null);
    setResult(r);
    setBusy(false);
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Mô phỏng phiên mua sắm</CardTitle>
            <p className="mt-1 text-xs text-text-muted">
              Thêm sự kiện (tìm kiếm / click / xem / giỏ hàng / mua / livestream) để mô phỏng hành trình và dự đoán bước tiếp theo.
            </p>
          </div>
          <Badge variant="muted">session simulator</Badge>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="mono text-2xs uppercase tracking-wider text-text-dim">Danh mục của sự kiện tiếp theo</label>
            <div className="mt-1.5 inline-flex overflow-hidden rounded-md border border-border">
              {CATEGORIES.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setCategory(c)}
                  className={cn(
                    "px-3 py-2 text-xs font-medium transition-colors",
                    category === c ? "bg-accent/15 text-accent" : "text-text-muted hover:text-text",
                  )}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            {EVENT_TYPES.map((e) => (
              <Button key={e.type} variant="secondary" size="sm" onClick={() => addEvent(e.type)}>
                <e.icon className="h-3.5 w-3.5" /> + {e.label}
              </Button>
            ))}
          </div>

          <div>
            <label className="mono text-2xs uppercase tracking-wider text-text-dim">
              Timeline phiên ({events.length} sự kiện)
            </label>
            <div className="mt-2 flex min-h-[44px] flex-wrap gap-1.5 rounded-md border border-border bg-bg-alt p-2">
              {events.length === 0 && (
                <span className="text-xs text-text-dim">Chưa có sự kiện — bấm nút phía trên để thêm.</span>
              )}
              {events.map((e, i) => {
                const meta = EVENT_TYPES.find((t) => t.type === e.type)!;
                return (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-2.5 py-1 text-2xs text-text"
                  >
                    <meta.icon className="h-3 w-3" />
                    {meta.label}
                    {e.query && <span className="text-text-dim">· &ldquo;{e.query}&rdquo;</span>}
                    {e.category && <span className="text-text-dim">· {e.category}</span>}
                    <button onClick={() => removeEvent(i)} className="text-text-dim hover:text-danger">
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                );
              })}
            </div>
          </div>

          <Button onClick={run} disabled={busy || !events.length} className="w-full">
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
            Phân tích phiên
          </Button>
        </CardContent>
      </Card>

      {error && (
        <p className="text-sm text-danger">Không lấy được kết quả. Kiểm tra kết nối backend rồi thử lại.</p>
      )}

      {result && (
        <Card>
          <CardHeader>
            <CardTitle>Hành động tiếp theo dự đoán</CardTitle>
            <Badge variant="muted">next-action prediction</Badge>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <ArrowRight className={cn("h-6 w-6", NEXT_ACTION_STYLE[result.predicted_next_action]?.cls)} />
              <span className={cn("text-2xl font-semibold tracking-tight", NEXT_ACTION_STYLE[result.predicted_next_action]?.cls)}>
                {result.next_action_label}
              </span>
            </div>

            {/* Funnel stage tracker */}
            <div className="flex items-center gap-1">
              {FUNNEL_ORDER.map((s, i) => {
                const active = FUNNEL_ORDER.indexOf(result.funnel_stage) >= i;
                return (
                  <div key={s} className="flex flex-1 items-center gap-1">
                    <div className="flex-1">
                      <div className={cn("h-1.5 rounded-full", active ? "bg-accent" : "bg-surface-2")} />
                      <div className={cn("mono mt-1 text-2xs", active ? "text-text" : "text-text-dim")}>{FUNNEL_LABEL[s]}</div>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="rounded-md border border-border bg-bg-alt px-3 py-2">
                <div className="mono text-2xs uppercase tracking-wider text-text-dim">Điểm tương tác</div>
                <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-surface-2">
                  <div className="h-full rounded-full bg-accent" style={{ width: `${Math.round(result.engagement_score * 100)}%` }} />
                </div>
                <div className="mono mt-1 text-2xs text-text-muted">{Math.round(result.engagement_score * 100)}%</div>
              </div>
              <div className="rounded-md border border-accent/30 bg-accent/5 px-3 py-2">
                <div className="mono text-2xs uppercase tracking-wider text-accent">Gợi ý cho seller (nudge)</div>
                <p className="mt-1 text-xs text-text">{result.nudge}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {result && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Card>
            <CardHeader><CardTitle>Khả năng mua hay rời đi?</CardTitle></CardHeader>
            <CardContent>
              <div className={cn("text-2xl font-semibold", result.will_purchase ? "text-success" : "text-danger")}>
                {result.will_purchase ? "Có khả năng MUA" : "Có khả năng RỜI ĐI"}
              </div>
              <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-surface-2">
                <div
                  className={cn("h-full rounded-full", result.will_purchase ? "bg-success" : "bg-danger")}
                  style={{ width: `${Math.round(result.purchase_probability * 100)}%` }}
                />
              </div>
              <div className="mono mt-1 text-xs text-text-muted">
                {Math.round(result.purchase_probability * 100)}% xác suất mua
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Đang quan tâm danh mục nào?</CardTitle></CardHeader>
            <CardContent>
              <div className="text-xl font-semibold text-text">{result.top_category ?? "Chưa rõ"}</div>
              <div className="mt-3 space-y-1.5">
                {Object.entries(result.category_breakdown).map(([cat, n]) => (
                  <div key={cat} className="flex items-center gap-2 text-xs">
                    <span className="w-20 truncate text-text-muted">{cat}</span>
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2">
                      <div className="h-full rounded-full bg-accent" style={{ width: `${Math.min(100, n * 20)}%` }} />
                    </div>
                    <span className="mono text-text-dim">{n}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Vì sao?</CardTitle></CardHeader>
            <CardContent>
              <p className="text-sm text-text-muted">{result.reasoning}</p>
            </CardContent>
          </Card>
        </div>
      )}

      {result && result.recommended_products.length > 0 && (
        <Card>
          <CardHeader><CardTitle>Top sản phẩm nên đề xuất</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {result.recommended_products.map((p) => (
                <ProductCard key={p.id} product={p} similarity={p.similarity} />
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
