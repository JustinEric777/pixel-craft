"""Small process-wide logging setup for API and inference diagnostics."""

from __future__ import annotations

import logging

request_logger = logging.getLogger("zpixel_edit.http")


def configure_logging(level_name: str = "INFO") -> None:
    level_name = level_name.upper()
    level = getattr(logging, level_name, logging.INFO)
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
    root.setLevel(level)
