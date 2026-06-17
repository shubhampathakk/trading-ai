# Shubham Trading Agent 3.5: An AI-Powered Algorithmic Trading System

The Shubham Trading Agent is a sophisticated, event-driven, and modular algorithmic trading application designed for the Indian stock market (NIFTY 50). It leverages modern AI, including Large Language Models (LLMs) and Retrieval-Augmented Generation (RAG), to make intelligent, data-driven trading decisions.

---

## 🌟 New Premium Capabilities: Multi-Leg Option Selling & Credit Spreads

The system has been upgraded with a institutional-grade **Multi-Leg Option Selling & Credit Spread Engine**, enabling the **Google Gemini Cognitive Boardroom** to dynamically debate and execute risk-defined credit setups:

### 1. Supported Credit & Income Strategies
*   **Iron Butterfly (`'Iron_Butterfly'`)** [Strictly Neutral]: Sell ATM CE + Sell ATM PE (Body), buy ATM + offset CE and ATM − offset PE (Wings). Captures high upfront net credit with strictly defined capped risk. Ideal for sideways, stagnant consolidation sessions.
*   **Bull Put Spread (`'Bull_Put_Spread'`)** [Bullish / Neutral]: Sell OTM Put near support, buy further OTM Put lower for protection. Ideal for rising markets to collect premium with capped tail risk.
*   **Bear Call Spread (`'Bear_Call_Spread'`)** [Bearish / Neutral]: Sell OTM Call near resistance, buy further OTM Call higher for protection. Ideal for falling markets to collect premium with capped risk.
*   **Intraday Strangle/Straddle (`'Intraday_Option_Selling'`)**:
    *   *Single-Phase Model*: Enters strangle/straddle at configured morning time, runs individual 25%-30% SL checks, and closes at exit time.
    *   *Sumeet Mongia two-phase Model*: Enters Morning Strangle (OTM-2) at 09:16 AM (exits 02:15 PM), then enters Afternoon Straddle (ATM) at 02:16 PM (exits 03:28 PM) to maximize daily theta decay.

### 2. Execution & Risk Safeguards
*   **Cooperative Boardroom Debate**: Gemini Pro 3.1 debates option selling vs buying dynamically. The **Alpha Strategist** lobbies for theta collection during range-bound days, the **Risk Manager** checks VIX thresholds and economic calendars to block entries on highly volatile event days, and the **Consensus Judge** makes the final bulletproof decision.
*   **Automated Margin Unlocking**: Automatically buys protection/long legs *first* to get immediate margin relief from your broker (reducing required margins by up to **70%**) before selling the short legs.
*   **Unified Combined Premium Monitor**: For credit spreads and Iron Butterflies, the engine monitors the unified combined premium of the entire spread. It automatically triggers profit-booking when the combined value drops by **50%** (max profit booking) or exits if combined losses exceed the SL threshold.

---

## Recent System Tweaks & Fixes
*   **Choppy State Tolerance (`trading_bot.py`)**: Adjusted the `DayQuality` algorithm to increase the `direction_changes` threshold from `7` to `12`. This prevents the bot from prematurely locking into a strict `CHOPPY` state during normal market noise, allowing primary trend strategies more room to operate.
*   **Volume Spread Analysis Tuning (`strategy_factory.py`)**: Lowered the `Volume_Spread_Analysis` high-volume requirement multiplier from `1.3x` to `1.2x` of the moving average. This balances trade frequency while effectively filtering out retail noise.
*   **Persistent Daily Logging (`trading_bot.py`)**: Added a robust `logging.FileHandler` that permanently saves daily terminal outputs into timestamped `.log` files (e.g., `output/logs/bot_YYYY-MM-DD.log`). Trade records, AI Post-Mortem analyses, and execution ticks are now preserved even if the terminal is closed or suspended.

---

