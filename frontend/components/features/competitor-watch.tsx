"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  ExternalLink,
  Loader2,
  Plus,
  RefreshCw,
  Sparkles,
  Trash2,
  TrendingUp,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  addTrackedCompetitor,
  collectCompetitorsNow,
  getCompetitorInsight,
  getTrackedCompetitors,
  removeTrackedCompetitor,
  type CompetitorInsight,
  type SalesSource,
  type TrackedCompetitor,
} from "@/lib/features";
import { ApiClientError } from "@/lib/api";
import { cn } from "@/lib/utils";

function fmtNum(v: number | null): string {
  return v === null || v === undefined ? "—" : v.toLocaleString("vi-VN");
}

/** Round to a unit a person reads at a glance, not to the dong. */
function fmtVnd(v: number | null): string {
  if (!v) return "—";
  if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)} tỷ₫`;
  if (v >= 1_000_000) return `${Math.round(v / 1_000_000)} triệu₫`;
  return `${v.toLocaleString("vi-VN")}₫`;
}

const SOURCE_LABEL: Record<SalesSource, string> = {
  vendor: "dữ liệu mua",
  session: "session Shopee",
};

/**
 * `suffix` is "%" for percent changes and "" for an absolute delta (rating,
 * where a percentage of a 4.9 average would say nothing).
 */
function Trend({ value, suffix = "%" }: { value: number | null; suffix?: string }) {
  if (value === null) {
    return <span className="text-2xs text-text-dim">chưa đủ dữ liệu</span>;
  }
  if (value === 0) return <span className="text-2xs text-text-dim">đi ngang</span>;
  const up = value > 0;
  return (
    <span
      className={cn(
        "mono inline-flex items-center gap-0.5 text-xs font-semibold",
        up ? "text-success" : "text-danger",
      )}
    >
      {up ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
      {Math.abs(value)}
      {suffix}
    </span>
  );
}

export function CompetitorWatch() {
  const [rows, setRows] = useState<TrackedCompetitor[] | null>(null);
  const [insight, setInsight] = useState<CompetitorInsight | null>(null);
  const [url, setUrl] = useState("");
  const [adding, setAdding] = useState(false);
  const [collecting, setCollecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [list, ins] = await Promise.all([
      getTrackedCompetitors(),
      getCompetitorInsight(),
    ]);
    setRows(list);
    setInsight(ins);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim() || adding) return;
    setAdding(true);
    setError(null);
    setNote(null);
    try {
      const added = await addTrackedCompetitor(url.trim());
      setUrl("");
      // The backend takes a first reading immediately, so surface its outcome
      // rather than leaving the row looking silently empty.
      if (added.last_attempt && !added.last_attempt.ok) {
        setNote(
          `Đã thêm ${added.display_name ?? "cửa hàng"}, nhưng lần thu thập đầu chưa thành công: ` +
            (added.last_attempt.error ?? "không rõ lý do"),
        );
      }
      await load();
    } catch (err) {
      setError(
        err instanceof ApiClientError
          ? (err.envelope.error?.message ?? "Không thêm được cửa hàng.")
          : "Không kết nối được máy chủ.",
      );
    } finally {
      setAdding(false);
    }
  }

  async function collect() {
    setCollecting(true);
    setError(null);
    setNote(null);
    const run = await collectCompetitorsNow();
    if (run) {
      setNote(
        `Đã thu thập ${run.attempted} cửa hàng: ${run.succeeded} thành công, ${run.failed} thất bại.` +
          (run.errors.length ? ` Lý do thất bại: ${run.errors[0]}` : "") +
          (run.notes.length ? ` Ghi chú: ${run.notes[0]}` : ""),
      );
    } else {
      setError("Không chạy được thu thập.");
    }
    await load();
    setCollecting(false);
  }

  async function remove(id: number) {
    if (await removeTrackedCompetitor(id)) await load();
  }

  return (
    <div className="space-y-4">
      {/* Paste a shop URL */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Theo dõi đối thủ</CardTitle>
            <p className="mt-1 text-xs text-text-muted">
              Dán link cửa hàng Shopee. Mỗi lần thu thập lưu lại một mốc số liệu —
              xu hướng chỉ xuất hiện từ lần thu thập thứ hai.
            </p>
          </div>
          <Button variant="secondary" size="sm" onClick={collect} disabled={collecting}>
            {collecting ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )}
            Thu thập ngay
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          <form onSubmit={add} className="flex flex-col gap-2 sm:flex-row">
            <Input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://shopee.vn/yody.official hoặc https://shopee.vn/shop/123456789"
            />
            <Button type="submit" disabled={adding || !url.trim()}>
              {adding ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
              Thêm
            </Button>
          </form>

          {error && (
            <p className="rounded-xl border border-danger/30 bg-danger/5 px-3 py-2 text-xs text-danger">
              {error}
            </p>
          )}
          {note && (
            <p className="rounded-xl border border-warning/30 bg-warning/5 px-3 py-2 text-xs text-warning">
              {note}
            </p>
          )}

          <div className="space-y-2 rounded-xl border border-border bg-bg-alt p-3">
            <p className="text-2xs text-text-muted">
              <span className="font-semibold">Lấy được ngay, không cần cấu hình:</span>{" "}
              tên shop, follower, điểm đánh giá, số sản phẩm — và xu hướng của chúng.
            </p>
            <p className="flex items-start gap-1.5 text-2xs text-text-muted">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" />
              <span>
                <span className="font-semibold">
                  Doanh thu / đã bán / bán chạy / khuyến mãi cần một nguồn riêng.
                </span>{" "}
                Shopee chỉ trả các số này cho phiên đã đăng nhập — mọi endpoint khác
                trả <span className="mono">error 90309999</span>, kể cả khi gọi từ
                browser thật. Hai cách bật:
              </span>
            </p>
            <ul className="space-y-1 pl-5 text-2xs text-text-dim">
              <li>
                <span className="font-semibold text-text-muted">
                  Nguồn dữ liệu thị trường
                </span>{" "}
                (Metric.vn, BeeCost…): đặt{" "}
                <span className="mono">COMPETITOR_VENDOR_BASE_URL</span> +{" "}
                <span className="mono">COMPETITOR_VENDOR_API_KEY</span>. Data có bản
                quyền, không rủi ro tài khoản. Được ưu tiên khi có.
              </li>
              <li>
                <span className="font-semibold text-text-muted">Session Shopee</span>:
                chạy <span className="mono">python scripts/shopee_login.py</span> để
                đăng nhập một lần, rồi bật{" "}
                <span className="mono">COMPETITOR_USE_SESSION=true</span>.{" "}
                <span className="text-warning">
                  Shopee cấm truy cập tự động — dùng tài khoản phụ, tài khoản có thể bị
                  giới hạn hoặc ban.
                </span>
              </li>
            </ul>
            <p className="pl-5 text-2xs text-text-dim">
              Lazada hiện trả trang chống bot cho mọi yêu cầu tự động, nên chỉ theo dõi
              được cửa hàng Shopee.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* AI insight */}
      {insight && (
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Nhận định</CardTitle>
              <p className="mt-1 text-sm font-semibold text-text">{insight.headline}</p>
            </div>
            <Badge variant={insight.ai_generated ? "live" : "muted"}>
              {insight.ai_generated ? "AI" : "Quy tắc"}
            </Badge>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <div>
              <div className="text-xs font-medium text-text-dim">Quan sát</div>
              <ul className="mt-2 space-y-1.5">
                {insight.findings.map((f, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-text-muted">
                    <TrendingUp className="mt-0.5 h-3 w-3 shrink-0 text-accent" />
                    {f}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <div className="text-xs font-medium text-text-dim">Nên làm</div>
              <ul className="mt-2 space-y-1.5">
                {insight.actions.map((a, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-text-muted">
                    <Sparkles className="mt-0.5 h-3 w-3 shrink-0 text-accent-2" />
                    {a}
                  </li>
                ))}
              </ul>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Watchlist */}
      <Card>
        <CardHeader>
          <CardTitle>Danh sách theo dõi</CardTitle>
          <Badge variant="muted">{rows?.length ?? 0} cửa hàng</Badge>
        </CardHeader>
        <CardContent>
          {rows === null ? (
            <p className="text-sm text-text-muted">Đang tải…</p>
          ) : rows.length === 0 ? (
            <p className="text-sm text-text-muted">
              Chưa theo dõi cửa hàng nào. Dán link ở trên để bắt đầu thu thập.
            </p>
          ) : (
            <div className="space-y-3">
              {rows.map((c) => {
                const snap = c.latest;
                const failed = c.last_attempt && !c.last_attempt.ok;
                return (
                  <div key={c.id} className="rounded-lg border border-border p-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-semibold">
                        {c.display_name ?? c.url}
                      </span>
                      <Badge variant="muted">{c.platform}</Badge>
                      {c.share_pct !== null && (
                        <Badge variant="live">
                          {c.share_pct}%{" "}
                          {c.share_basis === "revenue" ? "doanh thu" : "follower"} trong nhóm
                        </Badge>
                      )}
                      {snap?.sales_source && (
                        <Badge variant="muted">{SOURCE_LABEL[snap.sales_source]}</Badge>
                      )}
                      <a
                        href={c.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-text-dim hover:text-accent"
                        aria-label="Mở trang cửa hàng"
                      >
                        <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                      <button
                        onClick={() => remove(c.id)}
                        aria-label="Bỏ theo dõi"
                        className="ml-auto text-text-dim transition-colors hover:text-danger"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>

                    {/* A broken collector is shown, not hidden. */}
                    {failed && (
                      <p className="mt-2 rounded-lg border border-warning/30 bg-warning/5 px-2.5 py-1.5 text-2xs text-warning">
                        Lần thu thập gần nhất thất bại: {c.last_attempt?.error}
                      </p>
                    )}

                    {snap ? (
                      <>
                        {/* Always available: no session or vendor needed. */}
                        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
                          <Metric
                            label="Follower"
                            value={fmtNum(snap.follower_count)}
                            trend={c.follower_trend_pct}
                          />
                          <Metric
                            label="Số sản phẩm"
                            value={fmtNum(snap.product_count)}
                            trend={c.product_trend_pct}
                          />
                          <Metric
                            label="Đánh giá"
                            value={snap.rating ? snap.rating.toFixed(2) : "—"}
                            trend={c.rating_delta}
                            trendSuffix=""
                          />
                        </div>

                        {snap.sales_source ? (
                          <>
                            <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
                              {/* Period velocity leads: cumulative totals can't
                                  tell a shop selling now from one that sold in 2019. */}
                              <Metric
                                label={
                                  c.period_sales
                                    ? `Bán trong ${c.period_sales.days} ngày`
                                    : "Bán trong kỳ"
                                }
                                value={
                                  c.period_sales
                                    ? fmtNum(c.period_sales.units)
                                    : "cần 2 lần thu thập"
                                }
                                sub={
                                  c.period_sales
                                    ? `≈ ${fmtVnd(c.period_sales.revenue_vnd)}`
                                    : undefined
                                }
                                highlight
                              />
                              <Metric
                                label="GMV ước tính"
                                value={fmtVnd(snap.revenue_est_vnd)}
                                trend={c.revenue_trend_pct}
                                sub="tích luỹ"
                              />
                              <Metric
                                label="Đã bán"
                                value={fmtNum(snap.items_sold_total)}
                                trend={c.sold_trend_pct}
                                sub="tích luỹ"
                              />
                              <Metric
                                label="Khuyến mãi"
                                value={fmtNum(
                                  snap.promotions?.length ?? snap.voucher_count ?? null,
                                )}
                                sub="sản phẩm đang giảm"
                              />
                            </div>

                            {snap.promotions && snap.promotions.length > 0 && (
                              <div className="mt-3">
                                <div className="text-2xs font-medium text-text-dim">
                                  Đang giảm giá ({snap.promotions.length})
                                </div>
                                <div className="mt-1.5 flex flex-wrap gap-1.5">
                                  {snap.promotions.slice(0, 6).map((p, i) => (
                                    <span
                                      key={i}
                                      className="rounded-full bg-warning/10 px-2 py-0.5 text-2xs text-warning"
                                      title={p.name}
                                    >
                                      −{Math.round(p.discount_pct ?? 0)}% {p.name.slice(0, 24)}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}

                            {snap.top_products && snap.top_products.length > 0 && (
                              <div className="mt-3">
                                <div className="text-2xs font-medium text-text-dim">
                                  Bán chạy nhất
                                </div>
                                <div className="mt-1.5 space-y-1">
                                  {snap.top_products
                                    .slice()
                                    .sort((a, b) => (b.sold ?? 0) - (a.sold ?? 0))
                                    .slice(0, 3)
                                    .map((p, i) => (
                                      <div
                                        key={i}
                                        className="flex items-center gap-2 text-xs text-text-muted"
                                      >
                                        <span className="min-w-0 flex-1 truncate">{p.name}</span>
                                        <span className="mono text-text">
                                          {fmtVnd(p.price_vnd)}
                                        </span>
                                        <span className="mono w-20 text-right text-text-dim">
                                          {fmtNum(p.sold)} bán
                                        </span>
                                      </div>
                                    ))}
                                </div>
                              </div>
                            )}
                          </>
                        ) : (
                          /* Say which cards are missing and why, rather than
                             showing four dashes that look like a loading state. */
                          <p className="mt-3 rounded-lg border border-border bg-bg-alt px-3 py-2 text-2xs text-text-dim">
                            Chưa có số liệu bán hàng cho shop này — Shopee chỉ trả số đã
                            bán / GMV / khuyến mãi cho phiên đã đăng nhập. Cấu hình một
                            nguồn ở phần hướng dẫn bên trên để bật 4 chỉ số đó.
                          </p>
                        )}
                      </>
                    ) : (
                      !failed && (
                        <p className="mt-2 text-xs text-text-muted">
                          Chưa có dữ liệu — bấm “Thu thập ngay”.
                        </p>
                      )
                    )}

                    <div className="mt-3 text-2xs text-text-dim">
                      {c.snapshot_count} lần thu thập
                      {snap && ` · gần nhất ${new Date(snap.captured_at).toLocaleString("vi-VN")}`}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Metric({
  label,
  value,
  trend,
  trendSuffix = "%",
  sub,
  highlight = false,
}: {
  label: string;
  value: string;
  trend?: number | null;
  trendSuffix?: string;
  /** Fixed caption — used to mark a figure as cumulative vs per-period. */
  sub?: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border p-2.5",
        highlight ? "border-accent/40 bg-accent/5" : "border-border bg-bg-alt",
      )}
    >
      <div className="text-2xs font-medium text-text-dim">{label}</div>
      <div className="mono mt-0.5 text-sm font-semibold text-text">{value}</div>
      {trend !== undefined && (
        <div className="mt-0.5">
          <Trend value={trend} suffix={trendSuffix} />
        </div>
      )}
      {sub && <div className="mt-0.5 text-2xs text-text-dim">{sub}</div>}
    </div>
  );
}
