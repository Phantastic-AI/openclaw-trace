from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any, Mapping


class UnsafeCodeError(Exception):
    pass


_ALLOWED_BUILTINS = {
    "len": len,
    "min": min,
    "max": max,
    "sum": sum,
    "sorted": sorted,
    "enumerate": enumerate,
    "range": range,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "dict": dict,
    "list": list,
    "set": set,
    "tuple": tuple,
    "print": print,
    "isinstance": isinstance,
}


_DISALLOWED_NODES = (
    ast.Import,
    ast.ImportFrom,
    ast.Global,
    ast.Nonlocal,
    ast.With,
    ast.AsyncWith,
    ast.ClassDef,
    ast.Delete,
    ast.Try,
    ast.Raise,
)


def _check_ast(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(node, _DISALLOWED_NODES):
            raise UnsafeCodeError(f"Disallowed syntax: {node.__class__.__name__}")
        # prevent access to dunder attrs
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise UnsafeCodeError("Disallowed attribute access")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise UnsafeCodeError("Disallowed name")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in {"eval", "exec", "open", "compile", "__import__", "input"}:
                raise UnsafeCodeError(f"Disallowed builtin call: {node.func.id}")


@dataclass
class SafeExecResult:
    globals: dict[str, Any]
    locals: dict[str, Any]


def _strip_markdown_fences(code: str) -> str:
    """Best-effort cleanup for LLM outputs.

    The executor expects raw Python. Some models still wrap code in
    ```python ... ``` fences; we strip them here.
    """
    s = code.strip()
    if s.startswith("```"):
        # Remove first fence line (``` or ```python)
        lines = s.splitlines()
        if lines:
            lines = lines[1:]
        # Remove trailing fence if present
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    return s


def safe_exec(code: str, *, env: Mapping[str, Any]) -> SafeExecResult:
    """Execute analyzer code in a constrained environment.

    This is *not* a perfect sandbox, but it blocks most footguns and keeps the
    recursive-llm loop from importing or touching the filesystem/network.

    The provided `env` is merged into globals.
    """
    code = _strip_markdown_fences(code)
    tree = ast.parse(code, mode="exec")
    _check_ast(tree)

    g: dict[str, Any] = {
        "__builtins__": _ALLOWED_BUILTINS,
    }
    g.update(dict(env))
    l: dict[str, Any] = {}
    exec(compile(tree, filename="<rlm_generated>", mode="exec"), g, l)
    return SafeExecResult(globals=g, locals=l)
