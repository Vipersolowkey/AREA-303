"use client";

import { useState, useMemo } from "react";
import { Loader2, Sparkles, Users2, Lightbulb, Search } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { predictSegmentation, type SegmentationFeatures, type SegmentationResult } from "@/lib/features";
import { DEMO_CUSTOMERS, type DemoCustomer } from "@/lib/demo-customers";
import { cn } from "@/lib/utils";

const PERSONA_TONE: Record<string, { cls: string }> = {
  "Active Buyers": { cls: "text-success" },
  "Sellers (listing & selling activity)": { cls: "text-accent" },
  "At-risk / Low-activity Users": { cls: "text-warning" },
  "Dormant / Ghost Users": { cls: "text-danger" },
};

/**
 * Nhận xét + phân tích + đề xuất hành động cố định theo persona — theo yêu
 * cầu của lead: sau khi predict xong phải có chỗ giải thích "vì sao" và
 * "nên làm gì". Nội dung lấy từ bảng đã thống nhất với lead.
 */
const PERSONA_INSIGHT: Record<
  string,
  { note: string; analysis: string; action: string }
> = {
  "Active Buyers": {
    note: "Nhóm khách hàng \"vàng\" — hoạt động tích cực nhất trong 4 nhóm (28.3% tổng khách hàng).",
    analysis:
      "Đăng nhập gần đây hơn hẳn 3 nhóm còn lại, có mua hàng, thích sản phẩm và lưu wishlist nhiều — dấu hiệu rõ ràng của sự quan tâm và tương tác thật.",
    action:
      "Ưu tiên chương trình loyalty/VIP, gợi ý sản phẩm cá nhân hóa theo lịch sử thích/mua. Đây là nhóm tạo doanh thu chính nên ROI đầu tư cao nhất.",
  },
  "Sellers (listing & selling activity)": {
    note: "Nhóm người bán — có hoạt động đăng bán sản phẩm rõ rệt (14.0% tổng khách hàng).",
    analysis:
      "Tỷ lệ sản phẩm bị từ chối khi đăng bán cao bất thường (~4.14%, các nhóm khác gần 0%) — dấu hiệu chính phân biệt nhóm này.",
    action:
      "Hướng dẫn/checklist đăng bán chuẩn (ảnh, mô tả, giá) để giảm tỷ lệ bị từ chối. Cân nhắc hỗ trợ riêng qua Seller Coach để giữ chân seller.",
  },
  "At-risk / Low-activity Users": {
    note: "Nhóm \"sắp mất\" — còn hiện diện nhưng đang nguội dần (14.7% tổng khách hàng).",
    analysis:
      "Vẫn có cài app (69%, cao hơn hẳn nhóm Dormant) và còn mở app gần đây, nhưng gần như không mua/bán/thích gì — khác Dormant ở chỗ chưa hoàn toàn \"biến mất\".",
    action:
      "Can thiệp SỚM trước khi chuyển hẳn sang Dormant: push notification nhắc nhở, ưu đãi nhỏ có thời hạn ngắn. Chi phí giữ chân luôn thấp hơn kéo lại người đã bỏ hẳn.",
  },
  "Dormant / Ghost Users": {
    note: "Nhóm lớn nhất và đáng lo ngại nhất — chiếm tới 43.0% tổng khách hàng.",
    analysis:
      "98% hoàn toàn không có hoạt động mua/bán/thích/wishlist nào, không đăng nhập trung bình gần 2 năm — gần như đã \"biến mất\" khỏi hệ thống.",
    action:
      "Chiến dịch re-engagement: email/SMS định kỳ (không quá dày), ưu đãi \"chào mừng quay lại\" mạnh tay. Kỳ vọng tỷ lệ phản hồi thấp nhưng vì chiếm 43% nên dù chỉ 2-3% quay lại cũng là con số lớn.",
  },
};


