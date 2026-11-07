import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
os.chdir(ROOT)
sys.path.insert(0, str(BACKEND))

import uvicorn  # noqa: E402

from app.core.config import settings  # noqa: E402


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        app_dir=str(BACKEND),
    )
