"""
leetcodex.runner — execute LeetCode solutions locally
"""
from __future__ import annotations

import ast
import difflib
import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import List, Tuple

import yaml

from . import sandbox, stubs


# helpers #

def _ensure_stub_package() -> None:
    if "leetcodex" not in sys.modules:
        pkg = ModuleType("leetcodex"); pkg.__path__ = []
        sys.modules["leetcodex"] = pkg
    sys.modules["leetcodex.stubs"] = stubs


def _wrap_python(src: Path) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="lcx_pywrap_")) / src.name
    stubs_file = Path(__file__).with_name("stubs.py")
    with tmp.open("w", encoding="utf-8") as fout, \
         stubs_file.open("r", encoding="utf-8") as fstub, \
         src.open("r", encoding="utf-8") as fin:
        fout.write("# === Inlined Leetcodex stubs ===\n")
        fout.write(fstub.read())
        fout.write("\n# === User solution ===\n")
        shutil.copyfileobj(fin, fout)

        # improved driver: supports 1‑or‑many variables
        fout.write(
r"""
if __name__ == "__main__":
    import sys, ast, inspect
    raw = sys.stdin.read().strip()
    if not raw:
        sys.exit(0)

    def _split_assignments(line: str):
        # split on ',' but keep brackets intact
        depth = 0; cur = ""; parts=[]
        for ch in line:
            if ch in "[{(": depth += 1
            if ch in "]})": depth -= 1
            if ch == "," and depth == 0:
                parts.append(cur); cur=""
            else:
                cur += ch
        if cur: parts.append(cur)
        return parts

    if "," in raw and "=" in raw:
        # multiple 'name = value' pieces
        vals = {}
        for piece in _split_assignments(raw):
            if "=" not in piece: continue
            k, v = piece.split("=", 1)
            try:
                vals[k.strip()] = ast.literal_eval(v.strip())
            except Exception:
                vals[k.strip()] = v.strip()
        sol = Solution()
        meth = next((m for m in dir(sol) if not m.startswith("_")), None)
        func = getattr(sol, meth) if meth else None
        if func:
            sig = inspect.signature(func)
            if all(p in vals for p in sig.parameters):
                res = func(**{p: vals[p] for p in sig.parameters})
            else:
                res = func(*vals.values())
            print(res)
    else:
        rhs = raw.split("=", 1)[-1] if "=" in raw and not raw.lstrip().startswith(("{", "[")) else raw
        try: arg = ast.literal_eval(rhs.strip())
        except Exception: arg = rhs.strip()
        sol = Solution()
        meth = next((m for m in dir(sol) if not m.startswith("_")), None)
        res = getattr(sol, meth)(arg) if meth else ""
        print(res)
""")
    return tmp


CPP_HEADER = "#include <bits/stdc++.h>\nusing namespace std;\n\n"

def _wrap_cpp(src: Path) -> Path:
    """
    • Copies user code with <bits/stdc++.h> header.
    • If user already defines main(), do nothing else.
    • Otherwise append driver that:
          - reads stdin blob,
          - calls Solution::<LEE_METHOD|solve>(string),
          - prints its return value.
    """
    user_code = src.read_text(encoding="utf-8")
    has_main  = bool(re.search(r"\bint\s+main\s*\(", user_code))

    tmp = Path(tempfile.mkdtemp(prefix="lcx_cppwrap_")) / src.name
    with tmp.open("w", encoding="utf-8") as out, src.open("r", encoding="utf-8") as user:
        out.write(CPP_HEADER)
        shutil.copyfileobj(user, out)

        if not has_main:
            out.write(r"""
#ifndef LEE_METHOD
#define LEE_METHOD solve
#endif
int main(){
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    /* read stdin blob */
    std::string raw,line; while(std::getline(std::cin,line)) raw+=line+'\n';

    Solution sol;

    /* try call with std::string first */
    if constexpr (std::is_invocable_v<decltype(&Solution::LEE_METHOD),
                                      Solution,std::string const&>)
    {
        std::cout << sol.LEE_METHOD(raw) << '\n';
        return 0;
    }

    /* fallback: attempt to parse standard two-line LeetCode sample */
    std::istringstream ss(raw);
    int n; if(!(ss>>n)){ return 0; }
    std::string dump; std::getline(ss,dump); std::string json; std::getline(ss,json);

    std::vector<std::vector<int>> v; std::vector<int> cur;
    int num=-1; bool in=false;
    for(char c:json){
        if(std::isdigit(c)){ if(num==-1) num=0; num=num*10+(c-'0'); in=true; }
        else if(in){ cur.push_back(num); num=-1; in=false;
                     if(cur.size()==2){ v.push_back(cur); cur.clear(); } }
    }
    if(!cur.empty()) v.push_back(cur);

    std::cout << sol.LEE_METHOD(n,v) << '\n';
    return 0;
}
""")
    return tmp

