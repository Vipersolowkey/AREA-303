import { DashboardShell } from "@/components/shell/dashboard-shell";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { TrafficChart } from "@/components/dashboard/traffic-chart";
import { AlertsTable } from "@/components/dashboard/incidents-table";
import { GeoMap } from "@/components/dashboard/geo-map-client";
import { KPIS, TIMESERIES, ALERTS, PROVINCES } from "@/lib/mock-data";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Star } from "lucide-react";
import Link from "next/link";

export const dynamic = "force-dynamic";

export default function SellerHome() {
  const okNodes = PROVINCES.filter((n) => n.status === "ok").length;

  return (
    <DashboardShell breadcrumb={[{ label: "Seller", href: "/seller" }, { label: "Overview" }]}>
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="mono text-2xs uppercase tracking-wider text-text-dim">Seller Portal · today</div>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-text">Shop operations</h1>
          <p className="mt-1 text-sm text-text-muted">
            Theo dõi sức khoẻ shop + công cụ AI cho người bán trên Shopee · Tiki · TikTok Shop.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="live"><span className="live-dot" />live</Badge>
          <span className="mono text-xs text-text-muted">{okNodes}/{PROVINCES.length} tỉnh ổn định</span>
          <Button asChild size="sm" variant="primary">
            <Link href="/seller/review-intelligence"><Star className="h-3.5 w-3.5" />Phân tích review</Link>
          </Button>
        </div>
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {KPIS.map((k) => <KpiCard key={k.id} kpi={k} />)}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="lg:col-span-8"><TrafficChart data={TIMESERIES} /></div>
        <div className="lg:col-span-4"><GeoMap nodes={PROVINCES} /></div>
        <div className="lg:col-span-12"><AlertsTable data={ALERTS} /></div>
      </div>
    </DashboardShell>
  );
}
