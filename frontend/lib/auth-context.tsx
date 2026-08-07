"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import {
  claimsToUser,
  claimsValid,
  clearTokenCookie,
  decodeJwtPayload,
  readTokenCookie,
  writeTokenCookie,
  type AuthUser,
} from "@/lib/auth-token";

type AuthState = {
  user: AuthUser | null;
  /** True only for role "admin" — the gate for the whole seller portal. */
  isAdmin: boolean;
  /** True while a login/register request is in flight. */
  busy: boolean;
  login: (email: string, password: string) => Promise<AuthUser>;
  register: (email: string, password: string, name?: string) => Promise<AuthUser>;
  logout: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

type TokenPayload = { access_token: string; token_type: string; user: AuthUser };

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  // Seed from the cookie synchronously so the first paint already knows who
  // the user is — no /auth/me round trip on every page load, and no flash of
  // "logged out" chrome for a signed-in admin.
  const [user, setUser] = useState<AuthUser | null>(() => {
    const token = readTokenCookie();
    if (!token) return null;
    const claims = decodeJwtPayload(token);
    return claimsValid(claims) ? claimsToUser(claims!) : null;
  });
  const [busy, setBusy] = useState(false);

  // Drop an expired/garbage cookie left over from a previous session.
  useEffect(() => {
    const token = readTokenCookie();
    if (token && !claimsValid(decodeJwtPayload(token))) {
      clearTokenCookie();
      setUser(null);
    }
  }, []);

  const authenticate = useCallback(
    async (path: "/auth/login" | "/auth/register", body: unknown) => {
      setBusy(true);
      try {
        const env = await api.post<TokenPayload>(path, body);
        const data = env.data as TokenPayload;
        writeTokenCookie(data.access_token);
        setUser(data.user);
        return data.user;
      } finally {
        setBusy(false);
      }
    },
    [],
  );

  const value = useMemo<AuthState>(
    () => ({
      user,
      isAdmin: user?.role === "admin",
      busy,
      login: (email, password) => authenticate("/auth/login", { email, password }),
      register: (email, password, name) =>
        authenticate("/auth/register", { email, password, name: name || null }),
      logout: () => {
        clearTokenCookie();
        setUser(null);
        router.replace("/shop");
      },
    }),
    [user, busy, authenticate, router],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>.");
  return ctx;
}
