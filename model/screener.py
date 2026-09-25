"""
Signal Generation & Screening Engine.
Cross-references technical and statistical metrics against predefined entry criteria.
"""
from typing import Dict, List, Any
import numpy as np
import pandas as pd

from config import (
    RSI_OVERSOLD,
    MIN_LIQUIDITY_VOLUME
)
from .engine import NepseTechnicalEngine

class NepseScreener:
    def __init__(self, rsi_threshold: float = RSI_OVERSOLD, min_volume: int = MIN_LIQUIDITY_VOLUME):
        self.rsi_threshold = rsi_threshold
        self.min_volume = min_volume

    def evaluate_latest_bar(self, symbol: str, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Evaluates the most recent trading bar for a given stock symbol.
        Returns a standardized status dictionary consumed by the Controller & View.
        """
        if df.empty or len(df) < 20:
            return {
                "symbol": symbol,
                "date": None,
                "close": 0.0,
                "change_pct": 0.0,
                "rsi_14": 0.0,
                "volume": 0,
                "vol_mean_20": 0.0,
                "vol_std_20": 0.0,
                "vol_zscore": 0.0,
                "vol_spike": False,
                "sma_50": 0.0,
                "sma_200": 0.0,
                "is_entry_signal": False,
                "confirmation_notes": "Insufficient historical data (< 20 bars)"
            }

        # Ensure indicators are populated
        if "rsi_14" not in df.columns or "vol_spike" not in df.columns:
            df = NepseTechnicalEngine.enrich_dataframe(df)

        last_row = df.iloc[-1]
        prev_row = df.iloc[-2] if len(df) >= 2 else last_row

        close = float(last_row["close"])
        prev_close = float(prev_row["close"])
        change_pct = round(((close - prev_close) / prev_close) * 100.0, 2) if prev_close > 0 else 0.0

        rsi = float(last_row["rsi_14"]) if pd.notna(last_row["rsi_14"]) else 50.0
        volume = float(last_row["volume"])
        vol_mean = float(last_row["vol_mean_20"]) if pd.notna(last_row["vol_mean_20"]) else 0.0
        vol_std = float(last_row["vol_std_20"]) if pd.notna(last_row["vol_std_20"]) else 0.0
        vol_zscore = float(last_row["vol_zscore"]) if pd.notna(last_row["vol_zscore"]) else 0.0
        vol_spike = bool(last_row["vol_spike"])
        sma_50 = float(last_row["sma_50"]) if pd.notna(last_row["sma_50"]) else 0.0
        sma_200 = float(last_row["sma_200"]) if pd.notna(last_row["sma_200"]) else 0.0

        # Core criteria:
        # 1. RSI < 30
        # 2. Volume > 2-sigma (vol_spike)
        # 3. Volume >= min_volume
        cond_rsi = rsi < self.rsi_threshold
        cond_vol = vol_spike and (volume >= self.min_volume)

        # Candlestick Price Action Confirmation:
        # Check for hammer / lower shadow absorption
        body = abs(close - float(last_row["open"]))
        candle_range = float(last_row["high"]) - float(last_row["low"])
        lower_shadow = (min(close, float(last_row["open"])) - float(last_row["low"]))
        
        is_hammer = (lower_shadow >= 1.2 * body) and (candle_range > 0)
        is_engulfing = (close > float(last_row["open"])) and (close >= float(prev_row["high"]))
        recent_valley = bool(df["is_valley"].iloc[-5:].any())

        notes = []
        if cond_rsi:
            notes.append(f"RSI Oversold ({rsi:.1f} < {self.rsi_threshold})")
        if cond_vol:
            notes.append(f"Volume Spike ({vol_zscore:+.1f}σ, Vol: {int(volume):,})")
        if is_hammer:
            notes.append("Hammer/Lower Rejection Wick")
        elif is_engulfing:
            notes.append("Bullish Engulfing")
        elif recent_valley:
            notes.append("Support Valley Defended (last 5d)")

        is_entry = cond_rsi and cond_vol

        return {
            "symbol": symbol,
            "date": str(last_row["date"])[:10],
            "close": close,
            "change_pct": change_pct,
            "rsi_14": rsi,
            "volume": int(volume),
            "vol_mean_20": vol_mean,
            "vol_std_20": vol_std,
            "vol_zscore": vol_zscore,
            "vol_spike": vol_spike,
            "sma_50": sma_50,
            "sma_200": sma_200,
            "is_entry_signal": is_entry,
            "confirmation_notes": " | ".join(notes) if notes else "Neutral / No Setup"
        }

    def screen_watchlist(self, watchlist: List[str], data_provider) -> List[Dict[str, Any]]:
        """Screens all symbols in the watchlist using historical data from provider."""
        results = []
        for symbol in watchlist:
            df = data_provider(symbol)
            res = self.evaluate_latest_bar(symbol, df)
            results.append(res)
        return results
