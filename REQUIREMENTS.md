# REQUIREMENTS.md

# Complisoc Requirements Specification

Version: 1.0

---

# 1. Purpose

Complisoc is an AI-powered automated security compliance testing platform that transforms security findings into compliance intelligence.

The platform provides:

* Continuous scanning
* Finding normalization
* Compliance mapping
* AI verification
* Governance reporting
* Audit evidence generation
* Historical compliance tracking

---

# 2. Problem Statement

Organizations struggle with:

* Point-in-time compliance validation
* Infrastructure drift
* Fragmented audit evidence
* Manual compliance workflows
* Limited governance visibility

Complisoc addresses these challenges through continuous compliance intelligence.

---

# 3. Supported Frameworks

Initial frameworks:

* SOC 2 Trust Services Criteria (TSC) 2022
* ISO/IEC 27001:2022 Annex A

Reference control baselines:

* ISO/IEC 27001:2022 Annex A provides the primary control catalog for the platform and contains 93 controls organized into four families: Organizational, People, Physical, and Technological.
* SOC 2 TSC 2022 provides the secondary control baseline through the five Trust Services Categories: Security, Availability, Processing Integrity, Confidentiality, and Privacy.

Mappings are generated dynamically from discovered findings but must be traceable to an authoritative control entry in one of these framework catalogs.

The platform does not depend on a predefined control subset, but it must support the minimum control metadata needed for auditability and explainability.

Success Criteria:

* 15+ validated control mappings across supported frameworks.
* At least one seeded control catalog entry for each major ISO/IEC 27001:2022 Annex A family.
* At least one mapped control path for each SOC 2 TSC category used in the release baseline.

---

# 4. Target Environments

## AWS IaC + Container Environment

Assets may include:

* Terraform
* IAM
* Security Groups
* Storage Resources
* Containers

Scanners:

* Checkov
* Trivy
* SonarQube

---

## Azure Infrastructure Environment

Assets may include:

* Resource Groups
* Virtual Machines
* Storage Accounts
* Network Security Groups

Scanners:

* Microsoft Defender
* Checkov

---

## Kubernetes + CI/CD Environment

Assets may include:

* Kubernetes Manifests
* GitHub Actions Workflows

Scanners:

* Trivy
* Checkov

---

# 5. Functional Requirements

## FR-001 Continuous Scanning

The system shall execute security scans for supported environments.

Acceptance Criteria:

* Scan runs are recorded.
* Findings are persisted.
* Historical scan runs remain accessible.

---

## FR-002 Finding Normalization

The system shall normalize scanner outputs into a canonical format.

Acceptance Criteria:

* Supported scanners produce normalized findings.
* Invalid findings are rejected or logged.

---

## FR-003 Compliance Mapping

The system shall map findings to compliance controls using the authoritative control catalog for the selected framework.

Acceptance Criteria:

* Candidate controls are identified from the relevant framework catalog.
* The selected control ID, family, title, and objective are recorded for every mapping.
* Mapping rationale is recorded.
* Mapping confidence is recorded.
* Mappings must reference a known framework control source (for example, ISO/IEC 27001:2022 Annex A or SOC 2 TSC 2022).

---

## FR-004 AI Verification

The system shall independently verify mappings.

Acceptance Criteria:

* Verification result stored.
* Agreement status recorded.

---

## FR-005 Governance Reporting

The system shall generate governance reports.

Acceptance Criteria:

* Engineering Report generated.
* Leadership Report generated.

---

## FR-006 Dashboard Visualization

The system shall provide compliance dashboards.

Acceptance Criteria:

* Control Coverage View
* Severity Distribution View
* Compliance Gap Summary View
* Remediation Backlog View

---

## FR-007 Historical Tracking

The system shall maintain historical compliance records.

Acceptance Criteria:

* Historical findings retrievable.
* Historical reports retrievable.

---

## FR-008 Audit Evidence Generation

The system shall generate audit evidence bundles.

Acceptance Criteria:

* Evidence exportable.
* Evidence traceable.
* Evidence timestamped.

---

## FR-009 Confidence Thresholding

The system shall evaluate mapping confidence.

Acceptance Criteria:

* Confidence calculated.
* Threshold enforced.

