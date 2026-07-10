"""Standalone Locust file for Complisoc API load testing.

Usage:
    locust -f tests/load/locustfile.py --headless -u 50 -r 5 --run-time 1m --host=http://127.0.0.1:8000
"""

from __future__ import annotations

import os

try:
    from locust import HttpUser, between, task

    class ComplisocUser(HttpUser):
        wait_time = between(0.5, 2)
        host = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

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

except (ImportError, RecursionError, Exception):
    pass
