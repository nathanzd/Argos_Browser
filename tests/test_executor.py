from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from exceptions import CommandTimeoutError, SecurityViolation
from executor import CommandExecutor


class TestCommandExecutor:
    def test_execute_simple_expression(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        result = command_executor.execute_raw("1 + 1", mock_driver)
        assert result["success"] is True
        assert result["result"] == 2

    def test_execute_string_expression(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        result = command_executor.execute_raw('"hello".upper()', mock_driver)
        assert result["success"] is True
        assert result["result"] == "HELLO"

    def test_execute_list_comprehension(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        result = command_executor.execute_raw("[x*2 for x in range(3)]", mock_driver)
        assert result["success"] is True
        assert result["result"] == [0, 2, 4]

    def test_execute_dot_attr(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        mock_driver.title = "Test Title"
        result = command_executor.execute_raw("driver.title", mock_driver)
        assert result["success"] is True
        assert result["result"] == "Test Title"

    def test_execute_dot_get(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        mock_driver.current_url = "https://example.com"
        result = command_executor.execute_raw("driver.current_url", mock_driver)
        assert result["success"] is True
        assert result["result"] == "https://example.com"

    def test_execute_page_source(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        mock_driver.page_source = "<html></html>"
        result = command_executor.execute_raw("driver.page_source", mock_driver)
        assert result["success"] is True

    def test_execute_get(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        result = command_executor.execute_raw('driver.get("https://example.com")', mock_driver)
        assert result["success"] is True
        mock_driver.get.assert_called_once_with("https://example.com")

    def test_execute_find_element(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        mock_driver.find_element.return_value = MagicMock()
        result = command_executor.execute_raw(
            'driver.find_element(By.NAME, "q")', mock_driver
        )
        assert result["success"] is True

    def test_execute_send_keys(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        elem = MagicMock()
        mock_driver.find_element.return_value = elem
        result = command_executor.execute_raw(
            'driver.find_element(By.NAME, "q").send_keys("hello")', mock_driver
        )
        assert result["success"] is True
        elem.send_keys.assert_called_once_with("hello")

    def test_execute_statement(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        result = command_executor.execute_raw("x = 5", mock_driver)
        assert result["success"] is True
        assert result["result"] is None

    def test_execute_stdout_capture(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        result = command_executor.execute_raw(
            'print("hello world")', mock_driver
        )
        assert result["success"] is True
        assert "hello world" in result["stdout"]

    def test_execute_stderr_capture(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        result = command_executor.execute_raw(
            'print("error message", file=__import__("sys").stderr)', mock_driver
        )
        assert result["success"] is False
        assert result["exception"] is not None
        assert "not allowed" in result["exception"].lower()

    def test_execute_syntax_error(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        result = command_executor.execute_raw("x === 1", mock_driver)
        assert result["success"] is False
        assert result["exception"] is not None

    def test_execute_runtime_error(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        result = command_executor.execute_raw("1/0", mock_driver)
        assert result["success"] is False
        assert "division by zero" in result["exception"]

    def test_execute_name_error(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        result = command_executor.execute_raw("undefined_var", mock_driver)
        assert result["success"] is False
        assert "undefined_var" in result["exception"]

    def test_execution_time_is_measured(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        result = command_executor.execute_raw("1+1", mock_driver)
        assert result["execution_time"] > 0

    def test_security_violation_open(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        result = command_executor.execute_raw('open("/etc/passwd")', mock_driver)
        assert result["success"] is False
        assert "open" in result["exception"]

    def test_security_violation_import(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        result = command_executor.execute_raw("import subprocess", mock_driver)
        assert result["success"] is False
        assert "not allowed" in result["exception"].lower()

    def test_security_violation_os_system(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        result = command_executor.execute_raw('os.system("dir")', mock_driver)
        assert result["success"] is False
        assert "not allowed" in result["exception"].lower()

    def test_timeout(self, mock_driver: MagicMock):
        executor = CommandExecutor(timeout=0.1)
        result = executor.execute_raw("sleep(10)", mock_driver)
        assert result["success"] is False
        assert "timed out" in result["exception"].lower()

    def test_namespace_has_driver(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        result = command_executor.execute_raw("driver", mock_driver)
        assert result["success"] is True

    def test_namespace_has_by(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        result = command_executor.execute_raw("By", mock_driver)
        assert result["success"] is True

    def test_namespace_has_sleep(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        result = command_executor.execute_raw("sleep", mock_driver)
        assert result["success"] is True

    def test_execute_json_dumps(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        result = command_executor.execute_raw(
            'json.dumps({"a": 1})', mock_driver
        )
        assert result["success"] is True
        assert result["result"] == '{"a": 1}'

    def test_execute_re_search(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        result = command_executor.execute_raw(
            're.search(r"\\d+", "abc123def").group()', mock_driver
        )
        assert result["success"] is True
        assert result["result"] == "123"

    def test_execute_screenshot_in_result(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        img = Image.new("RGB", (100, 100), (128, 128, 128))
        buf = io.BytesIO()
        img.save(buf, "PNG")
        mock_driver.get_screenshot_as_png.return_value = buf.getvalue()
        result = command_executor.execute_raw("1+1", mock_driver)
        assert result["success"] is True
        assert result["screenshot_path"] is not None
        assert result["screenshot_path"].endswith((".png", ".jpg"))

    def test_execute_in_session(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        from interactive import InteractiveSession
        session = InteractiveSession("test-session")
        session.inject_driver(mock_driver)

        result1 = command_executor.execute_raw("x = 42", mock_driver, session)
        assert result1["success"] is True

        result2 = command_executor.execute_raw("x", mock_driver, session)
        assert result2["success"] is True
        assert result2["result"] == 42

    def test_execute_method_on_variable_in_session(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        from interactive import InteractiveSession
        elem = MagicMock()
        elem.text = "button text"
        mock_driver.find_element.return_value = elem
        session = InteractiveSession("test-session-2")
        session.inject_driver(mock_driver)

        command_executor.execute_raw(
            'btn = driver.find_element(By.TAG_NAME, "button")', mock_driver, session
        )
        result = command_executor.execute_raw("btn.text", mock_driver, session)
        assert result["success"] is True
        assert result["result"] == "button text"


class TestEvalVsExec:
    def test_eval_expression_returns_value(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        result = command_executor.execute_raw("42", mock_driver)
        assert result["result"] == 42

    def test_exec_statement_returns_none(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        result = command_executor.execute_raw("a = 10", mock_driver)
        assert result["result"] is None

    def test_function_call_returns_none(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        mock_driver.get.return_value = None
        result = command_executor.execute_raw(
            'driver.get("https://example.com")', mock_driver
        )
        assert result["result"] is None

    def test_print_returns_none(self, command_executor: CommandExecutor, mock_driver: MagicMock):
        result = command_executor.execute_raw('print("hi")', mock_driver)
        assert result["result"] is None
