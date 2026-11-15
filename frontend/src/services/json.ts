import type { RawFindingInput, ScannerFailureInput } from "../types";

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
