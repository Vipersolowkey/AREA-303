"use client";

import { useState } from "react";
import { Loader2, Network, ArrowUp, ArrowDown, Minus } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { exploreProductGraph, type ProductGraphResult } from "@/lib/features";
import { cn } from "@/lib/utils";

const DIRECTION: Record<string, { label: string; cls: string; icon: typeof ArrowUp }> = {
  up: { label: "Tăng", cls: "text-success", icon: ArrowUp },
  down: { label: "Giảm", cls: "text-danger", icon: ArrowDown },
  flat: { label: "Đi ngang", cls: "text-text-muted", icon: Minus },
};

const IMPACT: Record<string, string> = { low: "Thấp", medium: "Trung bình", high: "Cao" };

function vnd(n: number) {
  return n.toLocaleString("vi-VN") + "₫";
}

export function ProductGraphPanel() {
  const [query, setQuery] = useState("serum vitamin c");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ProductGraphResult | null>(null);
  const [error, setError] = useState(false);

  async function run() {
    if (busy) return;
    setBusy(true);
    setError(false);
    const r = await exploreProductGraph(query);
    setError(r === null);
    setResult(r);
    setBusy(false);
  }

  const dir = result?.sales ? DIRECTION[result.sales.direction] : null;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
      <Card className="lg:col-span-4">
        <CardHeader>
          <div>
            <CardTitle>Khám phá đồ thị sản phẩm</CardTitle>
            <p className="mt-1 text-xs text-text-muted">Nhập tên sản phẩm hoặc SKU để xem quan hệ SKU/brand và sản phẩm tương tự.</p>
          </div>
          <Badge variant="muted">knowledge graph</Badge>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="mono text-2xs uppercase tracking-wider text-text-dim">Tên sản phẩm hoặc SKU</label>
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") run();
              }}
              className="mt-1.5 h-10"
            />
          </div>
          <Button onClick={run} disabled={busy} className="w-full">
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Network className="h-3.5 w-3.5" />}
            Khám phá
          </Button>
        </CardContent>
      </Card>

      <Card className="lg:col-span-8">
        <CardHeader><CardTitle>Kết quả</CardTitle></CardHeader>
        <CardContent>
          {error ? (
            <p className="text-sm text-danger">Không lấy được kết quả. Kiểm tra kết nối backend rồi thử lại.</p>
          ) : !result ? (
            <p className="text-sm text-text-muted">Bấm Khám phá để xem quan hệ sản phẩm.</p>
          ) : !result.found || !result.product ? (
            <p className="text-sm text-text-muted">{result.summary}</p>
          ) : (
            <div className="space-y-5">
              {/* Entity header */}
              <div className="rounded-md border border-border bg-bg-alt px-4 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-base font-semibold tracking-tight text-text">{result.product.name}</div>
                    <div className="mono mt-1 text-2xs text-text-dim">
                      {result.product.sku} · {result.product.brand} · {result.product.category}
                    </div>
                  </div>
                  <Badge variant={result.product.trend === "up" ? "success" : result.product.trend === "down" ? "danger" : "muted"}>
                    {result.product.trend}
                  </Badge>
                </div>
                <div className="mono mt-2 text-xl font-semibold text-accent">{vnd(result.product.price_vnd)}</div>
              </div>

              {/* Sales block */}
              {result.sales && (
                <div>
                  <div className="mono text-2xs uppercase tracking-wider text-text-dim">Doanh số</div>
                  <div className="mt-2 flex items-center gap-3">
                    <span className="mono text-sm text-text-muted">{result.sales.sales_prev.toLocaleString("vi-VN")}</span>
                    <span className="text-text-dim">→</span>
                    <span className="mono text-sm text-text">{result.sales.sales_curr.toLocaleString("vi-VN")}</span>
                    <span className={cn("flex items-center gap-1 text-sm font-semibold", result.sales.direction === "up" ? "text-success" : result.sales.direction === "down" ? "text-danger" : "text-text-muted")}>
                      {dir && <dir.icon className="h-4 w-4" />}
                      {result.sales.change_pct > 0 ? "+" : ""}{result.sales.change_pct}%
                    </span>
                  </div>
                  {result.sales.drivers.length > 0 && (
                    <div className="mt-2 space-y-2">
                      {result.sales.drivers.map((d, i) => {
                        const dd = DIRECTION[d.direction];
                        return (
                          <div key={i} className="flex items-center justify-between gap-2 rounded-md border border-border bg-bg-alt px-3 py-2 text-xs">
                            <span className={cn("flex items-center gap-1.5", dd.cls)}>
                              <dd.icon className="h-3.5 w-3.5" />
                              <span className="text-text">{d.factor}</span>
                            </span>
                            <Badge variant={d.impact === "high" ? "danger" : d.impact === "medium" ? "warning" : "muted"}>
                              {IMPACT[d.impact]}
                            </Badge>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* Similar products */}
              {result.similar_products.length > 0 && (
                <div>
                  <div className="mono text-2xs uppercase tracking-wider text-text-dim">Sản phẩm tương tự SKU này</div>
                  <div className="mt-2 space-y-2">
                    {result.similar_products.map((p) => (
                      <div key={p.id} className="rounded-md border border-border bg-bg-alt px-3 py-2">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="text-sm text-text">{p.name}</div>
                            <div className="mono mt-0.5 text-2xs text-text-dim">{p.sku} · {p.brand}</div>
                          </div>
                          <div className="mono shrink-0 text-sm text-accent">{vnd(p.price_vnd)}</div>
                        </div>
                        <div className="mt-1.5 text-xs text-text-muted">{p.relation}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Brand siblings + category peers */}
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {result.brand_siblings.length > 0 && (
                  <div className="rounded-md border border-border bg-bg-alt px-3 py-2">
                    <div className="mono text-2xs uppercase tracking-wider text-text-dim">Cùng thương hiệu</div>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {result.brand_siblings.map((b) => (
                        <span key={b} className="rounded-md border border-border bg-surface px-2 py-0.5 text-xs text-text-muted">{b}</span>
                      ))}
                    </div>
                  </div>
                )}
                <div className="rounded-md border border-border bg-bg-alt px-3 py-2">
                  <div className="mono text-2xs uppercase tracking-wider text-text-dim">Sản phẩm cùng danh mục</div>
                  <div className="mono mt-2 text-lg font-semibold text-text">{result.category_peers}</div>
                </div>
              </div>

              {/* Promotions */}
              {result.promotions.length > 0 && (
                <div>
                  <div className="mono text-2xs uppercase tracking-wider text-text-dim">Khuyến mãi</div>
                  <div className="mt-2 space-y-2">
                    {result.promotions.map((p, i) => (
                      <div key={i} className="flex items-center justify-between gap-2 rounded-md border border-border bg-bg-alt px-3 py-2 text-xs">
                        <div className="min-w-0">
                          <span className="text-text">{p.name}</span>
                          <span className="mono ml-2 text-text-dim">-{p.discount_pct}% · lift +{p.lift_pct}%</span>
                        </div>
                        <Badge variant="muted">{p.effectiveness}</Badge>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* LLM summary */}
              <div className="rounded-md border border-accent/40 bg-accent/10 px-4 py-3">
                <div className="mono text-2xs uppercase tracking-wider text-text-dim">Tổng hợp</div>
                <p className="mt-1.5 text-sm leading-relaxed text-text">{result.summary}</p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
