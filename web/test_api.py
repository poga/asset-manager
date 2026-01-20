#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastapi>=0.109",
#     "httpx>=0.27",
#     "pytest>=8.0",
# ]
# ///
"""Tests for web API."""

import pytest
from fastapi.testclient import TestClient

from api import app

client = TestClient(app)


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
