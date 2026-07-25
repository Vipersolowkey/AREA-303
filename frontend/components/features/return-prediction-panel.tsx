"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, RefreshCw, RotateCcw, ChevronDown } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  scoreReturn,
  getReturnPortfolio,
  type ReturnResult,
  type ReturnPortfolio,
} from "@/lib/features";
import { cn } from "@/lib/utils";

const CATEGORIES = ["Thời trang", "Mỹ phẩm", "Phụ kiện"] as const;

const BAND: Record<string, { label: string; cls: string; variant: "success" | "warning" | "danger" }> = {
  low: { label: "Thấp", cls: "text-success", variant: "success" },
  medium: { label: "Trung bình", cls: "text-warning", variant: "warning" },
  high: { label: "Cao", cls: "text-danger", variant: "danger" },
};

function riskBar(band: string) {
  return band === "high" ? "bg-danger" : band === "medium" ? "bg-warning" : "bg-success";
}

function vnd(n: number) {
  return n.toLocaleString("vi-VN") + "₫";
}

export function ReturnPredictionPanel() {
  // --- primary: auto-loaded portfolio report ---
  const [portfolio, setPortfolio] = useState<ReturnPortfolio | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(false);
    const r = await getReturnPortfolio();
    setLoadError(r === null);
    setPortfolio(r);
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // --- secondary: manual single-case form ---
  const [showManual, setShowManual] = useState(false);
  const [category, setCategory] = useState<(typeof CATEGORIES)[number]>("Thời trang");
  const [price, setPrice] = useState(800000);
  const [newCustomer, setNewCustomer] = useState(true);
  const [sizeRelated, setSizeRelated] = useState(true);
  const [discount, setDiscount] = useState(35);
  const [reviewsRead, setReviewsRead] = useState(0);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ReturnResult | null>(null);
  const [error, setError] = useState(false);

  async function run() {
    if (busy) return;
    setBusy(true);
    setError(false);
    const r = await scoreReturn({
      category, priceVnd: price, isNewCustomer: newCustomer, sizeRelated,
      discountPct: discount, reviewsRead,
    });
    setError(r === null);
    setResult(r);
    setBusy(false);
  }

  const band = result ? BAND[result.risk_band] : null;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Nguy cơ hoàn trả — đơn hàng gần đây</CardTitle>
            <p className="mt-1 text-xs text-text-muted">
              {portfolio
                ? `${portfolio.total} đơn · ${portfolio.high_risk_count} nguy cơ cao`
                : "Ước tính nguy cơ hoàn trả trên các đơn hàng thật trước khi giao."}
            </p>
          </div>
          <Button variant="secondary" size="sm" onClick={load} disabled={loading}>
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            Làm mới
          </Button>
        </CardHeader>
        <CardContent>
          {loadError ? (
            <p className="text-sm text-danger">Không lấy được dữ liệu đơn hàng. Kiểm tra kết nối backend rồi thử lại.</p>
          ) : !portfolio ? (
            <p className="text-sm text-text-muted">{loading ? "Đang phân tích đơn hàng…" : "Chưa có dữ liệu."}</p>
          ) : portfolio.orders.length === 0 ? (
            <p className="text-sm text-text-muted">Không có đơn hàng nào cần chú ý.</p>
          ) : null}
        </CardContent>
      </Card>

      {portfolio && portfolio.orders.length > 0 && (
        <div className="space-y-3">
          {portfolio.orders.map((o) => {
            const b = BAND[o.risk_band];
            const pct = Math.round(o.return_risk * 100);
            return (
              <Card key={o.id}>
                <CardContent className="py-4">
                  <div className="flex items-start gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-medium text-text">{o.product}</span>
                        <Badge variant={b?.variant ?? "muted"}>{b?.label ?? o.risk_band}</Badge>
                        <span className="mono text-2xs text-text-dim">{o.customer} · {vnd(o.order_value_vnd)}</span>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {o.drivers.map((d, i) => (
                          <span key={i} className="rounded-full border border-border bg-bg-alt px-2 py-0.5 text-2xs text-text-muted">
                            {d}
                          </span>
                        ))}
                      </div>
                      <div className="mt-2 rounded-md border border-border bg-bg-alt px-3 py-2 text-xs text-text">
                        {o.action}
                      </div>
                    </div>
                    <div className="shrink-0 text-right">
                      <div className={cn("text-2xl font-semibold tracking-tight", b?.cls)}>{pct}%</div>
                      <div className="mt-1 h-1.5 w-20 overflow-hidden rounded-full bg-surface-2">
                        <div className={cn("h-full rounded-full", riskBar(o.risk_band))} style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Secondary: manual single-case */}
      <Card>
        <CardHeader>
          <button
            type="button"
            onClick={() => setShowManual((v) => !v)}
            className="flex w-full items-center justify-between text-left"
          >
            <div>
              <CardTitle>Thử 1 trường hợp thủ công</CardTitle>
              <p className="mt-1 text-xs text-text-muted">Ước tính nguy cơ hoàn trả cho một đơn hàng cụ thể.</p>
            </div>
            <ChevronDown className={cn("h-4 w-4 text-text-muted transition-transform", showManual && "rotate-180")} />
          </button>
        </CardHeader>
        {showManual && (
          <CardContent>
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
              <div className="space-y-4 lg:col-span-7">
                <div>
                  <label className="mono text-2xs uppercase tracking-wider text-text-dim">Danh mục</label>
                  <div className="mt-1.5 inline-flex overflow-hidden rounded-md border border-border">
                    {CATEGORIES.map((c) => (
                      <button key={c} type="button" onClick={() => setCategory(c)}
                        className={cn("px-3 py-2 text-xs font-medium transition-colors",
                          category === c ? "bg-accent/15 text-accent" : "text-text-muted hover:text-text")}>
                        {c}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="flex items-center justify-between">
                    <label className="mono text-2xs uppercase tracking-wider text-text-dim">Giá trị đơn (₫)</label>
                    <span className="mono text-xs text-text">{price.toLocaleString("vi-VN")}</span>
                  </div>
                  <input type="range" min={0} max={5_000_000} step={50_000} value={price}
                    onChange={(e) => setPrice(Number(e.target.value))} className="mt-1.5 w-full accent-accent" />
                </div>
                <div>
                  <div className="flex items-center justify-between">
                    <label className="mono text-2xs uppercase tracking-wider text-text-dim">Giảm giá (%)</label>
                    <span className="mono text-xs text-text">{discount}%</span>
                  </div>
                  <input type="range" min={0} max={100} value={discount}
                    onChange={(e) => setDiscount(Number(e.target.value))} className="mt-1.5 w-full accent-accent" />
                </div>
                <div>
                  <div className="flex items-center justify-between">
                    <label className="mono text-2xs uppercase tracking-wider text-text-dim">Số review đã đọc trước khi mua</label>
                    <span className="mono text-xs text-text">{reviewsRead}</span>
                  </div>
                  <input type="range" min={0} max={20} value={reviewsRead}
                    onChange={(e) => setReviewsRead(Number(e.target.value))} className="mt-1.5 w-full accent-accent" />
                </div>
                <div className="flex flex-wrap gap-4">
                  <label className="flex items-center gap-2 text-xs text-text-muted">
                    <input type="checkbox" checked={newCustomer} onChange={(e) => setNewCustomer(e.target.checked)} />
                    Khách hàng mới
                  </label>
                  <label className="flex items-center gap-2 text-xs text-text-muted">
                    <input type="checkbox" checked={sizeRelated} onChange={(e) => setSizeRelated(e.target.checked)} />
                    Sản phẩm liên quan size (áo/giày)
                  </label>
                </div>
                <Button onClick={run} disabled={busy} className="w-full">
                  {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}
                  Dự đoán nguy cơ hoàn trả
                </Button>
              </div>

              <div className="lg:col-span-5">
                {error ? (
                  <p className="text-sm text-danger">Không lấy được kết quả. Kiểm tra kết nối backend rồi thử lại.</p>
                ) : !result ? (
                  <p className="text-sm text-text-muted">Bấm Dự đoán để xem nguy cơ hoàn trả.</p>
                ) : (
                  <div className="space-y-4">
                    <div className={cn("text-3xl font-semibold tracking-tight", band?.cls)}>
                      {Math.round(result.return_risk * 100)}% — {band?.label}
                    </div>
                    <ul className="space-y-1">
                      {result.drivers.map((d, i) => (
                        <li key={i} className="text-xs text-text-muted">• {d}</li>
                      ))}
                    </ul>
                    <div className="rounded-md border border-border bg-bg-alt px-3 py-2 text-xs text-text">
                      {result.action}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        )}
      </Card>
    </div>
  );
}
