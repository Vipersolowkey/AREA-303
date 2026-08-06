"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, RefreshCw, UserMinus, RotateCcw, BadgePercent, ChevronDown } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  getRiskPortfolio,
  scoreChurn,
  scoreReturn,
  scoreRegret,
  type RiskPortfolio,
  type RiskBand,
  type ChurnResult,
  type ReturnResult,
  type RegretResult,
} from "@/lib/features";
import { cn } from "@/lib/utils";

const BAND: Record<string, { label: string; cls: string; variant: "success" | "warning" | "danger" }> = {
  low: { label: "Thấp", cls: "text-success", variant: "success" },
  medium: { label: "Trung bình", cls: "text-warning", variant: "warning" },
  high: { label: "Cao", cls: "text-danger", variant: "danger" },
};

function riskBar(band: string) {
  return band === "high" ? "bg-danger" : band === "medium" ? "bg-warning" : "bg-success";
}

function RiskCell({ band }: { band: RiskBand }) {
  if (!band) return <span className="text-2xs text-text-dim">—</span>;
  const b = BAND[band];
  return <Badge variant={b.variant}>{b.label}</Badge>;
}

/* ------------------------------------------------------------------ */
/* Phần 1 — Portfolio gộp: mỗi khách 1 dòng, 3 cột rủi ro              */
/* ------------------------------------------------------------------ */

