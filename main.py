"""
Entry point for NEPSE Algorithmic Screener & Automated Scheduler.
Supports PyQt6 GUI dashboard, automated market daemon, and headless CLI modes.
"""
import sys
import os
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-web-security --allow-file-access-from-files"

import argparse
import logging

from datetime import datetime, timezone, timedelta

def _npt_converter(*args):
    npt_tz = timezone(timedelta(hours=5, minutes=45))
    return datetime.now(npt_tz).timetuple()

logging.Formatter.converter = _npt_converter
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s NPT [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %I:%M:%S %p"
)
logger = logging.getLogger("nepse_screener")

def main():
    parser = argparse.ArgumentParser(description="NEPSE Algorithmic Screener & Automated Scheduler")
    parser.add_argument("--cli", action="store_true", help="Force headless CLI mode")
    parser.add_argument("--all", action="store_true", help="Scrape and screen all NEPSE stocks (not just watchlist)")
    parser.add_argument("--schedule", action="store_true", help="Run automated scraping scheduler daemon")
    parser.add_argument("--interval", type=int, default=1, help="Polling interval in minutes for live daemon (default: 1)")
    parser.add_argument("--add", type=str, help="Add a ticker symbol to the watchlist before running")
    parser.add_argument("--export-chart", type=str, help="Export technical chart for a specific symbol to PNG")
    parser.add_argument("--tradingview", type=str, help="Launch interactive TradingView chart in browser (e.g. --tradingview SHIVM)")
    args, _ = parser.parse_known_args()

    # If CLI commands are explicitly requested, run them directly
    if args.tradingview or args.export_chart or args.schedule or args.cli:
        from controller.controller import AppController
        controller = AppController()
        if args.add:
            controller.add_ticker_to_watchlist(args.add)
        
        if args.tradingview:
            sym = args.tradingview.upper().strip()
            df = controller.get_historical_data(sym)
            if df.empty:
                print(f"No historical data available in database for {sym}.")
                return
            from view.chart_canvas import open_tradingview_chart
            out = open_tradingview_chart(sym, df)
            print(f"✓ Interactive TradingView chart generated at: {out.resolve()}")
            return

        if args.export_chart:
            from view.chart_canvas import ChartCanvas
            sym = args.export_chart.upper().strip()
            df = controller.get_historical_data(sym)
            canvas = ChartCanvas(width=10, height=7)
            canvas.plot_stock(sym, df)
            out_file = f"{sym.lower()}_analysis.png"
            canvas.export_figure(out_file)
            print(f"Chart successfully saved to {out_file}")
            return

        if args.schedule:
            from view.gui import CLIViewer
            CLIViewer.run_scheduler_daemon(controller, poll_interval_minutes=args.interval)
            return

        from view.gui import CLIViewer
        CLIViewer.render_dashboard(controller, all_stocks=args.all)
        return

    # Headless Linux fallback
    if sys.platform.startswith("linux") and "DISPLAY" not in os.environ:
        from controller.controller import AppController
        from view.gui import CLIViewer
        controller = AppController()
        CLIViewer.render_dashboard(controller, all_stocks=args.all)
        return

    # --- INSTANT DESKTOP LAUNCH (< 0.2s) WITH GAME-STYLE LOADING SCREEN ---
    from PyQt6.QtWidgets import QApplication
    from view.loading_screen import GameLoadingWindow

    app = QApplication(sys.argv)
    loading_screen = GameLoadingWindow(cli_args=args)
    loading_screen.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        with open("crash_log.txt", "w", encoding="utf-8") as f:
            f.write(err_msg)
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, "Fatal Startup Error:\n\n" + err_msg, "NEPSE Screener Error", 0x10)
        except Exception:
            print(err_msg)
        sys.exit(1)
