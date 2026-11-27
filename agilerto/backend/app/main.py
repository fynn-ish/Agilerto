import asyncio
import contextlib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config, scheduler
from .db import init_db
from . import tiles
from .routes import chat, dashboard, facilities, reference


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()                                   # creates tables on first run
    task = asyncio.create_task(scheduler.loop()) if config.SCHEDULER_ENABLED else None
    yield
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="Disaster Info System", version="0.2.0", lifespan=lifespan)

# Dev only: lets the Vite dev server (port 5173) call the API directly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(facilities.router, prefix="/api")
app.include_router(reference.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(tiles.api_router, prefix="/api")
app.include_router(tiles.public_router)

# Production: serve the built React app from this same server (mounted last).
DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="frontend")
