# Complisoc Database Schema Reference

This document summarizes the current persisted schema used by Complisoc.

## Core tables

### scan_runs
- id: primary key
- target_environment: target environment description
- status: run status
- started_at, completed_at, created_at, updated_at

### scanner_executions
- id: primary key
- scan_run_id: foreign key to scan_runs
- scanner_name: scanner identifier
- status: execution status
- started_at, completed_at, created_at, updated_at

### raw_findings
- id: primary key
- scanner_execution_id: foreign key to scanner_executions
- scanner_finding_id: upstream scanner identifier
- scanner_name: scanner name
- raw_json: raw payload
- created_at

### normalized_findings
- id: primary key
- raw_finding_id: foreign key to raw_findings
- scanner_name
- finding_type
- resource_type
- resource_identifier
- severity
- title
- description
- metadata_json
- timestamp
- created_at, updated_at

### control_catalog
- id: primary key
- framework_name: e.g. ISO/IEC 27001:2022 Annex A or SOC 2 TSC 2022
- framework_version: version label
- control_id: framework-specific control identifier
- control_family: family or category grouping
- title: short title
- description: control description
- objective: intended objective
- evidence_examples: examples of supporting artifacts
- scanner_signals: keywords or signal hints for deterministic matching
- keywords: normalized search tokens
- source_url: authoritative reference URL
- active_status: active/inactive flag
- created_at, updated_at

Unique constraint:
- (framework_name, control_id)

### candidate_controls
- id: primary key
- normalized_finding_id: foreign key to normalized_findings
- control_catalog_id: foreign key to control_catalog
- source: origin of candidate generation
- match_score: numeric match score
- rank: ranking for candidate ordering
- created_at, updated_at

### control_mappings
- id: primary key
- normalized_finding_id: foreign key to normalized_findings
- candidate_control_id: foreign key to candidate_controls
- control_catalog_id: foreign key to control_catalog
- rank: ranking in mapping workflow
- mapping_model: model used for mapping
- prompt_version: prompt version used for mapping
- rationale: explanation of the mapping
- gemini_confidence: raw confidence from the initial mapping model
- verification_status: status from independent verification workflow
- final_confidence: computed final confidence after verification
- mapping_status: generated, verified, manual_review, published, or rejected
- created_at, updated_at

### verification_records
- id: primary key
- control_mapping_id: foreign key to control_mappings
- verification_model: verification model used
- prompt_version
- result: pass/fail/needs_review style result
- explanation
- timestamp
- created_at

### review_queue_items
- id: primary key
- control_mapping_id: foreign key to control_mappings
- status: review item status
- reviewer_id: assigned reviewer
- review_reason_code: reason category
- comments: reviewer comments
- reviewed_at
- created_at, updated_at

### compliance_reports
- id: primary key
- scan_run_id: foreign key to scan_runs
- report_type
- generated_by
- generated_at
- content_path
- content_hash
- created_at, updated_at

### audit_bundles
- id: primary key
- scan_run_id: foreign key to scan_runs
- generated_at
- bundle_path
- checksum
- created_at, updated_at

## Current implementation notes
- The schema supports framework-aware control catalogs.
- Control mappings explicitly track confidence, verification state, and status.
- The initial seeded baseline includes ISO/IEC 27001:2022 Annex A and SOC 2 TSC 2022 controls.
