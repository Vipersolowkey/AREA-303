import { api } from "@/lib/api";
import type { AuthUser } from "@/lib/auth-token";

export type WorkspaceRole =
  | "owner"
  | "manager"
  | "analyst"
  | "viewer"
  | "platform_admin";

export type SellerWorkspace = {
  id: number;
  name: string;
  slug: string;
  status: "active" | "suspended" | "archived";
  industry: "fashion" | "beauty" | "home_living" | "electronics" | "other";
  description: string | null;
  target_customer: string | null;
  brand_voice: string | null;
  current_role: WorkspaceRole;
  created_at: string;
  updated_at: string;
};

type TokenPayload = {
  access_token: string;
  token_type: string;
  user: AuthUser;
};

export type WorkspaceCreateResult = {
  workspace: SellerWorkspace;
  auth: TokenPayload;
};

export type WorkspaceMember = {
  user_id: number;
  email: string;
  name: string | null;
  role: Exclude<WorkspaceRole, "platform_admin">;
  joined_at: string;
};

export type MarketplaceShop = {
  id: number;
  workspace_id: number;
  platform: "shopee" | "lazada" | "tiktok_shop";
  external_shop_id: string;
  shop_name: string;
  status: "connected" | "expired" | "revoked" | "error";
  token_expires_at: string | null;
  last_synced_at: string | null;
  last_error: string | null;
  connected_at: string;
  updated_at: string;
};

export async function listWorkspaces(signal?: AbortSignal): Promise<SellerWorkspace[]> {
  const response = await api.get<SellerWorkspace[]>("/workspaces/", signal);
  return response.data ?? [];
}

export type WorkspaceCreateInput = Pick<SellerWorkspace, "name"> &
  Partial<Pick<SellerWorkspace, "industry" | "description" | "target_customer" | "brand_voice">>;

export async function createWorkspace(input: WorkspaceCreateInput): Promise<WorkspaceCreateResult> {
  const response = await api.post<WorkspaceCreateResult>("/workspaces/", input);
  if (!response.data) throw new Error("Workspace response is empty.");
  return response.data;
}

export async function updateWorkspaceProfile(
  workspaceId: number,
  input: Partial<WorkspaceCreateInput>,
): Promise<SellerWorkspace> {
  const response = await api.patch<SellerWorkspace>(`/workspaces/${workspaceId}`, input);
  if (!response.data) throw new Error("Workspace profile response is empty.");
  return response.data;
}

export async function listWorkspaceMembers(
  workspaceId: number,
  signal?: AbortSignal,
): Promise<WorkspaceMember[]> {
  const response = await api.get<WorkspaceMember[]>(
    `/workspaces/${workspaceId}/members`,
    signal,
  );
  return response.data ?? [];
}

export async function addWorkspaceMember(
  workspaceId: number,
  email: string,
  role: "manager" | "analyst" | "viewer",
): Promise<WorkspaceMember> {
  const response = await api.post<WorkspaceMember>(`/workspaces/${workspaceId}/members`, {
    email,
    role,
  });
  if (!response.data) throw new Error("Member response is empty.");
  return response.data;
}

export async function updateWorkspaceMemberRole(
  workspaceId: number,
  userId: number,
  role: WorkspaceMember["role"],
): Promise<WorkspaceMember> {
  const response = await api.patch<WorkspaceMember>(
    `/workspaces/${workspaceId}/members/${userId}`,
    { role },
  );
  if (!response.data) throw new Error("Member response is empty.");
  return response.data;
}

export async function removeWorkspaceMember(
  workspaceId: number,
  userId: number,
): Promise<void> {
  await api.delete(`/workspaces/${workspaceId}/members/${userId}`);
}

export async function listMarketplaceShops(
  workspaceId: number,
  signal?: AbortSignal,
): Promise<MarketplaceShop[]> {
  const response = await api.get<MarketplaceShop[]>(
    `/workspaces/${workspaceId}/shops`,
    signal,
  );
  return response.data ?? [];
}

export async function disconnectMarketplaceShop(
  workspaceId: number,
  shopId: number,
): Promise<MarketplaceShop> {
  const response = await api.delete<MarketplaceShop>(
    `/workspaces/${workspaceId}/shops/${shopId}`,
  );
  if (!response.data) throw new Error("Marketplace shop response is empty.");
  return response.data;
}
