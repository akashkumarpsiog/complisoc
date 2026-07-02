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

    await api.reviewQueue.approve(7, "approved");

    expect(String(fetchMock.mock.calls[0][0])).toContain("/review-queue/7/approve");
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
  });
});
