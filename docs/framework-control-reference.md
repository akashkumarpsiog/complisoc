# Framework Control Reference Baseline

This document captures the authoritative control inventory baseline for the first production-ready release of Complisoc.

## 1. ISO/IEC 27001:2022 Annex A

Source of truth:
- https://www.iso.org/standard/27001
- https://www.isms.online/iso-27001/annex-a-2022/

The ISO/IEC 27001:2022 Annex A control set is the primary control catalog for the platform.
It contains 93 controls organized into four families:

- Organizational controls (Annex A 5.1 to 5.37)
- People controls (Annex A 6.1 to 6.8)
- Physical controls (Annex A 7.1 to 7.14)
- Technological controls (Annex A 8.1 to 8.34)

Examples of controls that should be present in the control catalog:
- A 5.15 Access Control
- A 5.16 Identity Management
- A 5.17 Authentication Information
- A 5.18 Access Rights
- A 5.24 Information Security Incident Management Planning and Preparation
- A 5.31 Legal, Statutory, Regulatory and Contractual Requirements
- A 8.2 Privileged Access Rights
- A 8.5 Secure Authentication
- A 8.7 Protection Against Malware
- A 8.13 Information Backup
- A 8.20 Network Security
- A 8.24 Use of Cryptography
- A 8.32 Change Management

## 2. SOC 2 Trust Services Criteria

Source of truth:
- https://www.aicpa-cima.com/resources/landing/trust-services-criteria
- https://www.aicpa-cima.com/resources/article/trust-services-criteria-2022

SOC 2 does not expose a single flat list of controls in the same way as ISO 27001 Annex A.
The authoritative control logic is defined by the AICPA Trust Services Criteria (TSC), organized into five trust service categories:

- Security
- Availability
- Processing Integrity
- Confidentiality
- Privacy

For Complisoc, the expected behavior is to map findings to these TSC categories and to the relevant common criteria and subcriteria that describe the control objective.

Example mapping intent:
- Missing MFA or overly broad IAM policies -> Security
- Unavailable or unmonitored production services -> Availability
- Broken or unreviewed deployment/change workflow -> Processing Integrity
- Weak encryption or leakage of sensitive information -> Confidentiality
- Improper handling of personal information -> Privacy

## 3. Recommended implementation behavior

The catalog must store the following minimum control fields:
- framework_name
- framework_version
- control_id
- control_family
- title
- description
- objective
- evidence_examples
- scanner_signals
- keywords
- source_url

The mapping workflow should use:
- deterministic narrowing by framework-specific keywords and scanner signals
- AI mapping for candidate selection and rationale
- stored final confidence and verification status
- manual review for mappings below the 0.70 threshold
