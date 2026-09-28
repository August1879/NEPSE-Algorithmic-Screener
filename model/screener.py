from pathlib import Path
"""
Multi-Strategy Signal Generation & Screening Engine for NEPSE.
Evaluates Mean-Reversion Dips, Momentum Volume Breakouts, and Trend Pullbacks.
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

        open_p = float(last_row["open"])
        high_p = float(last_row["high"])
        low_p = float(last_row["low"])
        prev_high = float(prev_row["high"])

        body = abs(close - open_p)
        candle_range = high_p - low_p
        lower_shadow = min(close, open_p) - low_p
        is_hammer = (lower_shadow >= 1.2 * body) and (candle_range > 0)
        is_engulfing = (close > open_p) and (close >= prev_high)

        # 1. Strategy 1: Capitulation Dip
        is_dip = (rsi < self.rsi_threshold) and vol_spike and (volume >= self.min_volume)

        # 2. Strategy 2: Momentum Volume Breakout
        is_breakout = (
            vol_spike and
            (volume >= self.min_volume) and
            (close > prev_close) and
            (close >= prev_high or (sma_50 > 0 and close >= sma_50)) and
            (45.0 <= rsi <= 85.0)
        )

        # 3. Strategy 3: Trend Pullback / 50 SMA Bounce
        is_uptrend = (close > sma_200) if sma_200 > 0 else True
        near_sma_50 = (abs(close - sma_50) / sma_50 <= 0.035) if sma_50 > 0 else False
        is_pullback = is_uptrend and near_sma_50 and (change_pct >= 0.0) and (40.0 <= rsi <= 56.0)

        is_entry = is_dip or is_breakout or is_pullback

        notes = []
        if is_dip:
            notes.append("🟢 [OVERSOLD DIP]")
            notes.append(f"RSI Oversold ({rsi:.1f} < {self.rsi_threshold})")
            notes.append(f"Volume Spike ({vol_zscore:+.1f}σ)")
            if is_hammer: notes.append("Hammer Wick")
            elif is_engulfing: notes.append("Bullish Engulfing")
        elif is_breakout:
            notes.append("🚀 [MOMENTUM BREAKOUT]")
            notes.append(f"Volume Surge ({vol_zscore:+.1f}σ, Vol: {int(volume):,})")
            notes.append(f"Momentum RSI: {rsi:.1f}")
            if close >= prev_high: notes.append("Resistance Breakout")
        elif is_pullback:
            notes.append("📈 [TREND PULLBACK]")
            notes.append(f"50-SMA Support Rebound ({change_pct:+.2f}%)")
            notes.append(f"Reset RSI: {rsi:.1f}")
        elif rsi < 30.0:
            notes.append(f"🟡 [NEAR SETUP - Oversold ({rsi:.1f})]")
        elif vol_spike:
            notes.append(f"🟡 [NEAR SETUP - Volume Spike ({vol_zscore:+.1f}σ)]")
        else:
            notes.append("Neutral / No Setup")

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
            "confirmation_notes": " | ".join(notes)
        }

    def screen_watchlist(self, watchlist: List[str], data_provider) -> List[Dict[str, Any]]:
        results = []
        for symbol in watchlist:
            df = data_provider(symbol)
            if df is not None and not df.empty:
                res = self.evaluate_latest_bar(symbol, df)
                results.append(res)
        return results
