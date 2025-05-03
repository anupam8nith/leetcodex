"""
leetcodex.sandbox — thin wrapper around Docker / subprocess
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from typing import List, Optional

# helpers  

def _stream(cmd: List[str]) -> subprocess.CompletedProcess:
    """
    Run *cmd* streaming stdout/stderr live to the parent console.
    Returns CompletedProcess at the end.
    """
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, bufsize=1, universal_newlines=True) as p:
        for line in p.stdout:          # real‑time echo
            print(line, end="")
        p.wait()
        stdout, _ = p.communicate()
        return subprocess.CompletedProcess(cmd, p.returncode, stdout or "", "")


# public API

def is_docker_available() -> bool:
    return shutil.which("docker") is not None


def pull_image(image: str) -> None:
    """Pull *image* if not present, streaming progress live."""
    print(f"[leetcodex] pulling docker image {image} …")
    _stream(["docker", "pull", image]) 
    print("[leetcodex] image ready\n")


def run_subprocess(cmd: List[str], *, input_data=None,
                   timeout: Optional[int] = None,
                   memory_limit: Optional[int] = None) -> subprocess.CompletedProcess:
    """
    Run *cmd* locally with optional time/memory limits (timeout applies).
    """
    preexec = None
    if (timeout or memory_limit) and platform.system() != "Windows":
        import resource
        def _limits() -> None:
            if timeout:
                resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout))
            if memory_limit:
                mem = memory_limit * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        preexec = _limits

    try:
        return subprocess.run(cmd, input=input_data, text=True,
                              capture_output=True, timeout=timeout,
                              preexec_fn=preexec)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, -1, "", f"Timed out after {timeout}s")


def run_in_docker(image: str, workdir: str, cmd: List[str], *,
                  input_data=None, timeout: Optional[int] = None,
                  memory_limit: Optional[int] = None) -> subprocess.CompletedProcess:
    """
    Run *cmd* inside *image* with resource limits.
    Timeout applies only to the *container command*, NOT to `docker pull`.
    """
    base = ["docker", "run", "--rm", "--network", "none",
            "-v", f"{workdir}:/code", "-w", "/code"]
    if memory_limit:
        base += ["--memory", f"{memory_limit}m", "--memory-swap", f"{memory_limit}m"]
    if timeout:
        base += ["--ulimit", f"cpu={timeout}"]
    full_cmd = base + [image] + cmd
    return run_subprocess(full_cmd, input_data=input_data, timeout=timeout)
