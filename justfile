# Run all tests
test:
    uv run --script test_assetindex.py
    uv run --script web/test_api.py

# Run assetindex tests only
test-index:
    uv run --script test_assetindex.py

# Run API tests only
test-api:
    uv run --script web/test_api.py

# Index all assets in assets/ directory (incremental)
index-assets:
    uv run --script assetindex.py index assets/

# Force full reindex of all assets
reindex-assets:
    uv run --script assetindex.py index assets/ --force

# Start API server (port 8000)
start-api:
    uv run --script web/api.py

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
