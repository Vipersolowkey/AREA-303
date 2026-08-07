"use client";

import { useState } from "react";
import { Loader2, Tag } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { recommendPrice, type PricingResult } from "@/lib/features";
import { cn } from "@/lib/utils";

const CATEGORIES = ["Thời trang", "Mỹ phẩm", "Phụ kiện"] as const;

const VND = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 });

export function DynamicPricingPanel() {
  const [name, setName] = useState("Serum Vitamin C 15%");
  const [category, setCategory] = useState<(typeof CATEGORIES)[number]>("Mỹ phẩm");
  const [price, setPrice] = useState("450000");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<PricingResult | null>(null);
  const [error, setError] = useState(false);

  async function run() {
    if (busy) return;
    setBusy(true);
    setError(false);
    const cur = price.trim() ? Number(price.replace(/\D/g, "")) : undefined;
    const r = await recommendPrice(name, category, cur);
    setError(r === null);
    setResult(r);
    setBusy(false);
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
      <Card className="lg:col-span-7">
        <CardHeader>
          <div>
            <CardTitle>Sản phẩm cần định giá</CardTitle>
            <p className="mt-1 text-xs text-text-muted">
              So sánh với comps cùng danh mục để đề xuất giá cạnh tranh.
            </p>
          </div>
          <Badge variant="muted">comps median</Badge>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <label className="text-xs font-medium text-text-dim">Tên sản phẩm</label>
            <Input value={name} onChange={(e) => setName(e.target.value)} className="mt-1.5 h-10" />
          </div>
          <div>
            <label className="text-xs font-medium text-text-dim">Danh mục</label>
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
          <div>
            <label className="text-xs font-medium text-text-dim">Giá hiện tại (₫, tuỳ chọn)</label>
            <Input
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder="Để trống nếu chưa có giá"
              className="mt-1.5 h-10"
            />
          </div>
          <Button onClick={run} disabled={busy} className="w-full">
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Tag className="h-3.5 w-3.5" />}
            Đề xuất giá
          </Button>
        </CardContent>
      </Card>

      <Card className="lg:col-span-5">
        <CardHeader>
          <CardTitle>Đề xuất</CardTitle>
          {result && <Badge variant="muted">n={result.sample_size} comps</Badge>}
        </CardHeader>
        <CardContent>
          {error ? (
            <p className="text-sm text-danger">Không lấy được kết quả. Kiểm tra kết nối backend rồi thử lại.</p>
          ) : !result ? (
            <p className="text-sm text-text-muted">Nhập sản phẩm và bấm Đề xuất giá.</p>
          ) : (
            <div className="space-y-4">
              <div>
                <div className="mono text-3xl font-semibold tracking-tight text-accent">
                  {VND.format(result.recommended_price)}₫
                </div>
                <div className="mt-1 text-xs text-text-muted">
                  Khoảng đề xuất: {VND.format(result.low)}₫ – {VND.format(result.high)}₫
                </div>
              </div>
              <div className="rounded-md border border-border bg-bg-alt px-3 py-2 text-xs text-text-muted">
                Trung vị danh mục: <span className="mono text-text">{VND.format(result.category_median)}₫</span>
              </div>
              <p className="text-sm text-text-muted">{result.rationale}</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
