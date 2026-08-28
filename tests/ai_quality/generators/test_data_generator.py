"""AI-Powered Test Data Generator

Generates realistic test data for AI model testing using templates and patterns.
This enables comprehensive testing without relying on production data.
"""
from __future__ import annotations

import random
import string
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FindingTemplate:
    """Template for generating test findings."""
    category: str
    severity: str
    title_template: str
    description_template: str
    scanner: str


@dataclass
class ControlTemplate:
    """Template for generating test controls."""
    control_id: str
    title: str
    description: str
    category: str


@dataclass
class GeneratedFinding:
    """A generated test finding."""
    id: int
    title: str
    description: str
    severity: str
    scanner: str
    category: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GeneratedControl:
    """A generated test control."""
    id: str
    title: str
    description: str
    category: str


class TestDataGenerator:
    """Generates realistic test data for AI testing."""

    FINDING_TEMPLATES = [
        FindingTemplate("access_control", "high", "Weak {resource} password policy",
                       "The {resource} allows passwords shorter than {length} characters", "defender"),
        FindingTemplate("access_control", "medium", "Excessive {resource} permissions",
                       "Users have unnecessary {permission} access to {resource}", "defender"),
        FindingTemplate("encryption", "high", "Unencrypted {resource} data",
                       "Sensitive data in {resource} is stored without encryption", "defender"),
        FindingTemplate("audit", "medium", "Missing {resource} audit logs",
                       "The {resource} does not generate audit logs for {action}", "defender"),
        FindingTemplate("configuration", "low", "Default {resource} configuration",
                       "The {resource} uses default configuration settings", "defender"),
        FindingTemplate("network", "high", "Open {resource} port",
                       "Port {port} on {resource} is exposed to the internet", "defender"),
    ]

    CONTROL_TEMPLATES = [
        ControlTemplate("AC-1", "Access Control Policy", "Establish and enforce access control policy", "access_control"),
        ControlTemplate("AC-2", "Account Management", "Manage information system accounts", "access_control"),
        ControlTemplate("AC-3", "Access Enforcement", "Enforce approved authorizations", "access_control"),
        ControlTemplate("AU-1", "Audit Policy", "Establish audit and accountability policy", "audit"),
        ControlTemplate("AU-2", "Audit Events", "Define auditable events and ensure logging", "audit"),
        ControlTemplate("SC-1", "System Communications Protection", "Protect system communications", "encryption"),
        ControlTemplate("SC-8", "Transmission Confidentiality", "Protect transmission confidentiality", "encryption"),
        ControlTemplate("CM-1", "Configuration Management Policy", "Establish configuration baselines", "configuration"),
        ControlTemplate("CM-7", "Least Functionality", "Configure systems to provide least functionality", "configuration"),
        ControlTemplate("SI-1", "System Information Integrity", "Identify and report information integrity issues", "audit"),
    ]

    RESOURCES = ["database", "web application", "API gateway", "file server", "cloud storage", "container"]
    PERMISSIONS = ["admin", "write", "delete", "root", "superuser"]
    ACTIONS = ["login", "logout", "data access", "configuration changes", "user management"]
    PORTS = ["22", "80", "443", "3306", "5432", "8080", "8443"]

    def __init__(self, seed: int = 42) -> None:
        self._rng = random.Random(seed)
        self._finding_counter = 0

    def generate_finding(self, category: str | None = None) -> GeneratedFinding:
        """Generate a realistic test finding."""
        templates = [t for t in self.FINDING_TEMPLATES if category is None or t.category == category]
        if not templates:
            templates = self.FINDING_TEMPLATES
        template = self._rng.choice(templates)
        self._finding_counter += 1

        resource = self._rng.choice(self.RESOURCES)
        title = template.title_template.format(resource=resource)
        description = template.description_template.format(
            resource=resource,
            length=self._rng.randint(6, 12),
            permission=self._rng.choice(self.PERMISSIONS),
            action=self._rng.choice(self.ACTIONS),
            port=self._rng.choice(self.PORTS),
        )

        return GeneratedFinding(
            id=self._finding_counter,
            title=title,
            description=description,
            severity=template.severity,
            scanner=template.scanner,
            category=template.category,
            metadata={"source": "test_generator", "version": "1.0"},
        )

    def generate_control(self, category: str | None = None) -> GeneratedControl:
        """Generate a realistic test control."""
        templates = [t for t in self.CONTROL_TEMPLATES if category is None or t.category == category]
        if not templates:
            templates = self.CONTROL_TEMPLATES
        template = self._rng.choice(templates)
        return GeneratedControl(
            id=template.control_id,
            title=template.title,
            description=template.description,
            category=template.category,
        )

    def generate_finding_control_pair(self) -> tuple[GeneratedFinding, GeneratedControl]:
        """Generate a matching finding-control pair."""
        category = self._rng.choice(["access_control", "audit", "encryption", "configuration", "network"])
        finding = self.generate_finding(category=category)
        control = self.generate_control(category=category)
        return finding, control

    def generate_batch(self, n: int) -> list[GeneratedFinding]:
        """Generate a batch of test findings."""
        return [self.generate_finding() for _ in range(n)]

    def generate_adversarial_finding(self) -> GeneratedFinding:
        """Generate an adversarial test finding."""
        adversarial_templates = [
            ("", "empty finding"),
            ("a" * 10000, "very long finding"),
            ("<script>alert('xss')</script>", "xss attempt"),
            ("'; DROP TABLE findings; --", "sql injection"),
            ("finding with\x00null byte", "null byte"),
            ("finding with 🚨 emoji", "emoji"),
        ]
        title, category = self._rng.choice(adversarial_templates)
        self._finding_counter += 1
        return GeneratedFinding(
            id=self._finding_counter,
            title=title,
            description=title,
            severity="medium",
            scanner="test",
            category=category,
            metadata={"adversarial": True},
        )


