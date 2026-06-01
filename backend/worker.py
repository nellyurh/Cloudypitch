"""Worker process — runs the ingestion poller only, no HTTP server.

Used in the production Compose stack as a separate container so the API
can scale horizontally without spawning duplicate pollers.
"""
import asyncio
import logging
import os
import signal

from db import init_db, close_db
from ingestion import start_background_jobs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("cloudypitch.worker")


async def main():
    log.info("Cloudy Pitch worker starting (ingestion only, no HTTP)…")
    init_db()
    await start_background_jobs()
    log.info("Worker ingestion loop running. Press Ctrl+C to stop.")
    # Keep the event loop alive indefinitely
    stop = asyncio.Event()

    def _shutdown(*_):
        log.info("Shutdown signal received")
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            pass  # Windows fallback

    await stop.wait()
    close_db()
    log.info("Worker stopped cleanly")


if __name__ == "__main__":
    # Worker is ingestion by definition; this env var is ignored here but kept
    # for parity with the API container.
    os.environ.setdefault("RUN_INGESTION", "1")
    asyncio.run(main())
