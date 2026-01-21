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
