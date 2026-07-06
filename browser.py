from __future__ import annotations

import threading
from typing import Any

from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service

from config import settings
from exceptions import (
    BrowserAlreadyStartedError,
    BrowserError,
    BrowserNotStartedError,
)
from utils import get_logger

logger = get_logger(__name__)


class BrowserManager:
    _instance: BrowserManager | None = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> BrowserManager:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._driver: webdriver.Edge | None = None
        self._start_time: float | None = None
        self._commands_executed: int = 0
        self._initialized = True
        self._health_stop: threading.Event = threading.Event()
        self._health_thread: threading.Thread | None = None

    @property
    def driver(self) -> webdriver.Edge:
        if self._driver is None:
            raise BrowserNotStartedError()
        return self._driver

    @property
    def is_running(self) -> bool:
        if self._driver is None:
            return False
        try:
            _ = self._driver.current_url
            return True
        except Exception:
            return False

    @property
    def commands_executed(self) -> int:
        return self._commands_executed

    def increment_commands(self) -> None:
        self._commands_executed += 1

    @property
    def uptime_seconds(self) -> float:
        if self._start_time is None:
            return 0.0
        import time
        return time.time() - self._start_time

    def _build_options(self) -> Options:
        options = Options()

        if settings.HEADLESS:
            options.add_argument("--headless=new")

        options.add_argument(f"--window-size={settings.WINDOW_WIDTH},{settings.WINDOW_HEIGHT}")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-background-tasks")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-renderer-backgrounding")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--remote-debugging-port=0")
        options.add_argument(f"--user-data-dir={settings.EDGE_PROFILE_DIR}")

        prefs = {
            "download.default_directory": str(settings.DOWNLOAD_DIR),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": False,
            "profile.default_content_setting_values.automatic_downloads": 1,
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
        }
        options.add_experimental_option("prefs", prefs)
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        return options

    def start(self, edge_driver_path: str = "") -> webdriver.Edge:
        if self._driver is not None:
            raise BrowserAlreadyStartedError()

        import time
        self._start_time = time.time()
        opts = self._build_options()

        driver_path = edge_driver_path or settings.EDGE_DRIVER_PATH
        if driver_path:
            service = Service(executable_path=driver_path)
            self._driver = webdriver.Edge(service=service, options=opts)
        else:
            self._driver = webdriver.Edge(options=opts)

        self._driver.implicitly_wait(settings.IMPLICIT_WAIT)
        self._driver.set_page_load_timeout(settings.PAGE_LOAD_TIMEOUT)
        self._driver.set_script_timeout(settings.SCRIPT_TIMEOUT)

        logger.info(
            "Edge browser started | PID: %s | Window: %sx%s",
            self._driver.service.process.pid if self._driver.service else "N/A",
            settings.WINDOW_WIDTH,
            settings.WINDOW_HEIGHT,
        )
        return self._driver

    def stop(self) -> None:
        if self._driver is None:
            raise BrowserNotStartedError()
        try:
            pid = self._driver.service.process.pid if self._driver.service else None
            self._driver.quit()
            logger.info("Edge browser stopped | PID was: %s", pid)
        except Exception as exc:
            logger.error("Error stopping browser: %s", exc)
        finally:
            self._driver = None
            self._start_time = None

    def restart(self, edge_driver_path: str = "") -> webdriver.Edge:
        logger.info("Restarting browser...")
        if self._driver is not None:
            try:
                self.stop()
            except BrowserNotStartedError:
                pass
        return self.start(edge_driver_path)

    # ─── Auto-Heal ─────────────────────────────────────

    def start_health_check(self) -> None:
        if self._health_thread and self._health_thread.is_alive():
            return
        self._health_stop.clear()
        self._health_thread = threading.Thread(
            target=self._health_loop, name="browser-health", daemon=True
        )
        self._health_thread.start()
        logger.info(
            "Browser health check started (interval=%.1fs)", settings.BROWSER_HEALTH_CHECK_INTERVAL
        )

    def stop_health_check(self) -> None:
        self._health_stop.set()
        if self._health_thread:
            self._health_thread.join(timeout=5)
            self._health_thread = None
            logger.info("Browser health check stopped")

    def _health_loop(self) -> None:
        import time
        notified = False
        while not self._health_stop.is_set():
            if self._driver is not None and not self._is_healthy():
                if not notified:
                    logger.warning("Browser health check FAILED — attempting restart...")
                    notified = True
                try:
                    self.restart()
                    logger.info("Browser auto-restarted successfully")
                    notified = False
                except Exception as exc:
                    logger.error("Browser auto-restart failed: %s", exc)
            else:
                notified = False
            self._health_stop.wait(settings.BROWSER_HEALTH_CHECK_INTERVAL)

    def _is_healthy(self) -> bool:
        try:
            _ = self._driver.current_url
            return True
        except Exception:
            return False
