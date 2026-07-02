import { describe, expect, it } from "vitest";
import { parseFailureJson, parseFindingJson, sampleFindings } from "./json";

describe("scan-run JSON parsing", () => {
  it("accepts valid scanner findings", () => {
    expect(parseFindingJson(sampleFindings)).toHaveLength(1);
  });

  it("rejects malformed findings", () => {
    expect(() => parseFindingJson(JSON.stringify([{ scanner_name: "checkov" }]))).toThrow("requires");
  });

  it("accepts valid scanner failures", () => {
    expect(parseFailureJson(JSON.stringify([{ scanner_name: "trivy", error_message: "failed" }]))).toHaveLength(1);
  });
});