---

## FR-010 Manual Review Workflow

The system shall support manual review.

Acceptance Criteria:

* Low-confidence mappings routed for review.
* Review status recorded.

---

# 6. Compliance Intelligence Requirements

## CIR-001 Candidate Narrowing

Candidate controls shall be identified using deterministic rules derived from framework-specific control metadata.

For ISO/IEC 27001:2022, deterministic narrowing shall use control family, control ID, title, objective, keywords, and scanner signals.

For SOC 2 TSC 2022, deterministic narrowing shall use the relevant Trust Services Category and the related common criteria language that best matches the finding evidence.

---

## CIR-002 Primary Mapping

Gemini 2.5 Flash shall perform primary compliance mapping.

---

## CIR-003 Validation

All mapping outputs shall be validated before publication.

---

## CIR-004 Verification

Groq Llama 3.3 70B shall independently verify mappings.

---

## CIR-005 Confidence Calculation

Formula:

```text
(Gemini Confidence × 0.6)
+
(Groq Agreement × 0.4)
```

Agreement Values:

```text
Agree     = 1.0
Disagree  = 0.0
```

---

## CIR-006 Publication Threshold

Threshold:

```text
0.70
```

Mappings below threshold require manual review.

---

# 7. Reporting Requirements

## Engineering Report

Must include:

* Findings
* Resources
* Severity
* Failed Controls
* Remediation Guidance

---

## Leadership Report

Must include:

* Compliance Posture
* Risk Summary
* Trend Analysis

---

## Audit Bundle

Must include:

* Findings
* Control Mappings
* Verification Results
* Timestamps
* Metadata

---

# 8. Dashboard Requirements

Required Views:

## Control Coverage

Compliance coverage metrics.

---

## Severity Distribution

Finding severity breakdown.

---

## Compliance Gap Summary

Failed controls and affected assets.

---

## Remediation Backlog

Outstanding remediation items.

---

## Historical Trends

Compliance posture over time.

---

# 9. Audit Evidence Requirements

Evidence must contain:

* Evidence Identifier
* Scan Run Identifier
* Finding Identifier
* Timestamp
* Scanner Source
* Resource Identifier
* Mapping Information
* Confidence Information

Requirements:

* Immutable
* Traceable
* Reproducible

---

# 10. Non-Functional Requirements

## Explainability

Mappings must contain rationale and confidence.

---

## Auditability

All compliance conclusions must be traceable to evidence.

---

## Reliability

No finding shall be silently discarded.

---

## Security

Secrets shall not be stored in source code.

---

## Historical Retention

Historical records must remain queryable.

---

# 11. Technical Constraints

Backend:

* FastAPI
* SQLAlchemy
* Pydantic

Frontend:

* React
* TailwindCSS

Database:

* SQLite

Scanning:

* Trivy
* Checkov
* SonarQube
* Microsoft Defender

AI:

* Gemini 2.5 Flash
* Groq Llama 3.3 70B

Testing:

* Pytest
* Selenium
* Great Expectations
* Locust

CI/CD:

* GitHub Actions

---

# 12. Testing Requirements

Required Testing:

* Unit Testing
* Integration Testing
* End-to-End Testing
* Regression Testing
* Load Testing
* Validation Testing

Minimum Coverage:

```text
80%
```

Benchmark Dataset:

```text
30–50 curated findings
```

Evaluation Metrics:

* Precision
* Recall
* F1 Score
* Hallucination Rate
* Mapping Stability

---

# 13. Success Criteria

SC-001

15+ validated control mappings across SOC2 and ISO27001.

SC-002

Four dashboard views operational.

SC-003

Engineering Report operational.

SC-004

Leadership Report operational.

SC-005

Audit Bundle generation operational.

SC-006

End-to-end workflow operational.

SC-007

Historical compliance tracking operational.

SC-008

Target benchmark:

```text
500–1000 findings processed
in under 30 seconds
during synthetic evaluation
```

SC-009

Automated test coverage exceeds 80%.

---

# 14. Non-Goals

The platform will not:

* Replace auditors
* Issue compliance certifications
* Make autonomous compliance decisions
* Automatically remediate production systems
* Modify raw findings
* Bypass manual review workflows
