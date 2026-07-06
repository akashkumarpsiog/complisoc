# API.md

# Complisoc API Specification

Version: 1.0

API Style: REST

Format: JSON

Base Path:

```text
/api/v1
```

---

# Design Principles

* Resource-oriented APIs
* JSON requests and responses
* Consistent error model
* Versioned endpoints
* Immutable evidence records

---

# Resources

```text
ScanRun

Finding

ControlMapping

ReviewQueueItem

Control

ComplianceReport

AuditBundle
```

---

# Scan Runs

| Method | Endpoint                | Purpose         |
| ------ | ----------------------- | --------------- |
| POST   | /scan-runs              | Create scan run |
| GET    | /scan-runs              | List scan runs  |
| GET    | /scan-runs/{id}         | Get scan run    |
| GET    | /scan-runs/{id}/summary | Scan summary    |

---

# Findings

| Method | Endpoint                | Purpose       |
| ------ | ----------------------- | ------------- |
| GET    | /findings               | List findings |
| GET    | /findings/{id}          | Get finding   |
| GET    | /findings/{id}/mappings | Get mappings  |

Filters:

```text
scan_run_id
severity
scanner
finding_type
```

---

# Control Mappings

| Method | Endpoint                    | Purpose          |
| ------ | --------------------------- | ---------------- |
| GET    | /mappings                   | List mappings    |
| GET    | /mappings/{id}              | Get mapping      |
| GET    | /mappings/{id}/verification | Get verification |

Filters:

```text
framework
status
scan_run_id
```

---

# Review Queue

| Method | Endpoint                   | Purpose           |
| ------ | -------------------------- | ----------------- |
| GET    | /review-queue              | List review items |
| GET    | /review-queue/{id}         | Get review item   |
| POST   | /review-queue/{id}/approve | Approve mapping   |
| POST   | /review-queue/{id}/reject  | Reject mapping    |

---

# Controls

| Method | Endpoint       | Purpose       |
| ------ | -------------- | ------------- |
| GET    | /controls      | List controls |
| GET    | /controls/{id} | Get control   |

Filters:

```text
framework
```

---

# Reports

| Method | Endpoint             | Purpose                     |
| ------ | -------------------- | --------------------------- |
| GET    | /reports             | List reports                |
| GET    | /reports/{id}        | Get report                  |
| POST   | /reports/engineering | Generate engineering report |
| POST   | /reports/leadership  | Generate leadership report  |
| GET    | /reports/{id}/pdf    | Export PDF                  |

---

# Audit Bundles

| Method | Endpoint                     | Purpose         |
| ------ | ---------------------------- | --------------- |
| GET    | /audit-bundles               | List bundles    |
| GET    | /audit-bundles/{id}          | Get bundle      |
| POST   | /audit-bundles               | Generate bundle |
| GET    | /audit-bundles/{id}/download | Download bundle |

Formats:

```text
JSON
ZIP
```

---

# Dashboard

| Method | Endpoint                         | Purpose                 |
| ------ | -------------------------------- | ----------------------- |
| GET    | /dashboard/control-coverage      | Coverage metrics        |
| GET    | /dashboard/severity-distribution | Severity metrics        |
| GET    | /dashboard/gap-summary           | Gap analysis            |
| GET    | /dashboard/remediation-backlog   | Outstanding remediation |
| GET    | /dashboard/trends                | Historical trends       |

---

# Health

| Method | Endpoint   | Purpose              |
| ------ | ---------- | -------------------- |
| GET    | /health    | Health check         |
| GET    | /readiness | Dependency readiness |

---

# Pagination

Collection endpoints support:

```text
?page=1
&page_size=50
```

---

# Error Model

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Requested resource does not exist"
  }
}
```

---

# Status Codes

```text
200 OK
201 Created

400 Bad Request
401 Unauthorized
403 Forbidden
404 Not Found

409 Conflict
422 Validation Error

500 Internal Server Error
```

---

# API Rules

1. APIs are resource-oriented.
2. Evidence records are read-only.
3. Compliance calculations occur in backend services.
4. Dashboard endpoints return aggregated data.
5. API keys and credentials are never exposed.
6. All published mappings must be validated and verified.
