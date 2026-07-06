from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from browser import BrowserManager
from config import settings
from executor import CommandExecutor
from interactive import SessionManager
from models import (
    ExecuteRequest,
    ExecuteResponse,
    HealthResponse,
    SessionCreateResponse,
    StatusResponse,
)
from utils import get_logger

logger = get_logger(__name__)

browser = BrowserManager()
session_manager = SessionManager()
executor = CommandExecutor()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting Web Agent Server...")
    logger.info(
        "Config: host=%s port=%s headless=%s",
        settings.HOST,
        settings.PORT,
        settings.HEADLESS,
    )
    try:
        driver = browser.start()
        browser.start_health_check()
        session_manager.inject_driver_to_all(driver)
        logger.info("Browser started on startup")
    except Exception as exc:
        logger.warning("Could not start browser on startup: %s", exc)
    executor._screenshot_mgr.start_background_cleanup()
    yield
    logger.info("Shutting down...")
    try:
        browser.stop_health_check()
    except Exception as exc:
        logger.warning("Error stopping health check: %s", exc)
    try:
        executor._screenshot_mgr.stop_background_cleanup()
    except Exception as exc:
        logger.warning("Error stopping screenshot cleanup: %s", exc)
    try:
        session_manager.cleanup_all()
        browser.stop()
        logger.info("Browser stopped")
    except Exception as exc:
        logger.warning("Error during shutdown: %s", exc)


app = FastAPI(
    title="Web Agent Server",
    description="MCP-like web automation server for AI agents",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@app.get("/status", response_model=StatusResponse)
async def status() -> StatusResponse:
    return StatusResponse(
        browser_running=browser.is_running,
        active_sessions=session_manager.active_sessions,
        commands_executed=browser.commands_executed,
        uptime_seconds=round(browser.uptime_seconds, 2),
        pid=(
            browser.driver.service.process.pid
            if browser.is_running and browser.driver.service
            else None
        ),
    )


@app.post("/execute", response_model=ExecuteResponse)
async def execute(req: ExecuteRequest) -> ExecuteResponse:
    command = req.command.strip()
    if not command:
        raise HTTPException(status_code=422, detail="Command cannot be empty")

    if not browser.is_running:
        raise HTTPException(status_code=503, detail="Browser is not running")

    driver = browser.driver
    session = None
    if req.session_id:
        from exceptions import SessionNotFoundError
        try:
            session = session_manager.get_session(req.session_id)
        except SessionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    result = executor.execute_raw(command, driver, session)

    if result.get("success"):
        browser.increment_commands()

    return ExecuteResponse(**result)


@app.post("/restart")
async def restart() -> dict[str, str]:
    try:
        session_manager.cleanup_all()
        driver = browser.restart()
        session_manager.inject_driver_to_all(driver)
        return {"message": "Browser restarted successfully"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/close")
async def close() -> dict[str, str]:
    try:
        session_manager.cleanup_all()
        browser.stop()
        return {"message": "Browser closed successfully"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/session", response_model=SessionCreateResponse)
async def create_session() -> SessionCreateResponse:
    session = session_manager.create_session()
    if browser.is_running:
        session.inject_driver(browser.driver)
    return SessionCreateResponse(session_id=session.id)


@app.delete("/session/{session_id}")
async def delete_session(session_id: str) -> dict[str, str]:
    from exceptions import SessionNotFoundError
    try:
        session_manager.delete_session(session_id)
        return {"message": f"Session '{session_id}' deleted"}
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


SCREENSHOTS = frozenset(
    f.name for f in settings.DOWNLOAD_DIR.iterdir() if f.name.startswith("screenshot_")
)


@app.get("/screenshots/{filename}")
async def get_screenshot(filename: str) -> FileResponse:
    filepath = settings.DOWNLOAD_DIR / filename
    if not filepath.is_file():
        raise HTTPException(status_code=404, detail="Screenshot not found")
    media_type = "image/jpeg" if filename.endswith(".jpg") else "image/png"
    return FileResponse(path=str(filepath), media_type=media_type)


@app.get("/screenshots")
async def list_screenshots() -> list[str]:
    files = sorted(
        (f.name for f in settings.DOWNLOAD_DIR.iterdir() if f.name.startswith("screenshot_")),
        reverse=True,
    )
    return files


def main() -> None:
    import uvicorn
    uvicorn.run(
        "server:app",
        host=settings.HOST,
        port=settings.PORT,
        log_level=settings.LOG_LEVEL.lower(),
        reload=False,
    )


if __name__ == "__main__":
    main()
