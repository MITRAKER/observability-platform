"""Check the NASA/JPL "Power of Ten" rules that ruff and mypy do not cover.

Rule 1 (simple control flow): no function may call itself (direct recursion).
Rule 4 (small functions):      no function longer than MAX_FUNCTION_LINES lines.
Rule 5 (assertions):           every module under tests/ must contain asserts.

Usage: python tools/check_power_of_ten.py [paths...]
Exits with status 1 and prints every violation if any rule is broken.
"""

import ast
import sys
from collections.abc import Iterator
from pathlib import Path

MAX_FUNCTION_LINES = 60  # the limit JPL uses: one printed page
DEFAULT_PATHS = ("services", "loadgen", "alert-sink", "tools", "tests")
MAX_FILES = 1_000  # bounded walk (rule 2)

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def python_files(paths: list[str]) -> list[Path]:
    """Return the .py files under `paths`, at most MAX_FILES of them."""
    found: list[Path] = []
    for root in paths:
        base = Path(root)
        candidates = [base] if base.is_file() else sorted(base.rglob("*.py"))
        found.extend(p for p in candidates if p.suffix == ".py")
    if len(found) > MAX_FILES:
        raise SystemExit(f"refusing to scan more than {MAX_FILES} files")
    return found


def functions(tree: ast.AST) -> Iterator[FunctionNode]:
    """Yield every function and method definition in a syntax tree."""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            yield node


def calls_itself(func: FunctionNode) -> bool:
    """Return True if `func` contains a direct call to its own name."""
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        if called_name(node.func) == func.name:
            return True
    return False


def called_name(target: ast.expr) -> str | None:
    """Name of a call target if it can refer to the enclosing function.

    `f(...)` and `self.f(...)` / `cls.f(...)` count; `other.f(...)` does not,
    because that calls a method on a different object.
    """
    if isinstance(target, ast.Name):
        return target.id
    is_own_method = (
        isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and target.value.id in {"self", "cls"}
    )
    return target.attr if is_own_method and isinstance(target, ast.Attribute) else None


def function_length(func: FunctionNode) -> int:
    """Return the number of source lines a function spans."""
    end = func.end_lineno if func.end_lineno is not None else func.lineno
    return end - func.lineno + 1


def check_file(path: Path) -> list[str]:
    """Return the rule violations found in one file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    problems: list[str] = []
    for func in functions(tree):
        where = f"{path}:{func.lineno} {func.name}()"
        if calls_itself(func):
            problems.append(f"{where}: rule 1, recursion is not allowed")
        length = function_length(func)
        if length > MAX_FUNCTION_LINES:
            problems.append(f"{where}: rule 4, {length} lines (max {MAX_FUNCTION_LINES})")
    is_test = path.parts[0] == "tests" and path.name.startswith("test_")
    if is_test and not any(isinstance(n, ast.Assert) for n in ast.walk(tree)):
        problems.append(f"{path}: rule 5, test module contains no assertions")
    return problems


def main(argv: list[str]) -> int:
    """Check all files and print violations. Returns the process exit code."""
    files = python_files(argv or list(DEFAULT_PATHS))
    problems = [p for f in files for p in check_file(f)]
    for problem in problems:
        print(problem)
    print(f"checked {len(files)} files: {len(problems)} violation(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
