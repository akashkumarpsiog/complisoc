import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ComplianceScoreCard, ComplianceInsightsPanel } from "./ComplianceScore";

const mockUseResource = vi.fn();

vi.mock("../services/api", () => ({
  api: {
    dashboard: {
      coverage: { data: null, status: "idle", error: null, reload: vi.fn() },
      aiMetrics: { data: null, status: "idle", error: null, reload: vi.fn() },
      gap: { data: null, status: "idle", error: null, reload: vi.fn() },
      severity: { data: null, status: "idle", error: null, reload: vi.fn() },
      trends: { data: null, status: "idle", error: null, reload: vi.fn() },
    },
  },
}));

vi.mock("../hooks/useResource", () => ({
  useResource: () => mockUseResource(),
}));

describe("ComplianceScoreCard", () => {
  it("renders loading state when data is not available", () => {
    mockUseResource.mockReturnValue({ data: null, status: "loading", error: null, reload: vi.fn() });
    render(<ComplianceScoreCard />);
    expect(screen.getByText("Loading")).toBeInTheDocument();
  });

  it("renders independent metrics when data is available", () => {
    const reload = vi.fn();
    mockUseResource.mockReturnValueOnce({ data: { total_mappings: 50, published_mappings: 40, avg_final_confidence: 0.85 }, status: "success", error: null, reload });
    mockUseResource.mockReturnValueOnce({ data: { manual_review_mappings: 5, rejected_mappings: 3 }, status: "success", error: null, reload });
    mockUseResource.mockReturnValueOnce({ data: { severity_counts: { high: 2, critical: 1, low: 7 } }, status: "success", error: null, reload });
    render(<ComplianceScoreCard />);
    expect(screen.getByText("Findings")).toBeInTheDocument();
    expect(screen.getByText("High/Critical Findings")).toBeInTheDocument();
    expect(screen.queryByText(/Score =/)).not.toBeInTheDocument();
  });
});

describe("ComplianceInsightsPanel", () => {
  it("renders analyzing state when no data", () => {
    mockUseResource.mockReturnValue({ data: null, status: "loading", error: null, reload: vi.fn() });
    render(<ComplianceInsightsPanel />);
    expect(screen.getByText("Analyzing data...")).toBeInTheDocument();
  });

  it("renders insights when data is available", () => {
    const reload = vi.fn();
    mockUseResource.mockReturnValueOnce({ data: { covered_controls: 90, total_controls: 100 }, status: "success", error: null, reload });
    mockUseResource.mockReturnValueOnce({ data: { total_mappings: 50, published_mappings: 40, avg_final_confidence: 0.85 }, status: "success", error: null, reload });
    mockUseResource.mockReturnValueOnce({ data: { manual_review_mappings: 5, rejected_mappings: 3 }, status: "success", error: null, reload });
    mockUseResource.mockReturnValueOnce({ data: { trends: [{ published: 10, manual_review: 5, created_at: "2024-01-01", scan_run_id: 1 }] }, status: "success", error: null, reload });
    render(<ComplianceInsightsPanel />);
    expect(screen.getByText("Compliance Insights")).toBeInTheDocument();
  });
});
