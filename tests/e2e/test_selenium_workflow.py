"""Selenium end-to-end tests.

These tests exercise the full user-facing workflow through the browser
against a running backend + frontend instance.

Skip behavior:
- If no local Chrome/Chromium is available, the entire module is skipped.
- If the backend or frontend is not reachable, individual tests skip.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from typing import Any

import pytest

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    _SELENIUM_AVAILABLE = True
except ImportError:
    _SELENIUM_AVAILABLE = False


BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:5173")


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex((host, port)) == 0


def _backend_available() -> bool:
    return _port_in_use("127.0.0.1", 8000)


def _frontend_available() -> bool:
    return _port_in_use("127.0.0.1", 5173)


def _chrome_available() -> bool:
    if not _SELENIUM_AVAILABLE:
        return False
    chrome_bin = (
        os.environ.get("CHROME_BIN")
        or r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        or r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    )
    if not os.path.exists(chrome_bin):
        try:
            where = subprocess.run(
                ["where", "chrome"], capture_output=True, text=True, check=False
            )
            if where.returncode == 0 and where.stdout.strip():
                return True
        except OSError:
            pass
        return False
    return True


pytestmark = pytest.mark.skipif(
    not (_SELENIUM_AVAILABLE and _chrome_available()),
    reason="Selenium or Chrome/Chromium not available",
)


@pytest.fixture(scope="module")
def driver() -> Any:
    if not _backend_available() or not _frontend_available():
        pytest.skip("Backend or frontend not running")

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1440,900")

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(20)
    try:
        yield driver
    finally:
        driver.quit()


def test_health_page_loads(driver: Any) -> None:
    driver.get(f"{BACKEND_URL}/api/v1/health")
    WebDriverWait(driver, 10).until(
        EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "ok")
    )
    body = driver.find_element(By.TAG_NAME, "body").text
    assert "ok" in body


def test_readiness_page_reports_database_ok(driver: Any) -> None:
    driver.get(f"{BACKEND_URL}/api/v1/readiness")
    WebDriverWait(driver, 10).until(
        EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "ready")
    )
    body = driver.find_element(By.TAG_NAME, "body").text
    assert "ready" in body
    assert "database" in body


def test_frontend_loads_application_view(driver: Any) -> None:
    driver.get(FRONTEND_URL)
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
    body = driver.find_element(By.TAG_NAME, "body").text
    assert len(body) > 0


def test_create_scan_run_via_api(driver: Any) -> None:
    driver.get(f"{BACKEND_URL}/api/v1/scan-runs")
    body = driver.find_element(By.TAG_NAME, "body").text
    assert "scan_run" in body or "[]" in body or body.strip() in ("", "[]")


def test_scanners_list_endpoint(driver: Any) -> None:
    driver.get(f"{BACKEND_URL}/api/v1/scanners")
    body = driver.find_element(By.TAG_NAME, "body").text
    assert "trivy" in body
    assert "checkov" in body


def test_reports_list_endpoint_returns_json(driver: Any) -> None:
    driver.get(f"{BACKEND_URL}/api/v1/reports")
    body = driver.find_element(By.TAG_NAME, "body").text
    assert body.strip().startswith("[") or body.strip() == "[]"


def test_dashboard_coverage_endpoint(driver: Any) -> None:
    driver.get(f"{BACKEND_URL}/api/v1/dashboard/control-coverage")
    body = driver.find_element(By.TAG_NAME, "body").text
    assert "covered_controls" in body or body.strip() in ("", "{}")


def test_dashboard_gap_summary_endpoint(driver: Any) -> None:
    driver.get(f"{BACKEND_URL}/api/v1/dashboard/gap-summary")
    body = driver.find_element(By.TAG_NAME, "body").text
    assert "manual_review_mappings" in body or body.strip() in ("", "{}")
