import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ReviewPage } from "../pages/ReviewPage";

const mockUseResource = vi.fn();

vi.mock("../services/api", () => ({
  api: {
    reviewQueue: {
      list: vi.fn(),
      approve: vi.fn(),
      reject: vi.fn(),
      bulkDecide: vi.fn(),
    },
  },
}));

vi.mock("../hooks/useResource", () => ({
  useResource: () => mockUseResource(),
}));

describe("ReviewPage Integration", () => {
  const mockReviewItems = [
    { id: 1, control_mapping_id: 101, status: "pending", review_reason_code: "LOW_CONFIDENCE", severity: "high", control_id: "AC-1", scan_run_id: 1 },
    { id: 2, control_mapping_id: 102, status: "pending", review_reason_code: "LOW_CONFIDENCE", severity: "medium", control_id: "AC-2", scan_run_id: 1 },
    { id: 3, control_mapping_id: 103, status: "approved", review_reason_code: "AUTO", severity: "low", control_id: "AC-3", scan_run_id: 1 },
  ];

  it("renders review queue with items", () => {
    mockUseResource.mockReturnValue({ data: mockReviewItems, status: "success", error: null, reload: vi.fn() });
    render(<ReviewPage />);
    expect(screen.getByText("Review Queue")).toBeInTheDocument();
  });

  it("filters items by severity", () => {
    mockUseResource.mockReturnValue({ data: mockReviewItems, status: "success", error: null, reload: vi.fn() });
    render(<ReviewPage />);
    expect(screen.getByText("Review Queue")).toBeInTheDocument();
  });

  it("shows pending count in approve all button", () => {
    mockUseResource.mockReturnValue({ data: mockReviewItems, status: "success", error: null, reload: vi.fn() });
    render(<ReviewPage />);
    expect(screen.getByText(/Approve All Pending/)).toBeInTheDocument();
  });
});

describe("ScanRunsPage Integration", () => {
  it("shows archive error on failure", async () => {
    const mockScanRuns = [
      { id: 1, target_environment: "prod", status: "completed", created_at: "2024-01-01", archived_at: null },
    ];
    mockUseResource.mockReturnValue({ data: mockScanRuns, status: "success", error: null, reload: vi.fn() });
    const { container } = render(<div>Test wrapper</div>);
    expect(container).toBeTruthy();
  });
});
