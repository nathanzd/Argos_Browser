import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Settings:
    PROJECT_ROOT: Path = Path(__file__).parent.resolve()
    DOWNLOAD_DIR: Path = PROJECT_ROOT / "downloads"

    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))
    HEADLESS: bool = os.getenv("HEADLESS", "false").lower() == "true"

    # ─── Logging ────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR: Path = PROJECT_ROOT / "logs"
    LOG_FILE: str = os.getenv("LOG_FILE", "web-agent.log")
    LOG_MAX_MB: int = int(os.getenv("LOG_MAX_MB", "10"))
    LOG_BACKUP_COUNT: int = int(os.getenv("LOG_BACKUP_COUNT", "5"))

    # ─── Edge Driver ────────────────────────
    EDGE_DRIVER_PATH: str = os.getenv("EDGE_DRIVER_PATH", "")
    EDGE_PROFILE_DIR: Path = PROJECT_ROOT / "profile"

    # ─── Janela ─────────────────────────────
    WINDOW_WIDTH: int = int(os.getenv("WINDOW_WIDTH", "1280"))
    WINDOW_HEIGHT: int = int(os.getenv("WINDOW_HEIGHT", "800"))
    IMPLICIT_WAIT: float = float(os.getenv("IMPLICIT_WAIT", "2"))
    PAGE_LOAD_TIMEOUT: float = float(os.getenv("PAGE_LOAD_TIMEOUT", "30"))
    SCRIPT_TIMEOUT: float = float(os.getenv("SCRIPT_TIMEOUT", "10"))

    # ─── Execução ───────────────────────────
    COMMAND_TIMEOUT: float = float(os.getenv("COMMAND_TIMEOUT", "60"))
    MAX_SESSION_VARIABLES: int = int(os.getenv("MAX_SESSION_VARIABLES", "1000"))

    # ─── Screenshots ────────────────────────
    SCREENSHOT_QUALITY: int = int(os.getenv("SCREENSHOT_QUALITY", "70"))
    SCREENSHOT_FORMAT: str = os.getenv("SCREENSHOT_FORMAT", "jpeg")
    SCREENSHOT_RETENTION_DAYS: int = int(os.getenv("SCREENSHOT_RETENTION_DAYS", "7"))
    SCREENSHOT_CLEANUP_INTERVAL_MINUTES: int = int(
        os.getenv("SCREENSHOT_CLEANUP_INTERVAL_MINUTES", "60")
    )

    # ─── Auto-Heal ──────────────────────────
    BROWSER_HEALTH_CHECK_INTERVAL: float = float(
        os.getenv("BROWSER_HEALTH_CHECK_INTERVAL", "15")
    )

    ALLOWED_DOMAINS: list[str] | None = None


settings = Settings()
settings.DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
settings.EDGE_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
