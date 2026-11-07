"""Bounded command execution with process-tree cleanup on Windows and POSIX."""

import asyncio
import os
import signal
import shutil


async def _collect(process, timeout):
    output = bytearray()

    async def drain():
        while chunk := await process.stdout.read(8192):
            output.extend(chunk[: max(0, 1_000_000 - len(output))])
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


async def run_command(command: str, cwd, timeout: int):
    process = await asyncio.create_subprocess_shell(
        command,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        start_new_session=os.name != "nt",
    )
    return await _collect(process, timeout)


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
