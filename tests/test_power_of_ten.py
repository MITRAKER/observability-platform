from pathlib import Path

from tests.conftest import load_module

checker = load_module("power_of_ten", "tools/check_power_of_ten.py")


def write(tmp_path: Path, source: str) -> Path:
    path = tmp_path / "sample.py"
    path.write_text(source)
    return path


def test_flags_recursion(tmp_path):
    path = write(tmp_path, "def f(n):\n    return f(n - 1)\n")
    assert any("rule 1" in p for p in checker.check_file(path))


def test_flags_long_function(tmp_path):
    body = "".join(f"    x{i} = {i}\n" for i in range(70))
    path = write(tmp_path, f"def long():\n{body}")
    assert any("rule 4" in p for p in checker.check_file(path))


def test_clean_code_passes(tmp_path):
    path = write(tmp_path, "def ok(a):\n    return a + 1\n")
    assert checker.check_file(path) == []


def test_repository_follows_the_rules():
    assert checker.main([]) == 0


def test_flags_method_recursion_but_not_delegation(tmp_path):
    source = (
        "class A:\n"
        "    def get(self, k):\n"
        "        return self._items.get(k)\n"
        "    def loop(self):\n"
        "        return self.loop()\n"
    )
    problems = checker.check_file(write(tmp_path, source))
    assert len(problems) == 1
    assert "loop()" in problems[0]
