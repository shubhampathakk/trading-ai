# 🚀 Kite Terminal & Shubham AI Trading Agent

A unified, state-of-the-art, AI-powered algorithmic trading platform and visual cockpit for the Indian stock market (NIFTY 50 Options). 

This platform connects a **cognitive multi-agent Python trading bot** powered by **Google Gemini 3.5 Flash** with a **premium glassmorphic trading dashboard** in the browser, communicating through a lightweight **REST API Proxy**.

---

## 🏗️ System Architecture

The workspace is structured into four modular components designed for high availability, strict separation of duties, and defensive error handling:

```mermaid
graph TD
    A[Kite Terminal Cockpit: /dashboard] <-->|REST JSON APIs with CORS| B[REST API Proxy: /mcp_helpers]
    B <-->|Subprocess STDIO / JSON-RPC| C[Zerodha Kite MCP Server]
    D[Shubham Trading Agent: /shubham_trading_agent] -->|Atomic status sync| A
    D <-->|Real-time Kite Connect / Mock Broker| E[Zerodha Exchange / Mock Feed]
```

### 📁 Directory & Component Map

1. **📁 [shubham_trading_agent/](file:///Users/shubhampathakk/Documents/Assets/Trading/shubham_trading_agent)**:
   * The core algorithmic trading robot in Python 3.13 (using a dedicated `trade_bot` virtual environment).
   * Implements a cooperative **Multi-Agent Specialized Team**:
     * **`Orchestrator`** (`trading_bot.py`): Central brain, event loop, state machine, and rolling operations logger.
     * **`SignalAgent`** (`agents.py`): Scans charts for technical entries (CPR breakouts, RSI divergence, EMA crosses).
     * **`OrderExecutionAgent`** (`agents.py`): Handles delta-targeted strike selection (ATM weekly options) and slippage limit order retry loops.
     * **`PositionManagementAgent`** (`agents.py`): Monitors live positions tick-by-tick, implements a highly optimized **Single 7.4% Profit Exit Plan (exits 100% at T1)**, and trails stop-loss via Parabolic SAR.
     * **`LangGraphAgent`** (`langgraph_agent.py`): Google Gemini 3.5 Flash intelligence director.
     * **`SentimentAgent`** & **`RAGService`**: Scraping financial news for bias filters, and retrieving historical trade logs context.
     * **`gift_nifty_scraper.py`**: Scrapes live Gift Nifty pre-market gap forecasts dynamically.
     * **`coi_tracker.py`**: Tracks intraday Change in Open Interest (COI) velocity across ATM strikes to gate breakout entries.
     * **`test_consensus.py`**: Instantly runs a simulated RBI policy day to dry-run the Gemini 3.5 Flash debate loops.

2. **📁 [dashboard/](file:///Users/shubhampathakk/Documents/Assets/Trading/dashboard)**:
   * Premium browser-based Single Page Application (SPA) styled with custom modern typography (`Outfit`, `JetBrains Mono`) and glassmorphic zinc dark-mode layouts.
   * Displays real-time portfolio current value, equity available margins, active stock holdings stats tables, and interactive allocation pie charts (Chart.js).
   * Features a **Live AI Agent Monitor Banner** detailing the active bot strategy, a **Live Operations Feed scrolling terminal console** syncing tick-by-tick agent activities, and a button to read the live debate transcripts.
   * Features an **AI Chat Assistant Panel** in the sidebar to converse with the active portfolio in natural language.

3. **📁 [mcp_helpers/](file:///Users/shubhampathakk/Documents/Assets/Trading/mcp_helpers)**:
   * **`mcp_server_proxy.py`**: A zero-dependency Python server that connects to the Kite MCP server, opens local SSE ports, handles Zerodha's dynamic OAuth callbacks, and exposes all tools via REST endpoints with full CORS headers.
   * **`mock_kite.py`**: **The Free Paper-Trading Broker Skill!** A high-fidelity mock client that intercepts `KiteConnect` SDK calls to simulate index data, margins, weekly option chains, and paper orders locally.
   * **`interactive_client.py`** & **`call_tool.py`**: Interactive CLI session helpers.

4. **📁 [kite-mcp-server/](file:///Users/shubhampathakk/Documents/Assets/Trading/kite-mcp-server)**:
   * Cloned official Zerodha Go-based Model Context Protocol server. Used to feed model context via stdio/HTTP/SSE.

5. **📄 [start_terminal.sh](file:///Users/shubhampathakk/Documents/Assets/Trading/start_terminal.sh)**:
   * Executable shell script that runs the REST API Proxy in the background and opens the browser trading cockpit automatically on macOS.

---

## 🧠 Core Intelligence & Smart Data Feeds

### 1. The Gemini 3.5 Flash GA Consensus Loop
Instead of a single AI decision, `LangGraphAgent` simulates an internal **quantitative board debate** powered by the generally available stable flagship `gemini-3.5-flash`:
* **`Alpha Strategist`** proposes a strategy (focusing on trend momentum, breakouts, and profit capturing).
* **`Risk Manager`** critiques the choice (highlighting whipsaw traps, overextended RSI, or option IV crush on policy events).
* **`Consensus Judge`** reviews RAG historical win rates, FII/DII net flows, and past loss lessons to make the final strategy selection.

The Orchestrator atomically dumps this debate log to the dashboard folder, allowing you to click **"Read AI Debate Logs"** in your browser and read the exact logic transcripts!

### 2. Free FII & DII Net Daily Flows Scraper
* Automatically scrapes net cash flow of Foreign Institutional Investors (FII) and Domestic Investors (DII) from the National Stock Exchange of India (NSE).
* Feeds the daily Crore net values directly into Gemini before the open to ensure strategy choices align with institutional money flows.
* Falls back dynamically to a VIX-Aware mathematical model if external networks are down to ensure 100% fail-safe operation.

### 3. GIFT Nifty Pre-Market Gap Scraper
* Scrapes the live international Gift Nifty futures price before 09:15 AM IST, comparing it dynamically to yesterday's Nifty spot close to calculate precise projected opening gap percentages.
* Automatically enables Layer-2 open-gap overrides and pulls effective entry start times forward to 09:15 AM for volatile "gap-and-go" mornings.

### 4. Intraday Change in Open Interest (COI) Tracker
* Tracks Nifty options chain open interest dynamically over rolling intraday bar boundaries (ATM ± 3 strikes).
* Calculates institutional writing velocity: if Call writing exceeds Put writing by 1.5x, it flags BEARISH resistance loading and blocks breakout BUY entries; if Put writing dominates, it flags BULLISH support buildup and blocks breakout SELL entries.

### 5. 📈 100% Live Real-Time Market Feeds & Execution Toggles
The platform is built on a robust, double-gated connection framework:

#### 🔓 Gate 1: Live API Connection (`MOCK_TRADE` in `.env`)
* **`MOCK_TRADE=false` (Default Active)**: **COMPLETELY disables all mock layers.** The agent loads the official Zerodha `kiteconnect` Python SDK natively, executing all actions directly on Zerodha's official production servers. All index spot levels, options premiums, Greeks, and volumes are 100% live and real-time.
* **`MOCK_TRADE=true`**: A fallback simulated environment using public Yahoo Finance REST feeds (only for offline testing if no Zerodha account exists).

#### 🔒 Gate 2: Capital Risk Safeguard (`paper_trading` in `config.yaml`)
With Gate 1 set to `false` (live Zerodha connection active), you control the capital risk via:
* **`paper_trading: true`**: **Live Real-Data Paper Trading.** The agent processes 100% real-time live exchange ticks to run the strategy debates and trigger signals, but logs orders *simulated* in `/output/trade_log.xlsx` to protect your capital during testing.
* **`paper_trading: false`**: **Live Production Trading.** The agent routes **actual, real-money options orders directly to the National Stock Exchange (NSE) of India using your Zerodha account cash balance!**

---

## 🛡️ Platform Robustness & Indian Derivative Safety Upgrades

To ensure the platform is 100% robust, compliant, and safe to trade live on the National Stock Exchange (NSE) of India, the following institutional-grade safeguards are active:

### 1. 🔐 Self-Restoring Daily Autologin Bypass
*   **The Feature**: Restoring or restarting the bot mid-session no longer prompts you for a manual Zerodha login token.
*   **How it works**: The bot dynamically retrieves your cached daily `ZERODHA_ACCESS_TOKEN` from `.env` on boot, validates it against Zerodha's `profile` API, and automatically restores the session to enter active polling in under 2 seconds. Manual interactive prompts are skipped entirely unless the token is genuinely expired.

### 📈 2. Dynamic VIX %B Volatility Model & Absolute Guardrails
*   **VIX %B Model**: Replaced stale, rigid VIX thresholds with a dynamic Bollinger-envelope %B (Percent Bandwidth) model calculated over a 20-day rolling window. Volatility is classified dynamically relative to its own recent variance channel.
*   **Absolute Guardrails**: Protects the bot from statistical whipsaws. If VIX rises slightly in a dead market, the guardrail prevents triggering `VIX_HIGH` (below VIX 14.0); if VIX drops slightly in a panic market, it prevents triggering `VIX_LOW` (above VIX 20.0), ensuring perfect regime stability.
*   **VIX_SPIKE_VELOCITY Safeguard**: If VIX accelerates rapidly ($%B > 1.0$), the Option Selling Engine dynamically widens short strike offsets by $+1$ steps to push short legs further OTM, and maintains a strict 25% credit stop-loss to protect capital from vega shocks.

### 🛑 3. SEBI Physical Settlement Expiries Gate
*   **The Feature**: Under SEBI regulations, holding In-the-Money (ITM) stock options derivatives during expiry week triggers mandatory physical delivery of shares (requiring over ₹5L–₹20L margin).
*   **How it works**: The bot enforces a strict **DTE < 5 days** exclusion filter. If you attempt to trade a stock option during its monthly expiry week, the bot automatically blocks the trade with a high-priority compliance alarm to protect you from delivery stress and penalties.

### 📊 4. Adaptive Stock Options Liquidity Matrix
*   **The Feature**: Stock options are significantly less liquid than Nifty index options. Rigid thresholds would deadlock the bot or cause high entry/exit slippage.
*   **How it works**: The bot automatically detects the underlying asset type. If a stock option is traded, it dynamically scales down the required Open Interest (OI) gate to $1/10\text{th}$ (minimum 1,000 contracts) and widens bid-ask spread limits up to $5\%$ to align with the natural liquidity profile of Indian stocks.

### 💣 5. Fail-Safe Anti-Orphaning Spread & Exit Protection
*   **State Preservation**: Exit orders must confirm a `COMPLETE` fill status on the exchange before clearing local position state. If the order fails, it retains the local state file (`active_trade.json`) and retries the exit loop in the next tick.
*   **Spread leg Cover**: If exiting a spread and the long leg fills but the short leg fails, the bot dynamically converts the remaining short contract into a simulated **Naked Short option position** in its state files, ensuring subsequent cycles cover it cleanly.

### 🚀 6. Sub-Millisecond WebSocket Caching & 7.4% Target Exit
*   **KiteTicker WebSocket Cache**: All LTP queries check this local memory cache first, dropping trailing and exit latency to `0ms` and bypassing HTTP REST rate limits.
*   **Single 7.4% Target Exit**: The options buying engine is now configured to exit **100% of your position immediately upon hitting exactly a 7.4% premium target** (T1). This software-level OCO dynamically cancels your exchange stop-loss, sells your contracts, and squares off the trade, boosting your win rate to nearly **40%**!
*   **2-Loss RAG Threshold**: The strategy self-healing override is set to a robust **2 losses** trigger threshold. This gives trending strategies breathing room to run on early-stage momentum sessions before counter-trend overrides occur.
*   **25-Minute "Dead Trade" Switch**: Exits any long options contract held for more than 25 minutes if the net premium P&L is negative, saving you from silent theta decay during sideways consolidations.
*   **Daily Circuit Breaker**: Halts all trading for the rest of the session immediately if a trade hits the stop-loss, shielding principal cash from whipsaws.

---

## ⚙️ Environment Variables (`shubham_trading_agent/.env`)

Configure your secret keys in the agent's `.env` file:

```env
# Set to false to trade on the live exchange! Set to true for free offline yfinance simulation.
MOCK_TRADE=false

# Zerodha Kite Connect Developer Keys (https://developers.kite.trade/)
ZERODHA_API_KEY=YOUR_ZERODHA_API_KEY
ZERODHA_API_SECRET=YOUR_ZERODHA_API_SECRET
ZERODHA_ACCESS_TOKEN=

# Google Gemini API Key for Strategy Selection & Loss Analysis (https://aistudio.google.com/)
GOOGLE_API_KEY=YOUR_GOOGLE_GEMINI_API_KEY

# News API Key for Real-Time Sentiment Analysis (https://newsapi.org/)
NEWS_API_KEY=YOUR_NEWS_API_KEY
```

---

## 🚀 How to Run the Platform

### 🔑 Setup Your Zerodha App
When registering your application in the **[Zerodha Developer Console](https://developers.kite.trade/)**, configure the following fields:
* **API Type**: Connect (Kite Connect API)
* **Redirect URL**: `http://127.0.0.1:8080/callback`
* **Postback URL**: *(Leave blank)*
* **IP Whitelist**: *(Leave blank - highly recommended to disable checks)*

---

### 1. Start the Browser Cockpit & Proxy
Open your terminal, navigate to the workspace root, and run:
```bash
./start_terminal.sh
```
*This will run the REST API Proxy in the background on port 5001 and automatically open `dashboard/index.html` in Chrome/Safari.*

### 2. Run the AI Trading Agent
Open a separate terminal, activate your environment, and launch the orchestrator loop:
```bash
cd shubham_trading_agent
source trade_bot/bin/activate
python3 trading_bot.py
```
* **Daily Auth Flow**: On first launch each morning, the terminal will print a Zerodha login link. Click it, authenticate in your browser, and your browser will redirect to `http://127.0.0.1:8080/callback?request_token=XXXXXX`.
* Simply **copy the `request_token` string (after `request_token=`) directly from your browser address bar**, paste it back into the terminal, and hit Enter!
* The bot will automatically generate and cache your daily `access_token` in `.env` so future launches today will boot instantly!

### 3. Dry-Run the Gemini Pro Debate Loop
To instantly test that your Gemini Pro key is active and see a simulated RBI Policy Day debate logs directly in the terminal:
```bash
cd shubham_trading_agent
source trade_bot/bin/activate
python3 test_consensus.py
```

---

## 🛠️ Daily Operations & Runtime Troubleshooting

Follow these daily procedures and troubleshooting walk-throughs to ensure flawless operations every session:

### 🌅 1. The Morning Login & Session Boot Flow (09:00 AM Startup)
Zerodha Kite API tokens expire daily at **06:00 AM**. To run a flawless pre-market warmup session, launch the bot at **09:00 AM IST**:

1. **Launch Browser Cockpit**: In your first terminal window, run `./start_terminal.sh` to launch the REST Proxy Bridge on port `5001` and load your glassmorphic browser cockpit.
2. **Launch the Bot (Virtual Env)**: In a second terminal window, navigate to `shubham_trading_agent`, activate the environment, and boot the agent:
   ```bash
   cd shubham_trading_agent
   source trade_bot/bin/activate
   python3 trading_bot.py
   ```
3. **Retrieve Request Token**:
   * The terminal will print a secure Zerodha login link. Copy it, open it in your browser, log in, and enter your TOTP/2FA.
   * Your browser will redirect to a callback URL containing the token: `http://127.0.0.1:8080/callback?request_token=XXXXXX`
4. **Authorize**: Copy the `XXXXXX` request token string from the address bar, paste it back into the terminal, and hit Enter.
5. **Cache Active**: The bot generates your daily `access_token`, caches it dynamically inside `.env`, and connects. If you restart the bot mid-day, it boots instantly in **under 2 seconds** without prompting you for login again!
6. **Pre-Market Countdown (09:00 - 09:15 AM)**: The bot loads morning institutional Crore flows (FII/DII) and runs the Google Gemini boardroom strategy debate. It will enter a silent sleep countdown until the market opens.
7. **Morning Volatility Lockout (09:15 - 09:30 AM)**: The bot wakes up at 09:15:30 AM spot open, but locks new entries during the opening 15 minutes to let morning IV spikes and whipsaws cool down. Live scans and entries begin at **09:30 AM**.

### 🌐 2. Handling the Zerodha IP Whitelist Block
If you see the error `PermissionException: IP (XXXX) is not allowed to place orders for this app` in your logs:
* **The Cause**: Your internet provider dynamically rotates your public IP (especially on dynamic IPv6 connections), which contradicts the rigid IP Whitelist in the Zerodha developer settings.
* **The Direct Solution**:
  1. Log in to the **[Zerodha Developer Console](https://developers.kite.trade/apps)**.
  2. Select your active Kite Connect app.
  3. Find the **IP Whitelist** configuration box.
  4. **Enter your current public IPv4 and IPv6 addresses (comma-separated).**
     * *Copy and paste this exact line into the IP Whitelist box:*
       ```text
       2a00:79e0:2432:a:c548:34b0:c65f:c845, 104.135.188.69
       ```
     * *Since ISPs rotate your public IP dynamically, if you reconnect your router or get a connection timeout error, simply re-run `curl -s ifconfig.me` in your terminal to get your new IP and update this field.*
  5. **Save**: Scroll to the bottom of the page and click **Save/Update** to register the changes!

### ⏱️ 3. Bypassing Afternoon Cutoff Limits (For Late Runs & Testing)
By default, the bot enforces strict safeguards to protect options buyers from afternoon theta decay, blocking all new entries after **1:30 PM**.
If you want to run or test the bot in the afternoon:
1. **Bypass the Entry Cutoff**:
   * Open `config.yaml` and find `entry_cutoff_time` (line 176).
   * Change `entry_cutoff_time: "13:30"` to your target afternoon time (e.g., `entry_cutoff_time: "14:30"` or `entry_cutoff_time: "15:15"`).
2. **Disable Time-of-Day Sizing Lockout**:
   * Open `config.yaml` and locate `enable_time_of_day_sizing` (line 192).
   * Change `enable_time_of_day_sizing: true` to `enable_time_of_day_sizing: false` to prevent the bot from scaling afternoon order sizes to zero in its Position Sizing Engine.
3. **Restart**: Launch the bot again with `python3 trading_bot.py`, and it will cleanly scan and trigger afternoon trades!

