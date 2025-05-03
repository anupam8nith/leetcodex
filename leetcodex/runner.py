"""
leetcodex.runner — execute LeetCode solutions locally
"""
from __future__ import annotations

import ast
import difflib
import importlib.util
import io
import shutil
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import List, Tuple

import yaml

from . import sandbox, stubs


#  internal helpers

def _ensure_stub_package() -> None:
    """Guarantee that `import leetcodex.stubs` always succeeds."""
    if "leetcodex" not in sys.modules:
        pkg = ModuleType("leetcodex")
        pkg.__path__ = []          # mark as namespace package
        sys.modules["leetcodex"] = pkg
    sys.modules["leetcodex.stubs"] = stubs


def _make_wrapper(src: Path) -> Path:
    """
    Create a temp file that:
      • inlines the stubs
      • appends the user source
      • adds a tiny driver that calls the first public method of class Solution
        and prints its return value (so blank LeetCode files produce output)
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="lcx_pywrap_"))
    wrapper = tmp_dir / src.name
    stubs_file = Path(__file__).with_name("stubs.py")

    with wrapper.open("w", encoding="utf-8") as fout, \
         stubs_file.open("r", encoding="utf-8") as fstub, \
         src.open("r", encoding="utf-8") as fin:

        fout.write("# === Inlined Leetcodex stubs ===\n")
        fout.write(fstub.read())
        fout.write("\n# === User solution ===\n")
        shutil.copyfileobj(fin, fout)

        driver = r"""
        if __name__ == "__main__":
            import sys, ast
            raw = sys.stdin.read().strip()
            if not raw:
                sys.exit(0)
            # handle either `var = value` or raw literal
            rhs = raw.split("=", 1)[-1] if "=" in raw and not raw.lstrip().startswith(("{", "[")) else raw
            try:
                arg = ast.literal_eval(rhs.strip())
            except Exception:
                arg = rhs.strip()
            sol = Solution()
            public = next((m for m in dir(sol) if not m.startswith("_")), None)
            res = getattr(sol, public)(arg) if public else ""
            print(res)
        """
        fout.write(driver.strip() + "\n")

    return wrapper


def _diff(exp: str, act: str) -> List[str]:
    """Return unified‑diff lines."""
    return list(
        difflib.unified_diff(
            exp.splitlines(), act.splitlines(),
            fromfile="expected", tofile="actual", lineterm=""
        )
    )


# export for cli
diff_outputs = _diff


# public API
def run_tests(
    file_path: str | Path,
    test_cases: List[Tuple[str, str | None]],
    *,
    use_docker: bool | None = None,
    timeout: int = 2,
    memory: int = 256,
):
    """
    Execute *file_path* for every (input, expected) pair.
    Returns (compile_error: str | None, results: list[dict])
    """
    file_path = Path(file_path).resolve()

    # 1. detect language from languages.yaml
    lang_cfgs = yaml.safe_load(Path(__file__).with_name("languages.yaml").read_text())
    ext = file_path.suffix.lower()
    lang, cfg = next(((n, c) for n, c in lang_cfgs.items()
                      if ext in (e.lower() for e in c["extensions"])), (None, None))
    if cfg is None:
        raise RuntimeError(f"Unsupported extension '{ext}'")

    # 2. choose Docker if needed/available
    needs_compile = bool(cfg.get("compile"))
    if use_docker is None:
        has_compiler = importlib.util.find_spec(cfg["compile"][0]) is not None if needs_compile else False
        use_docker = needs_compile and not has_compiler and sandbox.is_docker_available()

    # 3. for Python: build wrapper, skip compilation
    run_path = file_path
    if lang == "python":
        _ensure_stub_package()
        run_path = _make_wrapper(file_path)
        needs_compile = False

    image = cfg.get("docker_image")

    # 4. compile (if required)
    if needs_compile:
        tpl = cfg["docker_compile"] if use_docker and image else cfg["compile"]
        compile_cmd = [a.format(file=str(run_path),
                                file_base=str(run_path.with_suffix("")),
                                file_name=run_path.name,
                                class_name="") for a in tpl]
        proc = (sandbox.run_in_docker(image, str(run_path.parent), compile_cmd,
                                      timeout=timeout, memory_limit=memory)
                if use_docker and image else
                sandbox.run_subprocess(compile_cmd, timeout=timeout))
        if proc.returncode:
            return (proc.stderr or "") + (proc.stdout or ""), []

    # 5. run each test case
    run_tpl = cfg["docker_run"] if use_docker and image else cfg["run"]
    results = []
    for raw_inp, expected in test_cases:
        cmd = [a.format(file=str(run_path),
                        file_base=str(run_path.with_suffix("")),
                        file_name=run_path.name,
                        class_name="") for a in run_tpl]

        proc = (sandbox.run_in_docker(image, str(run_path.parent), cmd,
                                      input_data=(raw_inp + "\n") if raw_inp else None,
                                      timeout=timeout, memory_limit=memory)
                if use_docker and image else
                sandbox.run_subprocess(cmd,
                                       input_data=(raw_inp + "\n") if raw_inp else None,
                                       timeout=timeout, memory_limit=memory))

        full_stdout = (proc.stdout or "").rstrip("\n")
        stderr      = (proc.stderr or "").strip()
        answer_line = full_stdout.splitlines()[-1].strip() if full_stdout else ""

        if expected is None:
            results.append(dict(input=raw_inp, expected=None,
                                output=full_stdout, answer=answer_line,
                                error=stderr or None, passed=True))
        else:
            passed = (proc.returncode == 0) and (answer_line == expected.strip())
            results.append(dict(input=raw_inp, expected=expected,
                                output=full_stdout, answer=answer_line,
                                error=stderr or None, passed=passed))

    return None, results
