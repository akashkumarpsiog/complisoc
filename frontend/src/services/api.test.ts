import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";

describe("api client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("builds documented filter query strings", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    vi.stubGlobal("fetch", fetchMock);

    await api.findings.list({ severity: "high", scanner: "checkov" });

    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain("/findings");
    expect(url).toContain("severity=high");
    expect(url).toContain("scanner=checkov");
  });

  it("posts review decisions to documented endpoints", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 1 }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await api.reviewQueue.approve(7);

    expect(String(fetchMock.mock.calls[0][0])).toContain("/review-queue/7/approve");
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ reviewer_id: "frontend-operator" });
  });

  it("posts scenario reports to the scenario endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 1, report_type: "scenario:container" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await api.reports.scenario(42, "container");

    expect(String(fetchMock.mock.calls[0][0])).toContain("/reports/scenario");
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      scan_run_id: 42,
      scenario: "container",
    });
    expect(result.report_type).toBe("scenario:container");
  });

  it("posts IaC scenario reports", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 2, report_type: "scenario:iac" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await api.reports.scenario(42, "iac");

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      scan_run_id: 42,
      scenario: "iac",
    });
    expect(result.report_type).toBe("scenario:iac");
  });

  it("uses focused dashboard endpoints for drill-down and on-demand remediation", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ items: [] }) });
    vi.stubGlobal("fetch", fetchMock);

    await api.dashboard.controlDrillDown(12);
    await api.dashboard.suggestion(34);

    expect(String(fetchMock.mock.calls[0][0])).toContain("/dashboard/controls/12/drill-down");
    expect(String(fetchMock.mock.calls[1][0])).toContain("/dashboard/remediation-backlog/34/suggestion");
    expect(fetchMock.mock.calls[1][1].method).toBe("POST");
  });
});
