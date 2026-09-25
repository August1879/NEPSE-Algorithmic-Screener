"""
Vectorized Technical Engine for Statistical & Indicator Computations.
Uses pandas, numpy, and scipy.signal without external dependency baggage.
"""
import numpy as np
import pandas as pd
from scipy.signal import find_peaks
from typing import Tuple

from config import (
    RSI_PERIOD,
    SMA_SHORT_PERIOD,
    SMA_LONG_PERIOD,
    VOLUME_WINDOW,
    VOLUME_STD_DEV_MULTIPLIER
)

class NepseTechnicalEngine:
    @staticmethod
    def calculate_wilders_rsi(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
        """
        Calculates Wilder's Smoothed Relative Strength Index (RSI).
        Uses Running Moving Average (RMA) with alpha = 1 / period.
        """
        if len(close) < period:
            return pd.Series(np.nan, index=close.index, name=f"RSI_{period}")

        delta = close.diff()
        gain = np.where(delta > 0, delta, 0.0)
        loss = np.where(delta < 0, -delta, 0.0)

        alpha = 1.0 / period

        # Exponential moving averages for gain and loss
        avg_gain = pd.Series(gain, index=close.index).ewm(
            alpha=alpha, min_periods=period, adjust=False
        ).mean()
        avg_loss = pd.Series(loss, index=close.index).ewm(
            alpha=alpha, min_periods=period, adjust=False
        ).mean()

        total_move = avg_gain + avg_loss
        
        # Safe vectorized ratio
        rsi = np.where(
            total_move == 0,
            50.0,
            100.0 * (avg_gain / total_move)
        )
        return pd.Series(rsi, index=close.index, name=f"RSI_{period}").round(2)

    @staticmethod
    def calculate_smas(
        close: pd.Series,
        short_window: int = SMA_SHORT_PERIOD,
        long_window: int = SMA_LONG_PERIOD
    ) -> pd.DataFrame:
        """Computes 50-day and 200-day Simple Moving Averages."""
        sma_short = close.rolling(window=short_window, min_periods=min(short_window, len(close))).mean()
        sma_long = close.rolling(window=long_window, min_periods=min(long_window, len(close))).mean()
        
        return pd.DataFrame({
            f"SMA_{short_window}": sma_short.round(2),
            f"SMA_{long_window}": sma_long.round(2)
        }, index=close.index)

    @staticmethod
    def calculate_volume_metrics(
        volume: pd.Series,
        window: int = VOLUME_WINDOW,
        k_sigma: float = VOLUME_STD_DEV_MULTIPLIER
    ) -> pd.DataFrame:
        """
        Computes rolling volume mean, standard deviation, volume Z-score,
        and identifies 2-sigma volume spikes.
        """
        vol_mean = volume.rolling(window=window, min_periods=min(window, len(volume))).mean()
        vol_std = volume.rolling(window=window, min_periods=min(window, len(volume))).std(ddof=1)
        
        # Replace 0 or NaN standard deviation to prevent division by zero
        safe_std = vol_std.replace(0, np.nan)
        z_score = (volume - vol_mean) / safe_std
        z_score = z_score.fillna(0.0).round(2)

        upper_2sigma = vol_mean + (k_sigma * vol_std)
        vol_spike = (volume > upper_2sigma) & (vol_std > 0)

        return pd.DataFrame({
            f"Vol_Mean_{window}": vol_mean.round(0),
            f"Vol_Std_{window}": vol_std.round(0),
            "Vol_Upper_2Sigma": upper_2sigma.round(0),
            "Vol_ZScore": z_score,
            "Vol_Spike": vol_spike
        }, index=volume.index)

    @staticmethod
    def detect_peaks_valleys(
        close: pd.Series,
        distance: int = 5,
        prominence_pct: float = 0.02
    ) -> pd.DataFrame:
        """
        Identifies localized price peaks and valleys using scipy.signal.find_peaks.
        Prominence is dynamically scaled to 2% of the local median price.
        """
        prices = close.values
        n = len(prices)
        is_peak = np.zeros(n, dtype=bool)
        is_valley = np.zeros(n, dtype=bool)

        if n >= distance * 2:
            median_p = float(np.nanmedian(prices))
            prominence = max(1.0, median_p * prominence_pct)

            # Local peaks
            peaks, _ = find_peaks(prices, distance=distance, prominence=prominence)
            is_peak[peaks] = True

            # Local valleys (inverting prices)
            valleys, _ = find_peaks(-prices, distance=distance, prominence=prominence)
            is_valley[valleys] = True

        return pd.DataFrame({
            "is_peak": is_peak,
            "is_valley": is_valley
        }, index=close.index)

    @classmethod
    def enrich_dataframe(cls, df: pd.DataFrame) -> pd.DataFrame:
        """Applies full technical indicator pipeline to raw OHLCV DataFrame."""
        if df.empty or len(df) < 5:
            return df

        result = df.copy()
        
        # 1. RSI
        result["rsi_14"] = cls.calculate_wilders_rsi(result["close"], period=RSI_PERIOD)
        
        # 2. SMAs
        smas = cls.calculate_smas(result["close"], SMA_SHORT_PERIOD, SMA_LONG_PERIOD)
        result["sma_50"] = smas[f"SMA_{SMA_SHORT_PERIOD}"]
        result["sma_200"] = smas[f"SMA_{SMA_LONG_PERIOD}"]

        # 3. Volume Statistics
        vol_df = cls.calculate_volume_metrics(result["volume"], VOLUME_WINDOW, VOLUME_STD_DEV_MULTIPLIER)
        result["vol_mean_20"] = vol_df[f"Vol_Mean_{VOLUME_WINDOW}"]
        result["vol_std_20"] = vol_df[f"Vol_Std_{VOLUME_WINDOW}"]
        result["vol_upper_2sigma"] = vol_df["Vol_Upper_2Sigma"]
        result["vol_zscore"] = vol_df["Vol_ZScore"]
        result["vol_spike"] = vol_df["Vol_Spike"]

        # 4. Peaks & Valleys
        extrema = cls.detect_peaks_valleys(result["close"], distance=5, prominence_pct=0.02)
        result["is_peak"] = extrema["is_peak"]
        result["is_valley"] = extrema["is_valley"]

        return result
