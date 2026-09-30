import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { api } from "./client";

export const keys = {
  status: ["status"] as const,
  shelf: ["shelf"] as const,
  series: (name: string) => ["series", name] as const,
  episode: (name: string, ep: string) => ["episode", name, ep] as const,
  glossary: (name: string) => ["glossary", name] as const,
  notes: (name: string) => ["notes", name] as const,
  assets: ["assets"] as const,
};

export const useStatus = () => useQuery({ queryKey: keys.status, queryFn: api.status, staleTime: 30_000 });
export const useShelf = () => useQuery({ queryKey: keys.shelf, queryFn: api.shelf });
export const useSeries = (name: string) => useQuery({ queryKey: keys.series(name), queryFn: () => api.series(name) });

/** 有工作在跑的時候每秒更新一次，頁面狀態與進度條會跟著前進。 */
export const useEpisode = (name: string, ep: string) =>
  useQuery({
    queryKey: keys.episode(name, ep),
    queryFn: () => api.episode(name, ep),
    refetchInterval: (q) => (q.state.data?.job ? 1000 : false),
  });

export const useGlossary = (name: string) =>
  useQuery({ queryKey: keys.glossary(name), queryFn: () => api.glossary(name) });
export const useNotes = (name: string) => useQuery({ queryKey: keys.notes(name), queryFn: () => api.notes(name) });
export const useAssets = () => useQuery({ queryKey: keys.assets, queryFn: api.assets });

/** 素材網址帶版本號，替換圖片後介面上的圖會立刻更新。 */
export function useAssetUrl(id: string): string {
  const { data } = useAssets();
  return data?.find((a) => a.id === id)?.url ?? `/api/assets/${id}/file`;
}

export function useInvalidateSeries() {
  const qc = useQueryClient();
  return useCallback(
    (name: string) => {
      qc.invalidateQueries({ queryKey: keys.shelf });
      qc.invalidateQueries({ queryKey: keys.series(name) });
      qc.invalidateQueries({ queryKey: ["episode", name] });
      qc.invalidateQueries({ queryKey: keys.glossary(name) });
    },
    [qc],
  );
}
