from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RawFindingInput(BaseModel):
    scanner_name: str = Field(min_length=1, max_length=128)
    scanner_finding_id: str = Field(min_length=1, max_length=256)
    raw_json: dict[str, Any]


class ScannerFailureInput(BaseModel):
    scanner_name: str = Field(min_length=1, max_length=128)
    error_message: str = Field(min_length=1, max_length=2048)


class ScanRunCreate(BaseModel):
    target_environment: str = Field(min_length=1, max_length=128)
    findings: list[RawFindingInput] = Field(default_factory=list)
    scanner_failures: list[ScannerFailureInput] = Field(default_factory=list)


class ReviewDecision(BaseModel):
    reviewer_id: str | None = None
    comments: str | None = None


class ReportCreate(BaseModel):
    scan_run_id: int


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ScanRunRead(ORMModel):
    id: int
    target_environment: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RawFindingRead(ORMModel):
    id: int
    scanner_execution_id: int
    scanner_finding_id: str
    scanner_name: str
    raw_json: dict[str, Any]
    created_at: datetime | None = None


class NormalizedFindingRead(ORMModel):
    id: int
    raw_finding_id: int
    scanner_name: str
    finding_type: str
    resource_type: str
    resource_identifier: str
    severity: str
    title: str
    description: str | None = None
    metadata_json: dict[str, Any] | None = None
    timestamp: datetime | None = None


class ControlRead(ORMModel):
    id: int
    framework_name: str
    framework_version: str
    control_id: str
    control_family: str
    title: str
    description: str
    objective: str | None = None
    evidence_examples: list[str] | None = None
    scanner_signals: list[str] | None = None
    keywords: list[str] | None = None
    source_url: str
    active_status: bool


class ControlMappingRead(ORMModel):
    id: int
    normalized_finding_id: int
    candidate_control_id: int
    control_catalog_id: int
    rank: int
    mapping_model: str
    prompt_version: str
    rationale: str | None = None
    gemini_confidence: float | None = None
    verification_status: str | None = None
    final_confidence: float | None = None
    mapping_status: str


class VerificationRecordRead(ORMModel):
    id: int
    control_mapping_id: int
    verification_model: str
    prompt_version: str
    result: str
    explanation: str | None = None
    timestamp: datetime | None = None


class ReviewQueueItemRead(ORMModel):
    id: int
    control_mapping_id: int
    status: str
    reviewer_id: str | None = None
    review_reason_code: str
    comments: str | None = None
    reviewed_at: datetime | None = None


class ComplianceReportRead(ORMModel):
    id: int
    scan_run_id: int
    report_type: str
    generated_by: str
    generated_at: datetime | None = None
    content_path: str | None = None
    content_hash: str | None = None


class AuditBundleRead(ORMModel):
    id: int
    scan_run_id: int
    generated_at: datetime | None = None
    bundle_path: str | None = None
    checksum: str
