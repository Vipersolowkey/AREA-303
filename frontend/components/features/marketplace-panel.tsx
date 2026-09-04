"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Bot, Check, DatabaseZap, ExternalLink, Loader2, RefreshCw, ShieldCheck, Store } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import {
  beginShopConnect, createSellerAccount, getMarketplacePlatforms,
  getSellerAccounts, getShopConnections, syncShop,
  type MarketplaceId, type MarketplacePlatform, type SellerAccount, type ShopConnection,
} from "@/lib/features";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type MigrationState = {
  phase: "idle" | "preparing" | "syncing" | "done" | "error";
  message: string;
  products: number;
  orders: number;
};
const EMPTY: MigrationState = { phase: "idle", message: "", products: 0, orders: 0 };

export function MarketplacePanel() {
  const { user } = useAuth();
  const [platforms, setPlatforms] = useState<MarketplacePlatform[]>([]);
  const [accounts, setAccounts] = useState<SellerAccount[]>([]);
  const [shops, setShops] = useState<ShopConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [migration, setMigration] = useState<MigrationState>(EMPTY);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [platformRows, accountRows, shopRows] = await Promise.all([
        getMarketplacePlatforms(), getSellerAccounts(), getShopConnections(),
      ]);
      setPlatforms(platformRows ?? []);
      setAccounts(accountRows ?? []);
      setShops(shopRows ?? []);
    } catch {
      setError("Không tải được trạng thái kết nối. Hãy kiểm tra backend rồi thử lại.");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { void load(); }, [load]);
  const connected = useMemo(() => shops.filter((shop) => shop.status === "connected"), [shops]);

  async function ensureAccount(): Promise<SellerAccount | null> {
    if (accounts[0]) return accounts[0];
    setMigration({ ...EMPTY, phase: "preparing", message: "Đang tạo hồ sơ nhập dữ liệu…" });
    const created = await createSellerAccount({
      name: user?.name || "Cửa hàng của tôi", business_type: "individual",
      contact_email: user?.email ?? null,
    });
    if (created) setAccounts([created]);
    return created;
  }

  async function connect(platform: MarketplacePlatform) {
    setWorking(platform.platform);
    setError(null);
    try {
      const account = await ensureAccount();
      if (!account) throw new Error("Không tạo được hồ sơ cửa hàng.");
      const result = await beginShopConnect(account.id, platform.platform as MarketplaceId);
      if (!result.ok) { setError(result.message); return; }
      window.location.assign(result.authorizeUrl);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể bắt đầu kết nối.");
    } finally { setWorking(null); }
  }

  async function migrate(targets = connected) {
    if (!targets.length) { setError("Hãy kết nối ít nhất một gian hàng trước khi nhập dữ liệu."); return; }
    setWorking("migrate");
    setError(null);
    setMigration({ ...EMPTY, phase: "syncing", message: "Đang đọc sản phẩm, tồn kho và đơn hàng 12 tháng…" });
    let products = 0;
    let orders = 0;
    const failures: string[] = [];
    for (const shop of targets) {
      const result = await syncShop(shop.id, 365);
      if (result.ok) {
        products += result.data.products;
        orders += result.data.orders;
        failures.push(...result.data.errors);
      } else failures.push(`${shop.shop_name || shop.platform_label}: ${result.message}`);
    }
    setMigration(failures.length ? {
      phase: "error", message: failures.join(" · "), products, orders,
    } : {
      phase: "done", message: "Dữ liệu đã được chuẩn hoá để các công cụ AI sử dụng.", products, orders,
    });
    setWorking(null);
    await load();
  }

  return (
    <div className="space-y-5">
      <Card className="overflow-hidden border-accent/25 bg-gradient-to-br from-accent/5 via-surface to-info/5 hover:translate-y-0 hover:shadow-none">
        <CardHeader className="border-b border-border/70 px-5 py-5 sm:px-6">
          <div>
            <div className="mb-2 flex items-center gap-2">
              <Badge variant="info"><Bot className="h-3 w-3" /> AI Migration Assistant</Badge>
              <Badge variant="muted">Không map cột thủ công</Badge>
            </div>
            <CardTitle className="text-xl">Đưa dữ liệu cửa hàng vào Cellaxnet</CardTitle>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-text-muted">
              Chỉ cần cấp quyền cho sàn. Hệ thống tự đọc sản phẩm, biến thể, tồn kho và đơn hàng,
              sau đó chuẩn hoá chúng để Copilot hiểu đúng cửa hàng.
            </p>
          </div>
        </CardHeader>
        <CardContent className="p-5 sm:p-6">
          <div className="grid gap-3 md:grid-cols-3">
            {[["1", "Kết nối", "Đăng nhập tại trang chính thức của sàn"], ["2", "Tự đọc dữ liệu", "Không tải file hay chọn cột thủ công"], ["3", "AI sẵn sàng", "Dùng catalogue và lịch sử đơn đã chuẩn hoá"]].map(([step, title, note]) => (
              <div key={step} className="rounded-xl border border-border bg-surface/80 p-4">
                <span className="grid h-7 w-7 place-items-center rounded-full bg-accent text-xs font-bold text-white">{step}</span>
                <p className="mt-3 text-sm font-semibold">{title}</p><p className="mt-1 text-xs leading-5 text-text-muted">{note}</p>
              </div>
            ))}
          </div>
          {migration.phase !== "idle" && (
            <div className={`mt-4 rounded-xl border p-4 ${migration.phase === "error" ? "border-danger/30 bg-danger/5" : "border-accent/25 bg-accent/5"}`}>
              <div className="flex items-start gap-3">
                {migration.phase === "syncing" || migration.phase === "preparing" ? <Loader2 className="mt-0.5 h-5 w-5 animate-spin text-accent" /> : migration.phase === "done" ? <Check className="mt-0.5 h-5 w-5 text-success" /> : <DatabaseZap className="mt-0.5 h-5 w-5 text-danger" />}
                <div><p className="text-sm font-semibold">{migration.message}</p>{(migration.products > 0 || migration.orders > 0) && <p className="mt-1 text-xs text-text-muted">{migration.products} sản phẩm · {migration.orders} đơn hàng</p>}</div>
              </div>
            </div>
          )}
          <Button className="mt-5" onClick={() => void migrate()} disabled={working !== null || connected.length === 0}>
            {working === "migrate" ? <Loader2 className="h-4 w-4 animate-spin" /> : <DatabaseZap className="h-4 w-4" />} Tự động nhập dữ liệu từ {connected.length} gian hàng
          </Button>
        </CardContent>
      </Card>

      {error && <div className="rounded-xl border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">{error}</div>}
      <Card className="hover:translate-y-0 hover:shadow-none">
        <CardHeader>
          <div><CardTitle className="flex items-center gap-2 text-base"><Store className="h-4 w-4 text-accent" /> Nguồn dữ liệu</CardTitle><p className="mt-1 text-xs text-text-muted">Cellaxnet không nhận mật khẩu; bạn cấp quyền tại trang OAuth chính thức của sàn.</p></div>
          <Button variant="ghost" size="sm" onClick={() => void load()} disabled={loading}><RefreshCw className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} /> Làm mới</Button>
        </CardHeader>
        <CardContent>
          {loading ? <div className="grid min-h-40 place-items-center"><Loader2 className="h-6 w-6 animate-spin text-accent" /></div> : (
            <div className="grid gap-3 md:grid-cols-3">
              {platforms.map((platform) => {
                const linked = shops.find((shop) => shop.platform === platform.platform && shop.status === "connected");
                return <article key={platform.platform} className="flex flex-col rounded-xl border border-border bg-surface-2 p-4">
                  <div className="flex items-center justify-between gap-2"><h3 className="font-semibold">{platform.display_name}</h3><Badge variant={linked ? "success" : platform.configured ? "muted" : "warning"}>{linked ? "Đã kết nối" : platform.configured ? "Sẵn sàng" : "Chưa cấu hình"}</Badge></div>
                  <p className="mt-2 min-h-10 text-xs leading-5 text-text-muted">{linked ? `${linked.products} sản phẩm · ${linked.orders} đơn · ${linked.last_synced_at ? new Date(linked.last_synced_at).toLocaleString("vi-VN") : "chưa đồng bộ"}` : platform.configured ? "Cấp quyền một lần, sau đó hệ thống tự đồng bộ." : `Máy chủ còn thiếu: ${platform.missing_settings.join(", ") || "ứng dụng đối tác"}`}</p>
                  {linked ? <Button variant="outline" className="mt-4" onClick={() => void migrate([linked])} disabled={working !== null}><RefreshCw className="h-4 w-4" /> Đồng bộ lại</Button> : <Button className="mt-4" onClick={() => void connect(platform)} disabled={!platform.configured || working !== null}>{working === platform.platform ? <Loader2 className="h-4 w-4 animate-spin" /> : <ExternalLink className="h-4 w-4" />} Kết nối an toàn</Button>}
                </article>;
              })}
            </div>
          )}
          <div className="mt-4 flex items-center gap-2 text-xs text-text-dim"><ShieldCheck className="h-4 w-4" /> Token sàn được mã hoá ở backend; không lưu trong trình duyệt.</div>
        </CardContent>
      </Card>
    </div>
  );
}
