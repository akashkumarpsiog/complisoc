import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ResourceState } from "../hooks/useResource";
import type { NormalizedFinding } from "../types";
import { FindingsTab } from "./ScanDetailPage";

describe("ScanDetailPage findings", () => {
  it("expands the complete description for non-Defender findings", () => {
    const description = "A detailed scanner explanation that is longer than the table preview.";
    const finding: NormalizedFinding = {
      id: 21,
      raw_finding_id: 42,
      scanner_name: "checkov",
      finding_type: "configuration",
      resource_type: "repository",
      resource_identifier: "repo/example",
      severity: "medium",
      title: "Configuration issue",
      description,
    };
    const resource: ResourceState<NormalizedFinding[]> = {
      data: [finding],
      status: "success",
      error: null,
      reload: vi.fn().mockResolvedValue(undefined),
      setData: vi.fn(),
    };

    render(<FindingsTab findings={[finding]} resource={resource} onRefresh={vi.fn()} />);

    const toggle = screen.getByRole("button", { name: "Show details" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(toggle);

    expect(screen.getByRole("button", { name: "Hide details" })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Description:")).toBeInTheDocument();
    expect(screen.getAllByText(description)).toHaveLength(2);
  });
});
