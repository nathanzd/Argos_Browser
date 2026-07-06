from __future__ import annotations

import pytest

from exceptions import SecurityViolation
from sandbox import (
    ALLOWED_BUILTIN_NAMES,
    ALLOWED_NAMES,
    ASTPreChecker,
    build_safe_namespace,
)


class TestBuildSafeNamespace:
    def test_contains_driver(self, mock_driver):
        ns = build_safe_namespace(mock_driver)
        assert ns["driver"] is mock_driver

    def test_contains_all_selenium_names(self, mock_driver):
        ns = build_safe_namespace(mock_driver)
        assert ns["By"] is ALLOWED_NAMES["By"]
        assert ns["Keys"] is ALLOWED_NAMES["Keys"]
        assert ns["EC"] is ALLOWED_NAMES["EC"]
        assert ns["WebDriverWait"] is ALLOWED_NAMES["WebDriverWait"]
        assert ns["ActionChains"] is ALLOWED_NAMES["ActionChains"]
        assert ns["Select"] is ALLOWED_NAMES["Select"]
        assert ns["NoSuchElementException"] is ALLOWED_NAMES["NoSuchElementException"]
        assert ns["TimeoutException"] is ALLOWED_NAMES["TimeoutException"]
        assert ns["JavascriptException"] is ALLOWED_NAMES["JavascriptException"]

    def test_contains_stdlib_names(self, mock_driver):
        ns = build_safe_namespace(mock_driver)
        assert ns["time"] is ALLOWED_NAMES["time"]
        assert ns["sleep"] is ALLOWED_NAMES["sleep"]
        assert ns["re"] is ALLOWED_NAMES["re"]
        assert ns["json"] is ALLOWED_NAMES["json"]
        assert ns["os"] is ALLOWED_NAMES["os"]
        assert ns["pathlib"] is ALLOWED_NAMES["pathlib"]
        assert ns["datetime"] is ALLOWED_NAMES["datetime"]

    def test_builtins_are_restricted(self, mock_driver):
        ns = build_safe_namespace(mock_driver)
        builtins_dict = ns["__builtins__"]
        assert "open" not in builtins_dict
        assert "__import__" not in builtins_dict
        assert "exec" not in builtins_dict
        assert "eval" not in builtins_dict
        assert "compile" not in builtins_dict
        assert "subprocess" not in builtins_dict

    def test_builtins_contain_safe_ones(self, mock_driver):
        ns = build_safe_namespace(mock_driver)
        builtins_dict = ns["__builtins__"]
        assert "print" in builtins_dict
        assert "len" in builtins_dict
        assert "str" in builtins_dict
        assert "int" in builtins_dict
        assert "range" in builtins_dict
        assert "Exception" in builtins_dict


class TestASTPreChecker:
    def test_allows_simple_get(self):
        ASTPreChecker.check('driver.get("https://google.com")')

    def test_allows_find_element(self):
        ASTPreChecker.check('driver.find_element(By.NAME, "q")')

    def test_allows_page_source(self):
        ASTPreChecker.check("driver.page_source")

    def test_allows_current_url(self):
        ASTPreChecker.check("driver.current_url")

    def test_allows_send_keys(self):
        ASTPreChecker.check('driver.find_element(By.NAME, "q").send_keys("hello")')

    def test_allows_sleep(self):
        ASTPreChecker.check("sleep(1)")

    def test_allows_os_path_join(self):
        ASTPreChecker.check('os.path.join("a", "b")')

    def test_allows_assignment(self):
        ASTPreChecker.check('x = driver.find_element(By.TAG_NAME, "div")')

    def test_allows_method_on_variable(self):
        ASTPreChecker.check("x.click()")

    def test_allows_execute_script(self):
        ASTPreChecker.check('driver.execute_script("return 1+1")')

    def test_allows_json_dumps(self):
        ASTPreChecker.check('json.dumps({"key": "value"})')

    def test_blocks_import_subprocess(self):
        with pytest.raises(SecurityViolation, match="Import.*not allowed"):
            ASTPreChecker.check("import subprocess")

    def test_blocks_import_socket(self):
        with pytest.raises(SecurityViolation, match="Import.*not allowed"):
            ASTPreChecker.check("import socket")

    def test_blocks_import_ctypes(self):
        with pytest.raises(SecurityViolation, match="Import.*not allowed"):
            ASTPreChecker.check("import ctypes")

    def test_blocks_from_import_subprocess(self):
        with pytest.raises(SecurityViolation, match="Import.*not allowed"):
            ASTPreChecker.check("from subprocess import Popen")

    def test_blocks_open_call(self):
        with pytest.raises(SecurityViolation, match="open"):
            ASTPreChecker.check('open("file.txt")')

    def test_blocks_exec_call(self):
        with pytest.raises(SecurityViolation, match="exec"):
            ASTPreChecker.check('exec("print(1)")')

    def test_blocks_eval_call(self):
        with pytest.raises(SecurityViolation, match="eval"):
            ASTPreChecker.check('eval("1+1")')

    def test_blocks_compile_call(self):
        with pytest.raises(SecurityViolation, match="compile"):
            ASTPreChecker.check('compile("1+1", "", "eval")')

    def test_blocks_input_call(self):
        with pytest.raises(SecurityViolation, match="input"):
            ASTPreChecker.check("input()")

    def test_blocks_os_system(self):
        with pytest.raises(SecurityViolation, match="os.system"):
            ASTPreChecker.check('os.system("cmd")')

    def test_blocks_os_popen(self):
        with pytest.raises(SecurityViolation, match="os.popen"):
            ASTPreChecker.check('os.popen("cmd")')

    def test_blocks_dunder_class_access(self):
        with pytest.raises(SecurityViolation, match="Access to '__class__'"):
            ASTPreChecker.check("driver.__class__")

    def test_blocks_dunder_subclasses(self):
        with pytest.raises(SecurityViolation, match="Access to '__subclasses__' is not allowed"):
            ASTPreChecker.check("driver.__class__.__subclasses__()")

    def test_blocks_getattr(self):
        with pytest.raises(SecurityViolation, match="getattr"):
            ASTPreChecker.check('getattr(driver, "__class__")')

    def test_blocks_breakpoint(self):
        with pytest.raises(SecurityViolation, match="breakpoint"):
            ASTPreChecker.check("breakpoint()")

    def test_raises_syntax_error_gracefully(self):
        ASTPreChecker.check("comando invalido @@")
