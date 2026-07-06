from __future__ import annotations

import threading
from typing import Any, Generator
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from fastapi.testclient import TestClient

from browser import BrowserManager
from executor import CommandExecutor
from interactive import SessionManager
from sandbox import build_safe_namespace


@pytest.fixture
def mock_driver() -> MagicMock:
    driver = MagicMock()
    driver.current_url = "https://example.com"
    driver.title = "Example Domain"
    driver.page_source = "<html><body>Hello</body></html>"
    type(driver).service = PropertyMock(
        return_value=MagicMock(process=MagicMock(pid=12345))
    )
    return driver


@pytest.fixture
def browser_manager() -> Generator[BrowserManager, None, None]:
    bm = BrowserManager()
    bm._driver = None
    bm._start_time = None
    bm._commands_executed = 0
    bm._health_stop = threading.Event()
    bm._health_thread = None
    yield bm


@pytest.fixture
def started_browser(browser_manager: BrowserManager, mock_driver: MagicMock) -> BrowserManager:
    with patch.object(browser_manager, "_build_options", return_value=MagicMock()):
        with patch("selenium.webdriver.Edge", return_value=mock_driver):
            browser_manager.start()
    yield browser_manager
    browser_manager._driver = None
    browser_manager._start_time = None


@pytest.fixture
def command_executor() -> CommandExecutor:
    return CommandExecutor(timeout=5.0)


@pytest.fixture
def session_manager() -> SessionManager:
    return SessionManager()


@pytest.fixture
def safe_namespace(mock_driver: MagicMock) -> dict[str, Any]:
    return build_safe_namespace(mock_driver)


@pytest.fixture
def api_client(started_browser: BrowserManager) -> Generator[TestClient, None, None]:
    with patch("server.browser", started_browser):
        from server import app
        with TestClient(app) as client:
            yield client
