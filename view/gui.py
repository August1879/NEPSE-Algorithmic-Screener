import time
from model.ingestion import NepseMarketCalendar
"""
Desktop View Layer for NEPSE Algorithmic Screener.
Built with PyQt6 (with PySide6 / CLI compatibility), featuring an interactive
dashboard, automated market-hours scheduler, live NPT status, green-highlighted entry setups,
and embedded Matplotlib technical charts.
"""
import sys
import logging
from typing import Optional, Dict, Any, List
import pandas as pd

from config import (
    APP_TITLE,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    SIGNAL_HIGHLIGHT_COLOR,
    SIGNAL_TEXT_COLOR
)
from .chart_canvas import ChartCanvas

logger = logging.getLogger(__name__)

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtCore import QUrl
    WEBENGINE_AVAILABLE = True
except Exception:
    WEBENGINE_AVAILABLE = False


# Check PyQt6 / PySide6 availability
try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QSplitter, QTableWidget, QTableWidgetItem, QLabel, QPushButton, QStackedWidget,
        QLineEdit, QHeaderView, QProgressBar, QTextEdit, QStatusBar, QComboBox
    )
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QColor, QFont, QBrush
    PYQT_GUI_AVAILABLE = True
except ImportError:
    PYQT_GUI_AVAILABLE = False
    QMainWindow = object
    QWidget = object


