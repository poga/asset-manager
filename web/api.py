#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastapi>=0.109",
#     "uvicorn>=0.27",
# ]
# ///
"""Web API for asset search."""

from fastapi import FastAPI

app = FastAPI(title="Asset Search API")


@app.get("/api/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}
