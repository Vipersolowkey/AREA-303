"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowRight, Bot, Check, CircleAlert, Clock3, Database, FlaskConical,
  RefreshCw, ShieldCheck, Target, X,
} from "lucide-react";
import { api, ApiClientError } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useT } from "@/lib/i18n";

type Option = { id: string; label: string; risk: string; impact: Record<string, number> };
type Opportunity = {
  id: number; kind: string; severity: string; status: string; title: string;
  explanation: string; evidence: Record<string, string | number>; options: Option[];
  model: string | null; llm_used: boolean; selected_option_id: string | null;
  problem: string; impact_level: string; data_updated_at: string | null;
  confidence: { score: number; basis: string };
  execution: { action: string; target: string; status: string; message: string; executed_at: string | null } | null;
  monitoring: { status: string; before: Record<string, unknown>; after: Record<string, unknown> | null; message: string } | null;
};
type CenterState = {
  state: "no_data" | "syncing" | "sync_failed" | "ready_unanalyzed" | "analyzed" | "awaiting_approval" | "monitoring";
  demo_mode: boolean;
  latest_data_at: string | null;
  sync: { completed_sources: number; total_sources: number };
  decisions: { total: number; awaiting_approval: number; approved: number; rejected: number };
};

const money = (value: number) => `${new Intl.NumberFormat("vi-VN").format(value)}₫`;
const labelMap: Record<string, string> = {
  inventory: "Tồn kho", reviews: "Trải nghiệm khách hàng", customer_risk: "Giữ chân khách",
  detected: "Cần mô phỏng", simulated: "Chờ duyệt", applied: "Đã tạo workflow", rejected: "Đã bỏ",
};
const evidenceLabels: Record<string, string> = {
  product_name: "Sản phẩm", runway_days: "Số ngày còn hàng", revenue_at_risk_vnd: "Doanh thu có rủi ro",
  negative_reviews_30d: "Review thấp / 30 ngày", customers_at_risk: "Khách cần giữ chân",
  ltv_at_risk_vnd: "LTV có rủi ro", stock: "Tồn hiện tại", daily_sales: "Bán/ngày",
  current_price_vnd: "Giá hiện tại", sku: "SKU",
};
const impactLabels: Record<string, string> = {
  revenue_protected_vnd: "Doanh thu được bảo vệ",
  wasted_spend_avoided_vnd: "Chi phí lãng phí tránh được",
  runway_days: "Số ngày tồn kho sau xử lý",
  campaigns_to_review: "Campaign cần rà soát",
  reviews_prioritized: "Review được ưu tiên",
  response_sla_hours: "SLA phản hồi (giờ)",
  customers_targeted: "Khách được nhắm tới",
  expected_reactivation_pct: "Tỷ lệ tái kích hoạt dự kiến (%)",
};
const riskLabels: Record<string, string> = { low: "thấp", medium: "vừa", high: "cao" };
const showValue = (key: string, value: string | number) =>
  key.endsWith("_vnd") && typeof value === "number" ? money(value) : String(value);

const stateCopy: Record<CenterState["state"], { title: string; detail: string; tone: "muted" | "warning" | "danger" | "live" }> = {
  no_data: { title: "Chưa sẵn sàng", detail: "Workspace chưa có dữ liệu đã xác nhận.", tone: "muted" },
  syncing: { title: "Đang đồng bộ dữ liệu", detail: "Tiến độ lấy trực tiếp từ các nguồn đã kết nối.", tone: "warning" },
  sync_failed: { title: "Đồng bộ thất bại", detail: "Kiểm tra kết nối nguồn dữ liệu trước khi phân tích.", tone: "danger" },
  ready_unanalyzed: { title: "Dữ liệu đã sẵn sàng", detail: "Có thể chạy phân tích lần đầu.", tone: "live" },
  analyzed: { title: "Đã phân tích", detail: "Không có quyết định đang chờ duyệt.", tone: "live" },
  awaiting_approval: { title: "Có quyết định chờ duyệt", detail: "AI chỉ đề xuất; seller quyết định sau khi mô phỏng.", tone: "warning" },
  monitoring: { title: "Cần theo dõi hiệu quả", detail: "Đồng bộ dữ liệu mới để đối chiếu KPI trước và sau.", tone: "live" },
};

