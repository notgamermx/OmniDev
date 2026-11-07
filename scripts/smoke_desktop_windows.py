"""Windows CI: verify the installed GUI starts and cleans up its own engine."""

import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request


def main():
    if os.name != "nt":
        raise SystemExit("This check requires Windows with WebView2.")
    executable = Path(sys.argv[1]).resolve()
    connection_file = (
        Path(os.environ.get("OMNIDEV_HOME", Path.home() / ".omnidev"))
        / "desktop-connection.json"
    )
    connection_file.unlink(missing_ok=True)
    process = subprocess.Popen([str(executable)])
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
        subprocess.run([str(executable)], check=True, timeout=15)
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


if __name__ == "__main__":
    main()
