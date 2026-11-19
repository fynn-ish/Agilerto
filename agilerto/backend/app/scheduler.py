"""Background refresh loop. Plain asyncio, so there is no extra package to install."""
import asyncio
import logging

from . import config
from .ingest import run_all

log = logging.getLogger("uvicorn.error.ingest")


async def loop():
    await asyncio.sleep(2)                         # let the server finish starting first
    while True:
        try:
            await asyncio.to_thread(run_all)       # blocking network calls run off the event loop
        except Exception:
            log.exception("Scheduled refresh crashed; will try again next cycle")
        await asyncio.sleep(config.REFRESH_MINUTES * 60)