## Key Features
*   **Automated F&O Trading**: Fully automates the process of analyzing market data, generating trade signals, and executing F&O (Futures & Options) orders via the Zerodha Kite Connect API.
*   **Multi-Strategy Framework**: Comes with a library of over 15+ pre-built trading strategies, from classic trend-following (Supertrend, MACD) to advanced reversal, volatility-based, and multi-leg credit spread strategies.
*   **AI-Powered Strategy Selection**: Utilizes Google's Gemini LLM to analyze real-time market conditions (VIX, IV, economic events) and select the most suitable trading strategy for the day.
*   **Retrieval-Augmented Generation (RAG)**: The bot's decision-making is enhanced by a RAG pipeline that retrieves historical performance data from its own trade logs, providing the AI with data-driven context. I have not added this `rag_service.py` to this code repository, but you can build your own RAG logic, placeholders are kept for you. In case you want to run the bot without this file, keep `use_rag` flag in `config.yaml` as false.
*   **Natural Language Prompting**: Allows the user to provide a natural language prompt (e.g., "market looks choppy, prefer breakout strategies") at startup, which the AI considers during strategy selection.
*   **Dynamic Strategy Reassessment**: If no trade signal is generated for a configurable period, the bot automatically re-evaluates market conditions and can switch to a more appropriate strategy mid-day.
*   **Real-Time Sentiment Analysis**: Fetches and analyzes the latest financial news using the News API and TextBlob to determine market sentiment, from "Very Bearish" to "Very Bullish".
*   **Economic Event Awareness**: Scrapes data on upcoming economic events (e.g., Fed and RBI meetings) to factor into its market condition analysis.
*   **Paper Trading Mode**: Includes a fully-featured paper trading mode to test strategies and bot performance without risking real capital.
*   **Automated Email Reporting**: Sends detailed daily and monthly performance reports via email, segregating live and paper trade P&L.
*   **Sovereign Robustness & Safety Upgrades**:
    *   *Self-Restoring Cached Authentication*: Bypasses manual login prompts by checking and validating the cached `access_token` against Zerodha on boot for 2-second hot restarts.
    *   *SEBI Physical Settlement Gate*: Automatically blocks stock options entries under 5 DTE during monthly expiry week to shield the operator from compulsory share delivery rules.
    *   *Adaptive Stock Options Liquidity*: Auto-scales down the required Open Interest threshold to 1/10th and expands bid-ask tolerances to 5% for individual stocks to prevent deadlocks.
    *   *Anti-Orphaning Exit loops*: Exit orders must confirm filled on exchange before clearing state memory, and orphaned spread legs are dynamically carried as naked short option states for clean covering.

---

## Architecture Overview
The application is built on a modular, agent-based architecture designed for scalability and resilience.

*   **Orchestrator (`trading_bot.py`)**: The central brain of the application. It manages the main event loop, state transitions (e.g., AWAITING_SIGNAL, IN_POSITION), and coordinates all other agents.
*   **Credit Spread & Strangle Engine (`option_selling_engine.py`)**: The high-frequency execution engine managing multi-leg strangle, straddle, credit spreads, and Iron Butterfly positions with combined premium tracking.
*   **Agents (`agents.py`)**:
    *   *OrderExecutionAgent*: Handles all aspects of order placement, sizing, and communication with the Kite API. Implements the "Isolated Worker Pattern" to ensure thread-safe order execution.
    *   *PositionManagementAgent*: Manages active trades, applying stop-loss, trailing stop-loss, and other risk management rules.
*   **Intelligence Layer**:
    *   *langgraph_agent.py*: Interfaces with the Gemini LLM to select strategies.
    *   *sentiment_agent.py*: Fetches and analyzes news to determine market sentiment.
    *   *market_context.py*: Identifies current market conditions (VIX, IV, etc.).
    *   *rag_service.py*: The RAG engine that retrieves historical performance from logs to augment the AI's prompts.
*   **Strategy & Indicators**:
    *   *strategy_factory.py*: A library of all trading strategies.
    *   *indicator_calculator.py* & *indicators.py*: Calculate all necessary technical indicators.
