# Discord Automation Engine — 24/7 Cloud & Owner Control Center

A private, high-density owner control panel for Discord broadcast campaigns, Embed Studio design, Developer Quest role-connection metadata syncs, live guild telemetry, and Server Boost perk matrices.

---

## ☁️ How to Host 24/7 (Without Your PC Turned On)

Because a website and background scheduler need a server that stays powered on when your PC is shut down, this repository includes complete **24/7 Cloud Deployment** configurations for **Fly.io**, **Render**, and **Railway**:

### Option 1: Fly.io 1-Click Cloud Deploy (Recommended — `fly.exe` is already installed on your PC)
1. Double-click **[`deploy_cloud.bat`](file:///c:/Users/regan/OneDrive/Desktop/auto%20mm/deploy_cloud.bat)** in your project folder.
2. It will open your browser once to sign in to Fly.io, provision a persistent `/data` volume for your database, and deploy your container with `min_machines_running = 1` and `auto_stop_machines = "off"` ([`fly.toml`](file:///c:/Users/regan/OneDrive/Desktop/auto%20mm/fly.toml)).
3. You get a permanent `https://discord-owner-engine.fly.dev` link that runs 24/7 even when your PC is completely powered off.

### Option 2: Render.com / Railway.app (Cloud Git Deploy)
1. Push this folder to a private GitHub repository.
2. Connect the repository to **Render.com** (auto-detected via [`render.yaml`](file:///c:/Users/regan/OneDrive/Desktop/auto%20mm/render.yaml)) or **Railway.app** (auto-detected via [`railway.json`](file:///c:/Users/regan/OneDrive/Desktop/auto%20mm/railway.json) and [`Dockerfile`](file:///c:/Users/regan/OneDrive/Desktop/auto%20mm/Dockerfile)).
3. Your container + background worker daemon will run 24/7 in the cloud.

---

## ⚡ Upgraded Features

1. **Overview & Live Daemon Console**:
   - Real-time streaming terminal console showing background worker execution logs (`SYSTEM`, `INFO`, `EXEC`, `TASK`, `OK`, `ERR`).
   - Quick-fire operation buttons (`Ping Bot API`, `Sync Quests`, `New Broadcast`), searchable audit trail, and live auto-sync selector (`5s`, `15s`, `30s`, `Paused`).
2. **Broadcast & Discord Embed Studio**:
   - Split-pane **Discord Embed Studio** with real-time Discord render preview as you type.
   - Supports Author header, Embed Title, Color Picker, Markdown Description, Footer, Saved Webhook dropdown selector, latency measurement (`ms`), and **"⚡ Run Now"** instant firing.
3. **Quest & Task Automation Engine**:
   - Real Discord Application Role Connection Metadata sync (`PUT /applications/{id}/role-connections/metadata`), Bot REST Latency Ping, Token & Guilds Health Audit, and Guild Telemetry Audit.
   - **Task JSON Inspector Modal** to view raw input payloads and execution output JSON.
4. **Member Operations & OAuth2 Permission Calculator**:
   - **Connected Bot Servers Explorer**: Automatically lists all Discord servers your bot is in (`GET /users/@me/guilds`) for 1-click inspection.
   - **Interactive OAuth2 Permission Calculator**: Checkboxes that compute the exact Discord permission bitmask and invite URL.
5. **Server Boost Telemetry & Perk Matrix**:
   - Visual Boost Level progress bar ($0 \to 2 \to 7 \to 14$ boosts) and a 3-tier **Unlocked vs. Locked Perk Matrix**.
6. **Batch Internal Node Keys**:
   - Custom key prefixes (`OWN-`, `NODE-`, `BOT-`, `API-`), batch generation ($1\text{--}25$), 1-click copy, and JSON export.

---

## 🔑 Access & Credentials

- **Local URL**: `http://127.0.0.1:5000` (or `http://192.168.4.33:5000` on your network)
- **Operator Username**: `admin`
- **Password**: `AdminPass6767!`
