"""Run the harness API server: python -m harness.serve"""

from __future__ import annotations

import uvicorn
from dotenv import load_dotenv

from harness.api import create_app
from harness.settings import HarnessSettings


def main() -> None:
    load_dotenv()
    settings = HarnessSettings.load()
    app = create_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
