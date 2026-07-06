from __future__ import annotations

import ast
import builtins
from typing import Any

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    JavascriptException,
)
import time as _time
import re
import json
import os as _os
from pathlib import Path
import datetime

from exceptions import SecurityViolation

ALLOWED_NAMES: dict[str, Any] = {
    "By": By,
    "Keys": Keys,
    "EC": EC,
    "WebDriverWait": WebDriverWait,
    "ActionChains": ActionChains,
    "Select": Select,
    "NoSuchElementException": NoSuchElementException,
    "TimeoutException": TimeoutException,
    "JavascriptException": JavascriptException,
    "time": _time,
    "sleep": _time.sleep,
    "re": re,
    "json": json,
    "os": _os,
    "pathlib": Path,
    "datetime": datetime,
}

ALLOWED_BUILTIN_NAMES: set[str] = {
    "True",
    "False",
    "None",
    "int",
    "float",
    "str",
    "bool",
    "list",
    "dict",
    "set",
    "tuple",
    "len",
    "range",
    "enumerate",
    "zip",
    "map",
    "filter",
    "min",
    "max",
    "sum",
    "abs",
    "round",
    "sorted",
    "reversed",
    "any",
    "all",
    "isinstance",
    "type",
    "print",
    "hasattr",
    "Exception",
    "ValueError",
    "TypeError",
    "KeyError",
    "IndexError",
    "RuntimeError",
    "AttributeError",
    "NameError",
    "StopIteration",
    "super",
    "object",
    "property",
    "classmethod",
    "staticmethod",
    "iter",
    "next",
    "callable",
    "format",
}

BLOCKED_CALL_NAMES: set[str] = {
    "__import__",
    "open",
    "exec",
    "eval",
    "compile",
    "breakpoint",
    "input",
    "vars",
    "dir",
    "globals",
    "locals",
    "memoryview",
    "bytearray",
    "getattr",
    "setattr",
    "delattr",
}

BLOCKED_ATTRIBUTE_PREFIXES: list[str] = [
    "os.system",
    "os.popen",
    "os.startfile",
    "os.execl",
    "os.execle",
    "os.execlp",
    "os.execlpe",
    "os.execv",
    "os.execve",
    "os.execvp",
    "os.execvpe",
    "os.fork",
    "os.kill",
    "os.spawnl",
    "os.spawnle",
    "os.spawnlp",
    "os.spawnlpe",
    "os.spawnv",
    "os.spawnve",
    "os.spawnvp",
    "os.spawnvpe",
    "os.posix_spawn",
    "os.posix_spawnp",
    "subprocess",
    "socket",
    "ctypes",
    "pickle",
    "shutil",
    "signal",
    "multiprocessing",
    "threading",
]

BLOCKED_DUNDER_ATTRS: set[str] = {
    "__builtins__",
    "__class__",
    "__base__",
    "__subclasses__",
    "__globals__",
    "__code__",
    "__closure__",
    "__func__",
    "__self__",
    "__dict__",
    "__mro__",
    "__bases__",
}


def _safe_builtins() -> dict[str, Any]:
    b = {}
    for name in ALLOWED_BUILTIN_NAMES:
        if hasattr(builtins, name):
            b[name] = getattr(builtins, name)
    return b


def build_safe_namespace(driver: Any) -> dict[str, Any]:
    namespace = {**ALLOWED_NAMES}
    namespace["driver"] = driver
    namespace["__builtins__"] = _safe_builtins()
    return namespace


class ASTPreChecker:
    @classmethod
    def check(cls, command: str) -> None:
        try:
            tree = ast.parse(command, mode="exec")
        except SyntaxError:
            return

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                cls._check_import(node)

            if isinstance(node, ast.Call):
                cls._check_call(node)

            if isinstance(node, ast.Attribute):
                cls._check_attribute(node)

    @classmethod
    def _check_import(cls, node: ast.Import | ast.ImportFrom) -> None:
        blacklist_roots = {
            b.split(".")[0]
            for b in BLOCKED_ATTRIBUTE_PREFIXES
        }

        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
            for name in names:
                root = name.split(".")[0]
                if root in blacklist_roots:
                    raise SecurityViolation(
                        f"Import of '{name}' is not allowed"
                    )
                if root == "os":
                    raise SecurityViolation(
                        "Direct import of 'os' is not allowed. "
                        "Use the provided 'os' object."
                    )

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".")[0]
            if root in blacklist_roots or root == "os":
                raise SecurityViolation(
                    f"Import from '{module}' is not allowed"
                )

    @classmethod
    def _check_call(cls, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            if node.func.id in BLOCKED_CALL_NAMES:
                raise SecurityViolation(
                    f"Call to '{node.func.id}()' is not allowed"
                )

        if isinstance(node.func, ast.Attribute):
            chain = cls._resolve_attr_chain(node.func)
            if chain:
                full = ".".join(chain)
                for blocked in BLOCKED_ATTRIBUTE_PREFIXES:
                    if full.startswith(blocked):
                        raise SecurityViolation(
                            f"Call to '{full}()' is not allowed"
                        )

    @classmethod
    def _check_attribute(cls, node: ast.Attribute) -> None:
        if node.attr in BLOCKED_DUNDER_ATTRS:
            raise SecurityViolation(
                f"Access to '{node.attr}' is not allowed"
            )
        chain = cls._resolve_attr_chain(node)
        if chain:
            for attr in BLOCKED_DUNDER_ATTRS:
                if attr in chain:
                    raise SecurityViolation(
                        f"Dunder attribute access in chain is not allowed"
                    )

    @classmethod
    def _resolve_attr_chain(cls, node: ast.AST) -> list[str] | None:
        parts: list[str] = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        elif isinstance(current, ast.Call):
            return None
        elif isinstance(current, ast.Subscript):
            return None
        else:
            return None
        return list(reversed(parts))
