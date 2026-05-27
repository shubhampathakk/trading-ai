import asyncio
import os
import logging
from dotenv import load_dotenv
from langgraph_agent import LangGraphAgent
from trading_bot import load_config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def test_consensus_agent():
    # Load the dotenv file
    load_dotenv()
    
    print("Loading Shubham Trading Agent configuration...", flush=True)
    config = load_config()
    
    # Verify Gemini API key
    gemini_key = os.environ.get("GOOGLE_API_KEY")
    if not gemini_key or gemini_key == "mock_gemini":
        print("❌ Error: Real GOOGLE_API_KEY must be set in your .env file to test the live Gemini Pro model.", flush=True)
        return
        
    # print("Initializing LangGraphAgent with gemini-3.5-flash...", flush=True) # Old model print
    print("Initializing LangGraphAgent with gemini-3.1-pro-preview...", flush=True)
    # Set use_llm to True in config to force the LLM path
    config['strategy_selector'] = config.get('strategy_selector', {}) or {}
    config['strategy_selector']['use_llm'] = True
    
    agent = LangGraphAgent(config, None)
    
    # Simulate high-volatility bullish breakout day
    market_conditions = {"VIX_MEDIUM", "IV_HIGH", "EVENT_RBI_POLICY"}
    sentiment = "Very Bullish"
    open_gap_pct = 1.2
    user_prompt = "RBI policy is expected to be positive, look for strong momentum buys."
    rag_context = (
        "Recent Strategy Performance (last 30 days):\n"
        "- 'Opening_Range_Breakout': WinRate=75.0% over 4 trades, AvgP/L=+₹12,500.00\n"
        "- 'EMA_Cross_RSI': WinRate=60.0% over 5 trades, AvgP/L=+₹4,200.00"
    )
    
    print("\n" + "="*60)
    print(f"🚀 TRIGGERING LIVE DYNAMIC STRATEGY DEBATE")
    print(f"• Market Conditions: {market_conditions}")
    print(f"• Bias: {sentiment} (Gap: {open_gap_pct:+.2f}%)")
    print(f"• RAG Context Active: Yes")
    print("="*60 + "\n")
    
    # We call Gemini API to run the internal Alpha Strategist vs Risk Manager debate
    import aiohttp
    
    # Construct the prompt directly from the agent code to see what the LLM sees
    prompt_sections = [
        "You are a prestigious consensus panel of 3 expert quantitative trading agents for the Indian NIFTY 50 options market:",
        "1. **Alpha Strategist** (Optimistic, focuses on capturing breakouts, trend momentum, and maximizing gains)",
        "2. **Risk Manager** (Skeptical, focuses on protecting capital, detecting stop-loss traps, high VIX/IV levels, option theta decay, and overextended RSI)",
        "3. **Consensus Judge** (Objective, weighs both arguments, reviews RAG logs, and makes the final bulletproof strategy pick)",
        "",
        "Your task is to run a collective intelligence debate to select the single best options buying strategy for today based on the latest market data.",
        f"\n**Today's Market Conditions:** {', '.join(market_conditions)}",
        f"**Market Sentiment Bias:** {sentiment}",
    ]
    
    # Inject mock FII/DII flow data
    fii_dii_data = {"date": "20-May-2026", "fii_net": 1450.00, "dii_net": 820.00}
    if fii_dii_data:
        fii = fii_dii_data.get("fii_net", 0.0)
        dii = fii_dii_data.get("dii_net", 0.0)
        flow_date = fii_dii_data.get("date", "")
        prompt_sections.append(
            f"\n**Indian Institutional Flows (Date: {flow_date}):**\n"
            f"- FII Net Cash Flow: {fii:+,} Crores (INR)\n"
            f"- DII Net Cash Flow: {dii:+,} Crores (INR)\n"
            f"*(Note: Positive FII flow represents strong institutional buying support; negative FII flow signifies distribution/selling pressure).* "
        )
    
    if rag_context:
        prompt_sections.append(f"\n**RAG Context (Historical Performance):**\n{rag_context}")
    if user_prompt:
        prompt_sections.append(f"\n**User's Preference/Observation:** '{user_prompt}'")
        
    prompt_sections.append(
        "\n**Available Strategies (and their primary purpose):**\n"
        "1.  **'Gemini_Default'**: A balanced, multi-indicator strategy (CPR, EMA, RSI Divergence).\n"
        "2.  **'Supertrend_MACD'**: A strong trend-following strategy.\n"
        "3.  **'Volatility_Cluster_Reversal'**: A counter-trend strategy for high volatility.\n"
        "4.  **'Volume_Spread_Analysis'**: Detects smart money activity.\n"
        "5.  **'EMA_Cross_RSI'**: A classic, fast-acting momentum strategy.\n"
        "6.  **'Momentum_VWAP_RSI'**: A momentum strategy using VWAP + RSI confirmation.\n"
        "7.  **'Breakout_Prev_Day_HL'**: A breakout strategy on previous day's high/low.\n"
        "8.  **'Opening_Range_Breakout'**: A classic ORB strategy.\n"
        "9.  **'BB_Squeeze_Breakout'**: A volatility breakout strategy.\n"
        "10. **'MA_Crossover'**: A simple moving average crossover strategy.\n"
        "11. **'RSI_Divergence'**: A pure reversal strategy on RSI divergence.\n"
        "12. **'Reversal_Detector'**: A specialized reversal strategy for overextended trends.\n"
        "13. **'VWAP_Reversion'**: HIGH-FREQUENCY intraday VWAP-reclaim play.\n"
        "14. **'NR7_Compression'**: Compression-then-expansion breakout.\n"
        "15. **'Expiry_Momentum_Scalp'**: Weekly-expiry gamma scalp.\n"
    )
    
    prompt_sections.append(
        "\nRun the debate and provide your output in the following format:\n"
        "[Alpha Strategist's Pitch]: (Proposes a strategy from the list + rationale)\n"
        "[Risk Manager's Critique]: (Critiques the strategy, highlighting risks, VIX level, or overextensions)\n"
        "[Consensus Verdict]: (The final chosen strategy name, followed by a 1-sentence reasoning summary)\n"
        "\nAt the very end of your response, on a new line, print ONLY the final chosen strategy name (e.g., 'VWAP_Reversion' or 'CPR_Breakout') with no punctuation, quotes, or extra text."
    )
    
    prompt = "\n".join(prompt_sections)
    
    try:
        import ssl
        ssl_ctx = ssl._create_unverified_context()
        conn = aiohttp.TCPConnector(ssl=ssl_ctx)
        
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={gemini_key}"
        payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}

        print("Connecting to Google AI Studio and sending debate prompt...", flush=True)
        async with aiohttp.ClientSession(connector=conn) as session:
            async with session.post(api_url, json=payload) as response:
                response.raise_for_status()
                result = await response.json()

        full_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
        # print("\n--- DEBATE LOGS RECEIVED FROM gemini-3.1-pro-preview ---") # Old model print
        print("\n--- DEBATE LOGS RECEIVED FROM gemini-3.5-flash ---")
        print(full_text)
        print("-------------------------------------------------------\n")
        
        # Extract final strategy line
        final_line = full_text.split('\n')[-1].strip().replace("'", "").replace('"', "")
        print(f"🎯 EXTRACTED DYNAMIC DECISION: '{final_line}'", flush=True)
        
    except Exception as e:
        print(f"❌ Error calling Gemini API: {e}", flush=True)

if __name__ == "__main__":
    asyncio.run(test_consensus_agent())
