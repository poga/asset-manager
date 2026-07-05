# Run all tests
test:
    uv run --script test_index.py
    uv run --script test_frame_detect.py
    uv run --script test_pack_themes.py
    uv run --script test_model_indexer.py
    uv run --script web/test_api.py

# Run index tests only
test-index:
    uv run --script test_index.py

# Run API tests only
test-api:
    uv run --script web/test_api.py

# Run model indexer tests only
test-model:
    uv run --script test_model_indexer.py

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

# Build frontend for production
build-frontend:
    cd web/frontend && npm run build

# Stop API server
stop-api:
    -lsof -ti:8000 | xargs kill

# Stop frontend server
stop-frontend:
    -lsof -ti:5173 | xargs kill

# Start both servers (run in separate terminals)
start-all:
    @echo "Run 'just start-api' and 'just start-frontend' in separate terminals"

# Start API server for background service (port 38471)
start-api-bg:
    /Users/poga/.local/bin/uv run --with fastapi --with uvicorn --with pillow uvicorn web.api:app --host 127.0.0.1 --port 38471

# Start frontend for background service (port 38472)
start-frontend-bg:
    cd web/frontend && /opt/homebrew/bin/npm run dev -- --port 38472
