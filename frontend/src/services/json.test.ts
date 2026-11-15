import { describe, expect, it } from "vitest";
import { parseFailureJson, parseFindingJson } from "./json";

describe("scan-run JSON parsing", () => {
  it("accepts valid scanner findings", () => {
    const findings = JSON.stringify([
      {
        scanner_name: "checkov",
        scanner_finding_id: "CKV_TEST_1",
        raw_json: { title: "Test finding" },
      },
    ]);
    expect(parseFindingJson(findings)).toHaveLength(1);
  });

  it("rejects malformed findings", () => {
    expect(() => parseFindingJson(JSON.stringify([{ scanner_name: "checkov" }]))).toThrow("requires");
  });

  it("accepts valid scanner failures", () => {
    expect(parseFailureJson(JSON.stringify([{ scanner_name: "trivy", error_message: "failed" }]))).toHaveLength(1);
  });
});
