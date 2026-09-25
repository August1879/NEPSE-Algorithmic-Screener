"""
Matplotlib Chart Canvas.
Renders candlestick charts, moving averages, RSI subplots, and volume standard deviation bands.
Compatible with PyQt6 / PySide6 FigureCanvasQTAgg and headless export.
"""
import logging
from typing import Optional
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

logger = logging.getLogger(__name__)

# Attempt PyQt6 backend integration
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as BaseCanvas
    CANVAS_AVAILABLE = True
except ImportError:
    try:
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as BaseCanvas
        CANVAS_AVAILABLE = True
    except ImportError:
        CANVAS_AVAILABLE = False
        BaseCanvas = object


class ChartCanvas(BaseCanvas):
    def __init__(self, parent=None, width=8, height=7, dpi=100):
        # Professional dark/light modern financial theme
        self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor="#1e1e1e")
        if CANVAS_AVAILABLE and BaseCanvas is not object:
            super().__init__(self.fig)
            if parent:
                self.setParent(parent)

        # 3 subplots: Price (top 55%), RSI (middle 25%), Volume (bottom 20%)
        self.axes = self.fig.subplots(
            nrows=3, ncols=1, sharex=True,
            gridspec_kw={"height_ratios": [3, 1.2, 1], "hspace": 0.08}
        )
        self._setup_styling()

    def _setup_styling(self):
        """Applies high-contrast dark theme for readability."""
        for ax in self.axes:
            ax.set_facecolor("#181818")
            ax.tick_params(colors="#cccccc", labelsize=8)
            for spine in ax.spines.values():
                spine.set_color("#333333")
            ax.grid(True, linestyle=":", alpha=0.3, color="#666666")

    def plot_stock(self, symbol: str, df: pd.DataFrame):
        """
        Renders complete multi-pane technical chart for the symbol:
        Pane 1: Candlesticks/OHLC, SMA 50, SMA 200, peaks and valleys.
        Pane 2: Wilder's RSI (14) with oversold (30) and overbought (70) levels.
        Pane 3: Volume bars with 20-day rolling mean & 2-sigma upper band.
        """
        for ax in self.axes:
            ax.clear()
        self._setup_styling()

        if df.empty or len(df) < 5:
            self.axes[0].text(
                0.5, 0.5, f"No sufficient data to chart for {symbol}",
                color="white", ha="center", va="center", transform=self.axes[0].transAxes
            )
            if CANVAS_AVAILABLE and hasattr(self, "draw"):
                self.draw()
            return

        # Prepare dates and numerical indexes for clean daily spacing without weekend gaps
        n_bars = min(120, len(df))
        plot_df = df.iloc[-n_bars:].reset_index(drop=True)
        x_indices = np.arange(len(plot_df))

        # --- PANE 1: PRICE & MOVING AVERAGES ---
        ax_price = self.axes[0]
        ax_price.set_title(f"{symbol} - Daily Technicals & Signal Verification", color="#ffffff", fontsize=11, fontweight="bold", pad=8)

        # Custom candlestick drawing using matplotlib patches
        candle_colors = np.where(plot_df["close"] >= plot_df["open"], "#26a69a", "#ef5350")
        
        # Wicks
        ax_price.vlines(x_indices, plot_df["low"], plot_df["high"], color=candle_colors, linewidth=1.0, alpha=0.9)
        # Bodies
        body_bottom = np.minimum(plot_df["open"], plot_df["close"])
        body_height = np.maximum(np.abs(plot_df["close"] - plot_df["open"]), 0.2)
        ax_price.bar(x_indices, body_height, bottom=body_bottom, color=candle_colors, width=0.6, align="center")

        # Moving Averages
        if "sma_50" in plot_df.columns:
            ax_price.plot(x_indices, plot_df["sma_50"], label="50 SMA", color="#ff9800", linewidth=1.2)
        if "sma_200" in plot_df.columns:
            ax_price.plot(x_indices, plot_df["sma_200"], label="200 SMA", color="#9c27b0", linewidth=1.4)

        # Peaks and Valleys from scipy.signal
        if "is_peak" in plot_df.columns:
            peak_mask = plot_df["is_peak"].values
            if peak_mask.any():
                ax_price.scatter(
                    x_indices[peak_mask], plot_df.loc[peak_mask, "high"] * 1.01,
                    marker="v", color="#ff5252", s=40, label="Swing Peak", zorder=5
                )
        if "is_valley" in plot_df.columns:
            valley_mask = plot_df["is_valley"].values
            if valley_mask.any():
                ax_price.scatter(
                    x_indices[valley_mask], plot_df.loc[valley_mask, "low"] * 0.99,
                    marker="^", color="#69f0ae", s=40, label="Swing Valley", zorder=5
                )

        ax_price.set_ylabel("Price (NPR)", color="#cccccc", fontsize=8)
        ax_price.legend(loc="upper left", facecolor="#262626", edgecolor="#444444", labelcolor="#dddddd", fontsize=7)

        # --- PANE 2: RSI (14) ---
        ax_rsi = self.axes[1]
        if "rsi_14" in plot_df.columns:
            rsi_vals = plot_df["rsi_14"].values
            ax_rsi.plot(x_indices, rsi_vals, color="#42a5f5", linewidth=1.2, label="RSI(14)")
            ax_rsi.axhline(70, color="#ef5350", linestyle="--", linewidth=0.8, alpha=0.7)
            ax_rsi.axhline(30, color="#26a69a", linestyle="--", linewidth=0.8, alpha=0.7)
            ax_rsi.axhline(50, color="#666666", linestyle=":", linewidth=0.7, alpha=0.5)

            # Highlight oversold zone (< 30)
            ax_rsi.fill_between(x_indices, rsi_vals, 30, where=(rsi_vals <= 30), color="#26a69a", alpha=0.25)
            # Highlight overbought zone (> 70)
            ax_rsi.fill_between(x_indices, rsi_vals, 70, where=(rsi_vals >= 70), color="#ef5350", alpha=0.25)

        ax_rsi.set_ylim(10, 90)
        ax_rsi.set_ylabel("RSI (14)", color="#cccccc", fontsize=8)

        # --- PANE 3: VOLUME & 2-SIGMA SPIKES ---
        ax_vol = self.axes[2]
        vol_colors = np.where(plot_df["close"] >= plot_df["open"], "#26a69a", "#ef5350")
        ax_vol.bar(x_indices, plot_df["volume"], color=vol_colors, alpha=0.7, width=0.6)

        if "vol_mean_20" in plot_df.columns:
            ax_vol.plot(x_indices, plot_df["vol_mean_20"], color="#ffeb3b", linewidth=1.0, label="Vol Mean(20)")
        if "vol_upper_2sigma" in plot_df.columns:
            ax_vol.plot(x_indices, plot_df["vol_upper_2sigma"], color="#ff7043", linestyle="--", linewidth=1.1, label="+2σ Threshold")

        ax_vol.set_ylabel("Volume", color="#cccccc", fontsize=8)
        ax_vol.legend(loc="upper left", facecolor="#262626", edgecolor="#444444", labelcolor="#dddddd", fontsize=7)

        # Format X-axis with sparse date labels
        step = max(1, len(plot_df) // 8)
        selected_ticks = x_indices[::step]
        date_labels = [pd.to_datetime(d).strftime("%b %d") for d in plot_df["date"].iloc[::step]]
        ax_vol.set_xticks(selected_ticks)
        ax_vol.set_xticklabels(date_labels, rotation=0, fontsize=8, color="#cccccc")

        if CANVAS_AVAILABLE and hasattr(self, "draw"):
            self.draw()

    def export_figure(self, filepath: str):
        """Saves current chart to an image file (useful for headless verification)."""
        self.fig.savefig(filepath, dpi=120, bbox_inches="tight", facecolor=self.fig.get_facecolor())
