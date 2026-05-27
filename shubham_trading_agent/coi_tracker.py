import asyncio
import datetime
import logging
import pandas as pd

class IntradayCOITracker:
    """
    Tracks Change in Open Interest (COI) velocity across Nifty ATM Option Chains.
    Measures the shifting speed of institutional writing layer-by-layer.
    """
    def __init__(self, orchestrator, strikes_each_side: int = 3):
        self.orchestrator = orchestrator
        self.kite = orchestrator.kite
        self.strikes_each_side = strikes_each_side
        # In-memory memory bank tracking the previous iteration's exact snapshot
        self.previous_oi_snapshot = {} # Maps: symbol -> open_interest_integer
        self.last_checked_bar_time = None

    async def evaluate_coi_velocity(self, current_spot: float, current_bar_timestamp) -> dict:
        """
        Evaluates shifting open interest boundaries.
        Returns a dictionary mapping absolute net contract changes and bias metrics.
        """
        # Dedup check: Ensure we only compute once per closed bar boundary
        if self.last_checked_bar_time == current_bar_timestamp:
            return {"status": "SKIPPED_SAME_BAR", "call_coi_velocity": 0, "put_coi_velocity": 0, "coi_bias": "NEUTRAL"}
            
        try:
            # Resolve nearest expiration options via orchestrator df references
            if self.orchestrator is None or not hasattr(self.orchestrator.order_agent, "nfo_instruments"):
                return {"status": "ERROR_NO_METADATA", "call_coi_velocity": 0, "put_coi_velocity": 0, "coi_bias": "NEUTRAL"}
                
            nfo = self.orchestrator.order_agent.nfo_instruments
            today = datetime.date.today()
            
            # Extract nearest option chain slice
            valid_expiries = sorted(nfo[nfo["expiry_date"] >= today]["expiry_date"].unique())
            if not valid_expiries:
                return {"status": "ERROR_NO_EXPIRY", "call_coi_velocity": 0, "put_coi_velocity": 0, "coi_bias": "NEUTRAL"}
            nearest_expiry = valid_expiries[0]

            # Dynamic ATM Strike Envelope Rounding
            step = float(self.orchestrator.order_agent._strike_step())
            atm_strike = round(current_spot / step) * step
            lower_bound = atm_strike - (self.strikes_each_side * step)
            upper_bound = atm_strike + (self.strikes_each_side * step)

            chain_slice = nfo[
                (nfo["name"] == "NIFTY") & 
                (nfo["strike"] >= lower_bound) & 
                (nfo["strike"] <= upper_bound) & 
                (nfo["expiry_date"] == nearest_expiry)
            ]

            if chain_slice.empty:
                return {"status": "ERROR_EMPTY_SLICE", "call_coi_velocity": 0, "put_coi_velocity": 0, "coi_bias": "NEUTRAL"}

            symbols_to_fetch = [f"NFO:{sym}" for sym in chain_slice["tradingsymbol"].tolist()]
            
            # Fetch active contracts snapshots from Zerodha
            quotes = await asyncio.to_thread(self.kite.quote, symbols_to_fetch)
            if not quotes:
                return {"status": "ERROR_QUOTE_FETCH_FAILED", "call_coi_velocity": 0, "put_coi_velocity": 0, "coi_bias": "NEUTRAL"}

            current_snapshot = {}
            net_call_coi = 0
            net_put_coi = 0

            # Loop through instruments and map current contract changes vs memory bank
            for _, row in chain_slice.iterrows():
                symbol = row["tradingsymbol"]
                opt_type = row["instrument_type"] # "CE" or "PE"
                key = f"NFO:{symbol}"
                
                if key in quotes:
                    current_oi = int(quotes[key].get("oi", 0))
                    current_snapshot[symbol] = current_oi
                    
                    # If memory bank holds previous data for this strike, track the change
                    if symbol in self.previous_oi_snapshot:
                        previous_oi = self.previous_oi_snapshot[symbol]
                        change_in_oi = current_oi - previous_oi
                        
                        if opt_type == "CE":
                            net_call_coi += change_in_oi
                        elif opt_type == "PE":
                            net_put_coi += change_in_oi

            # Update memory states for the next bar evaluation pass
            self.previous_oi_snapshot = current_snapshot
            self.last_checked_bar_time = current_bar_timestamp

            # Determine dynamic context tracking bias
            # Excessive Call writing signifies deep resistance loading (Intraday Bearish)
            # Excessive Put writing signifies intense support formatting (Intraday Bullish)
            coi_bias = "NEUTRAL"
            if net_call_coi > 0 or net_put_coi > 0:
                if net_call_coi > net_put_coi * 1.5:
                    coi_bias = "INSTITUTIONAL_BEARISH_RESISTANCE_LOADING"
                elif net_put_coi > net_call_coi * 1.5:
                    coi_bias = "INSTITUTIONAL_BULLISH_SUPPORT_BUILDUP"

            logging.info(
                f"[COI Tracker] Change in OI Velocity Evaluated — "
                f"Call COI: {net_call_coi:+,} | Put COI: {net_put_coi:+,} | Bias: {coi_bias}"
            )

            return {
                "status": "SUCCESS",
                "call_coi_velocity": net_call_coi,
                "put_coi_velocity": net_put_coi,
                "coi_bias": coi_bias
            }

        except Exception as e:
            logging.error(f"[COI Tracker] System exception inside momentum loops: {e}", exc_info=True)
            return {"status": "EXCEPTION_TRIGGERED", "call_coi_velocity": 0, "put_coi_velocity": 0, "coi_bias": "NEUTRAL"}
