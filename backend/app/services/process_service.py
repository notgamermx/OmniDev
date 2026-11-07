"""Bounded command execution with process-tree cleanup on Windows and POSIX."""

import asyncio
import os
import signal
import shutil
import uuid
from pathlib import Path
from app.core.config import settings


async def _collect(process, timeout):
    output = bytearray()

    async def drain():
        while chunk := await process.stdout.read(8192):
            output.extend(chunk[: max(0, settings.COMMAND_OUTPUT_BYTES - len(output))])
        await process.wait()

    timed_out = False
    try:
        await asyncio.wait_for(drain(), timeout)
    except (asyncio.TimeoutError, asyncio.CancelledError) as exc:
        if os.name != "nt":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        elif process.returncode is None:
            killer = await asyncio.create_subprocess_exec(
                "taskkill",
                "/PID",
                str(process.pid),
                "/T",
                "/F",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await killer.wait()
            if process.returncode is None:
                process.kill()
        await process.wait()
        if isinstance(exc, asyncio.CancelledError):
            raise
        timed_out = True
    return {
        "output": output.decode("utf-8", errors="replace"),
        "exit_code": process.returncode,
        "timed_out": timed_out,
    }


async def _run_host_command(command: str, cwd, timeout: int):
    process = await asyncio.create_subprocess_shell(
        command,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        start_new_session=os.name != "nt",
    )
    return await _collect(process, timeout)


async def run_command(command: str, cwd, timeout: int):
    """Execute with only the workspace mounted, no host environment or network."""
    root = Path(cwd).resolve(strict=True)
    if not shutil.which("docker"):
        raise RuntimeError("Shell execution requires Docker and the configured execution image")
    name = "omnidev-" + uuid.uuid4().hex
    argv = ["docker", "run", "--rm", "--pull=never", "--name", name,
            "--network=none", "--read-only", "--cap-drop=ALL",
            "--security-opt=no-new-privileges", "--pids-limit=128",
            "--memory=512m", "--cpus=1", "--tmpfs=/tmp:rw,nosuid,nodev,size=64m",
            "--user", f"{os.getuid()}:{os.getgid()}" if os.name != "nt" else "1000:1000",
            "--mount", f"type=bind,source={root},target=/workspace", "--workdir=/workspace",
            "--env=HOME=/tmp", "--env=PYTHONDONTWRITEBYTECODE=1"]
    from app.services.verification_guard import snapshot
    baseline = snapshot(root)
    # Nested read-only mounts prevent a shell from editing or replacing original checks.
    directories = {Path(p).parts[0] for p in baseline if Path(p).parts[0] in {"tests", "test", "__tests__"}}
    if (root / ".git").exists():
        argv += ["--mount", f"type=bind,source={root / '.git'},target=/workspace/.git,readonly"]
    for directory in sorted(directories):
        argv += ["--mount", f"type=bind,source={root / directory},target=/workspace/{directory},readonly"]
    for path in baseline:
        if Path(path).parts[0] not in directories:
            argv += ["--mount", f"type=bind,source={root / path},target=/workspace/{Path(path).as_posix()},readonly"]
    argv += [settings.EXECUTION_IMAGE, "sh", "-c", command]
    try:
        return await run_exec(argv, root, min(120, max(1, timeout)))
    finally:
        cleanup = await asyncio.create_subprocess_exec("docker", "rm", "-f", name,
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        try:
            await asyncio.wait_for(cleanup.wait(), 10)
        except asyncio.TimeoutError:
            cleanup.kill()
            await cleanup.wait()


async def run_exec(argv: list[str], cwd, timeout: int):
    executable = shutil.which(argv[0]) or argv[0]
    if os.name == "nt" and executable.lower().endswith((".cmd", ".bat")):
        # cmd.exe expands metacharacters even in some quoted arguments. Native
        # executables and node/python entrypoints accept arbitrary prompts safely.
        if any(any(c in arg for c in '&|<>^%!\r\n"') for arg in argv[1:]):
            raise OSError(
                "Use the native executable or node/python entrypoint for this prompt"
            )
    process = await asyncio.create_subprocess_exec(
        executable,
        *argv[1:],
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        start_new_session=os.name != "nt",
    )
    return await _collect(process, timeout)
