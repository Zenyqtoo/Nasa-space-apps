import type {
  Analysis,
  AppConfig,
  CompareRequest,
  Comparison,
  DemoField,
  FieldRequest,
  Job,
  LandingFact,
  LayerResponse,
  ReportRequest,
  RulesCatalog,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(`/api${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "network");
  }
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = (await resp.json()) as { detail?: unknown };
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* тело не JSON */
    }
    throw new ApiError(resp.status, detail);
  }
  return (await resp.json()) as T;
}

const post = <T>(path: string, body: unknown) => request<T>(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  health: () => request<{ status: string; offline: boolean; earthdata: boolean; demo: boolean }>("/health"),
  config: () => request<AppConfig>("/config"),
  demo: () => request<DemoField>("/demo"),
  analyze: (req: FieldRequest) => post<Analysis>("/field/analyze", req),
  compare: (req: CompareRequest) => post<Comparison>("/rotations/compare", req),
  job: (id: string) => request<Job>(`/jobs/${encodeURIComponent(id)}`),
  layer: (kind: string, bbox: number[], date?: string) =>
    request<LayerResponse>(`/layers/${kind}?bbox=${bbox.join(",")}${date ? `&date=${date}` : ""}`),
  rules: () => request<RulesCatalog>("/rules"),
  landing: () => request<{ facts: Record<string, LandingFact> }>("/content/landing"),
  retro: () => request<{ fields: RetroField[] }>("/retro"),
  retroSubmit: (body: unknown) => post<{ status: string; id: string }>("/retro/submissions", body),
  async reportPdf(req: ReportRequest): Promise<Blob> {
    const resp = await fetch("/api/report/pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    });
    if (!resp.ok) throw new ApiError(resp.status, await resp.text());
    return resp.blob();
  },
};

export interface RetroField {
  id: string;
  name: string;
  region: string;
  geometry: FieldRequest["geometry"];
  history: { year: number; crop: string }[];
  evidence: string;
}
