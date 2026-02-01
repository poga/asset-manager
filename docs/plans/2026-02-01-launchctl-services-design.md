# Launchctl Services for Asset Manager

## Overview

Set up launchd user agents to automatically start the API and frontend servers on login, using uncommon ports to avoid conflicts with development servers.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    On Login                              │
│  launchd loads:                                          │
│    • com.poga.asset-manager-api.plist                   │
│    • com.poga.asset-manager-frontend.plist              │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              Background Services                         │
│  • API:      just start-api-bg      → localhost:38471   │
│  • Frontend: just start-frontend-bg → localhost:38472   │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              Caddy (already running)                     │
│  dev.taileea02.ts.net/assets/api/* → localhost:38471    │
│  dev.taileea02.ts.net/assets/*     → localhost:38472    │
└─────────────────────────────────────────────────────────┘
```

## Port Allocation

| Service | Dev Port | Background Port |
|---------|----------|-----------------|
| API | 8000 | 38471 |
| Frontend | 5173 | 38472 |

## Files to Create/Modify

### 1. justfile - Add Background Targets

Note: Uses absolute paths because launchd has a limited PATH.

```just
# Start API server for background service (port 38471)
start-api-bg:
    /Users/poga/.local/bin/uv run --with fastapi --with uvicorn --with pillow uvicorn web.api:app --host 127.0.0.1 --port 38471

# Start frontend for background service (port 38472)
start-frontend-bg:
    cd web/frontend && /opt/homebrew/bin/npm run dev -- --port 38472
```

### 2. ~/Library/LaunchAgents/com.poga.asset-manager-api.plist

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.poga.asset-manager-api</string>
    <key>WorkingDirectory</key>
    <string>/Users/poga/projects/asset-manager</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/just</string>
        <string>start-api-bg</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/poga/Library/Logs/asset-manager-api.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/poga/Library/Logs/asset-manager-api.log</string>
</dict>
</plist>
```

### 3. ~/Library/LaunchAgents/com.poga.asset-manager-frontend.plist

Note: Requires EnvironmentVariables to set PATH because npm internally calls node.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.poga.asset-manager-frontend</string>
    <key>WorkingDirectory</key>
    <string>/Users/poga/projects/asset-manager</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/just</string>
        <string>start-frontend-bg</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/poga/Library/Logs/asset-manager-frontend.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/poga/Library/Logs/asset-manager-frontend.log</string>
</dict>
</plist>
```

### 4. /opt/homebrew/etc/Caddyfile

```caddyfile
dev.taileea02.ts.net {
    handle /assets/api/* {
        uri strip_prefix /assets
        reverse_proxy localhost:38471
    }
    handle /assets/* {
        reverse_proxy localhost:38472
    }
}
```

## Installation

```bash
# Load and start services
launchctl load ~/Library/LaunchAgents/com.poga.asset-manager-api.plist
launchctl load ~/Library/LaunchAgents/com.poga.asset-manager-frontend.plist

# Reload Caddy
brew services restart caddy
```

## Management Commands

```bash
# Stop services
launchctl unload ~/Library/LaunchAgents/com.poga.asset-manager-api.plist
launchctl unload ~/Library/LaunchAgents/com.poga.asset-manager-frontend.plist

# Check status
launchctl list | grep asset-manager

# View logs
tail -f ~/Library/Logs/asset-manager-api.log
tail -f ~/Library/Logs/asset-manager-frontend.log
```
