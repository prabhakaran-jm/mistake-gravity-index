import logging
import os

def setup_logging() -> None:
    level = os.getenv("MGI_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(message)s",
    )