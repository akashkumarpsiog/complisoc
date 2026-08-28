"""Shared test fixtures for AI quality tests.

Provides TestDataGenerator and other utilities as pytest fixtures.
"""
from __future__ import annotations

import os
import sys

import pytest

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from tests.ai_quality.generators.test_data_generator import TestDataGenerator


@pytest.fixture
def data_generator() -> TestDataGenerator:
    """Provide a deterministic TestDataGenerator."""
    return TestDataGenerator(seed=42)


@pytest.fixture
def sample_findings(data_generator: TestDataGenerator) -> list:
    """Generate a batch of sample findings."""
    return data_generator.generate_batch(10)


@pytest.fixture
def sample_controls(data_generator: TestDataGenerator) -> list:
    """Generate a batch of sample controls."""
    return [data_generator.generate_control() for _ in range(5)]


@pytest.fixture
def sample_finding_control_pairs(data_generator: TestDataGenerator) -> list:
    """Generate matching finding-control pairs."""
    return [data_generator.generate_finding_control_pair() for _ in range(5)]


@pytest.fixture
def adversarial_findings(data_generator: TestDataGenerator) -> list:
    """Generate adversarial test findings."""
    return [data_generator.generate_adversarial_finding() for _ in range(10)]


@pytest.fixture
def mock_gemini_response() -> dict:
    """Provide a mock Gemini API response."""
    return {
        "results": [
            {
                "finding_id": 1,
                "candidates": [
                    {"control_id": "AC-1", "maps": True, "confidence": 0.95, "rationale": "direct match"},
                    {"control_id": "AC-2", "maps": False, "confidence": 0.2, "rationale": "unrelated"},
                ],
            }
        ]
    }


@pytest.fixture
def mock_groq_response() -> dict:
    """Provide a mock Groq API response."""
    return {
        "results": [
            {"ref": 1, "result": "agree", "explanation": "correct mapping"},
        ]
    }


@pytest.fixture
def performance_benchmarks() -> list:
    """Provide performance benchmarks for AI operations."""
    return [
        {"operation": "single_mapping", "max_latency_ms": 2000, "max_tokens": 500},
        {"operation": "batch_mapping_10", "max_latency_ms": 5000, "max_tokens": 2000},
        {"operation": "single_verification", "max_latency_ms": 2000, "max_tokens": 400},
    ]