function RiskPortfolioTable() {
  const [portfolio, setPortfolio] = useState<RiskPortfolio | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(false);
    const r = await getRiskPortfolio();
    setLoadError(r === null);
    setPortfolio(r);
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Customer Risk — toàn bộ khách hàng</CardTitle>
          <p className="mt-1 text-xs text-text-muted">
            {portfolio
              ? `${portfolio.total} khách · ${portfolio.critical_count} khách rủi ro chồng (≥2 loại cao)`
              : "Gộp nguy cơ rời bỏ + hoàn trả + hối hận trên cùng 1 khách."}
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={load} disabled={loading}>
          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
          Làm mới
        </Button>
      </CardHeader>
      <CardContent>
        {loadError ? (
          <p className="text-sm text-danger">Không lấy được dữ liệu khách hàng. Kiểm tra kết nối backend rồi thử lại.</p>
        ) : !portfolio ? (
          <p className="text-sm text-text-muted">{loading ? "Đang phân tích khách hàng…" : "Chưa có dữ liệu."}</p>
        ) : portfolio.customers.length === 0 ? (
          <p className="text-sm text-text-muted">Không có khách hàng nào.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-2xs uppercase tracking-wider text-text-dim">
                  <th className="py-2 pr-3 font-medium">Khách hàng</th>
                  <th className="px-3 py-2 font-medium">Churn</th>
                  <th className="px-3 py-2 font-medium">Return</th>
                  <th className="px-3 py-2 font-medium">Regret</th>
                  <th className="py-2 pl-3 text-right font-medium">Rủi ro chồng</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.customers.map((c) => (
                  <tr key={c.id} className="border-b border-border/50 last:border-0">
                    <td className="py-2.5 pr-3 font-medium text-text">{c.customer}</td>
                    <td className="px-3 py-2.5"><RiskCell band={c.churn_band} /></td>
                    <td className="px-3 py-2.5"><RiskCell band={c.return_band} /></td>
                    <td className="px-3 py-2.5"><RiskCell band={c.regret_band} /></td>
                    <td className="py-2.5 pl-3 text-right">
                      {c.high_risk_count >= 2 ? (
                        <span className="text-xs font-semibold text-danger">{c.high_risk_count} loại cao</span>
                      ) : (
                        <span className="text-2xs text-text-dim">{c.high_risk_count} loại cao</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Phần 2 — 3 tab thử thủ công (giữ nguyên input gốc của từng feature) */
/* ------------------------------------------------------------------ */

const TABS = [
  { key: "churn", label: "Churn" },
  { key: "return", label: "Return Predict" },
  { key: "regret", label: "Regret Predict" },
] as const;
type TabKey = (typeof TABS)[number]["key"];

function NumberField({ label, value, onChange, max }: { label: string; value: number; onChange: (v: number) => void; max: number }) {
  return (
    <div>
      <div className="flex items-center justify-between">
        <label className="mono text-2xs uppercase tracking-wider text-text-dim">{label}</label>
        <span className="mono text-xs text-text">{value}</span>
      </div>
      <input
        type="range"
        min={0}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-1.5 w-full accent-accent"
      />
    </div>
  );
}

const TRENDS = [
  { value: "declining", label: "Giảm dần" },
  { value: "stable", label: "Ổn định" },
  { value: "growing", label: "Tăng dần" },
] as const;

function ChurnTab() {
  const [recency, setRecency] = useState(45);
  const [frequency, setFrequency] = useState(3);
  const [sessions, setSessions] = useState(2);
  const [abandon, setAbandon] = useState(30);
  const [trend, setTrend] = useState<(typeof TRENDS)[number]["value"]>("stable");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ChurnResult | null>(null);
  const [error, setError] = useState(false);

  async function run() {
    if (busy) return;
    setBusy(true);
    setError(false);
    const r = await scoreChurn({
      recencyDays: recency, frequencyOrders: frequency, sessionsLastMonth: sessions,
      cartAbandonRate: abandon / 100, trend,
    });
    setError(r === null);
    setResult(r);
    setBusy(false);
  }

  const band = result ? BAND[result.risk_band] : null;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
      <div className="space-y-4 lg:col-span-7">
        <NumberField label="Ngày chưa mua lại" value={recency} onChange={setRecency} max={200} />
        <NumberField label="Số đơn đã mua" value={frequency} onChange={setFrequency} max={30} />
        <NumberField label="Số phiên truy cập / tháng" value={sessions} onChange={setSessions} max={30} />
        <NumberField label="Tỉ lệ bỏ giỏ hàng (%)" value={abandon} onChange={setAbandon} max={100} />
        <div>
          <label className="mono text-2xs uppercase tracking-wider text-text-dim">Xu hướng hoạt động</label>
          <div className="mt-1.5 inline-flex overflow-hidden rounded-md border border-border">
            {TRENDS.map((t) => (
              <button
                key={t.value}
                type="button"
                onClick={() => setTrend(t.value)}
                className={cn(
                  "px-3 py-2 text-xs font-medium transition-colors",
                  trend === t.value ? "bg-accent/15 text-accent" : "text-text-muted hover:text-text",
                )}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
        <Button onClick={run} disabled={busy} className="w-full">
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <UserMinus className="h-3.5 w-3.5" />}
          Dự đoán churn
        </Button>
      </div>
      <div className="lg:col-span-5">
        {error ? (
          <p className="text-sm text-danger">Không lấy được kết quả. Kiểm tra kết nối backend rồi thử lại.</p>
        ) : !result ? (
          <p className="text-sm text-text-muted">Bấm Dự đoán churn để xem nguy cơ rời bỏ.</p>
        ) : (
          <div className="space-y-4">
            <div>
              <div className={cn("text-3xl font-semibold tracking-tight", band?.cls)}>
                {Math.round(result.churn_risk * 100)}% — {band?.label}
              </div>
              <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-surface-2">
                <div
                  className={cn("h-full rounded-full transition-all", riskBar(result.risk_band))}
                  style={{ width: `${Math.round(result.churn_risk * 100)}%` }}
                />
              </div>
            </div>
            <div>
              <div className="mono text-2xs uppercase tracking-wider text-text-dim">Yếu tố chính</div>
              <ul className="mt-2 space-y-1">
                {result.drivers.map((d, i) => (
                  <li key={i} className="text-xs text-text-muted">• {d}</li>
                ))}
              </ul>
            </div>
            <div className="rounded-md border border-border bg-bg-alt px-3 py-2 text-xs text-text">
              {result.retention_action}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const CATEGORIES = ["Thời trang", "Mỹ phẩm", "Phụ kiện"] as const;

function ReturnTab() {
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
  );
}

function RegretTab() {
  const [decisionTime, setDecisionTime] = useState(30);
  const [revisits, setRevisits] = useState(0);
  const [hour, setHour] = useState(1);
  const [price, setPrice] = useState(1500000);
  const [usedDiscount, setUsedDiscount] = useState(true);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<RegretResult | null>(null);
  const [error, setError] = useState(false);

  async function run() {
    if (busy) return;
    setBusy(true);
    setError(false);
    const r = await scoreRegret({
      decisionTimeSeconds: decisionTime, revisitCount: revisits, purchaseHour: hour,
      priceVnd: price, usedDiscount,
    });
    setError(r === null);
    setResult(r);
    setBusy(false);
  }

  const band = result ? BAND[result.risk_band] : null;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
      <div className="space-y-4 lg:col-span-7">
        <div>
          <div className="flex items-center justify-between">
            <label className="mono text-2xs uppercase tracking-wider text-text-dim">Thời gian quyết định (giây)</label>
            <span className="mono text-xs text-text">{decisionTime}s</span>
          </div>
          <input type="range" min={0} max={600} value={decisionTime}
            onChange={(e) => setDecisionTime(Number(e.target.value))} className="mt-1.5 w-full accent-accent" />
        </div>
        <div>
          <div className="flex items-center justify-between">
            <label className="mono text-2xs uppercase tracking-wider text-text-dim">Số lần xem lại trước khi mua</label>
            <span className="mono text-xs text-text">{revisits}</span>
          </div>
          <input type="range" min={0} max={10} value={revisits}
            onChange={(e) => setRevisits(Number(e.target.value))} className="mt-1.5 w-full accent-accent" />
        </div>
        <div>
          <div className="flex items-center justify-between">
            <label className="mono text-2xs uppercase tracking-wider text-text-dim">Giờ mua (0-23h)</label>
            <span className="mono text-xs text-text">{hour}:00</span>
          </div>
          <input type="range" min={0} max={23} value={hour}
            onChange={(e) => setHour(Number(e.target.value))} className="mt-1.5 w-full accent-accent" />
        </div>
        <div>
          <div className="flex items-center justify-between">
            <label className="mono text-2xs uppercase tracking-wider text-text-dim">Giá trị đơn (₫)</label>
            <span className="mono text-xs text-text">{price.toLocaleString("vi-VN")}</span>
          </div>
          <input type="range" min={0} max={5_000_000} step={50_000} value={price}
            onChange={(e) => setPrice(Number(e.target.value))} className="mt-1.5 w-full accent-accent" />
        </div>
        <label className="flex items-center gap-2 text-xs text-text-muted">
          <input type="checkbox" checked={usedDiscount} onChange={(e) => setUsedDiscount(e.target.checked)} />
          Mua chủ yếu vì có giảm giá
        </label>
        <Button onClick={run} disabled={busy} className="w-full">
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <BadgePercent className="h-3.5 w-3.5" />}
          Dự đoán khả năng hối hận
        </Button>
      </div>
      <div className="lg:col-span-5">
        {error ? (
          <p className="text-sm text-danger">Không lấy được kết quả. Kiểm tra kết nối backend rồi thử lại.</p>
        ) : !result ? (
          <p className="text-sm text-text-muted">Bấm Dự đoán để xem kết quả.</p>
        ) : (
          <div className="space-y-4">
            <div className={cn("text-3xl font-semibold tracking-tight", band?.cls)}>
              {Math.round(result.regret_risk * 100)}% — {band?.label}
            </div>
            <ul className="space-y-1">
              {result.drivers.map((d, i) => (
                <li key={i} className="text-xs text-text-muted">• {d}</li>
              ))}
            </ul>
            <div className="rounded-md border border-border bg-bg-alt px-3 py-2 text-xs text-text">
              <div className="mono mb-1 text-2xs uppercase tracking-wider text-text-dim">Tin nhắn tự động gửi khách</div>
              {result.reassurance_message}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function ManualTabs() {
  const [showManual, setShowManual] = useState(false);
  const [tab, setTab] = useState<TabKey>("churn");

  return (
    <Card>
      <CardHeader>
        <button
          type="button"
          onClick={() => setShowManual((v) => !v)}
          className="flex w-full items-center justify-between text-left"
        >
          <div>
            <CardTitle>Thử 1 trường hợp thủ công</CardTitle>
            <p className="mt-1 text-xs text-text-muted">Chỉnh chỉ số để mô phỏng 1 khách/đơn hàng cụ thể cho từng loại rủi ro.</p>
          </div>
          <ChevronDown className={cn("h-4 w-4 text-text-muted transition-transform", showManual && "rotate-180")} />
        </button>
      </CardHeader>
      {showManual && (
        <CardContent>
          <div className="mb-4 inline-flex overflow-hidden rounded-md border border-border">
            {TABS.map((t) => (
              <button
                key={t.key}
                type="button"
                onClick={() => setTab(t.key)}
                className={cn(
                  "px-3 py-2 text-xs font-medium transition-colors",
                  tab === t.key ? "bg-accent/15 text-accent" : "text-text-muted hover:text-text",
                )}
              >
                {t.label}
              </button>
            ))}
          </div>
          {tab === "churn" && <ChurnTab />}
          {tab === "return" && <ReturnTab />}
          {tab === "regret" && <RegretTab />}
        </CardContent>
      )}
    </Card>
  );
}

export function CustomerRiskPanel() {
  return (
    <div className="space-y-4">
      <RiskPortfolioTable />
      <ManualTabs />
    </div>
  );
}
