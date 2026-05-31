import os
import json
import logging
import datetime
import asyncio
from infra import state_path, safe_ltp, tick_round
from agents import _execute_order_sync, _cancel_order_sync, _wait_for_fill

STRANGLE_STATE_FILE = state_path("active_strangle.json")

class OptionSellingEngine:
    """
    Institutional-grade Multi-Leg Credit & Option Selling Engine.
    Supports:
      1. Intraday Strangle/Straddle (Dynamic / Sumeet Mongia two-phase).
      2. Iron Butterfly (ATM Short Straddle + OTM Long wings for risk definition).
      3. Bull Put Spread (OTM Credit Put Spread near support).
      4. Bear Call Spread (OTM Credit Call Spread near resistance).
      
    Risk Management:
      - Inherently risk-defined spread combined premium monitoring.
      - Targets 50% profit booking dynamically (squares off when combined premium drops by 50%).
      - Combined stop loss monitor: stops out if combined premium increases past configured threshold.
    """

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.kite = orchestrator.kite
        self.config = orchestrator.config
        self.flags = orchestrator.config["trading_flags"]
        
        # Read configurations
        self.os_config = orchestrator.config.get("option_selling", {}) or {}
        self.mode = self.os_config.get("mode", "strangle") # "strangle", "straddle", "iron_butterfly", "bull_put_spread", "bear_call_spread"
        self.entry_time_str = self.os_config.get("entry_time", "09:20:00")
        self.exit_time_str = self.os_config.get("exit_time", "15:15:00")
        self.sl_multiplier = float(self.os_config.get("sl_multiplier", 1.25))
        self.strike_offset_steps = int(self.os_config.get("strike_offset_steps", 2))
        self.hedge_offset_steps = int(self.os_config.get("hedge_offset_steps", 10))
        self.use_double_phase = bool(self.os_config.get("use_sumeet_mongia_double_phase", False))

        self.state = self._load_state()
        
    def _load_state(self) -> dict:
        if os.path.exists(STRANGLE_STATE_FILE):
            try:
                with open(STRANGLE_STATE_FILE, "r") as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"[OptionSelling] Failed to read strangle state file: {e}")
        return {}

    def _save_state(self):
        try:
            with open(STRANGLE_STATE_FILE, "w") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logging.error(f"[OptionSelling] Failed to write strangle state file: {e}")

    def _clear_state(self):
        self.state = {}
        if os.path.exists(STRANGLE_STATE_FILE):
            try:
                os.remove(STRANGLE_STATE_FILE)
            except Exception as e:
                logging.error(f"[OptionSelling] Failed to delete strangle state file: {e}")

    def _get_nearest_expiry(self) -> datetime.date:
        today = datetime.date.today()
        nfo = self.orchestrator.order_agent.nfo_instruments
        mask = (nfo["instrument_type"].isin(["CE", "PE"])) & (nfo["expiry_date"] >= today)
        expirys = nfo[mask]["expiry_date"].unique()
        if len(expirys) == 0:
            raise ValueError("No active Nifty option expiries found in instruments list.")
        return min(expirys)

    def _resolve_symbol(self, strike: float, option_type: str, expiry: datetime.date) -> str:
        nfo = self.orchestrator.order_agent.nfo_instruments
        match = nfo[
            (nfo["strike"] == strike) & 
            (nfo["instrument_type"] == option_type) & 
            (nfo["expiry_date"] == expiry)
        ]
        if match.empty:
            raise ValueError(f"No Nifty option contract found for strike {strike}, type {option_type}, expiry {expiry}")
        return str(match.iloc[0]["tradingsymbol"])

    def _get_lot_size(self, symbol: str) -> int:
        nfo = self.orchestrator.order_agent.nfo_instruments
        match = nfo[nfo["tradingsymbol"] == symbol]
        if match.empty:
            return 75
        return int(match.iloc[0].get("lot_size", 75))

    def _parse_hhmm(self, t_str: str) -> datetime.time:
        try:
            parts = [int(x) for x in t_str.split(":")]
            if len(parts) == 2:
                return datetime.time(parts[0], parts[1])
            elif len(parts) == 3:
                return datetime.time(parts[0], parts[1], parts[2])
        except Exception:
            pass
        return datetime.time(9, 20)

    async def run_step(self, is_paper: bool = False):
        """Main execution cycle called by orchestrator loop."""
        if not self.orchestrator.is_market_open():
            return

        now = datetime.datetime.now().time()
        strategy_name = self.orchestrator.active_strategy_name

        # Double-Phase Sumeet Mongia Strategy override
        if strategy_name == "Intraday_Option_Selling" and self.use_double_phase:
            await self._run_sumeet_double_phase(now, is_paper)
            return

        # Dynamic Single-Phase Credit Spread / strangle / straddle execution
        entry_time = self._parse_hhmm(self.entry_time_str)
        exit_time = self._parse_hhmm(self.exit_time_str)

        # Determine strategy mode dynamically from orchestrator strategy name
        current_mode = self.mode
        if strategy_name == "Bull_Put_Spread":
            current_mode = "bull_put_spread"
        elif strategy_name == "Bear_Call_Spread":
            current_mode = "bear_call_spread"
        elif strategy_name == "Iron_Butterfly":
            current_mode = "iron_butterfly"
        elif strategy_name == "Intraday_Option_Selling":
            current_mode = self.mode # defaults to strangle/straddle config

        if not self.state:
            # Entry Trigger
            if now >= entry_time and now < exit_time:
                today_str = datetime.date.today().isoformat()
                if not self.orchestrator.config.get("_single_strangle_done_today") == today_str:
                    logging.info(f"[OptionSelling] Initiating Single-Phase {current_mode.upper()}...")
                    await self._enter_position(mode=current_mode, is_paper=is_paper)
        else:
            # Active Monitoring loop: Combined premium & target profits
            await self._monitor_spread_premium(now, exit_time, is_paper)

    async def _run_sumeet_double_phase(self, now, is_paper: bool):
        """Executes the 2-phase Sumeet Mongia strategy."""
        if not self.state:
            if datetime.time(9, 16) <= now < datetime.time(14, 15):
                today_str = datetime.date.today().isoformat()
                if not self.orchestrator.config.get("_strangle_morning_done_today") == today_str:
                    logging.info("[OptionSelling] Initiating Masterclass Phase 1: Morning OTM-2 Strangle...")
                    await self._enter_position(mode="strangle", is_paper=is_paper, phase="morning")
            
            elif datetime.time(14, 16) <= now < datetime.time(15, 27):
                today_str = datetime.date.today().isoformat()
                if not self.orchestrator.config.get("_strangle_afternoon_done_today") == today_str:
                    logging.info("[OptionSelling] Initiating Masterclass Phase 2: Afternoon ATM Straddle...")
                    await self._enter_position(mode="straddle", is_paper=is_paper, phase="afternoon")
        else:
            await self._monitor_active_sumeet_strangle(now, is_paper)

    async def _enter_position(self, mode: str, is_paper: bool, phase: str = "single"):
        """Enters credit spreads, strangle, or iron butterfly multi-leg setups."""
        try:
            expiry = self._get_nearest_expiry()
            
            # Fetch underlying dynamically based on config
            underlying_name = self.flags.get("underlying_instrument", "NIFTY 50")
            spot_data = await asyncio.to_thread(self.kite.ltp, f"NSE:{underlying_name}")
            spot = float((spot_data or {}).get(f"NSE:{underlying_name}", {}).get("last_price", 0))
            if spot <= 0:
                logging.error("[OptionSelling] Spot LTP unavailable.")
                return

            # Fetch dynamic step size (50 for Nifty, 100 for BankNifty)
            step = float(self.orchestrator.order_agent._strike_step())
            atm_strike = round(spot / step) * step
            dte = (expiry - datetime.date.today()).days

            # Fetch India VIX dynamically to calculate standard-deviation expected move
            vix_data = await asyncio.to_thread(self.kite.ltp, "NSE:INDIA VIX")
            vix = float((vix_data or {}).get("NSE:INDIA VIX", {}).get("last_price", 15.0))

            # Calculate 1-day expected move using 252 trading days (safer quant buffer)
            import math
            expected_move = spot * (vix / 100.0) * math.sqrt(1.0 / 252.0)
            dynamic_offset_steps = max(2, math.ceil(expected_move / step))

            current_offset = dynamic_offset_steps
            current_sl_multiplier = self.sl_multiplier
            
            # Dynamic adjustment under rapid volatility expansion (VIX_SPIKE_VELOCITY +1 step!)
            if 'VIX_SPIKE_VELOCITY' in self.orchestrator.todays_conditions:
                current_offset += 1
                logging.info(f"[OptionSelling] VIX_SPIKE_VELOCITY detected! Expanding offset steps to {current_offset} | SL remains at {current_sl_multiplier}")
            else:
                logging.info(f"[OptionSelling] Dynamic VIX Expected Move: {expected_move:.2f} pts | Starting Offset steps: {current_offset}")

            # Widen the stop loss on 0-DTE to account for violent Gamma swings
            if dte == 0:
                base_sl_mult = current_sl_multiplier * 1.5 
                logging.info(f"[OptionSelling] 0-DTE Expiry Day detected. Widening base SL multiplier to {base_sl_mult}")
            else:
                base_sl_mult = current_sl_multiplier

            sl_mult = base_sl_mult if phase == "single" else (base_sl_mult * 1.20)

            ce_symbol = pe_symbol = ce_hedge_symbol = pe_hedge_symbol = None
            call_strike = put_strike = call_hedge_strike = put_hedge_strike = None

            # Strike construction mapping
            if mode == "strangle":
                offset = current_offset if phase == "single" else 2
                call_strike = atm_strike + (offset * step)
                put_strike = atm_strike - (offset * step)
                call_hedge_strike = atm_strike + (self.hedge_offset_steps * step)
                put_hedge_strike = atm_strike - (self.hedge_offset_steps * step)
                
            elif mode == "straddle":
                call_strike = atm_strike
                put_strike = atm_strike
                call_hedge_strike = atm_strike + (self.hedge_offset_steps * step)
                put_hedge_strike = atm_strike - (self.hedge_offset_steps * step)
                
            elif mode == "iron_butterfly":
                # Short ATM body
                call_strike = atm_strike
                put_strike = atm_strike
                # Long OTM wings (wing width config, e.g. 200 or 500 points)
                call_hedge_strike = atm_strike + (current_offset * step) # wing CE
                put_hedge_strike = atm_strike - (current_offset * step)  # wing PE

            elif mode == "bull_put_spread":
                # Sell Put close OTM near support, Buy lower OTM Put
                put_strike = atm_strike - (current_offset * step)
                put_hedge_strike = atm_strike - ((current_offset + 2) * step)
                
            elif mode == "bear_call_spread":
                # Sell Call close OTM near resistance, Buy higher OTM Call
                call_strike = atm_strike + (current_offset * step)
                call_hedge_strike = atm_strike + ((current_offset + 2) * step)

            # Resolve active contracts symbols
            if call_strike: ce_symbol = self._resolve_symbol(call_strike, "CE", expiry)
            if put_strike:  pe_symbol = self._resolve_symbol(put_strike, "PE", expiry)
            if call_hedge_strike: ce_hedge_symbol = self._resolve_symbol(call_hedge_strike, "CE", expiry)
            if put_hedge_strike:  pe_hedge_symbol = self._resolve_symbol(put_hedge_strike, "PE", expiry)

            # Sizing FIX: Respect the risk_per_trade_percent from config
            cap = self.orchestrator.starting_capital or 100000.0
            risk_pct = float(self.flags.get("_effective_risk_pct") or self.flags.get("risk_per_trade_percent", 25.0))
            allocated_capital = cap * (risk_pct / 100.0)
            
            # Approximate margin requirement per hedged lot is ~50k
            lots = max(1, int(allocated_capital // 50000))
            ref_sym = ce_symbol or pe_symbol
            lot_size = self._get_lot_size(ref_sym)
            qty = lots * lot_size

            logging.info(
                f"[OptionSelling] Enlisting {mode.upper()} portfolio strikes (phase={phase}):\n"
                f"  Spot: {spot:.2f} | Expiry: {expiry}\n"
                f"  Short CE: {ce_symbol} | Short PE: {pe_symbol}\n"
                f"  Long CE : {ce_hedge_symbol} | Long PE : {pe_hedge_symbol}\n"
                f"  Lots    : {lots} | Qty: {qty}"
            )

            # 1. Buy protection legs first (margin unlocking)
            ce_hedge_fill = pe_hedge_fill = 0.0
            if ce_hedge_symbol: ce_hedge_fill = await self._execute_leg(ce_hedge_symbol, qty, "BUY", is_paper)
            if pe_hedge_symbol: pe_hedge_fill = await self._execute_leg(pe_hedge_symbol, qty, "BUY", is_paper)

            # 2. Sell credit premium legs
            ce_short_fill = pe_short_fill = 0.0
            if ce_symbol: ce_short_fill = await self._execute_leg(ce_symbol, qty, "SELL", is_paper)
            if pe_symbol:  pe_short_fill = await self._execute_leg(pe_symbol, qty, "SELL", is_paper)

            # STRICT ROLLBACK: Verify no intended legs failed
            failed_legs = []
            if ce_symbol and ce_short_fill <= 0: failed_legs.append("CE_SHORT")
            if pe_symbol and pe_short_fill <= 0: failed_legs.append("PE_SHORT")
            if ce_hedge_symbol and ce_hedge_fill <= 0: failed_legs.append("CE_HEDGE")
            if pe_hedge_symbol and pe_hedge_fill <= 0: failed_legs.append("PE_HEDGE")

            if failed_legs:
                logging.error(f"[OptionSelling] Execution failure on legs: {failed_legs}. Executing IMMEDIATE ROLLBACK to prevent skewed portfolio.")
                # Rollback any legs that DID fill successfully
                if ce_short_fill > 0: await self._execute_leg(ce_symbol, qty, "BUY", is_paper)
                if pe_short_fill > 0: await self._execute_leg(pe_symbol, qty, "BUY", is_paper)
                if ce_hedge_fill > 0: await self._execute_leg(ce_hedge_symbol, qty, "SELL", is_paper)
                if pe_hedge_fill > 0: await self._execute_leg(pe_hedge_symbol, qty, "SELL", is_paper)
                return

            # Calculate net credit premium received upfront
            short_premium = (ce_short_fill if ce_symbol else 0.0) + (pe_short_fill if pe_symbol else 0.0)
            long_premium = (ce_hedge_fill if ce_hedge_symbol else 0.0) + (pe_hedge_fill if pe_hedge_symbol else 0.0)
            net_credit = short_premium - long_premium

            if net_credit <= 0:
                logging.error("[OptionSelling] Execution failed or negative net premium received. Aborting spread.")
                # Cleanup
                if ce_hedge_symbol: await self._execute_leg(ce_hedge_symbol, qty, "SELL", is_paper)
                if pe_hedge_symbol: await self._execute_leg(pe_hedge_symbol, qty, "SELL", is_paper)
                return

            # Calculate Stop Loss target (e.g., combined value increase or individual trigger)
            ce_sl_trigger = ce_short_fill * sl_mult if ce_symbol else None
            pe_sl_trigger = pe_short_fill * sl_mult if pe_symbol else None

            # Place broker SL orders (only for Strangles / Straddles which check individual legs)
            ce_sl_order_id = pe_sl_order_id = None
            if not is_paper and mode in ("strangle", "straddle"):
                if ce_symbol: ce_sl_order_id = await self._place_broker_buy_sl(ce_symbol, qty, ce_sl_trigger)
                if pe_symbol: pe_sl_order_id = await self._place_broker_buy_sl(pe_symbol, qty, pe_sl_trigger)

            self.state = {
                "mode": mode,
                "phase": phase,
                "expiry_date": expiry.isoformat(),
                "quantity": qty,
                "lot_size": lot_size,
                "entered_at": datetime.datetime.now().isoformat(),
                "is_paper": is_paper,
                "net_credit_received": net_credit,
                "sl_multiplier": sl_mult,
                "call_leg": {
                    "symbol": ce_symbol,
                    "entry_price": ce_short_fill,
                    "sl_trigger_price": ce_sl_trigger,
                    "sl_order_id": ce_sl_order_id,
                    "status": "OPEN" if ce_symbol else "NONE"
                } if ce_symbol else None,
                "put_leg": {
                    "symbol": pe_symbol,
                    "entry_price": pe_short_fill,
                    "sl_trigger_price": pe_sl_trigger,
                    "sl_order_id": pe_sl_order_id,
                    "status": "OPEN" if pe_symbol else "NONE"
                } if pe_symbol else None,
                "call_hedge": {
                    "symbol": ce_hedge_symbol,
                    "entry_price": ce_hedge_fill,
                    "status": "OPEN" if ce_hedge_symbol else "NONE"
                } if ce_hedge_symbol else None,
                "put_hedge": {
                    "symbol": pe_hedge_symbol,
                    "entry_price": pe_hedge_fill,
                    "status": "OPEN" if pe_hedge_symbol else "NONE"
                } if pe_hedge_symbol else None
            }
            self._save_state()

            self.orchestrator._print_event([
                f"Credit Spread Position Entered ({mode.upper()})",
                f"  Net Credit Received: ₹{net_credit:.2f} per lot",
                f"  Short CE: {ce_symbol or 'N/A'} | Short PE: {pe_symbol or 'N/A'}",
                f"  Long CE : {ce_hedge_symbol or 'N/A'} | Long PE : {pe_hedge_symbol or 'N/A'}",
                f"  Lots    : {lots} | Risk Model: {phase.upper()}"
            ], level="trade")

            self.orchestrator.bot_state = "IN_POSITION"

        except Exception as e:
            logging.error(f"[OptionSelling] Position entry failed: {e}", exc_info=True)

    async def _execute_leg(self, symbol: str, qty: int, transaction_type: str, is_paper: bool) -> float:
        ltp = safe_ltp(self.kite, f"NFO:{symbol}")
        if ltp is None or ltp <= 0:
            return 0.0
        if is_paper: return float(ltp)

        api_key = self.config["zerodha"]["api_key"]
        access_tok = self.config["zerodha"]["access_token"]
        slip = float(self.flags.get("limit_order_slippage_percent", 0.5)) / 100.0
        
        limit_price = tick_round(ltp * (1 + slip) if transaction_type == "BUY" else ltp * (1 - slip), 0.05)

        params = {
            "variety": self.flags["order_variety"],
            "exchange": self.kite.EXCHANGE_NFO,
            "tradingsymbol": symbol,
            "transaction_type": transaction_type,
            "quantity": qty,
            "product": self.flags["product_type"],
            "order_type": self.kite.ORDER_TYPE_LIMIT,
            "price": limit_price,
        }

        oid = await asyncio.to_thread(_execute_order_sync, api_key, access_tok, params)
        if not oid: return 0.0

        timeout = int(self.flags.get("order_fill_timeout_seconds", 30))
        status, avg, _ = await _wait_for_fill(api_key, access_tok, oid, timeout)
        if status == "COMPLETE" and avg > 0:
            return float(avg)

        # Cancel and MARKET-with-Protection fallback
        await asyncio.to_thread(_cancel_order_sync, api_key, access_tok, self.flags["order_variety"], oid)
        params.pop("price", None)
        params["order_type"] = self.kite.ORDER_TYPE_MARKET
        params["market_protection"] = self.os_config.get("market_protection", -1)
        mkt_id = await asyncio.to_thread(_execute_order_sync, api_key, access_tok, params)
        if mkt_id:
            s2, avg2, _ = await _wait_for_fill(api_key, access_tok, mkt_id, timeout)
            if s2 == "COMPLETE" and avg2 > 0:
                return float(avg2)

        return 0.0

    async def _place_broker_buy_sl(self, symbol: str, qty: int, trigger_price: float) -> str:
        # For options SELLING, SL is a BUY order. Limit price must be HIGHER than trigger to execute safely.
        limit_price = round((trigger_price * 1.05) / 0.05) * 0.05
        params = {
            "variety": self.flags["order_variety"],
            "exchange": self.kite.EXCHANGE_NFO,
            "tradingsymbol": symbol,
            "transaction_type": self.kite.TRANSACTION_TYPE_BUY,
            "quantity": qty,
            "product": self.flags["product_type"],
            "order_type": self.kite.ORDER_TYPE_SL,
            "trigger_price": trigger_price,
            "price": limit_price,
        }
        api_key = self.config["zerodha"]["api_key"]
        access_tok = self.config["zerodha"]["access_token"]
        return await asyncio.to_thread(_execute_order_sync, api_key, access_tok, params)

    async def _monitor_spread_premium(self, now, exit_time, is_paper: bool):
        """Monitors combined liquidation premium values using real-time market depth."""
        mode = self.state["mode"]
        qty = self.state["quantity"]
        net_credit = self.state["net_credit_received"]

        symbols_to_fetch = []
        ce_sym = pe_sym = ce_hedge_sym = pe_hedge_sym = None

        if self.state.get("call_leg") and self.state["call_leg"]["status"] == "OPEN":
            ce_sym = self.state['call_leg']['symbol']
            symbols_to_fetch.append(f"NFO:{ce_sym}")
        if self.state.get("put_leg") and self.state["put_leg"]["status"] == "OPEN":
            pe_sym = self.state['put_leg']['symbol']
            symbols_to_fetch.append(f"NFO:{pe_sym}")
        if self.state.get("call_hedge") and self.state["call_hedge"]["status"] == "OPEN":
            ce_hedge_sym = self.state['call_hedge']['symbol']
            symbols_to_fetch.append(f"NFO:{ce_hedge_sym}")
        if self.state.get("put_hedge") and self.state["put_hedge"]["status"] == "OPEN":
            pe_hedge_sym = self.state['put_hedge']['symbol']
            symbols_to_fetch.append(f"NFO:{pe_hedge_sym}")

        current_value = 0.0

        if symbols_to_fetch:
            try:
                # Use quote to extract full market depth instead of static last traded prices
                quote_dict = await asyncio.to_thread(self.kite.quote, symbols_to_fetch)
                
                # To exit a Short option contract, you must buy it back at the prevailing ASK price
                if ce_sym and f"NFO:{ce_sym}" in quote_dict:
                    ce_quote = quote_dict[f"NFO:{ce_sym}"]
                    sell_depth = ce_quote.get("depth", {}).get("sell") or [{}]
                    ce_ask = float(sell_depth[0].get("price", 0.0))
                    # Fallback to LTP if orderbook is completely empty at this millisecond
                    if ce_ask <= 0.0: ce_ask = float(ce_quote.get("last_price", 0.0))
                    current_value += ce_ask
                    
                if pe_sym and f"NFO:{pe_sym}" in quote_dict:
                    pe_quote = quote_dict[f"NFO:{pe_sym}"]
                    sell_depth = pe_quote.get("depth", {}).get("sell") or [{}]
                    pe_ask = float(sell_depth[0].get("price", 0.0))
                    if pe_ask <= 0.0: pe_ask = float(pe_quote.get("last_price", 0.0))
                    current_value += pe_ask
                    
                # To exit a Long option contract, you must sell it back at the prevailing BID price
                if ce_hedge_sym and f"NFO:{ce_hedge_sym}" in quote_dict:
                    ce_h_quote = quote_dict[f"NFO:{ce_hedge_sym}"]
                    buy_depth = ce_h_quote.get("depth", {}).get("buy") or [{}]
                    ce_h_bid = float(buy_depth[0].get("price", 0.0))
                    if ce_h_bid <= 0.0: ce_h_bid = float(ce_h_quote.get("last_price", 0.0))
                    current_value -= ce_h_bid
                    
                if pe_hedge_sym and f"NFO:{pe_hedge_sym}" in quote_dict:
                    pe_h_quote = quote_dict[f"NFO:{pe_hedge_sym}"]
                    buy_depth = pe_h_quote.get("depth", {}).get("buy") or [{}]
                    pe_h_bid = float(buy_depth[0].get("price", 0.0))
                    if pe_h_bid <= 0.0: pe_h_bid = float(pe_h_quote.get("last_price", 0.0))
                    current_value -= pe_h_bid

            except Exception as e:
                logging.warning(f"[OptionSelling] Batched market depth quote fetch failed: {e}")
                return # Skip this iteration to prevent garbage collections from triggering stops

        # 1. Target Profit booking (50% premium drop target)
        # If entry premium was ₹100 and now is at or below ₹50, we book ₹50 profit!
        if current_value <= 0.5 * net_credit:
            logging.info(f"[OptionSelling] Combined premium profit target hit! Value ₹{current_value:.2f} <= 50% of Credit ₹{net_credit:.2f}. Booking profit.")
            self.orchestrator.log_activity(f"🎯 Target hit! Premium value ₹{current_value:.2f} <= 50% of credit ₹{net_credit:.2f}.")
            await self._exit_strangle_fully(is_paper=is_paper, reason="PROFIT_TARGET_HIT")
            self.orchestrator.config["_single_strangle_done_today"] = datetime.date.today().isoformat()
            self._clear_state()
            self.orchestrator.bot_state = "AWAITing_SIGNAL"
            return

        # 2. Combined Stop Loss Check (e.g. risk limit breached)
        # If current value rises above the sl_multiplier * net_credit (e.g. 1.5x credit = 50% loss)
        sl_trigger = net_credit * self.sl_multiplier
        if current_value >= sl_trigger:
            logging.warning(f"[OptionSelling] Combined credit spread Stop Loss breached! Value ₹{current_value:.2f} >= Trigger ₹{sl_trigger:.2f}. Squaring off entire position.")
            self.orchestrator.log_activity(f"🚨 Combined credit SL hit! Value ₹{current_value:.2f} >= Trigger ₹{sl_trigger:.2f}.")
            await self._exit_strangle_fully(is_paper=is_paper, reason="COMBINED_STOP_LOSS_BREACHED")
            self.orchestrator.config["_single_strangle_done_today"] = datetime.date.today().isoformat()
            self._clear_state()
            self.orchestrator.bot_state = "AWAITING_SIGNAL"
            return

        # 3. Time-based Exit
        if now >= exit_time:
            logging.info(f"[OptionSelling] Time is past exit_time {self.exit_time_str}. Exiting credit spreads...")
            self.orchestrator.log_activity(f"⏳ Time cutoff reached. Exiting option selling portfolio.")
            await self._exit_strangle_fully(is_paper=is_paper, reason="TIME_CUTOFF")
            self.orchestrator.config["_single_strangle_done_today"] = datetime.date.today().isoformat()
            self._clear_state()
            self.orchestrator._send_shutdown_report_once()
            self.orchestrator.bot_state = "STOPPED"

    async def _monitor_active_sumeet_strangle(self, now, is_paper: bool):
        """Stop loss checks for naked legs in Sumeet Mongia's Strategy."""
        qty = self.state["quantity"]
        phase = self.state["phase"]
        
        ce_symbol = self.state["call_leg"]["symbol"]
        pe_symbol = self.state["put_leg"]["symbol"]
        ce_ltp = safe_ltp(self.kite, f"NFO:{ce_symbol}") or 0.0
        pe_ltp = safe_ltp(self.kite, f"NFO:{pe_symbol}") or 0.0

        if self.state["call_leg"]["status"] == "OPEN" and ce_ltp > 0:
            sl_trig = self.state["call_leg"]["sl_trigger_price"]
            if ce_ltp >= sl_trig:
                logging.warning(f"[OptionSelling] Call SL hit: {ce_ltp:.2f} >= {sl_trig:.2f}")
                await self._exit_leg_on_sl("call_leg", ce_symbol, qty, is_paper)

        if self.state["put_leg"]["status"] == "OPEN" and pe_ltp > 0:
            sl_trig = self.state["put_leg"]["sl_trigger_price"]
            if pe_ltp >= sl_trig:
                logging.warning(f"[OptionSelling] Put SL hit: {pe_ltp:.2f} >= {sl_trig:.2f}")
                await self._exit_leg_on_sl("put_leg", pe_symbol, qty, is_paper)

        if phase == "morning" and now >= datetime.time(14, 15):
            await self._exit_strangle_fully(is_paper=is_paper, reason="TIME_CUTOFF")
            self.orchestrator.config["_strangle_morning_done_today"] = datetime.date.today().isoformat()
            self._clear_state()
            self.orchestrator.bot_state = "AWAITING_SIGNAL"
            self.orchestrator.awaiting_signal_since = datetime.datetime.now()
            
        elif phase == "afternoon" and now >= datetime.time(15, 28):
            await self._exit_strangle_fully(is_paper=is_paper, reason="TIME_CUTOFF")
            self.orchestrator.config["_strangle_afternoon_done_today"] = datetime.date.today().isoformat()
            self._clear_state()
            self.orchestrator._send_shutdown_report_once()
            self.orchestrator.bot_state = "STOPPED"

    async def _exit_leg_on_sl(self, leg_key: str, symbol: str, qty: int, is_paper: bool):
        leg = self.state[leg_key]
        if not is_paper and leg.get("sl_order_id"):
            await asyncio.to_thread(
                _cancel_order_sync, 
                self.config["zerodha"]["api_key"], 
                self.config["zerodha"]["access_token"], 
                self.flags["order_variety"], 
                leg["sl_order_id"]
            )

        ltp = safe_ltp(self.kite, f"NFO:{symbol}") or leg["sl_trigger_price"]
        exit_px = await self._execute_leg(symbol, qty, "BUY", is_paper)
        if exit_px <= 0: exit_px = float(ltp)

        leg["status"] = "CLOSED"
        leg["exit_price"] = exit_px
        leg["exit_time"] = datetime.datetime.now().isoformat()
        self._save_state()

        pnl = (leg["entry_price"] - exit_px) * qty
        self.orchestrator.realized_pnl_today += pnl
        self.orchestrator.realized_pnl_week += pnl
        
        from infra import save_daily_pnl, save_weekly_pnl
        save_daily_pnl(datetime.date.today().isoformat(), self.orchestrator.realized_pnl_today)
        save_weekly_pnl(datetime.date.today().strftime("%G-W%V"), self.orchestrator.realized_pnl_week)

        self.orchestrator._print_event([
            f"Credit Spread Leg Stopped Out",
            f"  Symbol: {symbol} | Realized P&L: ₹{pnl:+.2f}"
        ], level="warn")

    async def _exit_strangle_fully(self, is_paper: bool, reason: str = "TIME_CUTOFF"):
        """Fully closes all remaining open legs of the credit spread portfolio."""
        qty = self.state["quantity"]
        total_pnl = 0.0

        # 1. Close Short Call CE leg
        if self.state.get("call_leg") and self.state["call_leg"]["status"] == "OPEN":
            symbol = self.state["call_leg"]["symbol"]
            if not is_paper and self.state["call_leg"].get("sl_order_id"):
                await asyncio.to_thread(_cancel_order_sync, self.config["zerodha"]["api_key"], self.config["zerodha"]["access_token"], self.flags["order_variety"], self.state["call_leg"]["sl_order_id"])
            
            ltp = safe_ltp(self.kite, f"NFO:{symbol}") or 0.0
            exit_px = await self._execute_leg(symbol, qty, "BUY", is_paper)
            if exit_px <= 0: exit_px = float(ltp)
            
            self.state["call_leg"]["status"] = "CLOSED"
            pnl = (self.state["call_leg"]["entry_price"] - exit_px) * qty
            total_pnl += pnl

        # 2. Close Short Put PE leg
        if self.state.get("put_leg") and self.state["put_leg"]["status"] == "OPEN":
            symbol = self.state["put_leg"]["symbol"]
            if not is_paper and self.state["put_leg"].get("sl_order_id"):
                await asyncio.to_thread(_cancel_order_sync, self.config["zerodha"]["api_key"], self.config["zerodha"]["access_token"], self.flags["order_variety"], self.state["put_leg"]["sl_order_id"])
            
            ltp = safe_ltp(self.kite, f"NFO:{symbol}") or 0.0
            exit_px = await self._execute_leg(symbol, qty, "BUY", is_paper)
            if exit_px <= 0: exit_px = float(ltp)
            
            self.state["put_leg"]["status"] = "CLOSED"
            pnl = (self.state["put_leg"]["entry_price"] - exit_px) * qty
            total_pnl += pnl

        # 3. Close Call Protection leg (SELL back)
        if self.state.get("call_hedge") and self.state["call_hedge"]["status"] == "OPEN":
            symbol = self.state["call_hedge"]["symbol"]
            ltp = safe_ltp(self.kite, f"NFO:{symbol}") or 0.0
            exit_px = await self._execute_leg(symbol, qty, "SELL", is_paper)
            if exit_px <= 0: exit_px = float(ltp)
            
            self.state["call_hedge"]["status"] = "CLOSED"
            pnl = (exit_px - self.state["call_hedge"]["entry_price"]) * qty
            total_pnl += pnl

        # 4. Close Put Protection leg (SELL back)
        if self.state.get("put_hedge") and self.state["put_hedge"]["status"] == "OPEN":
            symbol = self.state["put_hedge"]["symbol"]
            ltp = safe_ltp(self.kite, f"NFO:{symbol}") or 0.0
            exit_px = await self._execute_leg(symbol, qty, "SELL", is_paper)
            if exit_px <= 0: exit_px = float(ltp)
            
            self.state["put_hedge"]["status"] = "CLOSED"
            pnl = (exit_px - self.state["put_hedge"]["entry_price"]) * qty
            total_pnl += pnl

        # Save realized P&Ls
        self.orchestrator.realized_pnl_today += total_pnl
        self.orchestrator.realized_pnl_week += total_pnl
        
        from infra import save_daily_pnl, save_weekly_pnl
        save_daily_pnl(datetime.date.today().isoformat(), self.orchestrator.realized_pnl_today)
        save_weekly_pnl(datetime.date.today().strftime("%G-W%V"), self.orchestrator.realized_pnl_week)

        self.orchestrator._print_event([
            f"Position Exited completely ({reason})",
            f"  Realized session P&L: ₹{total_pnl:+,.2f}",
            f"  New total daily P&L: ₹{self.orchestrator.realized_pnl_today:+,.2f}"
        ], level="trade")
