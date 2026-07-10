---
name: verify
description: Runtime-verify frontend changes by driving the real app headless
---

# Verifying frontend changes

The user's dev servers (frontend 5173, API per vite proxy) serve the MAIN
checkout. To verify worktree code, start your own vite on a spare port:

```bash
cd <worktree>/web/frontend && npm install
npm run dev -- --port 5175 --strictPort   # background
curl -s http://localhost:5175/assets/api/filters | head -c 200   # sanity
```

The vite proxy forwards `/assets/api` to the running API — do not start
your own API. App URL: `http://localhost:5175/assets/`.

## Driving headless

Playwright chromium is cached at `~/Library/Caches/ms-playwright/`.
`npm install playwright-core` in a tmp dir and launch with
`executablePath: <cache>/chromium-*/chrome-mac-arm64/Google Chrome for
Testing.app/Contents/MacOS/Google Chrome for Testing`.

Useful selectors: `.pack-gallery` (home), `.gallery-card` (pack card),
`.asset-grid` / `.asset-item` (results), `.asset-detail` (detail view),
`.search-input-wrapper input` (search), `.suggestion` (tag suggestion),
`.search-bar .tag` (active tag chip), `.result-count`.

Gotchas: tag suggestions need typed input first; `kaykit` tag only
intersects KayKit packs (empty grid otherwise); searches debounce 150ms —
wait ~600ms after actions; watch `/api/search` requests to assert the
effective filters (`tag=`, `pack=` params).
