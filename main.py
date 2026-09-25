"""
Entry point for NEPSE Algorithmic Screener & Automated Scheduler.
Supports PyQt6 GUI dashboard, automated market daemon, and headless CLI modes.
"""
import sys
import os
import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("nepse_screener")

from controller.controller import AppController

def main():
    parser = argparse.ArgumentParser(description="NEPSE Algorithmic Screener & Automated Scheduler")
    parser.add_argument("--cli", action="store_true", help="Force headless CLI mode")
    parser.add_argument("--all", action="store_true", help="Scrape and screen all NEPSE stocks (not just watchlist)")
    parser.add_argument("--schedule", action="store_true", help="Run automated scraping scheduler daemon (10:45-14:45 NPT Mon-Fri)")
    parser.add_argument("--add", type=str, help="Add a ticker symbol to the watchlist before running")
    parser.add_argument("--export-chart", type=str, help="Export technical chart for a specific symbol to PNG")
    args = parser.parse_args()

    controller = AppController()

    if args.add:
        controller.add_ticker_to_watchlist(args.add)
        logger.info(f"Added ticker {args.add} to watchlist.")

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
        CLIViewer.run_scheduler_daemon(controller)
        return

    # Check GUI capability
    can_launch_gui = False
    if not args.cli:
        try:
            import PyQt6
            if sys.platform.startswith("linux") and "DISPLAY" not in os.environ:
                logger.info("No DISPLAY found in environment. Defaulting to CLI mode.")
                can_launch_gui = False
            else:
                can_launch_gui = True
        except ImportError:
            logger.info("PyQt6 not installed in current Python environment. Defaulting to CLI mode.")
            can_launch_gui = False

    if can_launch_gui:
        from PyQt6.QtWidgets import QApplication
        from view.gui import NepseScreenerMainWindow

        app = QApplication(sys.argv)
        window = NepseScreenerMainWindow(controller)
        window.show()
        sys.exit(app.exec())
    else:
        from view.gui import CLIViewer
        CLIViewer.render_dashboard(controller, all_stocks=args.all)

if __name__ == "__main__":
    main()
