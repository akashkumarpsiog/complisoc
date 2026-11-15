"""Add missing ISO 27001:2022 controls used by the audited benchmark.

Revision ID: 0011_correct_iso27001_benchmark_controls
Revises: 0010_add_audit_bundle_manifest
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_correct_iso27001_benchmark_controls"
down_revision = "0010_add_audit_bundle_manifest"
branch_labels = None
depends_on = None


FRAMEWORK = "ISO/IEC 27001:2022 Annex A"


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

    controls = [
        {
            "framework_name": "ISO/IEC 27001:2022 Annex A",
            "framework_version": "2022",
            "control_id": "A.5.19",
            "control_family": "Organizational",
            "title": "Information security in supplier relationships",
            "description": "Manage information security risks arising from supplier products and services.",
            "objective": "Protect organizational information and assets that are accessible to or affected by suppliers.",
            "evidence_examples": ["supplier_security_assessment", "vendor_risk_register", "supplier_contract"],
            "scanner_signals": ["vendor", "supplier", "third_party", "supply_chain"],
            "keywords": ["supplier", "vendor", "third party", "supply chain"],
            "source_url": "https://www.isms.online/iso-27001/annex-a-2022/5-19-information-security-supplier-relationships-2022/",
            "active_status": True,
        },
        {
            "framework_name": "ISO/IEC 27001:2022 Annex A",
            "framework_version": "2022",
            "control_id": "A.8.8",
            "control_family": "Technological",
            "title": "Management of technical vulnerabilities",
            "description": "Obtain information about technical vulnerabilities and take appropriate measures to address them.",
            "objective": "Reduce the likelihood and impact of exploitation of technical vulnerabilities.",
            "evidence_examples": ["vulnerability_scan", "patch_report", "cve_remediation_record"],
            "scanner_signals": ["dependency", "vulnerability", "patch", "cve"],
            "keywords": ["technical vulnerability", "dependency", "patch", "CVE"],
            "source_url": "https://www.isms.online/iso-27001/annex-a-2022/8-8-management-of-technical-vulnerabilities-2022/",
            "active_status": True,
        },
        {
            "framework_name": "ISO/IEC 27001:2022 Annex A",
            "framework_version": "2022",
            "control_id": "A.8.9",
            "control_family": "Technological",
            "title": "Configuration management",
            "description": "Establish, document, implement, monitor, and review configurations for technology.",
            "objective": "Maintain secure and controlled configurations throughout the technology lifecycle.",
            "evidence_examples": ["configuration_baseline", "drift_report", "change_record"],
            "scanner_signals": ["baseline", "hardening", "misconfiguration", "configuration"],
            "keywords": ["configuration management", "baseline", "hardening", "configuration drift"],
            "source_url": "https://www.isms.online/iso-27001/annex-a-2022/8-9-configuration-management-2022/",
            "active_status": True,
        },
        {
            "framework_name": "ISO/IEC 27001:2022 Annex A",
            "framework_version": "2022",
            "control_id": "A.8.15",
            "control_family": "Technological",
            "title": "Logging",
            "description": "Produce, store, protect, and analyse logs that record relevant activities and events.",
            "objective": "Create reliable event records that support security monitoring and investigation.",
            "evidence_examples": ["audit_log_configuration", "log_retention_policy", "log_integrity_report"],
            "scanner_signals": ["logging", "audit", "trail", "log"],
            "keywords": ["logging", "audit trail", "event log"],
            "source_url": "https://www.isms.online/iso-27001/annex-a-2022/8-15-logging-2022/",
            "active_status": True,
        },
        {
            "framework_name": "ISO/IEC 27001:2022 Annex A",
            "framework_version": "2022",
            "control_id": "A.8.16",
            "control_family": "Technological",
            "title": "Monitoring activities",
            "description": "Monitor networks, systems, and applications for anomalous behaviour and potential incidents.",
            "objective": "Detect anomalous activity and assess potential information security incidents.",
            "evidence_examples": ["monitoring_configuration", "alert_rules", "security_event_review"],
            "scanner_signals": ["monitor", "monitoring", "alert", "anomaly"],
            "keywords": ["monitoring activities", "monitoring", "anomaly detection"],
            "source_url": "https://www.isms.online/iso-27001/annex-a-2022/8-16-monitoring-activities-2022/",
            "active_status": True,
        },
        {
            "framework_name": "ISO/IEC 27001:2022 Annex A",
            "framework_version": "2022",
            "control_id": "A.8.22",
            "control_family": "Technological",
            "title": "Segregation of networks",
            "description": "Separate groups of information services, users, and systems within networks.",
            "objective": "Limit exposure and lateral movement by controlling communication between network segments.",
            "evidence_examples": ["network_segmentation_diagram", "firewall_zone_rules", "subnet_policy"],
            "scanner_signals": ["segmentation", "network_zone", "dmz", "zoning"],
            "keywords": ["segregation of networks", "network segmentation", "network zones"],
            "source_url": "https://www.isms.online/iso-27001/annex-a-2022/8-22-segregation-of-networks-2022/",
            "active_status": True,
        },
    ]

    control_updates = [
        {
            "control_id": "A.8.5",
            "control_family": "Technological",
            "title": "Secure authentication",
            "description": "Implement secure authentication technologies and procedures appropriate to access risks.",
            "objective": "Ensure users and systems authenticate securely before accessing information and services.",
            "evidence_examples": ["mfa_report"],
            "scanner_signals": ["mfa", "authentication", "password"],
            "keywords": ["mfa", "authentication", "password", "credential"],
            "source_url": "https://www.isms.online/iso-27001/annex-a-2022/8-5-secure-authentication-2022/",
        },
        {"control_id": "A.8.20", "title": "Networks security"},
    ]
    op.bulk_insert(control_table, controls)
    for update in control_updates:
        control_id = update["control_id"]
        values = {key: value for key, value in update.items() if key != "control_id"}
        op.execute(
            control_table.update()
            .where(
                sa.and_(
                    control_table.c.framework_name == FRAMEWORK,
                    control_table.c.framework_version == "2022",
                    control_table.c.control_id == control_id,
                )
            )
            .values(**values)
        )


def downgrade():
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
    )
    added_ids = ["A.5.19", "A.8.8", "A.8.9", "A.8.15", "A.8.16", "A.8.22"]
    op.execute(
        control_table.delete().where(
            sa.and_(
                control_table.c.framework_name == FRAMEWORK,
                control_table.c.framework_version == "2022",
                control_table.c.control_id.in_(added_ids),
            )
        )
    )
    op.execute(
        control_table.update()
        .where(
            sa.and_(
                control_table.c.framework_name == FRAMEWORK,
                control_table.c.framework_version == "2022",
                control_table.c.control_id == "A.8.5",
            )
        )
        .values(
            control_family="Technological",
            title="Secure Authentication",
            description="Use secure authentication mechanisms to protect system access from unauthorized use.",
            objective="Ensure authentication is strong, manageable, and resistant to common credential attacks.",
            evidence_examples=["mfa_policy", "authentication_configuration", "failed_login_report"],
            scanner_signals=["mfa", "auth", "password_policy"],
            keywords=["authentication", "MFA", "single sign-on"],
            source_url="https://www.isms.online/iso-27001/annex-a-2022/8-5-secure-authentication-2022/",
        )
    )
    op.execute(
        control_table.update()
        .where(
            sa.and_(
                control_table.c.framework_name == FRAMEWORK,
                control_table.c.framework_version == "2022",
                control_table.c.control_id == "A.8.20",
            )
        )
        .values(title="Network Security")
    )