class NepseScreenerMainWindow(QMainWindow):
    def __init__(self, controller):
        if not PYQT_GUI_AVAILABLE:
            raise RuntimeError("PyQt6 is required for the Desktop GUI. Use CLIViewer for terminal execution.")

        super().__init__()
        self.controller = controller
        self.selected_symbol: Optional[str] = None
        self.current_filter = "All Stocks"
        self._init_ui()

        # Timer for updating live NPT clock & market status
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_market_clock_display)
        self.clock_timer.start(1000)
        QTimer.singleShot(600, self._handle_cloud_sync)

    def _init_ui(self):
        self.setWindowTitle(APP_TITLE)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet("""
            QMainWindow { background-color: #121212; }
            QLabel { color: #ffffff; }
            QPushButton {
                background-color: #2b5c8f;
                color: #ffffff;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #3b7cbd; }
            QLineEdit, QComboBox {
                background-color: #242424;
                color: #ffffff;
                border: 1px solid #444444;
                padding: 5px;
                border-radius: 4px;
            }
            QTableWidget {
                background-color: #1e1e1e;
                color: #ffffff;
                gridline-color: #333333;
                selection-background-color: #2c3e50;
            }
            QHeaderView::section {
                background-color: #2a2a2a;
                color: #dddddd;
                padding: 5px;
                font-weight: bold;
                border: 1px solid #333333;
            }
            QProgressBar {
                border: 1px solid #444444;
                border-radius: 4px;
                text-align: center;
                color: white;
                background-color: #242424;
            }
            QProgressBar::chunk { background-color: #26a69a; }
            QTextEdit {
                background-color: #1a1a1a;
                color: #81c784;
                font-family: monospace;
                font-size: 11px;
                border: 1px solid #333333;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # === LEFT PANEL: CONTROLS & WATCHLIST TABLE ===
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(10, 10, 10, 10)

        # Title & Live Market Status
        header_layout = QHBoxLayout()
        header_label = QLabel("NEPSE Screener & Scheduler")
        header_font = QFont()
        header_font.setPointSize(13)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_layout.addWidget(header_label)

        self.market_status_badge = QLabel("Checking NPT...")
        self.market_status_badge.setStyleSheet("color: #ffb74d; font-weight: bold; font-size: 11px;")
        header_layout.addWidget(self.market_status_badge, alignment=Qt.AlignmentFlag.AlignRight)
        left_layout.addLayout(header_layout)

        # Automated Scheduler Controls Banner
        sched_banner = QHBoxLayout()
        self.cloud_sync_btn = QPushButton("☁ Sync Cloud (GitHub)")
        self.cloud_sync_btn.setStyleSheet("background-color: #5c6bc0; color: white; font-weight: bold;")
        self.cloud_sync_btn.clicked.connect(self._handle_cloud_sync)

        self.auto_sched_btn = QPushButton("▶ Enable Auto-Scraping (10:45-2:45 NPT)")
        self.auto_sched_btn.setStyleSheet("background-color: #00796b; color: white;")
        self.auto_sched_btn.clicked.connect(self._toggle_auto_scheduler)

        self.sync_all_btn = QPushButton("Sync All Stocks")
        self.sync_all_btn.setStyleSheet("background-color: #455a64; color: white;")
        self.sync_all_btn.clicked.connect(self._handle_sync_all)

        sched_banner.addWidget(self.cloud_sync_btn)
        sched_banner.addWidget(self.auto_sched_btn)
        sched_banner.addWidget(self.sync_all_btn)
        left_layout.addLayout(sched_banner)

        # Filter & Action Row
        action_row = QHBoxLayout()
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All Listed Stocks", "Entry Signals Only", "Core Watchlist"])
        self.filter_combo.currentTextChanged.connect(self._handle_filter_change)

        self.ticker_input = QLineEdit()
        self.ticker_input.setPlaceholderText("Symbol (e.g. UPPER)")
        self.add_btn = QPushButton("Add")
        self.add_btn.clicked.connect(self._handle_add_ticker)

        self.run_btn = QPushButton("▶ Run Screen")
        self.run_btn.setStyleSheet("background-color: #2e7d32; color: white;")
        self.run_btn.clicked.connect(self._handle_run_screener)

        action_row.addWidget(QLabel("View:"))
        action_row.addWidget(self.filter_combo)
        action_row.addWidget(self.ticker_input)
        action_row.addWidget(self.add_btn)
        action_row.addWidget(self.run_btn)
        left_layout.addLayout(action_row)

        # Watchlist Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Symbol", "LTP (NPR)", "Chg %", "RSI(14)", "Vol Z-Score", "Signal Status"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self._handle_table_selection)
        left_layout.addWidget(self.table)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        left_layout.addWidget(self.progress_bar)

        # Detail & Log Box
        log_label = QLabel("Scheduler Activity & Technical Log:")
        left_layout.addWidget(log_label)
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(140)
        left_layout.addWidget(self.log_box)

        # === RIGHT PANEL: EMBEDDED TRADINGVIEW & MATPLOTLIB CHARTS ===
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 8, 8, 8)

        chart_header = QHBoxLayout()
        self.chart_title_label = QLabel("Technical Analysis & Signal Verification")
        self.chart_title_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #ffffff;")
        chart_header.addWidget(self.chart_title_label)
        chart_header.addStretch()

        self.chart_mode_combo = QComboBox()
        if WEBENGINE_AVAILABLE:
            self.chart_mode_combo.addItems(["TradingView (Interactive)", "Classic (Matplotlib)"])
        else:
            self.chart_mode_combo.addItems(["Classic (Matplotlib)"])
        self.chart_mode_combo.currentTextChanged.connect(self._handle_chart_mode_change)

        chart_header.addWidget(QLabel("Engine:"))
        chart_header.addWidget(self.chart_mode_combo)
        right_layout.addLayout(chart_header)

        self.chart_stack = QStackedWidget()

        if WEBENGINE_AVAILABLE:
            self.web_view = QWebEngineView()
            self.chart_stack.addWidget(self.web_view)

        self.canvas = ChartCanvas(self, width=8, height=7)
        self.chart_stack.addWidget(self.canvas)

        right_layout.addWidget(self.chart_stack)

        # Add both panels to splitter
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([540, 910])

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready. Select a ticker or activate auto-scraping.")

        # Initial populate
        self._update_market_clock_display()
        self._populate_table_from_cache()

    def _update_market_clock_display(self):
        """Updates the live NPT clock and market operational status badge."""
        now_npt = self.controller.calendar.now_npt()
        is_open, reason = self.controller.get_market_status()
        time_str = now_npt.strftime("%I:%M:%S %p NPT")

        if is_open:
            self.market_status_badge.setText(f"🟢 MARKET OPEN ({time_str})")
            self.market_status_badge.setStyleSheet("color: #69f0ae; font-weight: bold; font-size: 11px;")
        else:
            self.market_status_badge.setText(f"🔴 MARKET CLOSED ({time_str})")
            self.market_status_badge.setStyleSheet("color: #ff5252; font-weight: bold; font-size: 11px;")

    def _toggle_auto_scheduler(self):
        """Toggles automated background scraping between 10:45 and 14:45 NPT."""
        if self.controller.scheduler and self.controller.scheduler.isRunning():
            self.controller.stop_automated_scheduler()
            self.auto_sched_btn.setText("▶ Enable Auto-Scraping (10:45-2:45 NPT)")
            self.auto_sched_btn.setStyleSheet("background-color: #00796b; color: white;")
            self.log_box.append("Automated NEPSE Scheduler paused by user.")
            self.status_bar.showMessage("Auto-scheduler paused.")
        else:
            self.auto_sched_btn.setText("⏹ Stop Auto-Scraping")
            self.auto_sched_btn.setStyleSheet("background-color: #c62828; color: white;")
            self.log_box.append("Automated NEPSE Scheduler started. Active Mon-Fri 10:45-14:45 NPT.")

            def on_status(msg):
                self.status_bar.showMessage(msg)
                self.log_box.append(f"[Scheduler] {msg}")

            def on_ticker(sym, res):
                if res.get("is_entry_signal"):
                    self.log_box.append(
                        f"★ [ENTRY ALERT] {sym} @ Rs. {res['close']:.2f} | RSI: {res['rsi_14']:.1f} | Vol Z: {res['vol_zscore']:+.1f}σ"
                    )

            def on_cycle_finished(results):
                self._populate_table_from_cache()

            def on_holiday(msg):
                self.log_box.append(f"[Market Exception] {msg}")

            self.controller.start_automated_scheduler(
                on_status=on_status,
                on_ticker=on_ticker,
                on_cycle_finished=on_cycle_finished,
                on_holiday=on_holiday
            )

    def _handle_sync_all(self):
        """Scrapes and registers all NEPSE stocks into the database."""
        self.sync_all_btn.setEnabled(False)
        self.log_box.append("Discovering and syncing all listed NEPSE securities...")
        
        def run_sync():
            count, msg = self.controller.sync_all_nepse_stocks()
            self.log_box.append(f"[Sync Complete] {msg}")
            self._populate_table_from_cache()
            self.sync_all_btn.setEnabled(True)

        QTimer.singleShot(100, run_sync)

    def _handle_filter_change(self, text: str):
        self.current_filter = text
        self._populate_table_from_cache()

    def _populate_table_from_cache(self):
        """Loads and filters the table based on current user selection."""
        all_symbols = self.controller.get_watchlist()
        latest_df = self.controller.get_latest_signals_df()

        signal_map = {}
        if not latest_df.empty:
            for _, row in latest_df.iterrows():
                signal_map[row["symbol"]] = row.to_dict()

        # Apply filtering
        display_symbols = []
        if self.current_filter == "Entry Signals Only":
            display_symbols = [s for s in all_symbols if signal_map.get(s, {}).get("is_entry_signal", False)]
        elif self.current_filter == "Core Watchlist":
            from config import DEFAULT_WATCHLIST
            display_symbols = [s for s in all_symbols if s in DEFAULT_WATCHLIST]
        else:
            display_symbols = all_symbols

        self.table.setRowCount(len(display_symbols))
        for row_idx, symbol in enumerate(display_symbols):
            data = signal_map.get(symbol, {})
            self._update_table_row(row_idx, symbol, data)

        if display_symbols and not self.selected_symbol:
            self.table.selectRow(0)

    def _update_table_row(self, row_idx: int, symbol: str, data: Dict[str, Any]):
        """Populates and formats a single row in the watchlist table."""
        close = data.get("close", 0.0)
        chg = data.get("change_pct", 0.0)
        rsi = data.get("rsi_14", 0.0)
        zscore = data.get("vol_zscore", 0.0)
        is_entry = data.get("is_entry_signal", False)

        item_sym = QTableWidgetItem(symbol)
        item_sym.setFont(QFont("Arial", 9, QFont.Weight.Bold))

        item_close = QTableWidgetItem(f"{close:.2f}" if close else "--")
        item_chg = QTableWidgetItem(f"{chg:+.2f}%" if chg else "--")
        if chg > 0:
            item_chg.setForeground(QBrush(QColor("#26a69a")))
        elif chg < 0:
            item_chg.setForeground(QBrush(QColor("#ef5350")))

        item_rsi = QTableWidgetItem(f"{rsi:.1f}" if rsi else "--")
        if rsi and rsi < 30.0:
            item_rsi.setForeground(QBrush(QColor("#69f0ae")))
            item_rsi.setFont(QFont("Arial", 9, QFont.Weight.Bold))

        item_z = QTableWidgetItem(f"{zscore:+.2f}σ" if zscore else "--")
        if zscore and zscore >= 2.0:
            item_z.setForeground(QBrush(QColor("#ffb74d")))
            item_z.setFont(QFont("Arial", 9, QFont.Weight.Bold))

        status_text = "ENTRY SIGNAL" if is_entry else "Neutral"
        item_status = QTableWidgetItem(status_text)
        item_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        if is_entry:
            highlight = QColor(SIGNAL_HIGHLIGHT_COLOR)
            text_color = QColor(SIGNAL_TEXT_COLOR)
            font_bold = QFont("Arial", 9, QFont.Weight.Bold)

            for item in (item_sym, item_close, item_chg, item_rsi, item_z, item_status):
                item.setBackground(QBrush(highlight))
                item.setForeground(QBrush(text_color))
                item.setFont(font_bold)

        self.table.setItem(row_idx, 0, item_sym)
        self.table.setItem(row_idx, 1, item_close)
        self.table.setItem(row_idx, 2, item_chg)
        self.table.setItem(row_idx, 3, item_rsi)
        self.table.setItem(row_idx, 4, item_z)
        self.table.setItem(row_idx, 5, item_status)

    def _handle_table_selection(self):
        selected_rows = self.table.selectedItems()
        if not selected_rows:
            return
        row = selected_rows[0].row()
        symbol_item = self.table.item(row, 0)
        if not symbol_item:
            return
        symbol = symbol_item.text()
        self.selected_symbol = symbol

        df = self.controller.get_historical_data(symbol)
        self._render_current_chart(symbol)
        self.status_bar.showMessage(f"Loaded {symbol} chart.")

    def _handle_add_ticker(self):
        sym = self.ticker_input.text().strip().upper()
        if not sym:
            return
        self.controller.add_ticker_to_watchlist(sym)
        self.ticker_input.clear()
        self._populate_table_from_cache()
        self.status_bar.showMessage(f"Added {sym} to watchlist.")

    def _handle_run_screener(self):
        self.run_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.log_box.append("Initiating calculation pipeline across displayed stocks...")

        symbols = [self.table.item(r, 0).text() for r in range(self.table.rowCount()) if self.table.item(r, 0)]
        if not symbols:
            symbols = self.controller.get_watchlist()

        def on_started():
            self.status_bar.showMessage("Screening stocks in background thread...")

        def on_ticker_done(symbol: str, res: dict):
            for row_idx in range(self.table.rowCount()):
                item = self.table.item(row_idx, 0)
                if item and item.text() == symbol:
                    self._update_table_row(row_idx, symbol, res)
                    break
            
            if res.get("is_entry_signal"):
                self.log_box.append(
                    f"★ [ENTRY SIGNAL] {symbol} @ Rs. {res['close']:.2f} | "
                    f"RSI: {res['rsi_14']:.1f} | Vol Z: {res['vol_zscore']:+.1f}σ | {res['confirmation_notes']}"
                )

        def on_progress(current: int, total: int):
            pct = int((current / total) * 100)
            self.progress_bar.setValue(pct)

        def on_finished(results: list):
            self.run_btn.setEnabled(True)
            self.progress_bar.setVisible(False)
            self.status_bar.showMessage(f"Screening complete. Evaluated {len(results)} symbols.")
            self.log_box.append("=== Screening Finished ===")
            if self.selected_symbol:
                df = self.controller.get_historical_data(self.selected_symbol)
                self._render_current_chart(self.selected_symbol)

        def on_error(err_msg: str):
            self.log_box.append(f"ERROR: {err_msg}")

        self.controller.run_screener_async(
            symbols=symbols,
            on_started=on_started,
            on_ticker_done=on_ticker_done,
            on_progress=on_progress,
            on_finished=on_finished,
            on_error=on_error
        )

    def _handle_cloud_sync(self):
        self.log_box.append("Connecting to GitHub to download latest market database...")
        self.status_bar.showMessage("Syncing from GitHub...")
        success, msg = self.controller.sync_from_cloud()
        if success:
            self.log_box.append(f"[Cloud Sync] {msg}")
            self.status_bar.showMessage("GitHub sync complete.", 5000)
            self._populate_table_from_cache()
        else:
            self.log_box.append(f"[Cloud Sync Info] {msg}")
            self.status_bar.showMessage("Local database active.", 5000)

    def _handle_open_tradingview(self):
        sym = self.selected_symbol or "NABIL"
        df = self.controller.get_historical_data(sym)
        if df.empty:
            self.status_bar.showMessage(f"No historical data available for {sym}", 4000)
            return
        from .chart_canvas import open_tradingview_chart
        out_file = open_tradingview_chart(sym, df)
        self.log_box.append(f"[TradingView] Opened interactive chart for {sym} ({out_file.name})")
        self.status_bar.showMessage(f"Launched TradingView chart for {sym} in browser.", 5000)

    def _handle_chart_mode_change(self, mode: str):
        if self.selected_symbol:
            self._render_current_chart(self.selected_symbol)

    def _render_current_chart(self, symbol: str):
        df = self.controller.get_historical_data(symbol)
        if df.empty:
            return

        mode = self.chart_mode_combo.currentText()
        if "TradingView" in mode and getattr(self, "web_view", None) is not None:
            from .chart_canvas import export_tradingview_html
            out_file = export_tradingview_html(symbol, df)
            self.web_view.setUrl(QUrl.fromLocalFile(str(out_file.resolve())))
            self.chart_stack.setCurrentIndex(0)
        else:
            self.canvas.plot_stock(symbol, df)
            idx = 1 if getattr(self, "web_view", None) is not None else 0
            self.chart_stack.setCurrentIndex(idx)


class CLIViewer:
    """Console / Terminal viewer used for headless environments and daemon modes."""
    @staticmethod
    def render_dashboard(controller, all_stocks: bool = False):
        import tabulate
        print("\n" + "=" * 90)
        print("   NEPSE ALGORITHMIC SCREENER & AUTOMATED SCHEDULER (CLI DASHBOARD)")
        print("=" * 90)

        now_npt = controller.calendar.now_npt()
        is_open, reason = controller.get_market_status()
        status_tag = "🟢 OPEN" if is_open else "🔴 CLOSED"
        print(f"Current NPT Time: {now_npt.strftime('%A, %Y-%m-%d %I:%M:%S %p')} NPT | Market Status: {status_tag}")
        print(f"Operational Window: 10:45 AM - 02:45 PM NPT (Monday - Friday) | Reason: {reason}")
        print("-" * 90)

        if all_stocks:
            print("Syncing all NEPSE securities (~80+ listed companies)...")
            count, msg = controller.sync_all_nepse_stocks()
            print(f"-> {msg}")

        watchlist = controller.get_watchlist()
        results = []
        for sym in watchlist:
            res = controller.process_single_ticker_pipeline(sym)
            results.append(res)

        table_data = []
        for r in results:
            status = "🟢 [BUY / ENTRY]" if r["is_entry_signal"] else "Neutral"
            table_data.append([
                r["symbol"],
                f"Rs. {r['close']:.2f}",
                f"{r['change_pct']:+.2f}%",
                f"{r['rsi_14']:.1f}",
                f"{r['vol_zscore']:+.2f}σ",
                f"{r['volume']:,}",
                status,
                r["confirmation_notes"]
            ])

        headers = ["Symbol", "LTP", "Chg %", "RSI(14)", "Vol Z", "Volume", "Signal Status", "Notes"]
        print(tabulate.tabulate(table_data, headers=headers, tablefmt="fancy_grid"))

        triggered = [r["symbol"] for r in results if r["is_entry_signal"]]
        target_sym = triggered[0] if triggered else watchlist[0]

        df = controller.get_historical_data(target_sym)
        canvas = ChartCanvas(width=10, height=7)
        canvas.plot_stock(target_sym, df)
        output_chart = f"nepse_{target_sym.lower()}_chart.png"
        canvas.export_figure(output_chart)
        print(f"\n[Chart Generated] Exported technical analysis plot to: {output_chart}")
        print("=" * 90 + "\n")
        return results

    @staticmethod
    def run_scheduler_daemon(controller, poll_interval_minutes: int = 1):
        """Runs the automated scraping scheduler as a foreground terminal daemon."""
        print("\n" + "=" * 90)
        print("   NEPSE AUTOMATED DATA SCRAPER & SCREENER DAEMON")
        print("   Schedule: Monday - Friday | 10:45 AM - 02:45 PM NPT")
        print("   Exceptions: Nepal Public Holidays & Market Closure Announcements")
        print("=" * 90)

        def on_status(msg):
            print(f"[{NepseMarketCalendar.now_npt().strftime('%I:%M:%S %p NPT')}] {msg}")

        def on_ticker(sym, res):
            if res.get("is_entry_signal"):
                print(f"  ★ [ENTRY ALERT] {sym} @ Rs. {res['close']:.2f} | RSI: {res['rsi_14']:.1f} | Vol Z: {res['vol_zscore']:+.1f}σ")

        def on_cycle_finished(results):
            triggered = [r for r in results if r.get("is_entry_signal")]
            print(f"[{NepseMarketCalendar.now_npt().strftime('%I:%M:%S %p NPT')}] Cycle complete: {len(results)} stocks scraped, {len(triggered)} entry signals detected.")

        def on_holiday(msg):
            print(f"[{NepseMarketCalendar.now_npt().strftime('%I:%M:%S %p NPT')}] [Market Inactive] {msg}")

        scheduler = controller.start_automated_scheduler(
            on_status=on_status,
            on_ticker=on_ticker,
            on_cycle_finished=on_cycle_finished,
            on_holiday=on_holiday,
            poll_interval_minutes=poll_interval_minutes
        )

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping scheduler daemon...")
            controller.stop_automated_scheduler()
            print("Daemon stopped.")
