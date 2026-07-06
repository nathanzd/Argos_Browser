from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from browser import BrowserManager
from exceptions import BrowserAlreadyStartedError, BrowserNotStartedError


class TestBrowserManager:
    def test_singleton(self):
        b1 = BrowserManager()
        b2 = BrowserManager()
        assert b1 is b2

    def test_initial_state(self, browser_manager: BrowserManager):
        assert browser_manager.is_running is False
        assert browser_manager.uptime_seconds == 0.0
        assert browser_manager.commands_executed == 0

    def test_get_driver_before_start_raises(self, browser_manager: BrowserManager):
        with pytest.raises(BrowserNotStartedError):
            _ = browser_manager.driver

    def test_start_success(self, browser_manager: BrowserManager, mock_driver: MagicMock):
        with patch.object(browser_manager, "_build_options", return_value=MagicMock()):
            with patch("selenium.webdriver.Edge", return_value=mock_driver):
                driver = browser_manager.start()

        assert driver is mock_driver
        assert browser_manager.is_running is True
        assert browser_manager._start_time is not None
        mock_driver.implicitly_wait.assert_called_once()
        mock_driver.set_page_load_timeout.assert_called_once()
        mock_driver.set_script_timeout.assert_called_once()

    def test_double_start_raises(self, browser_manager: BrowserManager, mock_driver: MagicMock):
        with patch.object(browser_manager, "_build_options", return_value=MagicMock()):
            with patch("selenium.webdriver.Edge", return_value=mock_driver):
                browser_manager.start()

        with pytest.raises(BrowserAlreadyStartedError):
            browser_manager.start()

    def test_stop_success(self, browser_manager: BrowserManager, mock_driver: MagicMock):
        with patch.object(browser_manager, "_build_options", return_value=MagicMock()):
            with patch("selenium.webdriver.Edge", return_value=mock_driver):
                browser_manager.start()

        browser_manager.stop()

        assert browser_manager.is_running is False
        assert browser_manager.uptime_seconds == 0.0
        mock_driver.quit.assert_called_once()

    def test_stop_before_start_raises(self, browser_manager: BrowserManager):
        with pytest.raises(BrowserNotStartedError):
            browser_manager.stop()

    def test_restart(self, browser_manager: BrowserManager, mock_driver: MagicMock):
        with patch.object(browser_manager, "_build_options", return_value=MagicMock()):
            with patch("selenium.webdriver.Edge", return_value=mock_driver):
                first_driver = browser_manager.start()
                browser_manager.restart()

        assert browser_manager.is_running is True
        assert first_driver.quit.called

    def test_increment_commands(self, browser_manager: BrowserManager):
        browser_manager.increment_commands()
        assert browser_manager.commands_executed == 1
        browser_manager.increment_commands()
        assert browser_manager.commands_executed == 2

    def test_edge_options(self, browser_manager: BrowserManager):
        options = browser_manager._build_options()
        assert options is not None

    def test_driver_property(self, browser_manager: BrowserManager, mock_driver: MagicMock):
        with patch.object(browser_manager, "_build_options", return_value=MagicMock()):
            with patch("selenium.webdriver.Edge", return_value=mock_driver):
                browser_manager.start()

        assert browser_manager.driver is mock_driver

    def test_is_running_returns_false_on_exception(self, browser_manager: BrowserManager):
        dead_driver = MagicMock()
        dead_driver.current_url
        type(dead_driver).current_url = PropertyMock(side_effect=Exception("tab crashed"))
        browser_manager._driver = dead_driver
        assert browser_manager.is_running is False

    @patch("browser.settings.DOWNLOAD_DIR", "C:\\downloads")
    def test_build_options_includes_download_dir(self, browser_manager: BrowserManager):
        options = browser_manager._build_options()
        assert options is not None

    @patch("browser.settings.EDGE_PROFILE_DIR", "C:\\profile")
    def test_build_options_includes_profile_dir(self, browser_manager: BrowserManager):
        options = browser_manager._build_options()
        assert options is not None

    def test_health_check_start_stop(self, browser_manager: BrowserManager):
        browser_manager.start_health_check()
        assert browser_manager._health_thread is not None
        assert browser_manager._health_thread.is_alive()
        browser_manager.stop_health_check()
        assert browser_manager._health_thread is None

    def test_health_check_double_start(self, browser_manager: BrowserManager):
        browser_manager.start_health_check()
        t1 = browser_manager._health_thread
        browser_manager.start_health_check()
        assert browser_manager._health_thread is t1
        browser_manager.stop_health_check()

    def test_health_check_stop_without_start(self, browser_manager: BrowserManager):
        browser_manager.stop_health_check()
        assert browser_manager._health_thread is None

    def test_is_healthy_returns_true(self, browser_manager: BrowserManager, mock_driver: MagicMock):
        browser_manager._driver = mock_driver
        assert browser_manager._is_healthy() is True

    def test_is_healthy_returns_false_on_exception(self, browser_manager: BrowserManager):
        dead_driver = MagicMock()
        type(dead_driver).current_url = PropertyMock(side_effect=Exception("crashed"))
        browser_manager._driver = dead_driver
        assert browser_manager._is_healthy() is False

    def test_is_healthy_returns_false_no_driver(self, browser_manager: BrowserManager):
        assert browser_manager._is_healthy() is False

    def test_health_loop_restarts_on_failure(self, browser_manager: BrowserManager, mock_driver: MagicMock):
        browser_manager._driver = mock_driver
        type(mock_driver).current_url = PropertyMock(side_effect=Exception("crashed"))
        restart_called = False
        def _stop_after_restart() -> None:
            nonlocal restart_called
            restart_called = True
            browser_manager._health_stop.set()
            browser_manager._driver = None
        with patch.object(browser_manager, "restart", side_effect=_stop_after_restart):
            browser_manager._health_loop()
        assert restart_called is True
