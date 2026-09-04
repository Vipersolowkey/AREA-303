"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Check, ChevronRight, FileSpreadsheet, Loader2, Store, Upload, Wifi } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { setActiveWorkspaceId } from "@/lib/active-workspace";
import { ApiClientError } from "@/lib/api";
import { createWorkspace, listWorkspaces, type SellerWorkspace } from "@/lib/workspaces";
import { beginMarketplaceConnect, confirmImport, getWorkspaceReadiness, previewImport, validateImport, type ImportBatch, type WorkspaceReadiness } from "@/lib/onboarding";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

const FIELDS = { products: ["sku", "name", "price", "stock", "category"], orders: ["order_id", "ordered_at", "total_amount", "status"] } as const;
const LABEL: Record<string, string> = { sku: "SKU / mã sản phẩm *", name: "Tên sản phẩm *", price: "Giá bán *", stock: "Tồn kho *", category: "Danh mục", order_id: "Mã đơn *", ordered_at: "Thời điểm đặt *", total_amount: "Tổng tiền *", status: "Trạng thái" };

function message(error: unknown) {
  if (error instanceof ApiClientError) return error.envelope.error?.message ?? "Không thể xử lý yêu cầu.";
  return error instanceof Error ? error.message : "Không kết nối được máy chủ.";
}

function guessMapping(headers: string[], type: "products" | "orders") {
  const aliases: Record<string, string[]> = { sku: ["sku", "mã", "ma"], name: ["name", "tên", "ten", "sản phẩm"], price: ["price", "giá", "gia"], stock: ["stock", "tồn", "ton", "quantity"], category: ["category", "danh mục"], order_id: ["order", "mã đơn", "ma don"], ordered_at: ["date", "ngày", "ngay", "thời gian"], total_amount: ["total", "tổng", "tong", "amount"], status: ["status", "trạng thái"] };
  return Object.fromEntries(FIELDS[type].map((field) => [field, headers.find((header) => aliases[field].some((alias) => header.toLowerCase().includes(alias))) ?? ""]));
}

