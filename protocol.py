from __future__ import annotations

from typing import Any
from models import ExecuteResponse


def success_response(
    result: Any = None,
    stdout: str = "",
    stderr: str = "",
    execution_time: float = 0.0,
    screenshot_path: str | None = None,
) -> ExecuteResponse:
    return ExecuteResponse(
        success=True,
        result=_serialize(result),
        stdout=stdout,
        stderr=stderr,
        execution_time=round(execution_time, 4),
        screenshot_path=screenshot_path,
    )


def error_response(
    exception: Exception,
    traceback_str: str = "",
    execution_time: float = 0.0,
) -> ExecuteResponse:
    return ExecuteResponse(
        success=False,
        exception=str(exception),
        traceback=traceback_str,
        execution_time=round(execution_time, 4),
    )


def _serialize(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_serialize(item) for item in obj]
    if isinstance(obj, dict):
        return {str(k): _serialize(v) for k, v in obj.items()}
    try:
        return str(obj)
    except Exception:
        return repr(obj)
