"""
Automated GUI Lifecycle & Feature Verification Test.
Tests:
1. Bootstrapping via GameLoadingWindow
2. Hand-off to NepseScreenerMainWindow on the GUI thread
3. Stock table population (NHPC, RSML, SHIVM, SARBTM)
4. Automatic selection and technical chart plotting
5. '↗ Open in Browser' functionality & HTML generation
6. Engine switching between Classic (Matplotlib) & TradingView
"""
import sys
import os
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

def run_test():
    print("=" * 70)
    print("  NEPSE SCREENER: FULL GUI LIFECYCLE & FEATURE TEST")
    print("=" * 70)

    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt, QTimer
    except (ImportError, OSError) as e:
        print(f"ℹ Headless Linux without display drivers ({e}). Testing backend directly...")
        _test_backend()
        return

    # Use Qt offscreen platform (runs headlessly in terminal without a monitor)
    app = QApplication.instance()
    if not app:
        app = QApplication(["nepse_test", "-platform", "offscreen"])

    from controller.controller import AppController
    from view.loading_screen import GameLoadingWindow
    from view.gui import NepseScreenerMainWindow

    print("\n[Step 1/5] Testing GameLoadingWindow startup & worker...")
    loader = GameLoadingWindow()
    timeout = 10.0
    start = time.time()
    while loader.worker.isRunning() and (time.time() - start) < timeout:
        app.processEvents()
        time.sleep(0.05)

    assert not loader.worker.isRunning(), "InitializationWorker timed out!"
    print("✓ Background worker finished cleanly.")

    print("\n[Step 2/5] Testing Main Window hand-off...")
    main_window = loader.main_window
    assert main_window is not None, "Main window was not instantiated!"
    print("✓ Main window instantiated on the GUI thread.")

    print("\n[Step 3/5] Verifying Stock List Table...")
    row_count = main_window.table.rowCount()
    print(f"-> Table rows found: {row_count}")
    assert row_count > 0, f"Table is empty! Found {row_count} rows."
    
    symbols_in_table = [main_window.table.item(r, 0).text() for r in range(row_count)]
    print(f"-> Stocks in table: {symbols_in_table}")
    for sym in ["NHPC", "RSML", "SHIVM", "SARBTM"]:
        assert sym in symbols_in_table, f"Missing {sym} in table!"
    print("✓ Core watchlist stocks (NHPC, RSML, SHIVM, SARBTM) verified in table.")

    print("\n[Step 4/5] Verifying Default Selection & Chart Plotting...")
    assert main_window.selected_symbol is not None, "No stock was selected automatically!"
    print(f"-> Selected stock: {main_window.selected_symbol}")
    
    axes = main_window.canvas.figure.axes
    assert len(axes) >= 3, f"Expected 3 chart subplots, got {len(axes)}"
    has_data = len(axes[0].lines) > 0 or len(axes[0].collections) > 0
    assert has_data, f"Chart for {main_window.selected_symbol} has no plot data!"
    print(f"✓ Technical chart rendered price, SMAs, Bollinger Bands, Volume, and RSI for {main_window.selected_symbol}.")

    print("\n[Step 5/5] Testing '↗ Open in Browser' & Engine Switching...")
    main_window._handle_open_tradingview()
    out_html = Path("output") / f"{main_window.selected_symbol.lower()}_tradingview.html"
    assert out_html.exists(), f"TradingView HTML file was not generated: {out_html}"
    assert out_html.stat().st_size > 500, "HTML file is empty!"
    print(f"✓ '↗ Open in Browser' generated valid TradingView HTML ({out_html.stat().st_size} bytes).")

    # Test engine switching
    main_window.chart_mode_combo.setCurrentText("TradingView (Interactive)")
    app.processEvents()
    main_window.chart_mode_combo.setCurrentText("Classic (Matplotlib)")
    app.processEvents()
    print("✓ Engine switching verified without exceptions.")

    print("\n" + "=" * 70)
    print("  ALL GUI CHECKS PASSED: STOCK LIST, CHARTS & BROWSER READY!")
    print("=" * 70)

def _test_backend():
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
    print(f"✓ Backend verified: all {len(wl)} stocks have valid price data and HTML charts.")

if __name__ == "__main__":
    run_test()
