"""
leetcodex.runner  —  execute LeetCode solutions locally

Features:
  • Injects LeetCode helper stubs (List, TreeNode, …) at import-time
  • Prepends stubs into a Python wrapper so subprocess runs see them
  • Auto-imports installed-but-forgotten modules once
  • Clearly reports truly missing packages
  • Falls back to Docker sandbox when needed
"""
from __future__ import annotations

import difflib
import importlib.util
import os
import shutil
import sys
import tempfile
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType
from typing import List, Tuple

import yaml
from . import sandbox, stubs

# Helpers

def _ensure_stub_package_in_sys_modules() -> None:
    """
    Create real in-memory modules for:
      • 'leetcodex'           (a namespace package)
      • 'leetcodex.stubs'     (the stubs module)
    so that any 'import leetcodex.stubs' in user code never falls back to
    the user_solution loader.  (PEP 451 ModuleSpec with loader=None) :contentReference[oaicite:4]{index=4}
    """
    # 1) create/claim the leetcodex package
    if "leetcodex" not in sys.modules:
        pkg = ModuleType("leetcodex")
        pkg.__path__ = []  # mark as namespace package
        # give it a proper spec so import machinery treats it as a package
        pkg.__spec__ = ModuleSpec(name="leetcodex", loader=None, is_package=True)
        sys.modules["leetcodex"] = pkg

    # 2) bind the real stubs module under that package
    stubs_mod = stubs
    sys.modules["leetcodex.stubs"] = stubs_mod
    # also fix its spec so importlib won’t attempt to reload it
    stubs_mod.__spec__ = ModuleSpec(
        name="leetcodex.stubs",
        loader=None,
        origin=str(Path(__file__).with_name("stubs.py")),
        is_package=False
    )


def _make_python_wrapper(src: Path) -> Path:
    """
    Create a temp file that **inlines** the stubs (no external import) and then
    appends the user’s original source verbatim.  This removes the ImportError
    in child interpreters.
    """
    wrapper_dir = Path(tempfile.mkdtemp(prefix="lcx_pywrap_"))
    wrapper_path = wrapper_dir / src.name
    stubs_path  = Path(__file__).with_name("stubs.py")

    with wrapper_path.open("w", encoding="utf-8") as fout, \
         stubs_path.open("r", encoding="utf-8") as fstub, \
         src.open("r", encoding="utf-8") as fin:
        # ① inline the stub definitions
        fout.write("# === Leetcodex inlined stubs ===\n")
        fout.write(fstub.read())
        fout.write("\n# === user solution below ===\n")
        shutil.copyfileobj(fin, fout)

    return wrapper_path


def _diff(expected: str, actual: str) -> List[str]:
    return list(
        difflib.unified_diff(
            expected.splitlines(),
            actual.splitlines(),
            fromfile="expected",
            tofile="actual",
            lineterm="",
        )
    )


# Public API

def run_tests(
    file_path: str | os.PathLike,
    test_cases: List[Tuple[str, str | None]],
    *,
    use_docker: bool | None = None,
    timeout: int = 2,
    memory: int = 256,
):
    """
    Execute <file_path> against each (input, expected) pair.
    Returns (compile_error: str | None, results: List[dict]).
    """
    file_path = Path(file_path).resolve()

    # 1) load language config
    cfg = yaml.safe_load((Path(__file__).with_name("languages.yaml")).read_text())
    ext = file_path.suffix.lower()
    lang, lang_cfg = next(
        ((n, c) for n, c in cfg.items() if ext in (e.lower() for e in c["extensions"])),
        (None, None),
    )
    if lang_cfg is None:
        raise RuntimeError(f"Unsupported extension '{ext}'")

    needs_compile = bool(lang_cfg.get("compile"))

    # decide Docker vs local if user didn’t force
    if use_docker is None:
        # check for local compiler
        has_compiler = False
        if needs_compile:
            has_compiler = importlib.util.find_spec(lang_cfg["compile"][0]) is not None
        # fallback to Docker only if compile needed and no compiler found
        use_docker = needs_compile and not has_compiler and sandbox.is_docker_available()

        # 2) Python: build wrapper & ensure stub package
        run_path = file_path
        if lang == "python":
            _ensure_stub_package_in_sys_modules()
            run_path = _make_python_wrapper(file_path)
            needs_compile = False  # interpreted

    # 3) compile step (C++, Java, Rust, etc.)
    image = lang_cfg.get("docker_image")
    if needs_compile:
        tpl = lang_cfg["docker_compile"] if use_docker and image else lang_cfg["compile"]
        cmd = [a.format(file=str(run_path), file_base=str(run_path.with_suffix(""))) for a in tpl]
        proc = (
            sandbox.run_in_docker(image, str(run_path.parent), cmd, timeout=10, memory_limit=memory)
            if use_docker and image
            else sandbox.run_subprocess(cmd, timeout=10)
        )
        if proc.returncode:
            return (proc.stderr or "") + (proc.stdout or ""), []

    # 4) run each test via Docker or local subprocess
    run_tpl = lang_cfg["docker_run"] if use_docker and image else lang_cfg["run"]
    results = []
    for inp, expected in test_cases:
        cmd = [a.format(file=str(run_path), file_base=str(run_path.with_suffix(""))) for a in run_tpl]
        proc = (
            sandbox.run_in_docker(
                image,
                str(run_path.parent),
                cmd,
                input_data=(inp + "\n") if inp is not None else None,
                timeout=timeout,
                memory_limit=memory,
            )
            if use_docker and image
            else sandbox.run_subprocess(
                cmd,
                input_data=(inp + "\n") if inp is not None else None,
                timeout=timeout,
                memory_limit=memory,
            )
        )

        out = (proc.stdout or "").rstrip("\n")
        err = (proc.stderr or "").strip()

        if expected is None:
            results.append(dict(input=inp, expected=None, output=out, error=err or None, passed=True))
        else:
            passed = proc.returncode == 0 and out.strip() == expected.strip()
            results.append(
                dict(
                    input=inp,
                    expected=expected,
                    output=out,
                    error=err or None,
                    passed=passed,
                    diff=_diff(expected, out) if not passed else [],
                )
            )

    return None, results
diff_outputs = _diff