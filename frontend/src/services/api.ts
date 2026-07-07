import type {
  AuditBundle,
  ComplianceReport,
  Control,
  ControlMapping,
  DashboardCoverage,
  DashboardGap,
  DashboardSeverity,
  DashboardTrend,
  NormalizedFinding,
  RawFindingInput,
  RemediationBacklog,
  ReviewQueueItem,
  ScanRun,
  ScanRunSummary,
  ScannerFailureInput,
  VerificationRecord,
} from "../types";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

type QueryValue = string | number | undefined | null;

function buildUrl(path: string, query?: Record<string, QueryValue>) {
  const url = new URL(`${API_BASE_URL}${path}`);
  Object.entries(query || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  });
  return url.toString();
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  query?: Record<string, QueryValue>,
): Promise<T> {
  const response = await fetch(buildUrl(path, query), {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!response.ok) {
    let message = `Request failed with ${response.status}`;
    try {
      const payload = await response.json();
      message = payload?.detail?.message || payload?.detail?.error?.message || payload?.detail || message;
    } catch {
      // Keep status-based message.
    }
    throw new ApiError(String(message), response.status);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  readiness: () => request<{ status: string; database: string }>("/readiness"),
  dashboard: {
    coverage: () => request<DashboardCoverage>("/dashboard/control-coverage"),
    severity: () => request<DashboardSeverity>("/dashboard/severity-distribution"),
    gap: () => request<DashboardGap>("/dashboard/gap-summary"),
    backlog: () => request<RemediationBacklog>("/dashboard/remediation-backlog"),
    trends: () => request<DashboardTrend>("/dashboard/trends"),
  },
  scanRuns: {
    list: () => request<ScanRun[]>("/scan-runs"),
    create: (payload: {
      target_environment: string;
      findings: RawFindingInput[];
      scanner_failures: ScannerFailureInput[];
    }) => request<ScanRun>("/scan-runs", { method: "POST", body: JSON.stringify(payload) }),
    summary: (id: number) => request<ScanRunSummary>(`/scan-runs/${id}/summary`),
  },
  findings: {
    list: (query?: Record<string, QueryValue>) => request<NormalizedFinding[]>("/findings", {}, query),
    mappings: (id: number) => request<ControlMapping[]>(`/findings/${id}/mappings`),
  },
  mappings: {
    list: (query?: Record<string, QueryValue>) => request<ControlMapping[]>("/mappings", {}, query),
    verification: (id: number) => request<VerificationRecord[]>(`/mappings/${id}/verification`),
  },
  controls: {
    list: (framework?: string) => request<Control[]>("/controls", {}, { framework }),
  },
  reviewQueue: {
    list: () => request<ReviewQueueItem[]>("/review-queue"),
    approve: (id: number, comments: string) =>
      request<ReviewQueueItem>(`/review-queue/${id}/approve`, {
        method: "POST",
        body: JSON.stringify({ reviewer_id: "frontend-operator", comments }),
      }),
    reject: (id: number, comments: string) =>
      request<ReviewQueueItem>(`/review-queue/${id}/reject`, {
        method: "POST",
        body: JSON.stringify({ reviewer_id: "frontend-operator", comments }),
      }),
  },
  reports: {
    list: () => request<ComplianceReport[]>("/reports"),
    create: (type: "engineering" | "leadership", scanRunId: number) =>
      request<ComplianceReport>(`/reports/${type}`, {
        method: "POST",
        body: JSON.stringify({ scan_run_id: scanRunId }),
      }),
    downloadUrl: (id: number) => buildUrl(`/reports/${id}/pdf`),
  },
  auditBundles: {
    list: () => request<AuditBundle[]>("/audit-bundles"),
    create: (scanRunId: number) =>
      request<AuditBundle>("/audit-bundles", {
        method: "POST",
        body: JSON.stringify({ scan_run_id: scanRunId }),
      }),
    downloadUrl: (id: number) => buildUrl(`/audit-bundles/${id}/download`),
  },
};
