"""Windows CI: verify the installed GUI starts and cleans up its own engine."""

import argparse
import json
import shlex
import tempfile
import os
from pathlib import Path
import subprocess
import time
import urllib.request


def verify_docker(connection, workspace):
    """Exercise the installed engine's Docker transport through authenticated HTTP."""

    def api(path, body, method="POST"):
        request = urllib.request.Request(
            connection["url"] + "/api/v1" + path,
            data=json.dumps(body).encode(),
            method=method,
            headers={
                "Authorization": "Bearer " + connection["token"],
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    api("/workspace/execution", {"enabled": True}, "PUT")

    def run(command, timeout=10):
        return api("/terminal", {"command": command, "timeout": timeout})

    # The process must see the Windows bind mount in its Linux container.
    script = "import pathlib,os; assert pathlib.Path('test_app.py').read_text() == 'original'; assert os.listdir('/sys/class/net') == ['lo']; pathlib.Path('result.txt').write_text('container-ok'); print('docker-ok')"
    result = run("python -c " + shlex.quote(script))
    assert result["exit_code"] == 0 and "docker-ok" in result["output"], result
    assert (workspace / "result.txt").read_text() == "container-ok"
    result = run("echo tampered > test_app.py")
    assert result["exit_code"] != 0, result
    assert (workspace / "test_app.py").read_text() == "original"
    result = run("python -c " + shlex.quote("print('x'*100000)"))
    assert result["exit_code"] == 0 and len(result["output"].encode()) <= 32000, result
    result = run("sleep 60", timeout=1)
    assert result["timed_out"], result
    print(
        "Installed MSI engine: Docker bind mount, network isolation, protected files, output cap and timeout passed"
    )


def main():
    if os.name != "nt":
        raise SystemExit("This check requires Windows with WebView2.")
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument(
        "--docker",
        action="store_true",
        help="Require the local Docker Linux-container execution image",
    )
    args = parser.parse_args()
    executable = args.executable.resolve()
    temporary = tempfile.TemporaryDirectory(prefix="omnidev-installed-smoke-")
    home = Path(temporary.name)
    workspace = home / "workspace"
    workspace.mkdir()
    (workspace / "test_app.py").write_text("original")
    environment = {
        **os.environ,
        "OMNIDEV_HOME": str(home),
        "PROJECT_ROOT": str(workspace),
        "COMMAND_OUTPUT_BYTES": "32000",
    }
    connection_file = home / "desktop-connection.json"
    connection_file.unlink(missing_ok=True)
    process = subprocess.Popen([str(executable)], env=environment)
    try:
        for _ in range(150):
            if process.poll() is not None:
                raise RuntimeError("Desktop exited before its engine became ready")
            try:
                connection = json.loads(connection_file.read_text())
                request = urllib.request.Request(
                    connection["url"] + "/api/v1/health/",
                    headers={"Authorization": "Bearer " + connection["token"]},
                )
                with urllib.request.urlopen(request, timeout=1) as response:
                    if response.status == 200:
                        break
            except (OSError, ValueError):
                time.sleep(0.2)
        else:
            raise RuntimeError("Desktop engine readiness timed out")
        if args.docker:
            verify_docker(connection, workspace)
        subprocess.run([str(executable)], check=True, timeout=15, env=environment)
        assert process.poll() is None, "Second instance must focus the first window"
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-Process -Id {process.pid}).CloseMainWindow() | Out-Null",
            ],
            check=True,
        )
        process.wait(timeout=20)
        assert not connection_file.exists(), (
            "Desktop must remove its CLI discovery file on exit"
        )
        try:
            urllib.request.urlopen(request, timeout=1).close()
        except OSError:
            pass
        else:
            raise AssertionError("Desktop engine remained running after exit")
        print(
            "Installed Windows desktop startup, single instance and engine shutdown passed"
        )
    finally:
        if process.poll() is None:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                capture_output=True,
            )
            process.wait(timeout=10)
        temporary.cleanup()


if __name__ == "__main__":
    main()
