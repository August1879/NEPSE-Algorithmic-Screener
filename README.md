# NEPSE Algorithmic Screener & Technical Dashboard

A desktop market screener, algorithmic signal detector, and automated data ingestion system for the Nepal Stock Exchange (NEPSE). Built with Python, PyQt6, Pandas, SciPy, Matplotlib, and TradingView Lightweight Charts using an asynchronous Model-View-Controller (MVC) architecture.

---

## Architecture Overview
* View Tier: PyQt6 Technical Dashboard, Instant Splash Launcher (<0.2s), Watchlist Table with Dynamic Badges, and Dual Chart Engine (Embedded In-App TradingView + Classic Matplotlib Canvas).
* Controller Tier: AppController Orchestrator, ScreenerWorker (QThread), NepseMarketScheduler (Daemon), and GitHub Cloud Sync Worker.
* Model Tier: SQLite Cache Database (nepse_cache.db), Vectorized Technical Engine (RSI 14, SMAs, Volume Z-Scores, RMS Bands), and Multi-Source Ingestion Layer with rate limiting and Nepal holiday filtering.

---

## Key Features
1. Automated Market Hours Scraping: Operates during NEPSE trading hours (10:45 AM - 02:45 PM NPT, Sun-Thu) with holiday calendar filtering.
2. Algorithmic Signal Engine: Wilder RSI (14), Volume Z-Score (+2.0 sigma), Moving Averages (20, 50, 200 SMA), RMS Volatility Bands (+-2.0 sigma), and SciPy swing peaks/valleys. Actionable green ENTRY SIGNAL badges.
3. Dual Charting Engine: Embedded Interactive TradingView (HTML5 via QWebEngineView) with 60 FPS rendering, mouse-wheel zoom, pan, toggleable overlays, plus Classic Matplotlib multi-panel technical charts.
4. Cloud Database Sync (GitHub): Downloads pre-scraped historical database snapshots directly from GitHub releases with optional auto-sync on startup.
5. High-Speed Desktop UI: Cold-start under 0.2s with animated loading screen and multi-category watchlist filtering.

---

## Installation & Setup

### Standalone Windows Executable (.exe)
1. Download NEPSE_Algorithmic_Screener_Windows.zip from GitHub Releases.
2. Extract the archive and launch NEPSE_Algorithmic_Screener.exe.

### Running from Source
- Clone: git clone https://github.com/August1879/NEPSE-Algorithmic-Screener.git
- Install: pip install -r requirements.txt PyQt6 PyQt6-WebEngine
- Launch: python main.py

---

## CLI Modes
- Launch Desktop GUI: python main.py
- Run Background Daemon: python main.py --schedule --interval 1
- Screen All Stocks in Terminal: python main.py --cli --all
- Open TradingView in Browser: python main.py --tradingview SHIVM
- Export Chart to PNG: python main.py --export-chart NHPC

---

## Testing
- Unit Tests: python -m unittest discover tests/
- GUI Lifecycle Verification: python test_gui_lifecycle.py

---

## License
MIT License. Developed for educational and research purposes.
