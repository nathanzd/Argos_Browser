from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from browser import BrowserManager
from server import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestHealth:
    def test_health_returns_ok(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"


class TestStatus:
    def test_status_returns_structure(self, client: TestClient, started_browser: BrowserManager):
        with patch("server.browser", started_browser):
            response = client.get("/status")
        assert response.status_code == 200
        data = response.json()
        assert "browser_running" in data
        assert "active_sessions" in data
        assert "commands_executed" in data
        assert "uptime_seconds" in data

    def test_status_browser_running(self, client: TestClient, started_browser: BrowserManager):
        with patch("server.browser", started_browser):
            response = client.get("/status")
        assert response.json()["browser_running"] is True

    def test_status_browser_not_running(self, client: TestClient, browser_manager: BrowserManager):
        with patch("server.browser", browser_manager):
            response = client.get("/status")
        assert response.json()["browser_running"] is False


class TestExecute:
    def test_execute_success(self, client: TestClient, started_browser: BrowserManager):
        with patch("server.browser", started_browser):
            response = client.post("/execute", json={"command": "1 + 1"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["result"] == 2

    def test_execute_with_session(self, client: TestClient, started_browser: BrowserManager):
        with patch("server.browser", started_browser):
            session_resp = client.post("/session")
            session_id = session_resp.json()["session_id"]

            client.post(
                "/execute",
                json={"command": "x = 99", "session_id": session_id},
            )
            resp2 = client.post(
                "/execute",
                json={"command": "x", "session_id": session_id},
            )
        assert resp2.status_code == 200
        assert resp2.json()["result"] == 99

    def test_execute_error(self, client: TestClient, started_browser: BrowserManager):
        with patch("server.browser", started_browser):
            response = client.post("/execute", json={"command": "1/0"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "division by zero" in data["exception"]

    def test_execute_without_browser(self, client: TestClient, browser_manager: BrowserManager):
        with patch("server.browser", browser_manager):
            response = client.post("/execute", json={"command": "1+1"})
        assert response.status_code == 503
        assert "not running" in response.json()["detail"].lower()

    def test_execute_empty_command(self, client: TestClient, started_browser: BrowserManager):
        with patch("server.browser", started_browser):
            response = client.post("/execute", json={"command": ""})
        assert response.status_code == 422

    def test_execute_invalid_session(self, client: TestClient, started_browser: BrowserManager):
        with patch("server.browser", started_browser):
            response = client.post(
                "/execute",
                json={"command": "1+1", "session_id": "non-existent"},
            )
        assert response.status_code == 404

    def test_execute_driver_get(self, client: TestClient, started_browser: BrowserManager):
        with patch("server.browser", started_browser):
            response = client.post(
                "/execute", json={"command": 'driver.get("https://example.com")'}
            )
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_execute_driver_title(self, client: TestClient, started_browser: BrowserManager, mock_driver: MagicMock):
        with patch("server.browser", started_browser):
            started_browser._driver = mock_driver
            mock_driver.title = "Test Page"
            response = client.post("/execute", json={"command": "driver.title"})
        assert response.status_code == 200
        assert response.json()["result"] == "Test Page"

    def test_execute_security_violation(self, client: TestClient, started_browser: BrowserManager):
        with patch("server.browser", started_browser):
            response = client.post(
                "/execute", json={"command": 'open("/etc/passwd")'}
            )
        assert response.status_code == 200
        assert response.json()["success"] is False
        assert "not allowed" in response.json()["exception"].lower()


class TestSession:
    def test_create_session(self, client: TestClient):
        response = client.post("/session")
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert len(data["session_id"]) > 0

    def test_delete_session(self, client: TestClient):
        create_resp = client.post("/session")
        session_id = create_resp.json()["session_id"]

        delete_resp = client.delete(f"/session/{session_id}")
        assert delete_resp.status_code == 200
        assert "deleted" in delete_resp.json()["message"].lower()

    def test_delete_nonexistent_session(self, client: TestClient):
        response = client.delete("/session/non-existent")
        assert response.status_code == 404

    def test_multiple_sessions(self, client: TestClient):
        resp1 = client.post("/session")
        resp2 = client.post("/session")
        assert resp1.json()["session_id"] != resp2.json()["session_id"]


class TestRestartAndClose:
    def test_restart(self, client: TestClient, started_browser: BrowserManager):
        with patch("server.browser", started_browser):
            response = client.post("/restart")
        assert response.status_code == 200
        assert "successfully" in response.json()["message"].lower()

    def test_close(self, client: TestClient, started_browser: BrowserManager):
        with patch("server.browser", started_browser):
            response = client.post("/close")
        assert response.status_code == 200
        assert "successfully" in response.json()["message"].lower()

    def test_close_when_not_running(self, client: TestClient, browser_manager: BrowserManager):
        with patch("server.browser", browser_manager):
            response = client.post("/close")
        assert response.status_code == 500


class TestScreenshots:
    def test_list_screenshots_empty(self, client: TestClient, tmp_path: Path):
        from config import settings as _settings
        with patch.object(_settings, "DOWNLOAD_DIR", tmp_path):
            response = client.get("/screenshots")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_screenshots(self, client: TestClient, tmp_path: Path):
        from config import settings as _settings
        (tmp_path / "screenshot_20250101_120000.jpg").touch()
        (tmp_path / "not_a_screenshot.txt").touch()
        with patch.object(_settings, "DOWNLOAD_DIR", tmp_path):
            response = client.get("/screenshots")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0] == "screenshot_20250101_120000.jpg"

    def test_get_screenshot_found(self, client: TestClient, tmp_path: Path):
        from config import settings as _settings
        img = Image.new("RGB", (10, 10), (255, 0, 0))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=50)
        filepath = tmp_path / "screenshot_test.jpg"
        filepath.write_bytes(buf.getvalue())
        with patch.object(_settings, "DOWNLOAD_DIR", tmp_path):
            response = client.get("/screenshots/screenshot_test.jpg")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"

    def test_get_screenshot_not_found(self, client: TestClient, tmp_path: Path):
        from config import settings as _settings
        with patch.object(_settings, "DOWNLOAD_DIR", tmp_path):
            response = client.get("/screenshots/nonexistent.jpg")
        assert response.status_code == 404
