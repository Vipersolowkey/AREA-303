import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { FeaturePanel } from "@/components/features/feature-registry";
import { findBySlug, IMPLEMENTED, SUBTITLE } from "@/lib/nav";

export const dynamic = "force-dynamic";

export default async function ShopFeaturePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const item = findBySlug(slug);

  if (!item || item.app !== "shop") {
    return (
      <div className="card-surface rounded-lg border p-10 text-center">
        <p className="text-lg font-bold">Không tìm thấy trang này</p>
        <Link href="/shop" className="mt-3 inline-block font-semibold text-accent">← Về trang chủ</Link>
      </div>
    );
  }

  const Icon = item.icon;

  return (
    <div className="space-y-6">
      <div className="flex items-start gap-4">
        <span className="grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-accent/10 text-accent">
          <Icon className="h-5 w-5" />
        </span>
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight">{item.label}</h1>
          <p className="mt-1 max-w-2xl text-text-muted">{SUBTITLE[slug] ?? "Tính năng mua sắm."}</p>
        </div>
      </div>

      {IMPLEMENTED.has(slug) ? (
        <FeaturePanel slug={slug} />
      ) : (
        <div className="card-surface rounded-lg border p-10 text-center">
          <div className="text-4xl">🛠️</div>
          <p className="mt-3 text-lg font-bold">Sắp ra mắt</p>
          <p className="mt-1 text-text-muted">Tính năng này đang được hoàn thiện. Quay lại sau nhé!</p>
          <Link href="/shop" className="mt-4 inline-flex items-center gap-1.5 font-semibold text-accent">
            <ArrowLeft className="h-4 w-4" /> Khám phá tính năng khác
          </Link>
        </div>
      )}
    </div>
  );
}
