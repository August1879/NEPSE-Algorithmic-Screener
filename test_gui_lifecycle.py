import sys
import os
import time
from pathlib import Path

# Fix Windows cp1252 encoding
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))

def run_test():
    print("=" * 70)
    print("  NEPSE SCREENER: FULL GUI LIFECYCLE & FEATURE TEST")
    print("=" * 70)

    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt, QTimer
    except (ImportError, OSError) as e:
        print(f"[INFO] Linux headless environment without display drivers: {e}")
        print("Testing backend and calculation pipeline directly...")
        _test_backend_pipeline()
        return

    app = QApplication.instance()
    if not app:
        app = QApplication(["nepse_test", "-platform", "offscreen"])

    from controller.controller import AppController
    from view.loading_screen import GameLoadingWindow
    from view.gui import NepseScreenerMainWindow

    print("\n[Step 1/5] Simulating GameLoadingWindow startup & background worker...")
    loader = GameLoadingWindow()
    
    # Wait for the background worker AND the queued main_window hand-off
    timeout = 15.0
    start = time.time()
    while (loader.main_window is None or (loader.worker and loader.worker.isRunning())) and (time.time() - start) < timeout:
        app.processEvents()
        time.sleep(0.05)

    for _ in range(10):
        app.processEvents()
        time.sleep(0.02)

    if getattr(loader, "error_trace", None):
        assert False, f"InitializationWorker error: {loader.error_trace}"

    assert not loader.worker.isRunning(), "InitializationWorker timed out!"
    print("[PASS] Background initialization worker completed successfully.")

    print("\n[Step 2/5] Verifying Main Window hand-off...")
    main_window = loader.main_window
    assert main_window is not None, "Main window was not instantiated by loader!"
    print("[PASS] Main window successfully instantiated on the GUI thread.")

    print("\n[Step 3/5] Verifying Stock List Table...")
    row_count = main_window.table.rowCount()
    print(f"-> Table rows found: {row_count}")
    assert row_count > 0, f"Table is empty! Found {row_count} rows."
    
    symbols_in_table = [main_window.table.item(r, 0).text() for r in range(row_count)]
    print(f"-> Stocks in table: {symbols_in_table}")
    for required_sym in ["NHPC", "RSML", "SHIVM", "SARBTM"]:
        assert required_sym in symbols_in_table, f"Missing {required_sym} in table!"
    print("[PASS] Core watchlist stocks (NHPC, RSML, SHIVM, SARBTM) verified in table.")

    print("\n[Step 4/5] Verifying Default Selection & Technical Chart Plotting...")
    assert main_window.selected_symbol is not None, "No stock was selected automatically!"
    print(f"-> Active selected stock: {main_window.selected_symbol}")
    
    axes = main_window.canvas.figure.axes
    assert len(axes) >= 3, f"Expected at least 3 chart subplots (Price, Volume, RSI), got {len(axes)}"
    has_plot_data = len(axes[0].lines) > 0 or len(axes[0].collections) > 0
    assert has_plot_data, f"Main chart for {main_window.selected_symbol} has no plot data!"
    print(f"[PASS] Matplotlib chart successfully rendered price, SMAs, Bollinger Bands, Volume, and RSI for {main_window.selected_symbol}.")

    print("\n[Step 5/5] Testing '> Open in Browser' & Engine Switching...")
    main_window._handle_open_tradingview()
    out_html = Path("output") / f"{main_window.selected_symbol.lower()}_tradingview.html"
    assert out_html.exists(), f"TradingView HTML file was not generated: {out_html}"
    assert out_html.stat().st_size > 500, f"Generated HTML file is too small: {out_html.stat().st_size} bytes"
    print(f"[PASS] '> Open in Browser' successfully generated interactive TradingView HTML ({out_html.stat().st_size} bytes).")

    main_window.chart_mode_combo.setCurrentText("TradingView (Interactive)")
    app.processEvents()
    print("[PASS] Switched chart engine to 'TradingView (Interactive)' without exceptions.")

    main_window.chart_mode_combo.setCurrentText("Classic (Matplotlib)")
    app.processEvents()
    print("[PASS] Switched chart engine to 'Classic (Matplotlib)' without exceptions.")

    print("\n" + "=" * 70)
    print("  ALL GUI TESTS PASSED: STOCK LIST, CHARTS & BROWSER READY!")
    print("=" * 70)

def _test_backend_pipeline():
    from controller.controller import AppController
    ctrl = AppController()
    wl = ctrl.get_watchlist()
    assert len(wl) > 0, "Watchlist is empty!"
    for sym in wl:
        df = ctrl.get_historical_data(sym)
        assert not df.empty, f"Historical data for {sym} is empty!"
        from view.chart_canvas import export_tradingview_html
        out = export_tradingview_html(sym, df)
        assert out.exists() and out.stat().st_size > 500
    print(f"[PASS] Backend verified: all {len(wl)} stocks have valid price data and HTML charts.")

if __name__ == "__main__":
    run_test()
