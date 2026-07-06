# AGENTS.md

# Complisoc AI Contributor Guide

Version: 1.0

---

# Documentation Hierarchy

When documents conflict:

1. REQUIREMENTS.md
2. ARCHITECTURE.md
3. DATA_MODEL.md
4. API.md
5. AGENTS.md

Higher-priority documents override lower-priority documents.

---

# Mission

Complisoc transforms security findings into compliance intelligence through:

* Continuous scanning
* Finding normalization
* Compliance mapping
* AI verification
* Governance reporting
* Audit evidence generation

---

# Core Principles

## Deterministic Before AI

Prefer deterministic logic whenever possible.

AI is reserved for:

* Compliance mapping
* Governance translation
* Remediation generation

---

## Preserve Auditability

Every compliance conclusion must be traceable to source evidence.

Every report must be reproducible.

---

## Preserve Data Lineage

Published mappings must support:

```text
ScanRun
→ RawFinding
→ NormalizedFinding
→ ControlMapping
→ VerificationRecord
```

---

## Raw Findings Are Immutable

Never modify:

* Raw findings
* Evidence records
* Historical scan data

All enrichment creates derived records.

---

# Required Architecture

Follow ARCHITECTURE.md.

Do not violate layer boundaries.

```text
Scanner
    → Normalization
    → Storage
    → Compliance Intelligence
    → Reporting
    → Dashboard
```

Responsibilities must remain isolated.

---

# Required Compliance Workflow

```text
Normalized Finding
    ↓
Candidate Narrowing
    ↓
Gemini Mapping
    ↓
Validation
    ↓
Groq Verification
    ↓
Confidence Calculation
    ↓
Published
or
Manual Review
```

Do not bypass workflow stages.

---

# Confidence Rules

Threshold:

0.70

Mappings below threshold:

Manual Review

Mappings below threshold must not be automatically published.

---

# Technology Constraints

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
* Locust
* Great Expectations

Do not introduce alternative frameworks without approval.

---

# API Rules

Follow API.md.

Do not create undocumented endpoints.

Keep APIs resource-oriented.

Examples:

```text
/scan-runs
/findings
/mappings
/reports
/audit-bundles
```

---

# Security Rules

Never:

* Hardcode secrets
* Hardcode API keys
* Commit credentials
* Disable validation
* Bypass confidence thresholds

Use environment variables.

---

# Testing Requirements

All new functionality must include:

* Unit tests
* Validation tests
* Error-path tests

Add integration and E2E tests when appropriate.

---

# Definition of Done

A task is complete only when:

1. Tests pass.
2. Validation passes.
3. Documentation remains accurate.
4. Data lineage remains intact.
5. Architecture boundaries are preserved.

---

# Decision Framework

When multiple implementations are possible:

1. Prefer deterministic solutions.
2. Prefer simple solutions.
3. Prefer testable solutions.
4. Prefer auditable solutions.
5. Preserve lineage and traceability.

If uncertain, favor transparency over automation.