export function SegmentationPanel() {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<DemoCustomer | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<SegmentationResult | null>(null);
  const [error, setError] = useState(false);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return DEMO_CUSTOMERS.slice(0, 8);
    return DEMO_CUSTOMERS.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.phone.includes(q) ||
        c.city.toLowerCase().includes(q),
    ).slice(0, 8);
  }, [query]);

  function pick(c: DemoCustomer) {
    setSelected(c);
    setResult(null);
    setError(false);
  }

  async function run() {
    if (busy || !selected) return;
    setBusy(true);
    setError(false);
    // Không fallback về nhãn có sẵn trong file demo: kết quả hiển thị phải
    // luôn đến từ model thật, nếu không sẽ hiểu nhầm là model đang chạy.
    const r = await predictSegmentation(selected.features as SegmentationFeatures);
    if (r) setResult(r);
    else setError(true);
    setBusy(false);
  }

  const topProb = result ? Math.max(...Object.values(result.probabilities)) : 0;
  const tone = result ? PERSONA_TONE[result.persona] : null;
  const insight = result ? PERSONA_INSIGHT[result.persona] : null;
  const sortedProbs = result
    ? Object.entries(result.probabilities).sort((a, b) => b[1] - a[1])
    : [];

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
      <Card className="lg:col-span-7">
        <CardHeader>
          <CardTitle>Danh sách khách hàng</CardTitle>
          <Badge variant="muted">{DEMO_CUSTOMERS.length} khách hàng</Badge>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-dim" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Tìm theo tên, số điện thoại, thành phố..."
              className="w-full rounded-md border border-border bg-bg-alt py-2 pl-8 pr-3 text-sm text-text placeholder:text-text-dim focus:border-accent focus:outline-none"
            />
          </div>

          <div className="max-h-72 space-y-1.5 overflow-y-auto">
            {filtered.length === 0 ? (
              <p className="px-2 py-4 text-center text-sm text-text-dim">Không tìm thấy khách hàng nào.</p>
            ) : (
              filtered.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => pick(c)}
                  className={cn(
                    "w-full rounded-md border px-3 py-2 text-left transition-colors",
                    selected?.id === c.id
                      ? "border-accent bg-accent/10"
                      : "border-border bg-bg-alt hover:border-accent/50",
                  )}
                >
                  <div className="text-sm font-medium text-text">{c.name}</div>
                  <div className="text-xs text-text-dim">
                    {c.age} tuổi · {c.city} · {c.phone}
                  </div>
                </button>
              ))
            )}
          </div>

          {selected && (
            <div className="border-t border-border pt-3">
              <p className="mb-2 text-xs font-medium uppercase tracking-wider text-text-dim">
                Khách hàng đã chọn
              </p>
              <div className="space-y-2 rounded-md border border-border bg-bg-alt p-3">
                <div className="text-sm font-medium text-text">{selected.name}</div>
                <p className="text-xs text-text-muted">{selected.behavior}</p>
                <p className="text-xs text-text-dim">{selected.history}</p>
              </div>
            </div>
          )}

          <Button onClick={run} disabled={busy || !selected} className="w-full">
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
            Predict Persona
          </Button>
        </CardContent>
      </Card>

      <Card className="lg:col-span-5">
        <CardHeader>
          <CardTitle>Result</CardTitle>
          {result && <Badge variant="muted">conf {Math.round(topProb * 100)}%</Badge>}
        </CardHeader>
        <CardContent>
          {error ? (
            <p className="text-sm text-danger">
              Không gọi được model. Kiểm tra backend có đang chạy không, rồi thử lại.
            </p>
          ) : !result ? (
            <p className="text-sm text-text-muted">
              {selected ? "Bấm Predict Persona để phân loại." : "Chọn 1 khách hàng từ danh sách bên trái."}
            </p>
          ) : (
            <div className="space-y-4">
              <div className={cn("flex items-center gap-2 text-2xl font-semibold tracking-tight", tone?.cls)}>
                <Users2 className="h-5 w-5" />
                {result.persona}
              </div>
              <div className="space-y-2">
                {sortedProbs.map(([persona, prob]) => (
                  <div key={persona} className="space-y-1">
                    <div className="flex justify-between text-xs text-text-muted">
                      <span>{persona}</span>
                      <span className="mono">{Math.round(prob * 100)}%</span>
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
                      <div
                        className="h-full rounded-full bg-accent transition-all"
                        style={{ width: `${Math.round(prob * 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>

              {insight && (
                <div className="space-y-3 rounded-md border border-border bg-bg-alt p-3">
                  <div className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-text-dim">
                    <Lightbulb className="h-3.5 w-3.5" />
                    Nhận xét & Đề xuất hành động
                  </div>
                  <div className="space-y-2 text-sm">
                    <p className="text-text">{insight.note}</p>
                    <div>
                      <span className="text-xs font-medium text-text-dim">Vì sao thuộc nhóm này: </span>
                      <span className="text-text-muted">{insight.analysis}</span>
                    </div>
                    <div>
                      <span className="text-xs font-medium text-text-dim">Nên làm gì: </span>
                      <span className="text-text-muted">{insight.action}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
