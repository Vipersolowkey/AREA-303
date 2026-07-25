"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, RefreshCw, UserMinus, ChevronDown } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  scoreChurn,
  getChurnPortfolio,
  type ChurnResult,
  type ChurnPortfolio,
} from "@/lib/features";
import { cn } from "@/lib/utils";

const TRENDS = [
  { value: "declining", label: "Giảm dần" },
  { value: "stable", label: "Ổn định" },
  { value: "growing", label: "Tăng dần" },
] as const;

const BAND: Record<string, { label: string; cls: string; variant: "success" | "warning" | "danger" }> = {
  low: { label: "Thấp", cls: "text-success", variant: "success" },
  medium: { label: "Trung bình", cls: "text-warning", variant: "warning" },
  high: { label: "Cao", cls: "text-danger", variant: "danger" },
};

function riskBar(band: string) {
  return band === "high" ? "bg-danger" : band === "medium" ? "bg-warning" : "bg-success";
}

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

export function ChurnPanel() {
  // --- primary: auto-loaded portfolio report ---
  const [portfolio, setPortfolio] = useState<ChurnPortfolio | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(false);
    const r = await getChurnPortfolio();
    setLoadError(r === null);
    setPortfolio(r);
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // --- secondary: manual single-case form ---
  const [showManual, setShowManual] = useState(false);
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
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Nguy cơ rời bỏ — toàn bộ khách hàng</CardTitle>
            <p className="mt-1 text-xs text-text-muted">
              {portfolio
                ? `${portfolio.total} khách · ${portfolio.at_risk_count} nguy cơ cao`
                : "Phân tích RFM trên dữ liệu khách hàng thật của shop."}
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
            <p className="text-sm text-text-muted">Không có khách hàng nào cần chú ý.</p>
          ) : null}
        </CardContent>
      </Card>

      {portfolio && portfolio.customers.length > 0 && (
        <div className="space-y-3">
          {portfolio.customers.map((c) => {
            const b = BAND[c.risk_band];
            const pct = Math.round(c.churn_risk * 100);
            return (
              <Card key={c.id}>
                <CardContent className="py-4">
                  <div className="flex items-start gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-medium text-text">{c.customer}</span>
                        <Badge variant={b?.variant ?? "muted"}>{b?.label ?? c.risk_band}</Badge>
                        <span className="mono text-2xs text-text-dim">{c.recency_days} ngày chưa mua lại</span>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {c.drivers.map((d, i) => (
                          <span key={i} className="rounded-full border border-border bg-bg-alt px-2 py-0.5 text-2xs text-text-muted">
                            {d}
                          </span>
                        ))}
                      </div>
                      <div className="mt-2 rounded-md border border-border bg-bg-alt px-3 py-2 text-xs text-text">
                        {c.retention_action}
                      </div>
                    </div>
                    <div className="shrink-0 text-right">
                      <div className={cn("text-2xl font-semibold tracking-tight", b?.cls)}>{pct}%</div>
                      <div className="mt-1 h-1.5 w-20 overflow-hidden rounded-full bg-surface-2">
                        <div className={cn("h-full rounded-full", riskBar(c.risk_band))} style={{ width: `${pct}%` }} />
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
              <p className="mt-1 text-xs text-text-muted">Chỉnh các chỉ số để mô phỏng một khách hàng cụ thể.</p>
            </div>
            <ChevronDown className={cn("h-4 w-4 text-text-muted transition-transform", showManual && "rotate-180")} />
          </button>
        </CardHeader>
        {showManual && (
          <CardContent>
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
          </CardContent>
        )}
      </Card>
    </div>
  );
}
