import asyncio
import os
import signal


async def run_command(command: str, cwd, timeout: int):
    process = await asyncio.create_subprocess_shell(
        command,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        start_new_session=os.name != "nt",
    )
    # Drain output continuously while bounding retained bytes.
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