function relativeTime(value: string | null) {
  if (!value) return "chưa xác định thời điểm";
  const minutes = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 60000));
  if (minutes < 1) return "vừa cập nhật";
  if (minutes < 60) return `${minutes} phút trước`;
  const hours = Math.round(minutes / 60);
  return hours < 24 ? `${hours} giờ trước` : `${Math.round(hours / 24)} ngày trước`;
}

export function AutopilotPanel() {
  const t = useT();
  const [items, setItems] = useState<Opportunity[]>([]);
  const [center, setCenter] = useState<CenterState | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshNotice, setRefreshNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [opportunities, state] = await Promise.all([
        api.get<Opportunity[]>("/autopilot/opportunities"),
        api.get<CenterState>("/autopilot/state"),
      ]);
      setItems(opportunities.data ?? []);
      setCenter(state.data ?? null);
    } catch (cause) {
      setError(cause instanceof ApiClientError ? cause.message : t("Hãy chọn workspace đang hoạt động."));
    }
  }, [t]);
  useEffect(() => { void load(); }, [load]);

  const refresh = async () => {
    setBusy("refresh"); setError(null); setRefreshNotice(null);
    try {
      const response = await api.post<Opportunity[]>("/autopilot/refresh", {});
      const refreshedItems = response.data ?? [];
      setItems(refreshedItems);
      const decisionsToReview = refreshedItems.filter(
        (item) => !["applied", "rejected"].includes(item.status),
      ).length;
      setRefreshNotice(
        decisionsToReview > 0
          ? `Phân tích hoàn tất: ${decisionsToReview} quyết định cần xem.`
          : "Phân tích hoàn tất: không phát hiện quyết định mới từ snapshot hiện tại.",
      );
      const state = await api.get<CenterState>("/autopilot/state");
      setCenter(state.data ?? null);
    } catch (cause) {
      setError(cause instanceof ApiClientError ? cause.message : t("Không thể phân tích dữ liệu vận hành."));
    } finally { setBusy(null); }
  };

  const resetDemo = async () => {
    setBusy("reset-demo"); setError(null); setRefreshNotice(null);
    try {
      const response = await api.post<Opportunity[]>("/autopilot/demo/reset", {});
      const demoItems = response.data ?? [];
      setItems(demoItems);
      const state = await api.get<CenterState>("/autopilot/state");
      setCenter(state.data ?? null);
      setRefreshNotice(`Đã tạo lại bản demo với ${demoItems.length} quyết định mẫu.`);
    } catch (cause) {
      setError(cause instanceof ApiClientError ? cause.message : "Không thể tạo lại bản demo.");
    } finally { setBusy(null); }
  };

  const act = async (item: Opportunity, option: Option, decision?: "approve" | "reject") => {
    const key = `${item.id}:${option.id}:${decision ?? "simulate"}`;
    setBusy(key); setError(null);
    try {
      const path = decision ? "decision" : "simulate";
      const body = decision ? { option_id: option.id, decision } : { option_id: option.id };
      const response = await api.post<{ opportunity: Opportunity }>(
        `/autopilot/opportunities/${item.id}/${path}`, body,
      );
      if (response.data) setItems((rows) => rows.map((row) =>
        row.id === item.id ? response.data!.opportunity : row));
      const state = await api.get<CenterState>("/autopilot/state");
      setCenter(state.data ?? null);
    } catch (cause) {
      setError(cause instanceof ApiClientError ? cause.message : t("Hành động không hợp lệ."));
    } finally { setBusy(null); }
  };

  const active = items.filter((item) => !["applied", "rejected"].includes(item.status));
  const completed = items.length - active.length;
  const currentState = center ? stateCopy[center.state] : null;

  return (
    <div className="space-y-6">
      <Card className="overflow-hidden border-accent/30">
        <CardContent className="grid gap-5 p-5 lg:grid-cols-[1fr_auto] lg:items-center">
          <div className="flex gap-3">
            <span className="doodle-sticker h-11 w-11 shrink-0"><Bot className="h-5 w-5" /></span>
            <div>
              <div className="text-sm font-semibold text-accent-deep">Commerce Decision Center</div>
              <h2 className="mt-1 text-2xl">{t("Từ tín hiệu thành một quyết định có thể thực thi")}</h2>
              <p className="mt-2 max-w-2xl text-sm text-text-muted">
                {t("Các module phân tích chạy phía sau để cung cấp bằng chứng. Màn hình này chỉ giữ lại vấn đề cần quyết định, tác động và hành động tiếp theo.")}
              </p>
            </div>
          </div>
          <div className="flex flex-col items-stretch gap-2 sm:items-end">
            {currentState && <div className="text-right">
              <Badge variant={currentState.tone}>{currentState.title}</Badge>
              <p className="mt-1 text-xs text-text-muted">
                {center?.latest_data_at ? `Dữ liệu mới nhất ${relativeTime(center.latest_data_at)}` : currentState.detail}
              </p>
              {center?.state === "syncing" && <p className="text-xs font-medium text-warning">
                {center.sync.completed_sources}/{center.sync.total_sources} nguồn đã đồng bộ
              </p>}
              {!!center?.decisions.awaiting_approval && <p className="text-xs font-medium text-warning">
                {center.decisions.awaiting_approval} quyết định chờ duyệt
              </p>}
            </div>}
            {center?.state === "no_data" || center?.state === "sync_failed" ? (
              <Button asChild><Link href="/seller/onboarding"><Database className="h-4 w-4" /> Nạp dữ liệu</Link></Button>
            ) : (
              <div className="flex flex-wrap justify-end gap-2">
                {center?.demo_mode && active.length === 0 && completed > 0 && (
                  <Button variant="secondary" onClick={resetDemo} disabled={busy !== null}>
                    <RefreshCw className={`h-4 w-4 ${busy === "reset-demo" ? "animate-spin" : ""}`} />
                    {busy === "reset-demo" ? "Đang tạo lại demo…" : "Tạo lại bản demo"}
                  </Button>
                )}
                <Button onClick={refresh} disabled={busy !== null || center?.state === "syncing"}>
                  <RefreshCw className={`h-4 w-4 ${busy === "refresh" ? "animate-spin" : ""}`} />
                  {busy === "refresh" ? t("Đang phân tích snapshot…") : center?.state === "ready_unanalyzed" ? "Chạy phân tích lần đầu" : t("Cập nhật phân tích")}
                </Button>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-3 sm:grid-cols-3">
        <Stage icon={Target} number="01" title={t("Phát hiện")} detail={`${active.length} việc cần quyết định`} active />
        <Stage icon={FlaskConical} number="02" title={t("Mô phỏng")} detail={t("So sánh tác động trước khi duyệt")} />
        <Stage icon={ShieldCheck} number="03" title={t("Thực thi")} detail={`${completed} quyết định đã ghi nhận`} />
      </div>

      {error && <div className="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger">{error}</div>}
      {refreshNotice && !error && (
        <div role="status" className="rounded-lg border border-success/30 bg-success/10 p-3 text-sm font-medium text-success">
          {refreshNotice}
        </div>
      )}
      {!items.length && !error && (
        <Card><CardContent className="p-10 text-center">
          <Target className="mx-auto h-8 w-8 text-accent" />
          <h3 className="mt-3 text-lg">{t("Chưa có snapshot quyết định")}</h3>
          <p className="mt-1 text-sm text-text-muted">{center?.state === "no_data" ? "Nạp dữ liệu sản phẩm hoặc kết nối sàn trước khi tạo quyết định." : t("Chạy phân tích để đọc dữ liệu đã xác nhận trong cùng một snapshot.")}</p>
        </CardContent></Card>
      )}

      <div className="space-y-4">
        {active.map((item) => {
          const selected = item.options.find((option) => option.id === item.selected_option_id) ?? item.options[0];
          const terminal = ["applied", "rejected"].includes(item.status);
          const evidence = Object.entries(item.evidence).filter(([key]) => evidenceLabels[key]).slice(0, 4);
          return (
            <Card key={item.id} className={item.severity === "critical" ? "border-danger/40" : ""}>
              <CardHeader className="border-b border-border">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant={item.severity === "critical" ? "danger" : "warning"}>{labelMap[item.kind] ?? item.kind}</Badge>
                      <Badge variant="muted">{labelMap[item.status] ?? item.status}</Badge>
                    </div>
                    <CardTitle className="mt-3">{item.title}</CardTitle>
                    <p className="mt-2 max-w-3xl text-sm leading-6 text-text-muted">{item.explanation}</p>
                    <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-dim">
                      <span>Mức ảnh hưởng: <b className="text-text">{item.impact_level === "critical" ? "Cao" : item.impact_level === "warning" ? "Trung bình" : "Thấp"}</b></span>
                      <span>Độ tin cậy: <b className="text-text">{Math.round(item.confidence.score * 100)}%</b> · {item.confidence.basis}</span>
                      <span className="inline-flex items-center gap-1"><Clock3 className="h-3 w-3" /> Dữ liệu {relativeTime(item.data_updated_at)}</span>
                    </div>
                  </div>
                  {item.llm_used && <span className="text-xs text-text-dim">{t("Ollama giải thích · số liệu do rule tính")}</span>}
                </div>
              </CardHeader>
              <CardContent className="grid gap-5 p-5 lg:grid-cols-[.8fr_1.2fr]">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wide text-text-dim">{t("Bằng chứng đủ để quyết định")}</div>
                  <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-1">
                    {evidence.map(([key, value]) => (
                      <div key={key} className="flex items-center justify-between gap-4 border-b border-dashed border-border pb-2 text-sm">
                        <span className="text-text-muted">{t(evidenceLabels[key])}</span>
                        <b>{showValue(key, value)}</b>
                      </div>
                    ))}
                  </div>
                  <p className="mt-3 text-xs text-text-dim">
                    Nguồn: {item.evidence.source === "confirmed_import"
                      ? "File đã xác nhận trong workspace"
                      : item.evidence.source === "seeded_admin_demo"
                        ? "Bộ dữ liệu mẫu của tài khoản admin"
                        : String(item.evidence.source ?? "Không xác định")}
                    {item.evidence.source_record_id ? ` · Bản ghi #${item.evidence.source_record_id}` : ""}
                  </p>
                </div>
                {selected ? (
                  <div className="rounded-md border-2 border-text/70 bg-surface p-4 shadow-[3px_4px_0_hsl(var(--text)/calc(.1*var(--shadow-strength)))]">
                    <div className="flex items-start justify-between gap-3">
                      <div><div className="text-xs font-semibold text-accent-deep">{t("HÀNH ĐỘNG ĐỀ XUẤT")}</div><div className="mt-1 font-semibold">{selected.label}</div></div>
                      <Badge variant={selected.risk === "low" ? "success" : "warning"}>{t("Rủi ro")} {riskLabels[selected.risk] ? t(riskLabels[selected.risk]) : selected.risk}</Badge>
                    </div>
                    <div className="mt-4 grid gap-2 sm:grid-cols-2">
                      {Object.entries(selected.impact).slice(0, 4).map(([key, value]) => (
                        <div key={key} className="rounded-md bg-surface-2 p-2.5 text-xs text-text-muted">
                          {impactLabels[key] ? t(impactLabels[key]) : key.replaceAll("_", " ")}<div className="mono mt-1 font-bold text-text">{showValue(key, value)}</div>
                        </div>
                      ))}
                    </div>
                    {item.status === "simulated" && (
                      <div role="status" className="mt-4 rounded-lg border-2 border-success/40 bg-success/10 p-4">
                        <div className="flex items-center gap-2 text-sm font-semibold text-success">
                          <FlaskConical className="h-4 w-4" /> Kết quả mô phỏng
                        </div>
                        <p className="mt-2 text-sm text-text">
                          Nếu duyệt <b>{selected.label.toLowerCase()}</b>, hệ thống dự kiến:
                        </p>
                        <div className="mt-3 grid gap-2 sm:grid-cols-2">
                          {Object.entries(selected.impact).map(([key, value]) => (
                            <div key={key} className="rounded-md border border-success/20 bg-surface px-3 py-2 text-xs text-text-muted">
                              {impactLabels[key] ? t(impactLabels[key]) : key.replaceAll("_", " ")}
                              <div className="mono mt-1 text-base font-bold text-text">{showValue(key, value)}</div>
                            </div>
                          ))}
                        </div>
                        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-muted">
                          <span>Rủi ro: <b className="text-text">{riskLabels[selected.risk] ? t(riskLabels[selected.risk]) : selected.risk}</b></span>
                          <span>Giả định: dữ liệu snapshot hiện tại không đổi trong thời gian chạy.</span>
                        </div>
                        <p className="mt-2 text-xs font-medium text-warning">
                          Đây là ước tính kịch bản. Chưa có hành động nào được thực thi hoặc gửi sang nền tảng.
                        </p>
                      </div>
                    )}
                    {!terminal && <div className="mt-4 flex flex-wrap gap-2">
                      {item.status !== "simulated" ? (
                        <Button size="sm" variant="secondary" disabled={busy !== null} onClick={() => act(item, selected)}>
                          <FlaskConical className="h-3.5 w-3.5" /> {t("Mô phỏng tác động")}
                        </Button>
                      ) : (
                        <Button size="sm" disabled={busy !== null} onClick={() => act(item, selected, "approve")}>
                          <Check className="h-3.5 w-3.5" /> {t("Duyệt tạo workflow")}
                        </Button>
                      )}
                      <Button size="sm" variant="ghost" disabled={busy !== null} onClick={() => act(item, selected, "reject")}>
                        <X className="h-3.5 w-3.5" /> {t("Bỏ qua")}
                      </Button>
                      {item.kind === "customer_risk" && (
                        <Button asChild size="sm" variant="ghost"><Link href="/seller/voucher-booster">{t("Mở Voucher Booster")} <ArrowRight className="h-3.5 w-3.5" /></Link></Button>
                      )}
                    </div>}
                    {item.options.length > 1 && !terminal && (
                      <details className="mt-4 border-t border-border pt-3 text-xs text-text-muted">
                        <summary className="cursor-pointer">Xem {item.options.length - 1} phương án khác</summary>
                        <div className="mt-2 space-y-1">
                          {item.options.filter((option) => option.id !== selected.id).map((option) => (
                            <button key={option.id} type="button" onClick={() => act(item, option)}
                              className="block w-full rounded-md border border-border px-3 py-2 text-left hover:border-accent hover:text-text">
                              {option.label}
                            </button>
                          ))}
                        </div>
                      </details>
                    )}
                  </div>
                ) : (
                  <div className="rounded-md border-2 border-text/70 bg-surface p-4 text-sm text-text-muted">
                    {t("Không có hành động nào cần duyệt — mục này chỉ mang tính thông tin.")}
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {completed > 0 && (
        <details className="rounded-lg border border-border bg-surface p-4">
          <summary className="cursor-pointer text-sm font-semibold">
            Lịch sử quyết định ({completed})
          </summary>
          <div className="mt-3 divide-y divide-border">
            {items.filter((item) => ["applied", "rejected"].includes(item.status)).map((item) => (
              <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm">
                <span>{item.title}</span>
                <Badge variant={item.status === "applied" ? "success" : "muted"}>
                  {labelMap[item.status] ?? item.status}
                </Badge>
                {item.execution && <div className="w-full rounded-md bg-surface-2 p-3 text-xs text-text-muted">
                  <b className="text-text">{item.execution.action}</b>
                  <p className="mt-1">{item.execution.message}</p>
                  <p className="mt-2 font-medium text-warning">KPI: {item.monitoring?.message}</p>
                </div>}
              </div>
            ))}
          </div>
        </details>
      )}

      <div className="flex items-start gap-2 rounded-md border border-warning/30 bg-warning/10 p-3 text-xs text-text-muted">
        <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
        {t("Trung tâm quyết định chỉ dùng dữ liệu có nguồn trong snapshot. LLM được phép giải thích, không được tự tạo chỉ số hoặc vượt qua bước seller duyệt.")}
      </div>
    </div>
  );
}

function Stage({ icon: Icon, number, title, detail, active = false }: {
  icon: typeof Target; number: string; title: string; detail: string; active?: boolean;
}) {
  return <div className={`rounded-lg border p-4 ${active ? "border-accent/40 bg-accent/10" : "border-border bg-surface"}`}>
    <div className="flex items-center gap-2"><Icon className="h-4 w-4 text-accent" /><span className="mono text-xs text-text-dim">{number}</span><b>{title}</b></div>
    <p className="mt-2 text-xs text-text-muted">{detail}</p>
  </div>;
}
