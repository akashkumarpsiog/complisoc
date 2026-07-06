# ARCHITECTURE.md

# Complisoc Architecture

Version: 1.0

---

# 1. Purpose

Defines the system architecture, component boundaries, data flow, and implementation constraints for Complisoc.

This document is the architectural source of truth for the repository.

---

# 2. Architectural Principles

## Deterministic Before AI

Use deterministic logic whenever possible.

AI is reserved for:

* Compliance Mapping
* Governance Translation
* Remediation Generation

---

## Auditability

Every compliance decision must be traceable to evidence.

---

## Explainability

Mappings must contain:

* rationale
* confidence
* verification status

---

## Immutability

Raw findings are immutable.

Evidence records are immutable.

---

## Layer Isolation

Each layer owns a specific responsibility.

Business logic must not leak across layers.

---

# 3. High-Level Architecture

```text
Scanner Layer
        ↓
Normalization Layer
        ↓
Storage Layer
        ↓
Compliance Intelligence Layer
        ↓
Reporting Layer
        ↓
Dashboard Layer
```

---

# 4. Repository Structure

```text
complisoc/

├── backend/
│
│   ├── api/
│   │
│   ├── scanners/
│   │   ├── trivy/
│   │   ├── checkov/
│   │   ├── sonarqube/
│   │   └── defender/
│   │
│   ├── normalization/
│   │
│   ├── compliance/
│   │   ├── candidate_narrowing/
│   │   ├── gemini_mapper/
│   │   ├── verifier/
│   │   ├── confidence/
│   │   └── review/
│   │
│   ├── reporting/
│   │
│   ├── repositories/
│   │
│   ├── services/
│   │
│   ├── models/
│   │
│   ├── database/
│   │
│   └── core/
│
├── frontend/
│
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── services/
│   │   └── hooks/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   ├── benchmark/
│   └── load/
│
├── benchmark_data/
│
├── scan_targets/
│
└── docs/
```

---

# 5. Layer Responsibilities

| Layer                   | Responsibility                                |
| ----------------------- | --------------------------------------------- |
| Scanner                 | Execute scanners and collect findings         |
| Normalization           | Transform findings into canonical schema      |
| Storage                 | Persist findings, mappings, reports, evidence |
| Compliance Intelligence | Mapping, verification, confidence calculation |
| Reporting               | Generate reports and audit bundles            |
| Dashboard               | Present compliance metrics and history        |

---

# 6. Scanner Layer

Supported Scanners:

* Trivy
* Checkov
* SonarQube
* Microsoft Defender

Responsibilities:

* Execute scans
* Parse scanner outputs
* Store raw findings

Must Not:

* Perform AI mapping
* Perform compliance reasoning
* Generate reports

Outputs:

```text
RawFinding
```

---

# 7. Normalization Layer

Responsibilities:

* Normalize scanner outputs
* Standardize severity
* Validate structure

Input:

```text
RawFinding
```

Output:

```text
NormalizedFinding
```

Must Not:

* Perform compliance mapping
* Generate reports
* Execute AI logic

---

# 8. Storage Layer

Technology:

```text
SQLite
SQLAlchemy
```

Responsibilities:

* Store ScanRuns
* Store Findings
* Store Mappings
* Store Reports
* Store Audit Bundles

Requirements:

* Traceability
* Historical retention
* Reproducibility

---

# 9. Compliance Intelligence Layer

Core business logic layer.

Responsibilities:

* Candidate Narrowing
* Gemini Mapping
* Validation
* Groq Verification
* Confidence Calculation
* Review Routing

Input:

```text
NormalizedFinding
```

Output:

```text
ControlMapping
```

---

# 10. Compliance Workflow

Mandatory workflow:

```text
NormalizedFinding
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

Workflow stages must not be bypassed.

---

# 11. Candidate Narrowing

Purpose:

Reduce compliance search space before AI mapping.

Input:

```text
Finding Category
```

Output:

```text
Candidate Controls
```

Requirements:

* Deterministic
* Explainable
* Configuration-driven

AI must never evaluate an entire framework.

---

# 12. Gemini Mapping

Purpose:

Map findings to candidate controls.

Inputs:

* Normalized Finding
* Candidate Controls
* Control Metadata

Outputs:

* Proposed Control Mapping
* Rationale
* Confidence Score

Requirements:

* Structured outputs
* Schema validation

---

# 13. Verification Layer

Model:

```text
Groq Llama 3.3 70B
```

Purpose:

Independently validate Gemini mappings.

Outputs:

```text
Agree

or

Disagree
```

Requirements:

* Independent evaluation
* Explanation preserved

---

# 14. Confidence Calculation

Formula:

```text
(Gemini Confidence × 0.6)
+
(Groq Agreement × 0.4)
```

Where:

```text
Agree     = 1.0
Disagree  = 0.0
```

Threshold:

```text
0.70
```

Results:

```text
≥ 0.70
    Published

< 0.70
    Manual Review
```

---

# 15. Reporting Layer

Produces:

* Engineering Reports
* Leadership Reports
* Audit Bundles

Requirements:

* Generated from validated mappings only
* Reproducible
* Traceable

Must Not:

* Consume raw AI responses

---

# 16. Dashboard Layer

Technology:

```text
React
TailwindCSS
```

Views:

* Control Coverage
* Severity Distribution
* Compliance Gap Summary
* Remediation Backlog
* Historical Trends

Requirements:

* Presentation only
* No compliance calculations

---

# 17. API Architecture

Technology:

```text
FastAPI
```

API Style:

```text
REST
JSON
```

Principle:

Resource-oriented APIs.

Examples:

```text
/scan-runs

/findings

/mappings

/reports

/audit-bundles
```

---

# 18. Security Architecture

Secrets:

* Environment Variables Only

Never:

* Hardcode credentials
* Commit API keys

Protected Assets:

* Findings
* Reports
* Audit Bundles
* AI Credentials

---

# 19. Failure Handling

Scanner Failure:

```text
Partial Results Allowed
```

AI Failure:

```text
Finding Retained
Mapping Deferred
```

Verification Failure:

```text
Manual Review
```

Database Failure:

```text
Fail Explicitly
No Silent Data Loss
```

---

# 20. Architectural Invariants

The following rules are mandatory:

1. Raw findings are immutable.
2. Evidence records are immutable.
3. Normalization is deterministic.
4. Candidate narrowing occurs before AI mapping.
5. Validation occurs before publication.
6. Verification occurs before publication.
7. Confidence threshold is enforced.
8. Published mappings require lineage.
9. Reports use validated mappings only.
10. Dashboards consume processed data only.

Violation of these rules is considered an architectural defect.

---

# 21. Future Architecture

Future versions may introduce:

* PostgreSQL
* Background Workers
* Message Queues
* Multi-Tenancy
* Real-Time Processing
* Additional Frameworks

These capabilities are outside Semester 1 scope.
