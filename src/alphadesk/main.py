"""Process entrypoint: `uv run python -m alphadesk.main` (or the Docker CMD)."""

import logging

import uvicorn

from alphadesk.config import get_settings
from alphadesk.server import create_app
from alphadesk.wiring import build_container


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    settings = get_settings()
    container = build_container(settings)
    app = create_app(
        container.settings,
        container.db,
        container.event_bus,
        container.alpaca,
        container.scheduler,
    )

    uvicorn.run(app, host="0.0.0.0", port=settings.port)  # noqa: S104 - intentional container bind


if __name__ == "__main__":
    main()
