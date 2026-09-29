import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { PageLoader } from "../components/ui";
import type { MessageKey, Translate } from "../i18n";
import { en } from "../i18n/en";
import { api, ApiError } from "./api";
import type { AppConfig, Me } from "./types";

export function useConfig() {
  return useQuery({ queryKey: ["config"], queryFn: () => api.get<AppConfig>("/api/config"), staleTime: Infinity });
}

export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: () => api.get<Me>("/api/me"), retry: false, staleTime: 60_000 });
}

/** The signed-in user; only call inside <RequireAuth>. */
export function useUser(): Me {
  const { data } = useMe();
  if (!data) throw new Error("useUser outside RequireAuth");
  return data;
}

export function RequireAuth({ children, admin }: { children: ReactNode; admin?: boolean }) {
  const { data, isLoading, error } = useMe();
  const location = useLocation();
  if (isLoading) return <PageLoader />;
  if (error || !data) {
    const expired = error instanceof ApiError && error.status === 403;
    return <Navigate to={expired ? "/login?expired=1" : "/login"} replace state={{ from: location.pathname }} />;
  }
  // A temporary password must be replaced before anything else.
  if (data.must_change_password && location.pathname !== "/password") return <Navigate to="/password" replace />;
  if (admin && !data.is_admin) return <Navigate to="/" replace />;
  return <>{children}</>;
}

export function useLogout() {
  const qc = useQueryClient();
  return async () => {
    try {
      await api.post("/api/auth/logout");
    } finally {
      qc.clear();
      window.location.assign("/login");
    }
  };
}

/** Human-readable message for an API error. */
export function errorMessage(err: unknown, t: Translate): string {
  if (err instanceof ApiError) {
    const key = `err.${err.code}` as MessageKey;
    if (key in en) return t(key);
    if (err.status === 403) return t("err.forbidden");
    if (err.status === 404) return t("err.not_found");
  }
  return t("err.generic");
}
