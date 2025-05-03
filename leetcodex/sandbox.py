import os
import platform
import shutil
import subprocess

def is_docker_available():
    """Check if Docker is installed and in PATH."""
    return shutil.which("docker") is not None

def run_subprocess(cmd_list, input_data=None, timeout=None, memory_limit=None):
    """
    Run a command in a local subprocess with optional time/memory limits.
    Returns CompletedProcess with captured output.
    """
    # Set resource limits on Unix (Linux/Mac) if memory or CPU time specified
    preexec_fn = None
    if (timeout or memory_limit) and platform.system() != "Windows":
        import resource
        def _limit_resources():
            # CPU time limit (seconds)
            if timeout:
                resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout))
            # Memory limit (address space, bytes)
            if memory_limit:
                mem_bytes = memory_limit * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        preexec_fn = _limit_resources
    try:
        result = subprocess.run(
            cmd_list, input=input_data if input_data is not None else None,
            capture_output=True, text=True, timeout=timeout, preexec_fn=preexec_fn
        )
    except subprocess.TimeoutExpired as e:
        # Return a CompletedProcess-like object on timeout
        return subprocess.CompletedProcess(cmd_list, -1, stdout="", stderr=f"Timed out after {timeout}s")
    return result

def run_in_docker(image, workdir, cmd_list, input_data=None, timeout=None, memory_limit=None):
    """
    Run a command inside a Docker container with resource limits.
    Returns CompletedProcess with captured output.
    """
    # Base docker run command
    docker_cmd = ["docker", "run", "--rm", "--network", "none"]
    # Apply memory limit if specified (in MB)
    if memory_limit:
        docker_cmd += ["--memory", f"{memory_limit}m", "--memory-swap", f"{memory_limit}m"]
    # Apply CPU time limit (ulimit for CPU seconds inside container)
    if timeout:
        docker_cmd += ["--ulimit", f"cpu={timeout}"]
    # Mount the working directory as /code in the container (read-only if no compile needed)
    docker_cmd += ["-v", f"{workdir}:/code", "-w", "/code"]
    docker_cmd.append(image)
    docker_cmd += cmd_list
    try:
        result = subprocess.run(
            docker_cmd, input=(input_data if input_data is not None else None),
            capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        # If a timeout occurs, kill the container (not implemented for brevity)
        return subprocess.CompletedProcess(docker_cmd, -1, stdout="", stderr=f"Timed out after {timeout}s")
    return result
