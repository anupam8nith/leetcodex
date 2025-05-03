import os
import difflib
import yaml
from . import sandbox

def diff_outputs(expected, actual):
    """Generate a unified diff between expected and actual output lines."""
    expected_lines = expected.splitlines()
    actual_lines = actual.splitlines()
    diff = difflib.unified_diff(expected_lines, actual_lines, fromfile="expected", tofile="actual", lineterm="")
    return list(diff)

def run_tests(file_path, test_cases, use_docker=None, timeout=None, memory=None):
    """
    Execute the code file against each test case.
    test_cases: list of (input, expected_output) tuples. expected_output can be None.
    Returns (compile_error, results) where compile_error is a string if compilation failed, 
    and results is a list of dicts for each test case.
    """
    # Load language config
    config_path = os.path.join(os.path.dirname(__file__), "languages.yaml")
    with open(config_path, "r") as f:
        lang_configs = yaml.safe_load(f)
    # Detect language by file extension
    ext = os.path.splitext(file_path)[1].lower()
    lang = None
    lang_conf = None
    for name, conf in lang_configs.items():
        for ext_opt in conf.get("extensions", []):
            if ext_opt.lower() == ext:
                lang = name
                lang_conf = conf
                break
        if lang_conf:
            break
    if not lang_conf:
        raise RuntimeError(f"Unsupported language for extension '{ext}'.")
    # Determine if compilation is needed
    needs_compile = bool(lang_conf.get("compile")) and len(lang_conf["compile"]) > 0
    # Choose sandbox mode if not explicitly specified
    if use_docker is None:
        use_docker = False
        # If a compiler is needed but not available, use Docker if possible
        if needs_compile:
            compiler_cmd = lang_conf["compile"][0] if lang_conf["compile"] else None
            if compiler_cmd and os.system(f"{compiler_cmd} --version >nul 2>&1") != 0:
                # Compiler not found, try Docker
                if sandbox.is_docker_available():
                    use_docker = True
    # Prepare format variables for command templates
    base_path = os.path.splitext(file_path)[0]
    file_name = os.path.basename(file_path)
    class_name = None
    if lang == "java":
        # Derive Java main class name (public class) from file content or file name
        try:
            with open(file_path, "r") as src:
                import re
                match = re.search(r"\bclass\s+([A-Za-z_]\w*)", src.read())
                if match:
                    class_name = match.group(1)
        except Exception:
            pass
        if not class_name:
            class_name = os.path.splitext(file_name)[0]
    # Commands from config (choose docker or direct)
    image = lang_conf.get("docker_image")
    compile_cmd_tmpl = None
    run_cmd_tmpl = None
    if use_docker and image:
        compile_cmd_tmpl = lang_conf.get("docker_compile", [])
        run_cmd_tmpl = lang_conf.get("docker_run", [])
    else:
        compile_cmd_tmpl = lang_conf.get("compile", [])
        run_cmd_tmpl = lang_conf.get("run", [])
    # Perform compilation if needed
    compile_error = None
    if needs_compile:
        # Format compile command
        compile_cmd = [arg.format(file=file_path, file_name=file_name, file_base=base_path, class_name=(class_name or "")) 
                       for arg in compile_cmd_tmpl]
        # Use Docker or subprocess for compilation
        if use_docker and image:
            result = sandbox.run_in_docker(image, os.path.dirname(file_path) or ".", compile_cmd, timeout=timeout or 10, memory_limit=memory or 512)
        else:
            result = sandbox.run_subprocess(compile_cmd, timeout=timeout or 10)
        if result.returncode != 0:
            # Capture compile error output
            compile_error = (result.stderr or "") + (result.stdout or "")
            return compile_error.strip(), []  # no results if compilation failed
    # Run each test case
    results = []
    for inp, expected in test_cases:
        # Format the run command for this language
        run_cmd = [arg.format(file=file_path, file_name=file_name, file_base=base_path, class_name=(class_name or "")) 
                   for arg in run_cmd_tmpl]
        # Execute using appropriate method
        if use_docker and image:
            res = sandbox.run_in_docker(image, os.path.dirname(file_path) or ".", run_cmd, input_data=(inp + "\n" if inp is not None else None), timeout=timeout, memory_limit=memory)
        else:
            res = sandbox.run_subprocess(run_cmd, input_data=(inp + "\n" if inp is not None else None), timeout=timeout, memory_limit=memory)
        # Prepare output and expected strings for comparison
        out_text = (res.stdout or "").rstrip("\n")
        err_text = res.stderr or ""
        # Determine test outcome
        if expected is None:
            # If no expected output provided, we just report the program's output (cannot pass/fail)
            results.append({
                "input": inp if inp is not None else "",
                "expected": None,
                "output": out_text,
                "error": err_text if res.returncode != 0 else None,
                "passed": True  # no expected, so can't fail
            })
        else:
            expected_str = str(expected).rstrip("\n")
            if res.returncode != 0:
                # Program error (non-zero exit)
                results.append({
                    "input": inp if inp is not None else "",
                    "expected": expected_str,
                    "output": out_text,
                    "error": err_text.strip(),
                    "passed": False
                })
            else:
                # Compare output to expected
                passed = (out_text.strip() == expected_str.strip())
                results.append({
                    "input": inp if inp is not None else "",
                    "expected": expected_str,
                    "output": out_text,
                    "error": None,
                    "passed": passed
                })
    return compile_error, results