export default function SellerOnboardingPage() {
  const router = useRouter();
  const { acceptAccessToken, logout } = useAuth();
  const [workspaces, setWorkspaces] = useState<SellerWorkspace[]>([]);
  const [readiness, setReadiness] = useState<Record<number, WorkspaceReadiness>>({});
  const [name, setName] = useState("");
  const [selected, setSelected] = useState<SellerWorkspace | null>(null);
  const [datasetType, setDatasetType] = useState<"products" | "orders">("products");
  const [batch, setBatch] = useState<ImportBatch | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    setLoading(true);
    try {
      const list = await listWorkspaces();
      setWorkspaces(list);
      const statuses = await Promise.all(list.map(async (workspace) => [workspace.id, await getWorkspaceReadiness(workspace.id)] as const));
      setReadiness(Object.fromEntries(statuses));
    } catch (err) { setError(message(err)); } finally { setLoading(false); }
  };
  useEffect(() => { void refresh(); }, []);

  const selectedReadiness = selected ? readiness[selected.id] : null;
  const valid = batch?.status === "validated" && batch.invalid_rows === 0 && batch.valid_rows > 0;
  const visibleRows = useMemo(() => batch?.rows ?? [], [batch]);

  async function create(event: React.FormEvent) {
    event.preventDefault(); if (!name.trim()) return;
    setBusy(true); setError(null);
    try {
      const result = await createWorkspace({ name: name.trim() });
      acceptAccessToken(result.auth.access_token); setActiveWorkspaceId(result.workspace.id);
      setWorkspaces((current) => [result.workspace, ...current]);
      setReadiness((current) => ({ ...current, [result.workspace.id]: { ready: false, total_records: 0, manual_records: 0, marketplace_records: 0, shops: [] } }));
      setSelected(result.workspace); setName("");
    } catch (err) { setError(message(err)); } finally { setBusy(false); }
  }
  function openData(workspace: SellerWorkspace) { setActiveWorkspaceId(workspace.id); setSelected(workspace); setBatch(null); setMapping({}); setError(null); }
  async function upload(file: File | undefined) {
    if (!file || !selected) return; setBusy(true); setError(null);
    try { const next = await previewImport(datasetType, file); setBatch(next); setMapping(guessMapping(next.headers, datasetType)); } catch (err) { setError(message(err)); } finally { setBusy(false); }
  }
  async function validate() { if (!batch) return; setBusy(true); setError(null); try { setBatch(await validateImport(batch.id, mapping)); } catch (err) { setError(message(err)); } finally { setBusy(false); } }
  async function confirm() {
    if (!batch || !selected) return; setBusy(true); setError(null);
    try { const status = await confirmImport(batch.id); setReadiness((current) => ({ ...current, [selected.id]: status })); setBatch(null); } catch (err) { setError(message(err)); } finally { setBusy(false); }
  }
  async function connect(platform: "shopee" | "lazada" | "tiktok") {
    if (!selected) return; setBusy(true); setError(null);
    try { window.location.assign(await beginMarketplaceConnect(platform)); } catch (err) { setError(message(err)); setBusy(false); }
  }

  return <main className="min-h-screen bg-bg px-4 py-8 text-text sm:px-6 lg:py-14"><div className="mx-auto max-w-5xl">
    <header className="mb-8 flex items-center justify-between gap-4"><Link href="/shop" className="text-sm text-text-muted hover:text-text">← Cửa hàng</Link><button onClick={logout} className="text-sm text-text-muted hover:text-text">Đăng xuất</button></header>
    <Badge variant="info">Onboarding dữ liệu thật</Badge><h1 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">Kết nối dữ liệu trước khi vào workspace</h1>
    <p className="mt-3 max-w-3xl text-sm leading-6 text-text-muted">Workspace chỉ mở khi đã có ít nhất một sản phẩm hoặc đơn hàng hợp lệ từ sàn, CSV hoặc Excel. Không có dữ liệu mẫu và không tự điền dữ liệu thay bạn.</p>
    {error && <div className="mt-5 rounded-xl border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">{error}</div>}
    {selected ? <section className="mt-8 space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-sm text-text-muted">Đang thiết lập</p><h2 className="text-xl font-bold">{selected.name}</h2></div><Button variant="outline" onClick={() => setSelected(null)}>Đổi workspace</Button></div>
      {selectedReadiness?.ready ? <Card><CardContent className="flex flex-wrap items-center justify-between gap-4 pt-6"><div className="flex gap-3"><Check className="mt-0.5 h-5 w-5 text-success"/><div><p className="font-semibold">Dữ liệu cửa hàng đã hợp lệ</p><p className="mt-1 text-sm text-text-muted">{selectedReadiness.total_records} bản ghi đã được xác nhận.</p></div></div><Button onClick={() => { setActiveWorkspaceId(selected.id); router.push("/seller/workspace"); }}>Vào workspace <ChevronRight className="h-4 w-4" /></Button></CardContent></Card> : <>
        <div className="grid gap-5 md:grid-cols-2">
          <Card><CardHeader><div><CardTitle className="text-base">1. Kết nối sàn</CardTitle><p className="mt-1 text-xs text-text-muted">Đăng nhập và cấp quyền trên sàn. Sau đó hệ thống đồng bộ dữ liệu thật để kiểm tra.</p></div><Wifi className="h-5 w-5 text-accent"/></CardHeader><CardContent className="grid gap-2"><Button onClick={() => void connect("tiktok")} disabled={busy}>Kết nối TikTok Shop</Button><Button variant="outline" onClick={() => void connect("lazada")} disabled={busy}>Kết nối Lazada</Button><Button variant="outline" onClick={() => void connect("shopee")} disabled={busy}>Kết nối Shopee</Button></CardContent></Card>
          <Card><CardHeader><div><CardTitle className="text-base">2. Import CSV / Excel</CardTitle><p className="mt-1 text-xs text-text-muted">Map cột, xem trước, sửa lỗi từng dòng rồi mới xác nhận ghi.</p></div><FileSpreadsheet className="h-5 w-5 text-accent"/></CardHeader><CardContent className="space-y-3"><select value={datasetType} onChange={(e) => { setDatasetType(e.target.value as typeof datasetType); setBatch(null); }} className="h-10 w-full rounded-xl border border-border bg-surface px-3 text-sm"><option value="products">Sản phẩm và tồn kho</option><option value="orders">Đơn hàng</option></select><label className="flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-border px-4 py-5 text-sm hover:border-accent"><Upload className="h-4 w-4"/>{busy ? "Đang đọc tệp..." : "Chọn .csv, .xlsx hoặc .xlsm"}<input type="file" className="sr-only" accept=".csv,.xlsx,.xlsm" disabled={busy} onChange={(e) => void upload(e.target.files?.[0])}/></label></CardContent></Card>
        </div>
        {batch && <Card><CardHeader><div><CardTitle className="text-base">Map cột và kiểm tra: {batch.filename}</CardTitle><p className="mt-1 text-xs text-text-muted">{batch.total_rows} dòng đang nằm ở vùng chờ; chưa ghi vào dữ liệu cửa hàng.</p></div><Badge variant="warning">Chưa ghi DB</Badge></CardHeader><CardContent className="space-y-5"><div className="grid gap-3 sm:grid-cols-2">{FIELDS[batch.dataset_type].map((field) => <label key={field} className="text-sm"><span className="mb-1 block font-medium">{LABEL[field]}</span><select value={mapping[field] ?? ""} onChange={(e) => setMapping((current) => ({...current, [field]: e.target.value}))} className="h-10 w-full rounded-xl border border-border bg-surface px-3"><option value="">Không map</option>{batch.headers.map((header) => <option key={header} value={header}>{header}</option>)}</select></label>)}</div><Button onClick={() => void validate()} disabled={busy}>{busy && <Loader2 className="h-4 w-4 animate-spin"/>}Chạy validation</Button>
          {batch.status === "validated" && <><div className="rounded-xl border border-border bg-surface-2 p-3 text-sm"><span className="font-semibold text-success">{batch.valid_rows} hợp lệ</span><span className="mx-2 text-text-dim">·</span><span className={batch.invalid_rows ? "font-semibold text-danger" : "text-text-muted"}>{batch.invalid_rows} lỗi</span></div><div className="max-h-80 overflow-auto rounded-xl border border-border"><table className="w-full text-left text-xs"><thead className="sticky top-0 bg-surface text-text-muted"><tr><th className="p-3">Dòng</th><th className="p-3">Dữ liệu</th><th className="p-3">Kết quả</th></tr></thead><tbody>{visibleRows.map((row) => <tr key={row.row_number} className="border-t border-border align-top"><td className="p-3">{row.row_number}</td><td className="max-w-80 p-3 break-words">{Object.entries(row.raw_values).map(([k,v]) => <div key={k}><span className="text-text-dim">{k}: </span>{v || "—"}</div>)}</td><td className="p-3">{row.is_valid ? <span className="text-success">Hợp lệ</span> : <ul className="space-y-1 text-danger">{row.errors.map((e) => <li key={e}>{e}</li>)}</ul>}</td></tr>)}</tbody></table></div><Button onClick={() => void confirm()} disabled={busy || !valid}>{busy && <Loader2 className="h-4 w-4 animate-spin"/>}Xác nhận ghi {batch.valid_rows} dòng vào workspace</Button>{batch.invalid_rows > 0 && <p className="text-xs text-danger">Cần sửa tệp và upload lại đến khi mọi dòng đều hợp lệ.</p>}</>}</CardContent></Card>}
      </>}
    </section> : <section className="mt-8 grid gap-6 lg:grid-cols-[1.1fr_.9fr]"><Card><CardHeader><div><CardTitle className="text-base">Workspace hiện có</CardTitle><p className="mt-1 text-xs text-text-muted">Chỉ workspace có dữ liệu hợp lệ mới có nút vào.</p></div><Store className="h-5 w-5 text-accent"/></CardHeader><CardContent>{loading ? <Loader2 className="mx-auto my-8 h-5 w-5 animate-spin"/> : workspaces.length ? <div className="space-y-3">{workspaces.map((workspace) => { const state = readiness[workspace.id]; return <div key={workspace.id} className="rounded-xl border border-border bg-surface-2 p-4"><div className="flex items-start justify-between gap-3"><div><p className="font-semibold">{workspace.name}</p><p className="mt-1 text-xs text-text-muted">{state ? `${state.total_records} bản ghi hợp lệ` : "Đang kiểm tra dữ liệu..."}</p></div><Badge variant={state?.ready ? "success" : "warning"}>{state?.ready ? "Sẵn sàng" : "Cần dữ liệu"}</Badge></div><Button className="mt-4 w-full" variant={state?.ready ? "default" : "outline"} disabled={!state} onClick={() => state?.ready ? (setActiveWorkspaceId(workspace.id), router.push("/seller/workspace")) : openData(workspace)}>{state?.ready ? "Vào workspace" : "Nạp dữ liệu"}</Button></div>; })}</div> : <p className="py-7 text-center text-sm text-text-muted">Chưa có workspace.</p>}</CardContent></Card><Card><CardHeader><CardTitle className="text-base">Tạo cửa hàng</CardTitle></CardHeader><CardContent><form onSubmit={create} className="space-y-4"><div><label className="mb-1.5 block text-sm font-medium" htmlFor="store-name">Tên cửa hàng</label><Input id="store-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Ví dụ: Minh Anh Fashion" maxLength={120}/></div><p className="text-xs leading-5 text-text-muted">Sau khi tạo, bạn sẽ kết nối sàn hoặc import file thật. Workspace chưa có dữ liệu sẽ chưa thể truy cập.</p><Button type="submit" className="w-full" disabled={busy || name.trim().length < 2}>{busy && <Loader2 className="h-4 w-4 animate-spin"/>}Tạo và nạp dữ liệu</Button></form></CardContent></Card></section>}
  </div></main>;
}
