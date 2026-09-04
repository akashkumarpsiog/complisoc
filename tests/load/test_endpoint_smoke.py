"""Endpoint smoke tests for the Complisoc API.

These tests do a small number of sequential HTTP requests against each
backend endpoint to prove the service is reachable and answering
correctly. They are not a load test — for concurrent load, use
``locust -f tests/load/locustfile.py`` (see ``locustfile.py`` for
endpoint weights and configuration).

Run via pytest:

    pytest tests/load/test_endpoint_smoke.py -v
"""
from __future__ import annotations

import json
import os
import socket
import time
from typing import Any

import pytest

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex((host, port)) == 0


def _backend_available() -> bool:
    return _port_in_use("127.0.0.1", 8000)


class TestLocustLoadScenarios:
    """Run lightweight locust-style load scenarios against a live backend."""

    @pytest.fixture()
    def api_url(self):
        if not _backend_available():
            pytest.skip("Backend not running on 127.0.0.1:8000")
        return BACKEND_URL

    def test_health_endpoint_under_sequential_load(self, api_url: str) -> None:
        import urllib.request

        failures = 0
        success = 0
        for _ in range(20):
            try:
                with urllib.request.urlopen(f"{api_url}/api/v1/health", timeout=5) as resp:
                    if resp.status == 200:
                        success += 1
            except Exception:
                failures += 1
            time.sleep(0.05)

        assert success >= 15
        assert failures <= 5

    def test_scanners_list_endpoint_load(self, api_url: str) -> None:
        import urllib.request

        failures = 0
        success = 0
        for _ in range(10):
            try:
                with urllib.request.urlopen(f"{api_url}/api/v1/scanners", timeout=5) as resp:
                    if resp.status == 200:
                        success += 1
            except Exception:
                failures += 1
            time.sleep(0.05)

        assert success >= 8
        assert failures <= 2

    def test_scan_runs_list_endpoint_load(self, api_url: str) -> None:
        import urllib.request

        failures = 0
        success = 0
        for _ in range(10):
            try:
                with urllib.request.urlopen(f"{api_url}/api/v1/scan-runs", timeout=5) as resp:
                    if resp.status == 200:
                        success += 1
            except Exception:
                failures += 1
            time.sleep(0.05)

        assert success >= 8
        assert failures <= 2

    def test_dashboard_gap_summary_endpoint_load(self, api_url: str) -> None:
        import urllib.request

        failures = 0
        success = 0
        for _ in range(10):
            try:
                with urllib.request.urlopen(f"{api_url}/api/v1/dashboard/gap-summary", timeout=5) as resp:
                    if resp.status == 200:
                        success += 1
            except Exception:
                failures += 1
            time.sleep(0.05)

        assert success >= 8
        assert failures <= 2
