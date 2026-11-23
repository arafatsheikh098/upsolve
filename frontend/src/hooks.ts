import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, type SyncStatus } from "./api";

const inFlight = (s?: SyncStatus) => s?.sync_state === "queued" || s?.sync_state === "syncing";

/** Ask the server to sync a handle, then poll its status until the sync settles. */
export function useSyncedHandle(handle: string | undefined) {
  const key = handle?.toLowerCase() ?? "";
  const sync = useQuery({
    queryKey: ["sync", key],
    queryFn: () => api.sync(handle!),
    enabled: !!handle,
    staleTime: 60_000,
    retry: false,
  });
  const status = useQuery({
    queryKey: ["status", key],
    queryFn: () => api.status(handle!),
    enabled: !!sync.data,
    initialData: sync.data,
    refetchInterval: (q) => (inFlight(q.state.data) ? 1500 : false),
  });
  const s = status.data ?? sync.data;
  return {
    status: s,
    error: sync.error ?? status.error,
    syncing: inFlight(s),
    ready: !!s?.last_synced_at,
    resync: () => sync.refetch(),
  };
}

export function useAnalysis(handle: string | undefined, syncedAt: string | null | undefined) {
  return useQuery({
    queryKey: ["analysis", handle?.toLowerCase(), syncedAt],
    queryFn: () => api.analysis(handle!),
    enabled: !!handle && !!syncedAt,
    placeholderData: (prev) => prev,
  });
}

export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: api.me, retry: false, staleTime: 5 * 60_000 });
}

export function useLogout() {
  const qc = useQueryClient();
  return async () => {
    await api.logout();
    qc.setQueryData(["me"], null);
    qc.removeQueries({ queryKey: ["plan"] });
    qc.removeQueries({ queryKey: ["progress"] });
    qc.invalidateQueries({ queryKey: ["me"] });
  };
}

export type Theme = "system" | "light" | "dark";

export function useTheme(): [Theme, (t: Theme) => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    try {
      const t = localStorage.getItem("upsolve-theme");
      return t === "light" || t === "dark" ? t : "system";
    } catch {
      return "system";
    }
  });
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") delete root.dataset.theme;
    else root.dataset.theme = theme;
    try {
      if (theme === "system") localStorage.removeItem("upsolve-theme");
      else localStorage.setItem("upsolve-theme", theme);
    } catch {
      /* storage unavailable: the choice just won't persist */
    }
  }, [theme]);
  return [theme, setTheme];
}
