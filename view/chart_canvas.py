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

import json
import webbrowser
from pathlib import Path

TRADINGVIEW_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NEPSE - {{SYMBOL}} TradingView Chart</title>
    <script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background-color: #131722; color: #d1d4dc;
            font-family: -apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, sans-serif;
            overflow: hidden; display: flex; flex-direction: column; height: 100vh;
        }
        #nav-toolbar {
            background-color: #1e222d; border-bottom: 1px solid #2a2e39;
            padding: 10px 18px; display: flex; align-items: center;
            justify-content: space-between; flex-wrap: wrap; gap: 12px;
        }
        .symbol-badge { font-size: 20px; font-weight: 700; color: #ffffff; }
        .price-tag { font-size: 15px; font-weight: 700; padding: 3px 10px; border-radius: 4px; }
        .price-up { color: #26a69a; background: rgba(38, 166, 154, 0.12); }
        .price-down { color: #ef5350; background: rgba(239, 83, 80, 0.12); }
        .indicators-panel { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font-size: 12px; }
        .toggle-btn {
            display: flex; align-items: center; gap: 6px; background: #2a2e39; color: #d1d4dc;
            padding: 5px 10px; border-radius: 5px; cursor: pointer; user-select: none;
        }
        .toggle-btn:hover { background: #363c4e; }
        .toggle-btn input { cursor: pointer; }
        .color-dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
        #chart-container { flex: 1; width: 100%; position: relative; }
        #legend-bar {
            position: absolute; top: 14px; left: 18px; z-index: 10; font-size: 13px;
            background: rgba(19, 23, 34, 0.85); padding: 6px 14px; border-radius: 4px;
            border: 1px solid #2a2e39; pointer-events: none; line-height: 1.6;
        }
    </style>
</head>
<body>
    <div id="nav-toolbar">
        <div style="display:flex; align-items:center; gap:12px;">
            <span class="symbol-badge">{{SYMBOL}}</span>
            <span style="font-size:11px; color:#787b86; background:#2a2e39; padding:3px 8px; border-radius:4px;">NEPSE DAILY</span>
            <span class="price-tag {{PRICE_CLASS}}">LTP: NPR {{LTP}} ({{CHG_SIGN}}{{CHG}}, {{CHG_SIGN}}{{CHG_PCT}}%)</span>
        </div>
        <div class="indicators-panel">
            <strong style="color:#787b86; margin-right:4px;">PROJECT OVERLAYS:</strong>
            <label class="toggle-btn">
                <input type="checkbox" id="chk-sma20" checked onchange="toggleSeries('sma20', this.checked)">
                <span class="color-dot" style="background:#2962FF"></span> SMA 20
            </label>
            <label class="toggle-btn">
                <input type="checkbox" id="chk-sma50" checked onchange="toggleSeries('sma50', this.checked)">
                <span class="color-dot" style="background:#FF9800"></span> SMA 50
            </label>
            <label class="toggle-btn">
                <input type="checkbox" id="chk-sma200" checked onchange="toggleSeries('sma200', this.checked)">
                <span class="color-dot" style="background:#9C27B0"></span> SMA 200
            </label>
            <label class="toggle-btn">
                <input type="checkbox" id="chk-rms" checked onchange="toggleSeries('rms', this.checked)">
                <span class="color-dot" style="background:#E91E63"></span> RMS Bands (±2σ)
            </label>
            <label class="toggle-btn">
                <input type="checkbox" id="chk-vol" checked onchange="toggleSeries('vol', this.checked)">
                Volume
            </label>
        </div>
    </div>
    <div id="chart-container">
        <div id="legend-bar"><span id="legend-info"><strong style="color:#fff;">{{SYMBOL}}</strong> | Hover over candlesticks to view OHLC</span></div>
    </div>
    <script>
        const candleData = {{CANDLE_DATA}};
        const volumeData = {{VOLUME_DATA}};
        const sma20Data = {{SMA20_DATA}};
        const sma50Data = {{SMA50_DATA}};
        const sma200Data = {{SMA200_DATA}};
        const rmsUpperData = {{RMS_UPPER_DATA}};
        const rmsLowerData = {{RMS_LOWER_DATA}};

        const container = document.getElementById("chart-container");
        const chart = LightweightCharts.createChart(container, {
            layout: { background: { color: "#131722" }, textColor: "#d1d4dc" },
            grid: { vertLines: { color: "#1e222d" }, horzLines: { color: "#1e222d" } },
            crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
            rightPriceScale: { borderColor: "#2a2e39", scaleMargins: { top: 0.08, bottom: 0.22 } },
            timeScale: { borderColor: "#2a2e39", timeVisible: true, secondsVisible: false },
        });

        const candleSeries = chart.addCandlestickSeries({
            upColor: "#26a69a", downColor: "#ef5350", borderVisible: false,
            wickUpColor: "#26a69a", wickDownColor: "#ef5350",
        });
        candleSeries.setData(candleData);

        const volumeSeries = chart.addHistogramSeries({
            priceFormat: { type: "volume" }, priceScaleId: "", scaleMargins: { top: 0.8, bottom: 0 },
        });
        volumeSeries.setData(volumeData);

        const s20 = chart.addLineSeries({ color: "#2962FF", lineWidth: 1.5, title: "SMA 20" });
        s20.setData(sma20Data);
        const s50 = chart.addLineSeries({ color: "#FF9800", lineWidth: 1.5, title: "SMA 50" });
        s50.setData(sma50Data);
        const s200 = chart.addLineSeries({ color: "#9C27B0", lineWidth: 2, title: "SMA 200" });
        s200.setData(sma200Data);

        const rUp = chart.addLineSeries({ color: "#E91E63", lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed, title: "RMS Upper (+2σ)" });
        rUp.setData(rmsUpperData);
        const rLow = chart.addLineSeries({ color: "#E91E63", lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed, title: "RMS Lower (-2σ)" });
        rLow.setData(rmsLowerData);

        function toggleSeries(name, isVisible) {
            if (name === "sma20") s20.applyOptions({ visible: isVisible });
            if (name === "sma50") s50.applyOptions({ visible: isVisible });
            if (name === "sma200") s200.applyOptions({ visible: isVisible });
            if (name === "vol") volumeSeries.applyOptions({ visible: isVisible });
            if (name === "rms") {
                rUp.applyOptions({ visible: isVisible });
                rLow.applyOptions({ visible: isVisible });
            }
        }

        const legendInfo = document.getElementById("legend-info");
        chart.subscribeCrosshairMove(param => {
            if (!param.time || !param.seriesData.get(candleSeries)) {
                if (candleData.length > 0) updateLegend(candleData[candleData.length - 1]);
                return;
            }
            updateLegend(param.seriesData.get(candleSeries));
        });

        function updateLegend(bar) {
            if (!bar) return;
            const isUp = bar.close >= bar.open;
            const clr = isUp ? "#26a69a" : "#ef5350";
            legendInfo.innerHTML = "<strong style=\"color:#fff;\">{{SYMBOL}}</strong> | " +
                "O: <span style=\"color:" + clr + "\">" + bar.open.toFixed(2) + "</span> " +
                "H: <span style=\"color:" + clr + "\">" + bar.high.toFixed(2) + "</span> " +
                "L: <span style=\"color:" + clr + "\">" + bar.low.toFixed(2) + "</span> " +
                "C: <span style=\"color:" + clr + "\">" + bar.close.toFixed(2) + "</span>";
        }
        if (candleData.length > 0) updateLegend(candleData[candleData.length - 1]);

        window.addEventListener("resize", () => {
            chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
        });
        chart.timeScale().fitContent();
    </script>
</body>
</html>
"""

def export_tradingview_html(symbol: str, df: pd.DataFrame, output_dir: Path = Path("output")) -> Path:
    """Generates an interactive HTML5 TradingView chart with toggleable indicators."""
    output_dir.mkdir(parents=True, exist_ok=True)
    sym = symbol.upper().strip()

    if df.empty:
        out_file = output_dir / f"{sym.lower()}_tradingview.html"
        out_file.write_text("<h3>No historical data to chart.</h3>", encoding="utf-8")
        return out_file

    work_df = df.copy()
    work_df["date_str"] = pd.to_datetime(work_df["date"]).dt.strftime("%Y-%m-%d")
    work_df = work_df.sort_values("date_str").reset_index(drop=True)

    work_df["sma_20"] = work_df["close"].rolling(20, min_periods=5).mean().round(2)
    work_df["sma_50"] = work_df["close"].rolling(50, min_periods=10).mean().round(2)
    work_df["sma_200"] = work_df["close"].rolling(200, min_periods=20).mean().round(2)
    rolling_std = work_df["close"].rolling(20, min_periods=5).std().fillna(0.0)
    work_df["rms_upper"] = (work_df["sma_20"] + 2.0 * rolling_std).round(2)
    work_df["rms_lower"] = (work_df["sma_20"] - 2.0 * rolling_std).round(2)

    candles, volumes, sma20, sma50, sma200, rms_up, rms_low = [], [], [], [], [], [], []

    for _, row in work_df.iterrows():
        t = row["date_str"]
        o = float(row.get("open", row["close"]))
        h = float(row.get("high", row["close"]))
        l = float(row.get("low", row["close"]))
        c = float(row["close"])
        v = float(row.get("volume", 0.0))

        candles.append({"time": t, "open": o, "high": h, "low": l, "close": c})
        vol_color = "rgba(38, 166, 154, 0.45)" if c >= o else "rgba(239, 83, 80, 0.45)"
        volumes.append({"time": t, "value": v, "color": vol_color})

        if pd.notna(row["sma_20"]): sma20.append({"time": t, "value": float(row["sma_20"])})
        if pd.notna(row["sma_50"]): sma50.append({"time": t, "value": float(row["sma_50"])})
        if pd.notna(row["sma_200"]): sma200.append({"time": t, "value": float(row["sma_200"])})
        if pd.notna(row["rms_upper"]): rms_up.append({"time": t, "value": float(row["rms_upper"])})
        if pd.notna(row["rms_lower"]): rms_low.append({"time": t, "value": float(row["rms_lower"])})

    ltp = work_df["close"].iloc[-1]
    prev = work_df["close"].iloc[-2] if len(work_df) > 1 else ltp
    chg = ltp - prev
    chg_pct = (chg / prev) * 100 if prev else 0.0
    price_class = "price-up" if chg >= 0 else "price-down"
    chg_sign = "+" if chg >= 0 else ""

    html = (
        TRADINGVIEW_HTML_TEMPLATE
        .replace("{{SYMBOL}}", sym)
        .replace("{{LTP}}", f"{ltp:.2f}")
        .replace("{{CHG}}", f"{chg:.2f}")
        .replace("{{CHG_PCT}}", f"{chg_pct:.2f}")
        .replace("{{CHG_SIGN}}", chg_sign)
        .replace("{{PRICE_CLASS}}", price_class)
        .replace("{{CANDLE_DATA}}", json.dumps(candles))
        .replace("{{VOLUME_DATA}}", json.dumps(volumes))
        .replace("{{SMA20_DATA}}", json.dumps(sma20))
        .replace("{{SMA50_DATA}}", json.dumps(sma50))
        .replace("{{SMA200_DATA}}", json.dumps(sma200))
        .replace("{{RMS_UPPER_DATA}}", json.dumps(rms_up))
        .replace("{{RMS_LOWER_DATA}}", json.dumps(rms_low))
    )

    out_file = output_dir / f"{sym.lower()}_tradingview.html"
    out_file.write_text(html, encoding="utf-8")
    return out_file

def open_tradingview_chart(symbol: str, df: pd.DataFrame, output_dir: Path = Path("output")) -> Path:
    out_file = export_tradingview_html(symbol, df, output_dir)
    try:
        webbrowser.open(f"file://{out_file.resolve()}")
    except Exception:
        pass
    return out_file
