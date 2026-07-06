from __future__ import annotations

import io
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from PIL import Image

from config import settings
from utils import get_logger

logger = get_logger(__name__)


class ScreenshotManager:
    def __init__(self) -> None:
        self._dir: Path = settings.DOWNLOAD_DIR
        self._quality: int = settings.SCREENSHOT_QUALITY
        self._fmt: str = settings.SCREENSHOT_FORMAT
        self._retention_days: int = settings.SCREENSHOT_RETENTION_DAYS
        self._cleanup_interval: int = settings.SCREENSHOT_CLEANUP_INTERVAL_MINUTES
        self._lock: threading.Lock = threading.Lock()
        self._stop_event: threading.Event = threading.Event()
        self._thread: threading.Thread | None = None
        self._dir.mkdir(parents=True, exist_ok=True)

    def capture(self, driver: Any) -> str | None:
        try:
            raw_png = driver.get_screenshot_as_png()
            img = Image.open(io.BytesIO(raw_png))

            if img.mode == "RGBA":
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3])
                img = bg

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            ext = "jpg" if self._fmt == "jpeg" else self._fmt
            filename = f"screenshot_{timestamp}.{ext}"
            path = str(self._dir / filename)

            if self._fmt == "jpeg":
                img.save(path, "JPEG", quality=self._quality, optimize=True)
            else:
                img.save(path, "PNG", optimize=True)

            logger.info(
                "Screenshot saved: %s (quality=%s, format=%s)",
                filename,
                self._quality,
                self._fmt,
            )
            return path
        except Exception as exc:
            logger.warning("Screenshot failed: %s", exc)
            return None

    def cleanup(self) -> int:
        cutoff = datetime.now() - timedelta(days=self._retention_days)
        removed = 0
        with self._lock:
            for f in self._dir.glob("screenshot_*"):
                try:
                    mtime = datetime.fromtimestamp(f.stat().st_mtime)
                    if mtime < cutoff:
                        f.unlink()
                        removed += 1
                except Exception as exc:
                    logger.warning("Error cleaning up %s: %s", f.name, exc)
        if removed:
            logger.info("Cleaned up %d old screenshots (>%d days)", removed, self._retention_days)
        return removed

    def start_background_cleanup(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self.cleanup()

        def _run() -> None:
            logger.info(
                "Screenshot cleanup thread started (interval=%d min, retention=%d days)",
                self._cleanup_interval,
                self._retention_days,
            )
            while not self._stop_event.is_set():
                self._stop_event.wait(self._cleanup_interval * 60)
                if not self._stop_event.is_set():
                    self.cleanup()

        self._stop_event.clear()
        self._thread = threading.Thread(target=_run, name="screenshot-cleanup", daemon=True)
        self._thread.start()

    def stop_background_cleanup(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
