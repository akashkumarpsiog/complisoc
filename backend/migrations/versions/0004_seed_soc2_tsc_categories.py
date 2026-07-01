"""Seed the SOC 2 Common Criteria (Security category) baseline into the control catalog.

Source: AICPA TSP Section 100, 2017 Trust Services Criteria for Security, Availability,
Processing Integrity, Confidentiality, and Privacy (with Revised Points of Focus - 2022).
https://www.aicpa-cima.com/resources/download/2017-trust-services-criteria-with-revised-points-of-focus-2022

Scope note: Security (Common Criteria, CC1-CC9) is the only mandatory SOC 2 category and is
the only category referenced in this catalog. The optional categories (Availability A1.x,
Confidentiality C1.x, Processing Integrity PI1.x, Privacy P1-P8) are not seeded here, since
this project's scanners (Trivy, Checkov, SonarQube, Microsoft Defender) produce findings that
map to Security controls, not to the optional trust categories.

Within Security, CC1-CC5 (Control Environment, Communication and Information, Risk Assessment,
Monitoring Activities, Control Activities) are governance/COSO-principle criteria that are not
directly observable from scanner output, so they are seeded at the series level. CC6-CC9
(Logical/Physical Access, System Operations, Change Management, Risk Mitigation) are the
criteria scanner findings actually map to, so they are seeded at the full AICPA sub-criterion
level (CC6.1-CC6.8, CC7.1-CC7.5, CC8.1, CC9.1-CC9.2), matching the official 8/5/1/2 point counts.

Revision ID: 0004_seed_soc2_tsc_categories
Revises: 0003_seed_iso27001_annex_a
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_seed_soc2_tsc_categories"
down_revision = "0003_seed_iso27001_annex_a"
branch_labels = None
depends_on = None


def upgrade():
    control_table = sa.table(
        "control_catalog",
        sa.column("framework_name", sa.String),
        sa.column("framework_version", sa.String),
        sa.column("control_id", sa.String),
        sa.column("control_family", sa.String),
        sa.column("title", sa.String),
        sa.column("description", sa.Text),
        sa.column("objective", sa.Text),
        sa.column("evidence_examples", sa.JSON),
        sa.column("scanner_signals", sa.JSON),
        sa.column("keywords", sa.JSON),
        sa.column("source_url", sa.String),
        sa.column("active_status", sa.Boolean),
    )

    FRAMEWORK = "SOC 2 Trust Services Criteria (TSC) 2022"
    VERSION = "2017 (Revised Points of Focus - 2022)"
    SOURCE = "https://www.aicpa-cima.com/resources/download/2017-trust-services-criteria-with-revised-points-of-focus-2022"

    controls = [
        # --- CC1-CC5: governance/COSO principle series (seeded at series level) ---
        {
            "framework_name": FRAMEWORK,
            "framework_version": VERSION,
            "control_id": "CC1",
            "control_family": "Control Environment",
            "title": "Control Environment",
            "description": "The entity demonstrates a commitment to integrity and ethical values, exercises board oversight independent of management, establishes organizational structure and reporting lines, demonstrates commitment to competence, and holds individuals accountable for internal control responsibilities.",
            "objective": "Establish the governance foundation that supports the design and operation of all other Security criteria.",
            "evidence_examples": ["code_of_conduct", "board_oversight_minutes", "org_chart", "hiring_and_competency_records"],
            "scanner_signals": ["policy", "governance", "documentation"],
            "keywords": ["control environment", "governance", "COSO", "accountability"],
            "source_url": SOURCE,
            "active_status": True,
        },
        {
            "framework_name": FRAMEWORK,
            "framework_version": VERSION,
            "control_id": "CC2",
            "control_family": "Communication and Information",
            "title": "Communication and Information",
            "description": "The entity obtains, generates, and uses relevant, quality information to support internal control, and internally and externally communicates information necessary to support the functioning of internal control, including objectives and responsibilities for security.",
            "objective": "Ensure security-relevant information is captured and communicated to the people who need it to operate controls.",
            "evidence_examples": ["security_policy_distribution_log", "incident_communications", "status_page", "employee_acknowledgment_records"],
            "scanner_signals": ["documentation", "communications", "wiki"],
            "keywords": ["communication", "information quality", "reporting"],
            "source_url": SOURCE,
            "active_status": True,
        },
        {
            "framework_name": FRAMEWORK,
            "framework_version": VERSION,
            "control_id": "CC3",
            "control_family": "Risk Assessment",
            "title": "Risk Assessment",
            "description": "The entity specifies objectives with sufficient clarity, identifies and analyzes risk (including fraud risk) to the achievement of its objectives, and identifies and assesses changes that could significantly affect the system of internal control.",
            "objective": "Ensure security risks, including risks arising from change, are identified and analyzed on an ongoing basis.",
            "evidence_examples": ["risk_register", "threat_model", "fraud_risk_assessment", "change_impact_analysis"],
            "scanner_signals": ["risk", "threat_model"],
            "keywords": ["risk assessment", "fraud risk", "threat modeling"],
            "source_url": SOURCE,
            "active_status": True,
        },
        {
            "framework_name": FRAMEWORK,
            "framework_version": VERSION,
            "control_id": "CC4",
            "control_family": "Monitoring Activities",
            "title": "Monitoring Activities",
            "description": "The entity selects, develops, and performs ongoing and/or separate evaluations to ascertain whether the components of internal control are present and functioning, and communicates internal control deficiencies in a timely manner to parties responsible for corrective action.",
            "objective": "Provide ongoing assurance that security controls remain designed and operating effectively.",
            "evidence_examples": ["internal_audit_reports", "control_self_assessments", "deficiency_tracking_log"],
            "scanner_signals": ["audit_log", "monitoring", "internal_review"],
            "keywords": ["monitoring", "internal audit", "control deficiency"],
            "source_url": SOURCE,
            "active_status": True,
        },
        {
            "framework_name": FRAMEWORK,
            "framework_version": VERSION,
            "control_id": "CC5",
            "control_family": "Control Activities",
            "title": "Control Activities",
            "description": "The entity selects and develops control activities that contribute to the mitigation of risk to acceptable levels, selects and develops general controls over technology, and deploys control activities through policies that establish expectations and procedures that put policies into action.",
            "objective": "Translate identified risks into designed, deployed control activities, including technology general controls.",
            "evidence_examples": ["control_matrix", "policy_and_procedure_library", "technology_general_controls_documentation"],
            "scanner_signals": ["policy", "procedure", "control_matrix"],
            "keywords": ["control activities", "general controls", "policy deployment"],
            "source_url": SOURCE,
            "active_status": True,
        },
        # --- CC6: Logical and Physical Access Controls (8 sub-criteria) ---
        {
            "framework_name": FRAMEWORK,
            "framework_version": VERSION,
            "control_id": "CC6.1",
            "control_family": "Logical and Physical Access Controls",
            "title": "Logical Access Security Software, Infrastructure, and Architectures",
            "description": "The entity implements logical access security software, infrastructure, and architectures over protected information assets to protect them from security events, covering asset inventory, restriction of logical access, identification and authentication, network segmentation, and encryption.",
            "objective": "Prevent unauthorized logical access to protected information assets.",
            "evidence_examples": ["iam_policy", "network_segmentation_diagram", "encryption_configuration", "asset_inventory"],
            "scanner_signals": ["iam", "s3_public_access", "security_group", "network_acl", "encryption_at_rest", "public_exposure"],
            "keywords": ["logical access", "asset inventory", "network segmentation", "encryption"],
            "source_url": SOURCE,
            "active_status": True,
        },
        {
            "framework_name": FRAMEWORK,
            "framework_version": VERSION,
            "control_id": "CC6.2",
            "control_family": "Logical and Physical Access Controls",
            "title": "User Registration and Authorization",
            "description": "Prior to issuing system credentials and granting system access, the entity registers and authorizes new internal and external users whose access is administered by the entity, and access is removed when access is no longer authorized.",
            "objective": "Ensure credentials are issued only to authorized users and revoked promptly when access is no longer required.",
            "evidence_examples": ["onboarding_offboarding_procedure", "access_provisioning_tickets", "deprovisioning_log"],
            "scanner_signals": ["iam_user", "stale_credentials", "orphaned_account"],
            "keywords": ["user registration", "provisioning", "deprovisioning"],
            "source_url": SOURCE,
            "active_status": True,
        },
        {
            "framework_name": FRAMEWORK,
            "framework_version": VERSION,
            "control_id": "CC6.3",
            "control_family": "Logical and Physical Access Controls",
            "title": "Role-Based Access and Least Privilege",
            "description": "The entity authorizes, modifies, or removes access to data, software, functions, and other protected information assets based on roles, responsibilities, or the system design and changes, giving consideration to the concepts of least privilege and segregation of duties.",
            "objective": "Ensure access rights reflect job function and minimize unnecessary privilege.",
            "evidence_examples": ["rbac_policy", "access_review_report", "segregation_of_duties_matrix"],
            "scanner_signals": ["rbac", "iam_policy", "least_privilege", "wildcard_permission", "overly_permissive_role"],
            "keywords": ["role-based access", "least privilege", "segregation of duties"],
            "source_url": SOURCE,
            "active_status": True,
        },
        {
            "framework_name": FRAMEWORK,
            "framework_version": VERSION,
            "control_id": "CC6.4",
            "control_family": "Logical and Physical Access Controls",
            "title": "Physical Access Restriction",
            "description": "The entity restricts physical access to facilities and protected information assets (for example, data center facilities, backup media storage, and other sensitive locations) to authorized personnel to meet the entity's objectives.",
            "objective": "Prevent unauthorized physical access to facilities housing protected information assets.",
            "evidence_examples": ["badge_access_logs", "data_center_access_policy", "visitor_log"],
            "scanner_signals": ["physical", "badge", "data_center"],
            "keywords": ["physical access", "data center security"],
            "source_url": SOURCE,
            "active_status": True,
        },
        {
            "framework_name": FRAMEWORK,
            "framework_version": VERSION,
            "control_id": "CC6.5",
            "control_family": "Logical and Physical Access Controls",
            "title": "Decommissioning of Protections",
            "description": "The entity discontinues logical and physical protections over physical assets only after the ability to read or recover data and software from those assets has been diminished and is no longer required to meet the entity's objectives.",
            "objective": "Ensure data cannot be recovered from decommissioned assets before protections are removed.",
            "evidence_examples": ["asset_decommissioning_procedure", "media_destruction_certificate"],
            "scanner_signals": ["asset_disposal", "decommission", "orphaned_resource"],
            "keywords": ["decommissioning", "asset disposal", "data destruction"],
            "source_url": SOURCE,
            "active_status": True,
        },
        {
            "framework_name": FRAMEWORK,
            "framework_version": VERSION,
            "control_id": "CC6.6",
            "control_family": "Logical and Physical Access Controls",
            "title": "Protection Against External Threats",
            "description": "The entity implements logical access security measures to protect against threats from sources outside its system boundaries, including boundary protection systems, network segmentation, and restriction of inbound and outbound network traffic.",
            "objective": "Limit exposure of systems and data to threats originating outside the entity's system boundary.",
            "evidence_examples": ["firewall_rules", "network_security_group_config", "boundary_protection_diagram"],
            "scanner_signals": ["security_group", "network_security_group", "firewall", "public_ip", "open_ingress", "0.0.0.0/0"],
            "keywords": ["boundary protection", "network segmentation", "firewall"],
            "source_url": SOURCE,
            "active_status": True,
        },
        {
            "framework_name": FRAMEWORK,
            "framework_version": VERSION,
            "control_id": "CC6.7",
            "control_family": "Logical and Physical Access Controls",
            "title": "Restriction of Data Transmission and Movement",
            "description": "The entity restricts the transmission, movement, and removal of information to authorized internal and external users and processes, and protects it during transmission, movement, or removal to meet the entity's objectives, including through encryption.",
            "objective": "Protect information in transit or in the process of being moved or removed from the system.",
            "evidence_examples": ["encryption_in_transit_config", "data_loss_prevention_policy", "secure_transfer_procedure"],
            "scanner_signals": ["tls", "encryption_in_transit", "unencrypted_transport", "dlp"],
            "keywords": ["data transmission", "encryption in transit", "data loss prevention"],
            "source_url": SOURCE,
            "active_status": True,
        },
        {
            "framework_name": FRAMEWORK,
            "framework_version": VERSION,
            "control_id": "CC6.8",
            "control_family": "Logical and Physical Access Controls",
            "title": "Prevention and Detection of Unauthorized or Malicious Software",
            "description": "The entity implements controls to prevent or detect and act upon the introduction of unauthorized or malicious software to meet the entity's objectives.",
            "objective": "Reduce the risk of malware or unauthorized software compromising protected information assets.",
            "evidence_examples": ["container_image_scan_results", "endpoint_protection_dashboard", "malware_detection_alerts"],
            "scanner_signals": ["cve", "vulnerability_scan", "container_image_scan", "malware", "known_vulnerability"],
            "keywords": ["malware", "unauthorized software", "vulnerability scanning"],
            "source_url": SOURCE,
            "active_status": True,
        },
        # --- CC7: System Operations (5 sub-criteria) ---
        {
            "framework_name": FRAMEWORK,
            "framework_version": VERSION,
            "control_id": "CC7.1",
            "control_family": "System Operations",
            "title": "Detection and Monitoring of New Vulnerabilities",
            "description": "To meet its objectives, the entity uses detection and monitoring procedures to identify changes to configurations that result in the introduction of new vulnerabilities, and susceptibilities to newly discovered vulnerabilities.",
            "objective": "Detect configuration changes and newly disclosed vulnerabilities that introduce new risk.",
            "evidence_examples": ["vulnerability_scan_reports", "configuration_drift_alerts", "cve_feed_subscription"],
            "scanner_signals": ["config_drift", "misconfiguration", "vulnerability_scan", "cve"],
            "keywords": ["vulnerability detection", "configuration monitoring"],
            "source_url": SOURCE,
            "active_status": True,
        },
        {
            "framework_name": FRAMEWORK,
            "framework_version": VERSION,
            "control_id": "CC7.2",
            "control_family": "System Operations",
            "title": "Monitoring for Security Events",
            "description": "The entity monitors system components and the operation of controls for anomalies that are indicative of malicious acts, natural disasters, and errors affecting the entity's ability to meet its objectives, and evaluates whether the anomalies represent security events.",
            "objective": "Detect anomalies that may indicate a security event requiring further evaluation and response.",
            "evidence_examples": ["siem_dashboard", "anomaly_detection_alerts", "log_monitoring_configuration"],
            "scanner_signals": ["siem", "anomaly_detection", "log_monitoring", "unusual_activity"],
            "keywords": ["security event monitoring", "anomaly detection", "SIEM"],
            "source_url": SOURCE,
            "active_status": True,
        },
        {
            "framework_name": FRAMEWORK,
            "framework_version": VERSION,
            "control_id": "CC7.3",
            "control_family": "System Operations",
            "title": "Evaluation of Security Events",
            "description": "The entity evaluates security events to determine whether they could or did result in a failure of the entity to meet its objectives (security incidents) and, if so, takes actions to prevent or address such failures.",
            "objective": "Triage detected anomalies to determine whether they constitute a security incident.",
            "evidence_examples": ["incident_triage_log", "security_event_evaluation_criteria"],
            "scanner_signals": ["incident_triage", "security_event"],
            "keywords": ["security event evaluation", "incident triage"],
            "source_url": SOURCE,
            "active_status": True,
        },
        {
            "framework_name": FRAMEWORK,
            "framework_version": VERSION,
            "control_id": "CC7.4",
            "control_family": "System Operations",
            "title": "Incident Response",
            "description": "The entity responds to identified security incidents by executing a defined incident response program to understand, contain, remediate, and communicate security incidents, as appropriate.",
            "objective": "Ensure a defined, executed process exists for containing and remediating security incidents.",
            "evidence_examples": ["incident_response_plan", "incident_postmortem_reports", "tabletop_exercise_results"],
            "scanner_signals": ["incident_response", "playbook", "breach_notification"],
            "keywords": ["incident response", "containment", "remediation"],
            "source_url": SOURCE,
            "active_status": True,
        },
        {
            "framework_name": FRAMEWORK,
            "framework_version": VERSION,
            "control_id": "CC7.5",
            "control_family": "System Operations",
            "title": "Recovery from Security Incidents",
            "description": "The entity identifies, develops, and implements activities to recover from identified security incidents.",
            "objective": "Ensure the entity can restore normal operations following a security incident.",
            "evidence_examples": ["disaster_recovery_plan", "recovery_test_results", "post_incident_recovery_report"],
            "scanner_signals": ["disaster_recovery", "recovery", "restore", "backup"],
            "keywords": ["incident recovery", "disaster recovery"],
            "source_url": SOURCE,
            "active_status": True,
        },
        # --- CC8: Change Management (1 sub-criterion) ---
        {
            "framework_name": FRAMEWORK,
            "framework_version": VERSION,
            "control_id": "CC8.1",
            "control_family": "Change Management",
            "title": "Change Management",
            "description": "The entity authorizes, designs, develops or acquires, configures, documents, tests, approves, and implements changes to infrastructure, data, software, and procedures to meet its objectives.",
            "objective": "Ensure changes to infrastructure and software are authorized, tested, and documented before deployment.",
            "evidence_examples": ["change_approval_records", "pull_request_review_log", "deployment_pipeline_policy", "change_calendar"],
            "scanner_signals": ["ci_cd", "pull_request", "deployment_pipeline", "unpinned_action", "unreviewed_change"],
            "keywords": ["change management", "deployment approval", "CI/CD"],
            "source_url": SOURCE,
            "active_status": True,
        },
        # --- CC9: Risk Mitigation (2 sub-criteria) ---
        {
            "framework_name": FRAMEWORK,
            "framework_version": VERSION,
            "control_id": "CC9.1",
            "control_family": "Risk Mitigation",
            "title": "Business Disruption Risk Mitigation",
            "description": "The entity identifies, selects, and develops risk mitigation activities for risks arising from potential business disruptions.",
            "objective": "Reduce the impact of events that could disrupt business operations.",
            "evidence_examples": ["business_continuity_plan", "insurance_documentation", "bcp_dr_test_results"],
            "scanner_signals": ["business_continuity", "disaster_recovery_plan"],
            "keywords": ["business continuity", "disruption risk"],
            "source_url": SOURCE,
            "active_status": True,
        },
        {
            "framework_name": FRAMEWORK,
            "framework_version": VERSION,
            "control_id": "CC9.2",
            "control_family": "Risk Mitigation",
            "title": "Vendor and Business Partner Risk Management",
            "description": "The entity assesses and manages risks associated with vendors and business partners.",
            "objective": "Ensure third-party relationships do not introduce unmanaged security risk.",
            "evidence_examples": ["vendor_risk_assessment", "third_party_contract_review", "supply_chain_inventory"],
            "scanner_signals": ["vendor_risk", "third_party", "supply_chain", "dependency_scan"],
            "keywords": ["vendor risk", "third-party management", "supply chain"],
            "source_url": SOURCE,
            "active_status": True,
        },
    ]

    op.bulk_insert(control_table, controls)


def downgrade():
    op.execute(
        f"DELETE FROM control_catalog WHERE framework_name = 'SOC 2 Trust Services Criteria (TSC) 2022'"
    )