# Run all tests
test:
    uv run --script test_index.py
    uv run --script web/test_api.py

# Run index tests only
test-index:
    uv run --script test_index.py

# Run API tests only
test-api:
    uv run --script web/test_api.py

# Index all assets in assets/ directory (incremental)
index-assets:
    uv run --script index.py index assets/

# Force full reindex of all assets
reindex-assets:
    uv run --script index.py index assets/ --force

# Start API server (port 8000) with auto-reload
start-api:
    uv run --with fastapi --with uvicorn --with pillow uvicorn web.api:app --host 0.0.0.0 --port 8000 --reload

# Start frontend dev server (port 5173)
start-frontend:
    cd web/frontend && npm run dev

# Stop API server
stop-api:
    -lsof -ti:8000 | xargs kill

# Stop frontend server
stop-frontend:
    -lsof -ti:5173 | xargs kill

# Start both servers (run in separate terminals)
start-all:
    @echo "Run 'just start-api' and 'just start-frontend' in separate terminals"