*   **Reporting & Persistence**:
    *   *reporting.py*: Manages the generation and emailing of performance reports.
    *   *output/*: Directory where trade logs and backtest results are stored.

---

## Setup and Installation
### Prerequisites
*   **Python**: Python 3.9 or higher.
*   **TA-Lib**: The TA-Lib library must be installed on your system before you can install the Python wrapper. This is a critical step.
    *   *macOS (using Homebrew)*: `brew install ta-lib`
    *   *Ubuntu/Debian*: `sudo apt-get install -y ta-lib-dev`
    *   *Windows*: Download `ta-lib-0.4.0-msvc.zip` from SourceForge, unzip it to `C:\ta-lib`, and then install the Python wrapper.

### Installation Steps
1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/zackakshayy/zAck_trading_bot.git shubham_trading_agent
    cd shubham_trading_agent
    ```
2.  **Create and Activate a Virtual Environment**:
    ```bash
    # For macOS/Linux
    python3 -m venv trade_bot
    source trade_bot/bin/activate
    
    # For Windows
    python -m venv trade_bot
    trade_bot\Scripts\activate
    ```
3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
4.  **Configure the Bot (`config.yaml`)**:
    Create a `config.yaml` file in the root directory. Use the following template and fill in your details. Do not commit this file to GitHub.

    ```yaml
    zerodha:
      api_key: "YOUR_KITE_API_KEY"
      api_secret: "YOUR_KITE_API_SECRET"
      # The access_token will be populated automatically after the first login
      access_token: ""

    google_api:
      api_key: "YOUR_GOOGLE_GEMINI_API_KEY"

    news_api:
      api_key: "YOUR_NEWSAPI_API_KEY"

    email_settings:
      send_daily_report: true
      smtp_server: "smtp.gmail.com"
      smtp_port: 587
      sender_email: "your_email@gmail.com"
      sender_password: "YOUR_GMAIL_APP_PASSWORD" # Use an App Password for security
      receiver_email: "receiver_email@example.com"

    strategy_selector:
      use_llm: true # enable Gemini Boardroom Strangle/Credit Spread debate!

    option_selling:
      enable: true
      mode: "strangle" # strangle, straddle, iron_butterfly, bull_put_spread, bear_call_spread
      entry_time: "09:20:00"
      exit_time: "15:15:00"
      sl_multiplier: 1.25 # 25% combined stop loss
      strike_offset_steps: 2
      hedge_offset_steps: 10
      use_sumeet_mongia_double_phase: false

    trading_flags:
      underlying_instrument: "NIFTY 50"
      chart_timeframe: "5minute"
      product_type: "MIS" # or "NRML"
      order_variety: "REGULAR"
      risk_per_trade_percent: 1.0 # e.g., 1% of capital
      stop_loss_percent: 15.0 # 15% stop-loss on the option premium
      max_trades_per_day: 5
      paper_trading: true # Set to false for live trading
      enable_gemini_loss_analysis: true
      enable_natural_language_prompt: true
      strategy_reassessment_period_minutes: 60
      use_rag: false
      rag_min_trading_days: 5
    ```

---

## How to Run
1.  **Activate Your Virtual Environment**:
    ```bash
    source trade_bot/bin/activate
    ```
2.  **Run the Main Bot Script**:
    ```bash
    python trading_bot.py
    ```
3.  **First-Time Authentication**:
    *   The first time you run the script, it will print a Kite login URL in the console.
    *   Copy this URL and paste it into your web browser.
    *   Log in with your Zerodha credentials.
    *   After a successful login, you will be redirected to a blank page. Copy the `request_token` from the URL in your browser's address bar.
    *   Paste this `request_token` back into the terminal when prompted.
    *   The bot will automatically cache your token for the rest of the day and begin trading.

---

## Disclaimer
This software is provided for educational and experimental purposes only. Algorithmic trading involves substantial risk and is not suitable for all investors. The authors and contributors are not responsible for any financial losses incurred through the use of this software. Always test thoroughly in paper trading mode before deploying with real capital.