import { QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  AuditRow, CaseDetail, CaseRow, Drift, FeedRow, Investigation, ModelInfo, Overview, PolicyAnswer,
  ScoreResult, Traffic,
} from "./types";

const KEY_STORAGE = "sentinel.apiKey";

export function getKey(): string {
  try {
    return localStorage.getItem(KEY_STORAGE) ?? "";
  } catch {
    return "";
  }
}

export function setKey(key: string | null) {
  try {
    if (key) localStorage.setItem(KEY_STORAGE, key);
    else localStorage.removeItem(KEY_STORAGE);
  } catch {
    /* storage unavailable: key lives for this tab only */
  }
  window.dispatchEvent(new Event("sentinel-auth"));
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export const VIEW_ONLY = "View-only mode: sign in with an API key to make changes.";
// Writes a visitor may still make without a key (the server treats them as reads)
const OPEN_WRITES = ["/v1/policy/ask"];

export async function api<T>(path: string, init?: RequestInit & { json?: unknown; key?: string }): Promise<T> {
  const key = init?.key ?? getKey();
  const method = (init?.method ?? "GET").toUpperCase();
  if (!key && method !== "GET" && !OPEN_WRITES.includes(path)) throw new ApiError(401, VIEW_ONLY);
  const headers: Record<string, string> = key ? { "X-API-Key": key } : {};
  let body = init?.body;
  if (init?.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(init.json);
  }
  const res = await fetch(path, { ...init, headers, body });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j);
    } catch {
      /* not JSON */
    }
    if (res.status === 401 && !init?.key && key) setKey(null);
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (n, err) => !(err instanceof ApiError && [401, 404, 422].includes(err.status)) && n < 2,
      refetchOnWindowFocus: false,
    },
  },
});

const LIVE = 2000;

export const useOverview = (minutes = 30) =>
  useQuery({ queryKey: ["overview", minutes], queryFn: () => api<Overview>(`/v1/console/overview?minutes=${minutes}`), refetchInterval: LIVE });

export const useFeed = (limit = 40, flagged = false) =>
  useQuery({
    queryKey: ["feed", limit, flagged],
    queryFn: () => api<FeedRow[]>(`/v1/console/feed?limit=${limit}&flagged=${flagged}`),
    refetchInterval: LIVE,
  });

export const useCases = (status: string, limit = 300) =>
  useQuery({ queryKey: ["cases", status, limit], queryFn: () => api<CaseRow[]>(`/v1/cases?status=${status}&limit=${limit}`), refetchInterval: 4000 });

export const useCase = (id: number | null) =>
  useQuery({ queryKey: ["case", id], queryFn: () => api<CaseDetail>(`/v1/console/cases/${id}`), enabled: id != null });

export const useInvestigations = (limit = 30, actor?: string) =>
  useQuery({
    queryKey: ["investigations", limit, actor],
    queryFn: () =>
      api<{ items: Investigation[]; actors: string[] }>(
        `/v1/console/investigations?limit=${limit}${actor ? `&actor=${encodeURIComponent(actor)}` : ""}`,
      ),
    refetchInterval: LIVE,
  });

export const useInvestigationsSince = (since: number) =>
  useQuery({
    queryKey: ["investigations-since", Math.floor(since / 60)],
    queryFn: () => api<{ items: Investigation[] }>(`/v1/console/investigations?limit=500&since=${since}`),
    refetchInterval: 5000,
  });

export const useModel = () => useQuery({ queryKey: ["model"], queryFn: () => api<ModelInfo>("/v1/console/model") });
export const useDrift = () => useQuery({ queryKey: ["drift"], queryFn: () => api<Drift>("/v1/drift"), refetchInterval: 15000 });
export const useAudit = (limit = 60) =>
  useQuery({ queryKey: ["audit", limit], queryFn: () => api<AuditRow[]>(`/v1/console/audit?limit=${limit}`), refetchInterval: 4000 });
export const useConnect = () =>
  useQuery({ queryKey: ["connect"], queryFn: () => api<{ mcp: unknown; tools: string[] }>("/v1/console/connect") });

export function useTraffic() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<Traffic>) => api<Traffic>("/v1/console/traffic", { method: "POST", json: body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["overview"] }),
  });
}

export function useResolve(caseId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { is_fraud: boolean; analyst: string; notes: string }) =>
      api<{ case_id: number; status: string }>(`/v1/cases/${caseId}/resolve`, { method: "POST", json: body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["case", caseId] });
      qc.invalidateQueries({ queryKey: ["cases"] });
    },
  });
}

export const scoreTransaction = (body: Record<string, unknown>) =>
  api<ScoreResult>("/v1/transactions", { method: "POST", json: body });

export const askPolicy = (question: string) =>
  api<PolicyAnswer>("/v1/policy/ask", { method: "POST", json: { question } });

export const runRetrain = () => api<{ decision: string; reason: string; challenger: string; champion: string }>(
  "/v1/console/retrain", { method: "POST" });
