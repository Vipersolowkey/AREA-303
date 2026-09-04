"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PackageX, RefreshCcw, Star, TrendingUp, Users } from "lucide-react";
import { api } from "@/lib/api";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { TrafficChart } from "@/components/dashboard/traffic-chart";
import { AlertsTable } from "@/components/dashboard/incidents-table";
import { GeoMap } from "@/components/dashboard/geo-map-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  KPIS,
  TIMESERIES,
  ALERTS,
  PROVINCES,
  type Kpi,
  type Alert,
  type ProvinceNode,
} from "@/lib/mock-data";
import { useT, useTf } from "@/lib/i18n";

type Summary = {
  shop: { name: string; channels: string[]; data_as_of: string };
  counts: { products: number; customers: number; orders: number; reviews: number };
  period_summary: {
    days: number;
    revenue_vnd: number;
    total_orders: number;
    recognized_orders: number;
    average_order_value_vnd: number;
    active_customers: number;
    returning_customer_rate_pct: number;
    cancellation_rate_pct: number;
    return_rate_pct: number;
    low_stock_skus: number;
    out_of_stock_skus: number;
  };
  kpis: Kpi[];
  timeseries: typeof TIMESERIES;
  alerts: Alert[];
  provinces: ProvinceNode[];
};

const COMPACT_VND = new Intl.NumberFormat("vi-VN", {
  notation: "compact",
  maximumFractionDigits: 1,
});

const SNAPSHOT_DATE = new Intl.DateTimeFormat("vi-VN", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  timeZone: "Asia/Ho_Chi_Minh",
});

export function SellerOverview() {
  const t = useT();
  const tf = useTf();
  const [data, setData] = useState<Summary | null>(null);

  useEffect(() => {
    let active = true;
    api.get<Summary>("/kpis/summary")
      .then((response) => {
        if (active && response.data) setData(response.data);
      })
      .catch(() => {});
    return () => { active = false; };
  }, []);

  const kpis = data?.kpis ?? KPIS;
  const timeseries = data?.timeseries ?? TIMESERIES;
  const alerts = data?.alerts ?? ALERTS;
  const provinces = data?.provinces ?? PROVINCES;
  const okNodes = provinces.filter((node) => node.status === "ok").length;
  const period = data?.period_summary;
  const periodFacts = period ? [
    {
      label: t("GMV ghi nhận / 30 ngày"),
      value: `${COMPACT_VND.format(period.revenue_vnd)}₫`,
      note: tf("{recognized}/{total} đơn được ghi nhận", {
        recognized: period.recognized_orders,
        total: period.total_orders,
      }),
      icon: TrendingUp,
      tone: "bg-accent/10 text-accent",
    },
    {
      label: t("Khách hoạt động"),
      value: period.active_customers.toLocaleString("vi-VN"),
      note: tf("{rate}% đã quay lại mua", { rate: period.returning_customer_rate_pct }),
      icon: Users,
      tone: "bg-accent-2/10 text-accent-2",
    },
    {
      label: t("Sau bán hàng"),
      value: tf("{rate}% hoàn", { rate: period.return_rate_pct }),
      note: tf("{rate}% đơn bị huỷ", { rate: period.cancellation_rate_pct }),
      icon: RefreshCcw,
      tone: "bg-warning/10 text-warning",
    },
    {
      label: t("Tồn kho cần xử lý"),
      value: tf("{count} hết hàng", { count: period.out_of_stock_skus }),
      note: tf("{count} SKU sắp thiếu", { count: period.low_stock_skus }),
      icon: PackageX,
      tone: "bg-danger/10 text-danger",
    },
  ] : [];

  return (
    <>
      <div className="dashboard-reveal relative mb-8 flex flex-col gap-4 overflow-hidden rounded-2xl border border-dashed border-accent/25 bg-surface/55 p-5 sm:flex-row sm:items-end sm:justify-between">
        <span className="dashboard-orbit dashboard-orbit-one" aria-hidden="true" />
        <span className="dashboard-orbit dashboard-orbit-two" aria-hidden="true" />
        <div>
          <div className="text-sm font-medium text-text-dim">
            {data?.shop.name ?? "Mây House Official"} · {t("snapshot vận hành liên kết")}
          </div>
          <h1 className="mt-2 text-5xl font-extrabold leading-[1.05] tracking-tight text-text sm:text-6xl">
            {t("Tình hình")} <span className="text-gradient">{t("cửa hàng")}</span>
          </h1>
          <p className="mt-3 max-w-2xl text-base text-text-muted">
            {data
              ? tf("{products} SKU · {customers} khách · {orders} đơn · {reviews} đánh giá.", {
                  products: data.counts.products,
                  customers: data.counts.customers,
                  orders: data.counts.orders,
                  reviews: data.counts.reviews,
                })
              : t("Đang tải snapshot sản phẩm, khách, đơn, tồn kho và đánh giá dùng chung cho mọi feature.")}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="muted">
            {data
              ? tf("Cập nhật {date}", { date: SNAPSHOT_DATE.format(new Date(data.shop.data_as_of)) })
              : t("Đang đồng bộ dữ liệu")}
          </Badge>
          <span className="mono text-xs text-text-muted">
            {tf("{ok}/{total} khu vực ổn định", { ok: okNodes, total: provinces.length })}
          </span>
          <Button asChild size="sm" variant="primary">
            <Link href="/seller/review-intelligence"><Star className="h-3.5 w-3.5" />{t("Phân tích đánh giá")}</Link>
          </Button>
        </div>
      </div>

      {periodFacts.length > 0 && (
        <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {periodFacts.map((fact, index) => {
            const Icon = fact.icon;
            return (
              <div
                key={fact.label}
                className="business-fact dashboard-reveal card-surface flex items-center gap-3 rounded-xl border p-4"
                style={{ animationDelay: `${100 + index * 70}ms` }}
              >
                <span className={`doodle-sticker h-10 w-10 shrink-0 ${fact.tone}`}>
                  <Icon className="h-4 w-4" />
                </span>
                <div className="min-w-0">
                  <p className="text-2xs font-semibold uppercase tracking-wide text-text-dim">{fact.label}</p>
                  <p className="mt-0.5 text-lg font-extrabold text-text">{fact.value}</p>
                  <p className="truncate text-xs text-text-muted">{fact.note}</p>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {kpis.map((kpi, index) => (
          <div
            key={kpi.id}
            className="dashboard-reveal"
            style={{ animationDelay: `${(periodFacts.length ? 380 : 100) + index * 70}ms` }}
          >
            <KpiCard kpi={kpi} />
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="dashboard-reveal lg:col-span-8" style={{ animationDelay: "450ms" }}><TrafficChart data={timeseries} /></div>
        <div className="dashboard-reveal lg:col-span-4" style={{ animationDelay: "520ms" }}><GeoMap nodes={provinces} /></div>
        <div className="dashboard-reveal lg:col-span-12" style={{ animationDelay: "590ms" }}><AlertsTable data={alerts} /></div>
      </div>
    </>
  );
}
