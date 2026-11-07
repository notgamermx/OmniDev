"""Exercise a frozen engine or CLI using an isolated home and real SQLite."""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request


def main():
    executable = str(Path(sys.argv[1]).resolve())
    with tempfile.TemporaryDirectory() as directory:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        environment = {
            **os.environ,
            "OMNIDEV_HOME": directory,
            "API_TOKEN": "synthetic-smoke-token-0123456789012345",
            "OMNIDEV_URL": url,
            "OMNIDEV_TOKEN": "synthetic-smoke-token-0123456789012345",
        }
        with open(Path(directory) / "engine.log", "wb") as log:
            process = subprocess.Popen(
                [executable, "serve", "--port", str(port)],
                env=environment,
                cwd=directory,
                stdout=log,
                stderr=log,
            )
            try:
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError(
                            "Engine exited before readiness: "
                            + (Path(directory) / "engine.log").read_text(
                                errors="replace"
                            )
                        )
                    try:
                        request = urllib.request.Request(
                            url + "/api/v1/health/",
                            headers={
                                "Authorization": "Bearer " + environment["API_TOKEN"]
                            },
                        )
                        with urllib.request.urlopen(request, timeout=1) as response:
                            if response.status == 200:
                                break
                    except OSError:
                        time.sleep(0.2)
                else:
                    raise RuntimeError("Engine readiness timed out")
                with urllib.request.urlopen(url + "/app/", timeout=3) as response:
                    assert b'<div id="root">' in response.read()
                for arguments in (
                    ["health"],
                    [
                        "projects",
                        "create",
                        "--json",
                        json.dumps({"name": "Windows smoke"}),
                    ],
                    ["connectors", "list"],
                    ["files"],
                ):
                    subprocess.run(
                        [executable, *arguments],
                        env=environment,
                        cwd=directory,
                        check=True,
                        timeout=30,
                    )
                assert (Path(directory) / "data/app.db").exists()
                print(
                    "Frozen engine migrations, web assets, authenticated API and CLI passed"
                )
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    main()
