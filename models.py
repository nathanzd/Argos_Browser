from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class ExecuteRequest(BaseModel):
    command: str = Field(..., min_length=1, description="Python command to execute")
    session_id: str | None = Field(None, description="Interactive session ID")


class ExecuteResponse(BaseModel):
    success: bool
    result: Any = None
    stdout: str = ""
    stderr: str = ""
    exception: str | None = None
    traceback: str | None = None
    execution_time: float = 0.0
    screenshot_path: str | None = None


class StatusResponse(BaseModel):
    browser_running: bool
    active_sessions: list[str]
    commands_executed: int
    uptime_seconds: float
    pid: int | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"


class SessionCreateResponse(BaseModel):
    session_id: str
    message: str = "Session created"