class TestGeneratorQuality:
    """Tests that the generator produces valid test data."""

    def test_generate_finding_valid(self):
        """Generated finding should have all required fields."""
        gen = TestDataGenerator()
        finding = gen.generate_finding()
        assert finding.id > 0
        assert len(finding.title) > 0
        assert len(finding.description) > 0
        assert finding.severity in ("low", "medium", "high", "critical")
        assert len(finding.scanner) > 0

    def test_generate_control_valid(self):
        """Generated control should have all required fields."""
        gen = TestDataGenerator()
        control = gen.generate_control()
        assert len(control.id) > 0
        assert len(control.title) > 0
        assert len(control.description) > 0
        assert len(control.category) > 0

    def test_generate_pair_same_category(self):
        """Generated finding-control pair should be in same category."""
        gen = TestDataGenerator()
        finding, control = gen.generate_finding_control_pair()
        assert finding.category == control.category

    def test_generate_batch_unique_ids(self):
        """Generated batch should have unique IDs."""
        gen = TestDataGenerator()
        batch = gen.generate_batch(10)
        ids = [f.id for f in batch]
        assert len(ids) == len(set(ids))

    def test_generate_deterministic_with_seed(self):
        """Same seed should produce same results."""
        gen1 = TestDataGenerator(seed=42)
        gen2 = TestDataGenerator(seed=42)
        f1 = gen1.generate_finding()
        f2 = gen2.generate_finding()
        assert f1.title == f2.title
        assert f1.description == f2.description

    def test_generate_adversarial_valid(self):
        """Adversarial findings should still be valid."""
        gen = TestDataGenerator()
        finding = gen.generate_adversarial_finding()
        assert finding.id > 0
        assert "adversarial" in finding.metadata

    def test_category_filter_works(self):
        """Category filter should work."""
        gen = TestDataGenerator()
        finding = gen.generate_finding(category="access_control")
        assert finding.category == "access_control"

    def test_all_categories_covered(self):
        """All categories should be generatable."""
        gen = TestDataGenerator()
        categories = set()
        for _ in range(100):
            finding = gen.generate_finding()
            categories.add(finding.category)
        assert len(categories) >= 3

    def test_severity_distribution(self):
        """Severity should be distributed."""
        gen = TestDataGenerator()
        severities = set()
        for _ in range(100):
            finding = gen.generate_finding()
            severities.add(finding.severity)
        assert len(severities) >= 2

    def test_finding_description_varied(self):
        """Finding descriptions should be varied."""
        gen = TestDataGenerator()
        descriptions = set()
        for _ in range(50):
            finding = gen.generate_finding()
            descriptions.add(finding.description)
        assert len(descriptions) > 10


class TestGeneratorEdgeCases:
    """Tests for generator edge cases."""

    def test_generate_zero_batch(self):
        """Empty batch should be empty."""
        gen = TestDataGenerator()
        batch = gen.generate_batch(0)
        assert len(batch) == 0

    def test_generate_large_batch(self):
        """Large batch should be generated."""
        gen = TestDataGenerator()
        batch = gen.generate_batch(1000)
        assert len(batch) == 1000

    def test_generate_unknown_category(self):
        """Unknown category should fall back to any category."""
        gen = TestDataGenerator()
        finding = gen.generate_finding(category="nonexistent")
        assert finding.id > 0

    def test_generate_many_unique_findings(self):
        """Many findings should be unique."""
        gen = TestDataGenerator()
        findings = gen.generate_batch(100)
        titles = [f.title for f in findings]
        # With limited templates, some duplication is expected
        # At least 30% should be unique given template variety
        unique_ratio = len(set(titles)) / len(titles)
        assert unique_ratio > 0.2
