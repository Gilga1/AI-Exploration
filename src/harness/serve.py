"""Run the harness API server: python -m harness.serve"""

from __future__ import annotations

import uvicorn

from harness.api import create_app
from harness.settings import HarnessSettings


def main() -> None:
    settings = HarnessSettings()
    app = create_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
