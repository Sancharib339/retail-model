"""
FastAPI application exposing live retail intelligence stats to the dashboard.
State (counter, tracker, heatmap, db) is injected by main.py via app.state,
which keeps this module free of any direct dependency on the capture loop.
"""
import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Edge AI Retail Intelligence Platform",
    description="Live occupancy, entry/exit counts, and movement heatmap for the CV pipeline.",
    version="1.0.0",
)


class StatsResponse(BaseModel):
    occupancy: int
    total_entries: int
    total_exits: int
    active_tracks: int
    uptime_seconds: float
    timestamp: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/stats", response_model=StatsResponse)
def get_stats(request: Request):
    """Live occupancy and entry/exit statistics."""
    counter = request.app.state.counter
    tracker = request.app.state.tracker
    start_time = request.app.state.start_time

    stats = counter.get_stats()
    return StatsResponse(
        occupancy=stats["occupancy"],
        total_entries=stats["entries"],
        total_exits=stats["exits"],
        active_tracks=tracker.get_active_count(),
        uptime_seconds=round(time.time() - start_time, 1),
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )


@app.get("/heatmap")
def get_heatmap(request: Request):
    """Returns the accumulated customer movement heatmap as a PNG image."""
    heatmap = request.app.state.heatmap
    png_bytes = heatmap.get_png_bytes()
    return Response(content=png_bytes, media_type="image/png")