def _norm(s: str):
    """Return a comparison‑ready value (object or condensed string)."""
    try:
        return ast.literal_eval(s.strip())
    except Exception:
        return re.sub(r"\s+", "", s.strip())


def _diff(a: str, b: str) -> List[str]:
    return list(difflib.unified_diff(a.splitlines(), b.splitlines(),
                                     fromfile="expected", tofile="actual",
                                     lineterm=""))

diff_outputs = _diff


# main runner #

def run_tests(
    file_path: str | Path,
    test_cases: List[Tuple[str, str | None]],
    *, use_docker: bool | None = None,
    timeout: int = 2, memory: int = 256
):
    file_path = Path(file_path).resolve()
    cfg_all = yaml.safe_load(Path(__file__).with_name("languages.yaml").read_text())
    ext = file_path.suffix.lower()
    lang, cfg = next(((n, c) for n, c in cfg_all.items()
                      if ext in (e.lower() for e in c["extensions"])), (None, None))
    if cfg is None:
        raise RuntimeError(f"Unsupported extension '{ext}'")

    # needs_compile = bool(cfg.get("compile"))
    # if use_docker is None:
    #     has_comp = importlib.util.find_spec(cfg["compile"][0]) is not None if needs_compile else False
    #     use_docker = needs_compile and not has_comp and sandbox.is_docker_available()

    needs_compile = bool(cfg.get("compile"))
    if use_docker is None:
        # Try local compiler first
        if needs_compile:
            compiler = cfg["compile"][0]
            has_local = shutil.which(compiler) is not None
            use_docker = not has_local
        else:
            use_docker = False

    # Skip pull if image already present
    if use_docker and image:
        if subprocess.run(["docker", "inspect", "--type=image", image],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL).returncode != 0:
            sandbox.pull_image(image)
    
    
    run_path = file_path
    if lang == "python":
        _ensure_stub_package()
        run_path = _wrap_python(file_path)
        needs_compile = False
    elif lang == "cpp":
        run_path = _wrap_cpp(file_path)

    image = cfg.get("docker_image")
    if use_docker and image:
        sandbox.pull_image(image)

    if needs_compile:
        tpl = cfg["docker_compile"] if use_docker and image else cfg["compile"]
        cmd = [a.format(file=str(run_path),
                        file_base=str(run_path.with_suffix("")),
                        file_name=run_path.name,
                        class_name="") for a in tpl]
        proc = (sandbox.run_in_docker(image, str(run_path.parent), cmd,
                                      timeout=None, memory_limit=memory)
                if use_docker and image else
                sandbox.run_subprocess(cmd, timeout=None))
        if proc.returncode:
            return (proc.stderr or "") + (proc.stdout or ""), []

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
        full_out = (proc.stdout or "").rstrip("\n")
        stderr   = (proc.stderr or "").strip()
        answer   = full_out.splitlines()[-1].strip() if full_out else ""
        passed = expected is None or (_norm(answer) == _norm(expected))
        results.append(dict(input=raw_inp, expected=expected, output=full_out,
                            answer=answer, error=stderr or None, passed=passed))
    return None, results
