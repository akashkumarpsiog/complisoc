"""Locust load test for Complisoc API.

Run with:
    locust -f tests/load/locustfile.py --headless -u 50 -r 5 --run-time 1m --host=http://127.0.0.1:8000

Or via pytest:
    pytest tests/load/test_locust.py -v
"""

from __future__ import annotations

import json
import os
import socket
import time
from typing import Any

import pytest

try:
    from locust import HttpUser, between, task

    _LOCUST_AVAILABLE = True
except (ImportError, RecursionError, Exception):
    _LOCUST_AVAILABLE = False


BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex((host, port)) == 0


def _backend_available() -> bool:
    return _port_in_use("127.0.0.1", 8000)


def _load_locust():
    if not _LOCUST_AVAILABLE:
        pytest.skip("locust not available")
    from locust import HttpUser, between, task

    return HttpUser, between, task


@pytest.mark.skipif(not _LOCUST_AVAILABLE, reason="locust not available")
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


if _LOCUST_AVAILABLE:
    class ComplisocUser(HttpUser):
        wait_time = between(0.5, 2)
        host = BACKEND_URL

        @task(4)
        def health(self):
            self.client.get("/api/v1/health")

        @task(3)
        def scanners(self):
            self.client.get("/api/v1/scanners")

        @task(3)
        def scan_runs(self):
            self.client.get("/api/v1/scan-runs")

        @task(2)
        def dashboard_gap(self):
            self.client.get("/api/v1/dashboard/gap-summary")

        @task(2)
        def coverage(self):
            self.client.get("/api/v1/dashboard/control-coverage")

        @task(1)
        def severity_distribution(self):
            self.client.get("/api/v1/dashboard/severity-distribution")
