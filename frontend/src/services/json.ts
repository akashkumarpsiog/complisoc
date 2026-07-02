import type { RawFindingInput, ScannerFailureInput } from "../types";

export const sampleFindings = JSON.stringify(
  [
    {
      scanner_name: "checkov",
      scanner_finding_id: "CKV_AWS_FRONTEND_1",
      raw_json: {
        finding_type: "iam public access permission",
        resource_type: "aws_iam_policy",
        resource_identifier: "aws_iam_policy.frontend_sample",
        severity: "high",
        title: "IAM policy allows public access permission",
        description: "iam public access permission public iam access permission",
      },
    },
  ],
  null,
  2,
);

export const sampleFailures = JSON.stringify([], null, 2);

export function parseFindingJson(value: string): RawFindingInput[] {
  const parsed = JSON.parse(value);
  if (!Array.isArray(parsed)) {
    throw new Error("Findings JSON must be an array.");
  }
  parsed.forEach((finding, index) => {
    if (!finding?.scanner_name || !finding?.scanner_finding_id || typeof finding?.raw_json !== "object") {
      throw new Error(`Finding ${index + 1} requires scanner_name, scanner_finding_id, and raw_json.`);
    }
  });
  return parsed as RawFindingInput[];
}

export function parseFailureJson(value: string): ScannerFailureInput[] {
  const parsed = JSON.parse(value);
  if (!Array.isArray(parsed)) {
    throw new Error("Scanner failures JSON must be an array.");
  }
  parsed.forEach((failure, index) => {
    if (!failure?.scanner_name || !failure?.error_message) {
      throw new Error(`Scanner failure ${index + 1} requires scanner_name and error_message.`);
    }
  });
  return parsed as ScannerFailureInput[];
}
