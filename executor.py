from __future__ import annotations

import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Any

from config import settings
from exceptions import CommandTimeoutError, ExecutionError, SecurityViolation
from interactive import InteractiveSession
from protocol import error_response, success_response
from sandbox import ASTPreChecker, build_safe_namespace
from screenshot import ScreenshotManager
from utils import capture_output, get_logger, time_context

logger = get_logger(__name__)


class CommandExecutor:
    def __init__(self, timeout: float | None = None) -> None:
        self._timeout = timeout or settings.COMMAND_TIMEOUT
        self._pool = ThreadPoolExecutor(max_workers=1)
        self._screenshot_mgr = ScreenshotManager()

    def execute(
        self,
        command: str,
        driver: Any,
        session: InteractiveSession | None = None,
    ) -> dict[str, Any]:

        logger.info("Executing: %s", command)

        ASTPreChecker.check(command)

        namespace = (
            session.get_namespace()
            if session
            else build_safe_namespace(driver)
        )

        if session:
            session.inject_driver(driver)

        with time_context() as elapsed:
            try:
                compiled, mode = self._compile(command)
                with capture_output() as get_captured:
                    result = self._run_in_thread(compiled, mode, namespace)
                    stdout_capture, stderr_capture = get_captured()
                    stdout = stdout_capture.getvalue()
                    stderr = stderr_capture.getvalue()
            except SecurityViolation:
                raise
            except SyntaxError as exc:
                return error_response(
                    exception=exc,
                    traceback_str=traceback.format_exc(),
                    execution_time=elapsed(),
                ).model_dump(mode="json")
            except CommandTimeoutError:
                raise
            except Exception as exc:
                tb = traceback.format_exc()
                logger.error("Execution error: %s\n%s", exc, tb)
                return error_response(
                    exception=exc,
                    traceback_str=tb,
                    execution_time=elapsed(),
                ).model_dump(mode="json")

        exec_time = elapsed()

        if session:
            session.increment_commands()

        screenshot_path = self._try_save_screenshot(driver)

        logger.info(
            "Result: success=%s | time=%.3fs | stdout=%s",
            True,
            exec_time,
            stdout[:100] if stdout else "",
        )

        return success_response(
            result=result,
            stdout=stdout,
            stderr=stderr,
            execution_time=exec_time,
            screenshot_path=screenshot_path,
        ).model_dump(mode="json")

    def execute_raw(
        self,
        command: str,
        driver: Any,
        session: InteractiveSession | None = None,
    ) -> dict[str, Any]:
        try:
            return self.execute(command, driver, session)
        except SecurityViolation as exc:
            tb = traceback.format_exc()
            logger.error("Security violation: %s\n%s", exc, tb)
            return error_response(
                exception=exc,
                traceback_str=tb,
            ).model_dump(mode="json")
        except SyntaxError as exc:
            tb = traceback.format_exc()
            logger.error("Syntax error: %s", exc)
            return error_response(
                exception=exc,
                traceback_str=tb,
            ).model_dump(mode="json")
        except CommandTimeoutError as exc:
            logger.error("Timeout: %s", exc)
            return error_response(
                exception=exc,
                traceback_str="",
            ).model_dump(mode="json")

    def _compile(self, command: str) -> tuple[Any, str]:
        for mode in ("eval", "exec"):
            try:
                code = compile(command, "<command>", mode)
                return code, mode
            except SyntaxError:
                continue
        raise SyntaxError(f"Unable to compile command: {command}")

    def _run_in_thread(
        self,
        code: Any,
        mode: str,
        namespace: dict[str, Any],
    ) -> Any:
        future = self._pool.submit(self._execute_code, code, mode, namespace)
        try:
            return future.result(timeout=self._timeout)
        except FutureTimeoutError:
            future.cancel()
            raise CommandTimeoutError(self._timeout)

    @staticmethod
    def _execute_code(code: Any, mode: str, namespace: dict[str, Any]) -> Any:
        if mode == "eval":
            return eval(code, namespace)
        exec(code, namespace)
        return None

    def _try_save_screenshot(self, driver: Any) -> str | None:
        return self._screenshot_mgr.capture(driver)
