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
    {
      scanner_name: "defender",
      scanner_finding_id: "defender-sample-1",
      raw_json: {
        finding_type: "DefenderAlert",
        resource_type: "Microsoft.Compute/virtualMachines",
        resource_identifier: "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1",
        severity: "high",
        title: "Suspicious login from unrecognized location",
        description: "A sign-in from an unrecognized location was detected.",
        defender_source: "alerts",
        alertType: "Signin",
        remediationSteps: "Review sign-in logs and block the source IP if malicious.",
      },
    },
    {
      scanner_name: "defender",
      scanner_finding_id: "defender-sample-2",
      raw_json: {
        finding_type: "DefenderRecommendation",
        resource_type: "Microsoft.Storage/storageAccounts",
        resource_identifier: "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/sa1",
        severity: "high",
        title: "Public access setting detected",
        description: "Storage account allows public access at the container level.",
        defender_source: "assessments",
        assessmentType: "BlobPublicAccess",
        resourceType: "Microsoft.Storage/storageAccounts",
        remediationSteps: "Disable public access and use SAS tokens with RBAC.",
      },
    },
    {
      scanner_name: "defender",
      scanner_finding_id: "defender-sample-3",
      raw_json: {
        finding_type: "DefenderSecureScore",
        resource_type: "secure-score",
        resource_identifier: "diskEncryption",
        severity: "medium",
        title: "Enable disk encryption",
        description: "Managed disks should be encrypted with customer-managed keys.",
        defender_source: "secureScores",
        score: { "controlId": "diskEncryption", "current": 2, "max": 10 },
        percentage: 20,
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
