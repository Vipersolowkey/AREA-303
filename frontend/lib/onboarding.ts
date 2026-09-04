import { api } from "@/lib/api";

export type WorkspaceReadiness = {
  ready: boolean;
  total_records: number;
  manual_records: number;
  marketplace_records: number;
  shops: Array<{ platform: string; shop_name: string | null; status: string; last_synced_at: string | null }>;
};

export type ImportRow = {
  row_number: number;
  raw_values: Record<string, string>;
  normalized_values: Record<string, unknown> | null;
  errors: string[];
  is_valid: boolean;
};

export type ImportBatch = {
  id: number;
  dataset_type: "products" | "orders";
  filename: string;
  status: "draft" | "validated" | "committed";
  headers: string[];
  mapping: Record<string, string> | null;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  rows: ImportRow[];
};

export type WorkspaceProduct = {
  id: string;
  sku: string;
  name: string;
  price_vnd: number;
  stock: number;
  category: string;
};

export async function getWorkspaceProducts(): Promise<WorkspaceProduct[]> {
  const response = await api.get<WorkspaceProduct[]>("/onboarding/products");
  return response.data ?? [];
}

export async function getWorkspaceReadiness(workspaceId: number): Promise<WorkspaceReadiness> {
  const response = await api.get<WorkspaceReadiness>(`/onboarding/readiness/${workspaceId}`);
  if (!response.data) throw new Error("Không nhận được trạng thái dữ liệu workspace.");
  return response.data;
}

export async function previewImport(datasetType: "products" | "orders", file: File): Promise<ImportBatch> {
  const body = new FormData();
  body.append("dataset_type", datasetType);
  body.append("file", file);
  const response = await api.postForm<ImportBatch>("/onboarding/imports/preview", body);
  if (!response.data) throw new Error("Không nhận được preview import.");
  return response.data;
}

export async function validateImport(importId: number, mapping: Record<string, string>): Promise<ImportBatch> {
  const response = await api.post<ImportBatch>(`/onboarding/imports/${importId}/validate`, { mapping });
  if (!response.data) throw new Error("Không nhận được kết quả validation.");
  return response.data;
}

export async function confirmImport(importId: number): Promise<WorkspaceReadiness> {
  const response = await api.post<{ readiness: WorkspaceReadiness }>(`/onboarding/imports/${importId}/confirm`, {});
  if (!response.data) throw new Error("Không xác nhận được import.");
  return response.data.readiness;
}

export async function beginMarketplaceConnect(platform: "shopee" | "lazada" | "tiktok"): Promise<string> {
  const response = await api.post<{ authorize_url: string }>("/onboarding/marketplace/connect", { platform });
  if (!response.data?.authorize_url) throw new Error("Không nhận được URL kết nối sàn.");
  return response.data.authorize_url;
}
