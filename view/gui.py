"""
Desktop View Layer for NEPSE Algorithmic Screener & Quantitative Suite.
Modern, sleek tabbed interface featuring:
  • Screener & Interactive Technical Charts
  • Market Psychology & Crowd Breadth Index
  • Live Financial News & Policy Announcements
  • Settings, Cloud Database Sync & Scheduler Daemon
"""
import sys
import time
import logging
from typing import Optional, Dict, Any, List
import pandas as pd
import numpy as np
from datetime import datetime
from model.ingestion import NepseMarketCalendar

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
    from PyQt6.QtCore import QUrl
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineSettings
    WEBENGINE_AVAILABLE = True
except Exception:
    WEBENGINE_AVAILABLE = False


# Check PyQt6 / PySide6 availability
try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QSplitter, QTableWidget, QTableWidgetItem, QLabel, QPushButton, QStackedWidget,
        QLineEdit, QHeaderView, QProgressBar, QTextEdit, QStatusBar, QComboBox,
        QCheckBox, QTabWidget, QGroupBox, QFrame
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
        self.current_filter = "All Listed Stocks"
        self.web_view = None
        self._init_ui()

        # Timer for updating live NPT clock & market status
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_market_clock_display)
        self.clock_timer.start(1000)
        QTimer.singleShot(0, self._deferred_startup)

    def _init_ui(self):
        self.setWindowTitle(APP_TITLE)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet("""
            QMainWindow { background-color: #111417; }
            QLabel { color: #e0e0e0; }
            QTabWidget::pane {
                border: 1px solid #23272d;
                background-color: #161a1e;
                border-radius: 6px;
            }
            QTabBar::tab {
                background: #191d22;
                color: #9aa0a6;
                padding: 9px 18px;
                font-weight: bold;
                font-size: 12px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                margin-right: 3px;
                border: 1px solid #23272d;
                border-bottom: none;
            }
            QTabBar::tab:selected {
                background: #1e242b;
                color: #00e676;
                border-bottom: 2px solid #00e676;
            }
            QTabBar::tab:hover:!selected {
                background: #20262e;
                color: #e0e0e0;
            }
            QPushButton {
                background-color: #1f3a52;
                color: #ffffff;
                font-weight: bold;
                padding: 6px 14px;
                border-radius: 5px;
                border: 1px solid #2e5577;
            }
            QPushButton:hover { background-color: #2b5073; }
            QPushButton:pressed { background-color: #152c40; }
            QLineEdit, QComboBox {
                background-color: #1a1e24;
                color: #ffffff;
                border: 1px solid #333a42;
                padding: 6px 10px;
                border-radius: 5px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #00b0ff;
            }
            QTableWidget {
                background-color: #161a1e;
                color: #e0e0e0;
                gridline-color: #242930;
                selection-background-color: #1e354d;
                border: 1px solid #242930;
                border-radius: 5px;
            }
            QHeaderView::section {
                background-color: #1c2127;
                color: #90a4ae;
                padding: 6px;
                font-weight: bold;
                border: 1px solid #242930;
            }
            QProgressBar {
                border: 1px solid #333a42;
                border-radius: 4px;
                text-align: center;
                color: white;
                background-color: #1a1e24;
                font-size: 11px;
            }
            QProgressBar::chunk { background-color: #00b0ff; border-radius: 3px; }
            QGroupBox {
                border: 1px solid #262c35;
                border-radius: 6px;
                margin-top: 10px;
                font-weight: bold;
                color: #90caf9;
                padding: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QTextEdit {
                background-color: #14171a;
                color: #a5d6a7;
                font-family: Consolas, monospace;
                font-size: 11px;
                border: 1px solid #262c35;
                border-radius: 5px;
                padding: 6px;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(8)

        # === GLOBAL TOP HEADER ===
        header_bar = QHBoxLayout()
        header_title = QLabel("📈 NEPSE ALGORITHMIC QUANT SUITE")
        header_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        header_title.setStyleSheet("color: #ffffff; letter-spacing: 0.5px;")
        header_bar.addWidget(header_title)

        header_bar.addStretch()

        self.market_status_badge = QLabel("Checking NPT...")
        self.market_status_badge.setStyleSheet("color: #ffb74d; font-weight: bold; font-size: 11px; background-color: #21262d; padding: 4px 10px; border-radius: 4px;")
        header_bar.addWidget(self.market_status_badge)
        main_layout.addLayout(header_bar)

        # === MAIN TAB WIDGET ===
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # -----------------------------------------------------------------
        # TAB 1: 📊 SCREENER & TECHNICAL CHARTS
        # -----------------------------------------------------------------
        screener_tab = QWidget()
        screener_layout = QHBoxLayout(screener_tab)
        screener_layout.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        screener_layout.addWidget(splitter)

        # Left Column: Stock Table & Filtering
        left_widget = QWidget()
        left_col = QVBoxLayout(left_widget)
        left_col.setContentsMargins(0, 0, 4, 0)
        left_col.setSpacing(6)

        filter_bar = QHBoxLayout()
        filter_bar.addWidget(QLabel("Filter:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All Listed Stocks", "All Actionable Signals", "Momentum Breakouts", "Trend Pullbacks", "Oversold Dips", "Core Watchlist"])
        self.filter_combo.currentTextChanged.connect(self._handle_filter_change)
        filter_bar.addWidget(self.filter_combo)

        self.ticker_input = QLineEdit()
        self.ticker_input.setPlaceholderText("Symbol (e.g. UPPER)")
        filter_bar.addWidget(self.ticker_input)

        self.add_btn = QPushButton("Add")
        self.add_btn.setStyleSheet("background-color: #243542; color: #90caf9;")
        self.add_btn.clicked.connect(self._handle_add_ticker)
        filter_bar.addWidget(self.add_btn)

        self.run_btn = QPushButton("▶ Run Screener")
        self.run_btn.setStyleSheet("background-color: #00796b; color: white;")
        self.run_btn.clicked.connect(self._handle_run_screener)
        filter_bar.addWidget(self.run_btn)
        left_col.addLayout(filter_bar)

        # Watchlist Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Symbol", "LTP (Rs.)", "Chg %", "RSI(14)", "Vol Z-Score", "Signal Setup"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self._handle_table_selection)
        left_col.addWidget(self.table)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        left_col.addWidget(self.progress_bar)

        # Right Column: Chart Canvas & TradingView WebEngine
        right_widget = QWidget()
        right_col = QVBoxLayout(right_widget)
        right_col.setContentsMargins(4, 0, 0, 0)
        right_col.setSpacing(6)

        chart_bar = QHBoxLayout()
        self.chart_title_label = QLabel("Technical Verification")
        self.chart_title_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        chart_bar.addWidget(self.chart_title_label)
        chart_bar.addStretch()

        self.chart_mode_combo = QComboBox()
        self.chart_mode_combo.addItems(["Classic (Matplotlib)", "TradingView (Interactive)"])
        self.chart_mode_combo.currentTextChanged.connect(self._handle_chart_mode_change)
        chart_bar.addWidget(QLabel("Engine:"))
        chart_bar.addWidget(self.chart_mode_combo)

        self.browser_btn = QPushButton("↗ Open in Browser")
        self.browser_btn.setStyleSheet("background-color: #21262d; color: #80d8ff; font-size: 11px;")
        self.browser_btn.clicked.connect(self._handle_open_tradingview)
        chart_bar.addWidget(self.browser_btn)
        right_col.addLayout(chart_bar)

        self.chart_stack = QStackedWidget()
        self.canvas = ChartCanvas(self, width=8, height=7)
        self.chart_stack.addWidget(self.canvas)
        right_col.addWidget(self.chart_stack)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([560, 890])
        self.tab_widget.addTab(screener_tab, "📊 Screener & Charts")

        # -----------------------------------------------------------------
        # TAB 2: 🧠 MARKET PSYCHOLOGY & BREADTH
        # -----------------------------------------------------------------
        psychology_tab = QWidget()
        psy_layout = QVBoxLayout(psychology_tab)
        psy_layout.setContentsMargins(14, 14, 14, 14)
        psy_layout.setSpacing(12)

        # Metrics Summary Cards
        cards_row = QHBoxLayout()

        self.card_fg = QGroupBox("Retail Fear & Greed Index")
        card_fg_lay = QVBoxLayout(self.card_fg)
        self.fg_score_lbl = QLabel("-- / 100")
        self.fg_score_lbl.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        self.fg_score_lbl.setStyleSheet("color: #00e676;")
        self.fg_label_lbl = QLabel("Calculating...")
        self.fg_label_lbl.setStyleSheet("color: #b0bec5; font-size: 12px;")
        card_fg_lay.addWidget(self.fg_score_lbl)
        card_fg_lay.addWidget(self.fg_label_lbl)
        cards_row.addWidget(self.card_fg)

        self.card_breadth = QGroupBox("Daily Market Breadth (Advances vs Declines)")
        card_br_lay = QVBoxLayout(self.card_breadth)
        self.breadth_counts_lbl = QLabel("Advances: -- | Declines: -- | Unchanged: --")
        self.breadth_counts_lbl.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.breadth_ratio_lbl = QLabel("A/D Ratio: --")
        self.breadth_ratio_lbl.setStyleSheet("color: #90caf9; font-size: 11px;")
        card_br_lay.addWidget(self.breadth_counts_lbl)
        card_br_lay.addWidget(self.breadth_ratio_lbl)
        cards_row.addWidget(self.card_breadth)

        self.card_circuit = QGroupBox("Circuit Breakers & Turnover")
        card_cir_lay = QVBoxLayout(self.card_circuit)
        self.circuit_counts_lbl = QLabel("Upper (+10%): -- | Lower (-10%): --")
        self.circuit_counts_lbl.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.turnover_lbl = QLabel("Total Turnover: Rs. --")
        self.turnover_lbl.setStyleSheet("color: #ffb74d; font-size: 11px;")
        card_cir_lay.addWidget(self.circuit_counts_lbl)
        card_cir_lay.addWidget(self.turnover_lbl)
        cards_row.addWidget(self.card_circuit)

        psy_layout.addLayout(cards_row)

        # Historical Psychology Table
        psy_history_box = QGroupBox("Historical Market Psychology & Breadth Index (Past Sessions)")
        psy_hist_lay = QVBoxLayout(psy_history_box)

        psy_btn_bar = QHBoxLayout()
        psy_refresh_btn = QPushButton("🔄 Refresh Psychology")
        psy_refresh_btn.setStyleSheet("background-color: #243542; color: #90caf9; font-size: 11px;")
        psy_refresh_btn.clicked.connect(self._handle_refresh_psychology)
        psy_btn_bar.addStretch()
        psy_btn_bar.addWidget(psy_refresh_btn)
        psy_hist_lay.addLayout(psy_btn_bar)

        self.psychology_table = QTableWidget()
        self.psychology_table.setColumnCount(8)
        self.psychology_table.setHorizontalHeaderLabels([
            "Date", "Fear & Greed", "Advances", "Declines", "Unchanged", "A/D Ratio", "Upper Circuits", "Turnover (Rs.)"
        ])
        self.psychology_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        psy_hist_lay.addWidget(self.psychology_table)
        psy_layout.addWidget(psy_history_box)

        self.tab_widget.addTab(psychology_tab, "🧠 Market Psychology")

        # -----------------------------------------------------------------
        # TAB 3: 📰 FINANCIAL NEWS & POLICY
        # -----------------------------------------------------------------
        news_tab = QWidget()
        news_layout = QVBoxLayout(news_tab)
        news_layout.setContentsMargins(14, 14, 14, 14)
        news_layout.setSpacing(10)

        news_header = QHBoxLayout()
        news_header.addWidget(QLabel("Real-Time Financial Headlines, NRB Directives & Disclosures"))
        news_header.addStretch()

        self.news_refresh_btn = QPushButton("🔄 Fetch Latest News")
        self.news_refresh_btn.setStyleSheet("background-color: #243542; color: #90caf9;")
        self.news_refresh_btn.clicked.connect(self._handle_fetch_news)
        news_header.addWidget(self.news_refresh_btn)
        news_layout.addLayout(news_header)

        self.news_table = QTableWidget()
        self.news_table.setColumnCount(5)
        self.news_table.setHorizontalHeaderLabels([
            "Date / Time", "Source", "Category", "Sentiment", "Article Headline"
        ])
        self.news_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.news_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.news_table.setColumnWidth(0, 140)
        self.news_table.setColumnWidth(1, 160)
        self.news_table.setColumnWidth(2, 160)
        self.news_table.setColumnWidth(3, 100)
        news_layout.addWidget(self.news_table)

        self.tab_widget.addTab(news_tab, "📰 Daily News")

        # -----------------------------------------------------------------
        # TAB 4: ⚙ SETTINGS & CLOUD SYNC
        # -----------------------------------------------------------------
        settings_tab = QWidget()
        settings_layout = QVBoxLayout(settings_tab)
        settings_layout.setContentsMargins(14, 14, 14, 14)
        settings_layout.setSpacing(12)

        # Cloud Sync Group
        sync_group = QGroupBox("GitHub Cloud Sync & Market Universe")
        sync_lay = QHBoxLayout(sync_group)

        self.cloud_sync_btn = QPushButton("☁ Sync Cloud (GitHub)")
        self.cloud_sync_btn.setStyleSheet("background-color: #5c6bc0; color: white;")
        self.cloud_sync_btn.clicked.connect(getattr(self, "_handle_cloud_sync", lambda: None))
        sync_lay.addWidget(self.cloud_sync_btn)

        self.auto_sync_startup_cb = QCheckBox("Auto-sync database on startup")
        self.auto_sync_startup_cb.setStyleSheet("color: #bbdefb; font-size: 12px;")
        self.auto_sync_startup_cb.setChecked(getattr(self.controller, "get_auto_sync_startup", lambda: False)())
        self.auto_sync_startup_cb.toggled.connect(getattr(self, "_handle_toggle_auto_sync_startup", lambda checked: None))
        sync_lay.addWidget(self.auto_sync_startup_cb)

        self.sync_all_btn = QPushButton("Sync All 300+ Stocks")
        self.sync_all_btn.setStyleSheet("background-color: #37474f; color: white;")
        self.sync_all_btn.clicked.connect(self._handle_sync_all)
        sync_lay.addWidget(self.sync_all_btn)
        sync_lay.addStretch()
        settings_layout.addWidget(sync_group)

        # Automation Daemon & Updates Group
        daemon_group = QGroupBox("Automated Market Daemon & App Updates")
        daemon_lay = QHBoxLayout(daemon_group)

        self.auto_sched_btn = QPushButton("▶ Enable Auto-Scraping Daemon (10:45–2:45 NPT)")
        self.auto_sched_btn.setStyleSheet("background-color: #00796b; color: white;")
        self.auto_sched_btn.clicked.connect(self._toggle_auto_scheduler)
        daemon_lay.addWidget(self.auto_sched_btn)

        self.check_update_btn = QPushButton("🔄 Check for Updates")
        self.check_update_btn.setStyleSheet("background-color: #37474f; color: white;")
        self.check_update_btn.clicked.connect(lambda: self._handle_check_updates(silent=False))
        daemon_lay.addWidget(self.check_update_btn)
        daemon_lay.addStretch()
        settings_layout.addWidget(daemon_group)

        # System Logs Group
        log_group = QGroupBox("System Activity & Execution Logs")
        log_lay = QVBoxLayout(log_group)
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        log_lay.addWidget(self.log_box)
        settings_layout.addWidget(log_group)

        self.tab_widget.addTab(settings_tab, "⚙ Settings & Sync")

        # Status Bar
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("background-color: #111417; color: #9aa0a6; font-size: 11px;")
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready.")

    def _update_market_clock_display(self):
        cal = self.controller.calendar
        now_npt = cal.now_npt()
        time_str = now_npt.strftime("%I:%M:%S %p NPT")
        date_str = now_npt.strftime("%A, %b %d")

        is_open, reason = self.controller.get_market_status()
        if is_open:
            self.market_status_badge.setText(f"🟢 OPEN | {date_str} {time_str}")
            self.market_status_badge.setStyleSheet("color: #00e676; font-weight: bold; background-color: #1b2e22; padding: 4px 10px; border-radius: 4px;")
        else:
            self.market_status_badge.setText(f"🔴 CLOSED | {date_str} {time_str}")
            self.market_status_badge.setStyleSheet("color: #ff5252; font-weight: bold; background-color: #2b1d1d; padding: 4px 10px; border-radius: 4px;")

    def _toggle_auto_scheduler(self):
        if self.controller.is_scheduler_running():
            self.controller.stop_scheduler()
            self.auto_sched_btn.setText("▶ Enable Auto-Scraping Daemon (10:45–2:45 NPT)")
            self.auto_sched_btn.setStyleSheet("background-color: #00796b; color: white;")
            self.log_box.append("[Scheduler] Automated market daemon stopped.")
            self.status_bar.showMessage("Automated scheduler paused.", 4000)
        else:
            self.auto_sched_btn.setText("⏹ Stop Auto-Scraper Daemon")
            self.auto_sched_btn.setStyleSheet("background-color: #d32f2f; color: white;")
            self.log_box.append("[Scheduler] Automated market daemon active. Polling during trading window.")
            self.status_bar.showMessage("Automated scheduler active.", 4000)

            def on_status(msg):
                self.status_bar.showMessage(msg, 3000)
                self.log_box.append(f"[Live] {msg}")

            def on_ticker(sym, res):
                for row in range(self.table.rowCount()):
                    item = self.table.item(row, 0)
                    if item and item.text() == sym:
                        self._update_table_row(row, sym, res)
                        break

            def on_cycle_finished(results):
                self.log_box.append(f"[Scheduler Cycle] Finished processing {len(results)} stocks.")
                self._populate_table_from_cache()

            def on_holiday(msg):
                self.log_box.append(f"[Market Holiday] {msg}")

            self.controller.start_scheduler(
                poll_interval_minutes=1,
                on_status=on_status,
                on_ticker=on_ticker,
                on_cycle_finished=on_cycle_finished,
                on_holiday=on_holiday
            )

    def _handle_sync_all(self):
        self.sync_all_btn.setEnabled(False)
        self.log_box.append("Discovering and syncing all listed NEPSE securities...")

        def run_sync():
            count, msg = self.controller.sync_all_nepse_stocks()
            self.log_box.append(f"[Sync Complete] {msg}")
            _, p_msg = self.controller.sync_daily_market_psychology()
            self.log_box.append(f"[Psychology] {p_msg}")
            _, n_msg = self.controller.sync_daily_news()
            self.log_box.append(f"[News] {n_msg}")
            self._populate_table_from_cache()
            self._populate_psychology_tab()
            self._populate_news_tab()
            self.sync_all_btn.setEnabled(True)

        QTimer.singleShot(100, run_sync)

    def _handle_filter_change(self, text: str):
        self.current_filter = text
        self._populate_table_from_cache()

    def _populate_table_from_cache(self):
        all_symbols = self.controller.get_watchlist()
        latest_df = self.controller.get_latest_signals_df()

        signal_map = {}
        if not latest_df.empty:
            for _, row in latest_df.iterrows():
                signal_map[row["symbol"]] = row.to_dict()

        display_symbols = []
        if self.current_filter in ("All Actionable Signals", "Entry Signals Only"):
            display_symbols = [s for s in all_symbols if signal_map.get(s, {}).get("is_entry_signal", False)]
        elif self.current_filter == "Momentum Breakouts":
            display_symbols = [s for s in all_symbols if "BREAKOUT" in signal_map.get(s, {}).get("confirmation_notes", "")]
        elif self.current_filter == "Trend Pullbacks":
            display_symbols = [s for s in all_symbols if "PULLBACK" in signal_map.get(s, {}).get("confirmation_notes", "")]
        elif self.current_filter == "Oversold Dips":
            display_symbols = [s for s in all_symbols if "DIP" in signal_map.get(s, {}).get("confirmation_notes", "")]
        elif self.current_filter == "Core Watchlist":
            from config import DEFAULT_WATCHLIST
            display_symbols = [s for s in all_symbols if s in DEFAULT_WATCHLIST]
        else:
            display_symbols = all_symbols

        self.table.setRowCount(len(display_symbols))
        for row_idx, symbol in enumerate(display_symbols):
            data = signal_map.get(symbol, {})
            self._update_table_row(row_idx, symbol, data)

        if display_symbols:
            target_row = 0
            if self.selected_symbol and self.selected_symbol in display_symbols:
                target_row = display_symbols.index(self.selected_symbol)
            self.table.selectRow(target_row)

    def _update_table_row(self, row_idx: int, symbol: str, data: Dict[str, Any]):
        close = data.get("close", 0.0)
        chg = data.get("change_pct", 0.0)
        rsi = data.get("rsi_14", 0.0)
        zscore = data.get("vol_zscore", 0.0)
        is_entry = data.get("is_entry_signal", False)

        item_sym = QTableWidgetItem(symbol)
        item_sym.setFont(QFont("Arial", 9, QFont.Weight.Bold))

        item_close = QTableWidgetItem(f"{close:.2f}" if close else "--")
        if chg is not None and not (isinstance(chg, float) and np.isnan(chg)):
            item_chg = QTableWidgetItem(f"{float(chg):+.2f}%")
            if chg > 0:
                item_chg.setForeground(QBrush(QColor("#00e676")))
            elif chg < 0:
                item_chg.setForeground(QBrush(QColor("#ff5252")))
            else:
                item_chg.setForeground(QBrush(QColor("#b0bec5")))
        else:
            item_chg = QTableWidgetItem("--")

        item_rsi = QTableWidgetItem(f"{rsi:.1f}" if rsi else "--")
        if rsi and rsi < 30.0:
            item_rsi.setForeground(QBrush(QColor("#69f0ae")))
            item_rsi.setFont(QFont("Arial", 9, QFont.Weight.Bold))

        item_z = QTableWidgetItem(f"{zscore:+.2f}σ" if zscore else "--")
        if zscore and zscore >= 2.0:
            item_z.setForeground(QBrush(QColor("#ffb74d")))
            item_z.setFont(QFont("Arial", 9, QFont.Weight.Bold))

        notes = data.get("confirmation_notes", "")
        status_text = "Neutral"
        badge_fg = None
        badge_bg = None

        if "BREAKOUT" in notes:
            status_text = "🚀 BREAKOUT"
            badge_fg = QColor("#00e676")
            badge_bg = QColor("#143122")
        elif "PULLBACK" in notes:
            status_text = "📈 PULLBACK"
            badge_fg = QColor("#64b5f6")
            badge_bg = QColor("#102a43")
        elif "DIP" in notes:
            status_text = "🟢 DIP BUY"
            badge_fg = QColor("#69f0ae")
            badge_bg = QColor("#133926")
        elif "NEAR SETUP - Oversold" in notes or (rsi and rsi < 30.0):
            status_text = "🟡 Oversold"
            badge_fg = QColor("#ffd54f")
        elif "NEAR SETUP - Volume" in notes or (zscore and zscore >= 2.0):
            status_text = "🟡 Vol Surge"
            badge_fg = QColor("#ffb74d")

        item_status = QTableWidgetItem(status_text)
        item_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if badge_fg:
            item_status.setForeground(QBrush(badge_fg))
            item_status.setFont(QFont("Arial", 9, QFont.Weight.Bold))

        if is_entry:
            highlight = badge_bg if badge_bg else QColor(SIGNAL_HIGHLIGHT_COLOR)
            for item in (item_sym, item_close, item_chg, item_rsi, item_z, item_status):
                item.setBackground(QBrush(highlight))

        for col_idx, item in enumerate([item_sym, item_close, item_chg, item_rsi, item_z, item_status]):
            self.table.setItem(row_idx, col_idx, item)

    def _handle_table_selection(self):
        selected_rows = self.table.selectedItems()
        if not selected_rows:
            return
        row = selected_rows[0].row()
        symbol_item = self.table.item(row, 0)
        if not symbol_item:
            return
        symbol = symbol_item.text()
        if symbol != self.selected_symbol:
            self.selected_symbol = symbol
            self._render_current_chart(symbol)

    def _handle_add_ticker(self):
        raw = self.ticker_input.text().strip().upper()
        if not raw:
            return
        self.controller.add_ticker_to_watchlist(raw)
        self.ticker_input.clear()
        self.log_box.append(f"[Watchlist] Added {raw} to universe.")
        self._populate_table_from_cache()

    def _handle_run_screener(self):
        self.run_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.log_box.append("Initiating quantitative multi-factor screening across universe...")

        def on_started():
            self.status_bar.showMessage("Screening active universe...")

        def on_ticker_done(symbol: str, res: dict):
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item and item.text() == symbol:
                    self._update_table_row(row, symbol, res)
                    break
            if res.get("is_entry_signal"):
                self.log_box.append(f"🟢 [ENTRY SETUP] {symbol}: {res.get('confirmation_notes')}")

        def on_progress(current: int, total: int):
            percent = int((current / max(total, 1)) * 100)
            self.progress_bar.setValue(percent)

        def on_finished(results: list):
            self.run_btn.setEnabled(True)
            self.progress_bar.setVisible(False)
            self.status_bar.showMessage(f"Screener complete. Processed {len(results)} securities.", 5000)
            self.log_box.append(f"Screener finished. {len(results)} securities processed.")
            self._populate_table_from_cache()
            self._populate_psychology_tab()

        def on_error(err_msg: str):
            self.run_btn.setEnabled(True)
            self.progress_bar.setVisible(False)
            self.status_bar.showMessage(f"Error: {err_msg}", 5000)
            self.log_box.append(f"[Error] {err_msg}")

        self.controller.run_screener_async(
            on_started=on_started,
            on_ticker_done=on_ticker_done,
            on_progress=on_progress,
            on_finished=on_finished,
            on_error=on_error
        )

    def _deferred_startup(self):
        self._update_market_clock_display()
        self._populate_table_from_cache()
        self._populate_psychology_tab()
        self._populate_news_tab()
        if self.controller.get_auto_sync_startup():
            QTimer.singleShot(1500, self._handle_cloud_sync)
        QTimer.singleShot(4000, lambda: self._handle_check_updates(silent=True))

    def _ensure_web_view(self):
        if getattr(self, "web_view", None) is None and WEBENGINE_AVAILABLE:
            self.web_view = QWebEngineView()
            try:
                self.web_view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
                self.web_view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
                self.web_view.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
            except Exception as e:
                logger.warning(f"WebEngine settings error: {e}")
            self.chart_stack.addWidget(self.web_view)
        return self.web_view

    def _handle_toggle_auto_sync_startup(self, checked: bool):
        self.controller.set_auto_sync_startup(checked)
        status = "enabled" if checked else "disabled"
        self.status_bar.showMessage(f"Auto-sync on startup {status}.", 4000)
        self.log_box.append(f"Auto-sync on startup {status}.")

    def _handle_check_updates(self, silent: bool = False):
        if not silent:
            self.status_bar.showMessage("Checking GitHub for updates...", 4000)
            self.log_box.append("Checking GitHub Releases for application updates...")

        from view.updater_dialog import UpdateCheckWorker, UpdateDialog
        self._update_worker = UpdateCheckWorker()

        def on_result(has_update: bool, info: dict):
            if has_update:
                self.log_box.append(f"[Update Available] Found {info.get('tag_name')} on GitHub.")
                dlg = UpdateDialog(info, self)
                dlg.exec()
            else:
                if not silent:
                    from model.updater import APP_VERSION
                    from PyQt6.QtWidgets import QMessageBox
                    err = info.get("error")
                    if err:
                        QMessageBox.warning(self, "Update Check", f"Could not check for updates:\n{err}")
                    else:
                        QMessageBox.information(
                            self,
                            "Up to Date",
                            f"You are running the latest version (v{APP_VERSION})."
                        )

        self._update_worker.result_signal.connect(on_result)
        self._update_worker.start()

    def _handle_cloud_sync(self):
        self.log_box.append("Connecting to GitHub to download latest market database...")
        self.status_bar.showMessage("Syncing from GitHub...")
        success, msg = self.controller.sync_from_cloud()
        if success:
            self.log_box.append(f"[Cloud Sync] {msg}")
            self.status_bar.showMessage("GitHub sync complete.", 5000)
            self._populate_table_from_cache()
            self._populate_psychology_tab()
            self._populate_news_tab()
        else:
            self.log_box.append(f"[Cloud Sync Info] {msg}")
            self.status_bar.showMessage("Local database active.", 5000)

    def _handle_open_tradingview(self):
        wl = self.controller.get_watchlist()
        sym = self.selected_symbol or (wl[0] if wl else "NEPSE")
        self.selected_symbol = sym
        df = self.controller.get_historical_data(sym)
        if df.empty:
            seed_df = self.controller.ingestion.generate_synthetic_history(sym, n_days=260, base_price=420.0)
            self.controller.db.upsert_eod_data(sym, seed_df)
            df = self.controller.get_historical_data(sym)
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
            seed_df = self.controller.ingestion.generate_synthetic_history(symbol, n_days=260, base_price=450.0)
            self.controller.db.upsert_eod_data(symbol, seed_df)
            df = self.controller.get_historical_data(symbol)

        self.chart_title_label.setText(f"{symbol} — Quantitative Technical Analysis")

        mode = self.chart_mode_combo.currentText()
        if "TradingView" in mode:
            try:
                if getattr(self, "web_view", None) is None:
                    self._ensure_web_view()

                from .chart_canvas import export_tradingview_html
                out_file = export_tradingview_html(symbol, df)
                if self.web_view:
                    self.web_view.setUrl(QUrl.fromLocalFile(str(out_file.resolve())))
                    self.chart_stack.setCurrentWidget(self.web_view)
                    return
            except Exception as e:
                err_msg = f"[TradingView Note] In-App WebEngine: {e}. Defaulting to Classic Matplotlib."
                logger.warning(err_msg)
                self.log_box.append(err_msg)

        self.canvas.plot_stock(symbol, df)
        self.chart_stack.setCurrentWidget(self.canvas)

    def _populate_psychology_tab(self):
        """Populates Market Psychology & Breadth cards and historical table."""
        try:
            df = self.controller.db.get_market_psychology(limit=30)
            if df.empty:
                from model.engine import NepsePsychologyEngine
                engine = NepsePsychologyEngine(self.controller.db)
                engine.backfill_history(limit_days=30)
                df = self.controller.db.get_market_psychology(limit=30)

            if df.empty:
                return

            latest = df.iloc[0]
            fg = float(latest.get("fear_greed_score", 50.0))
            adv = int(latest.get("advances", 0))
            dec = int(latest.get("declines", 0))
            unc = int(latest.get("unchanged", 0))
            ad_r = float(latest.get("ad_ratio", 1.0))
            c_high = int(latest.get("circuit_high_count", 0))
            c_low = int(latest.get("circuit_low_count", 0))
            t_over = float(latest.get("total_turnover", 0.0))

            # Update top cards
            self.fg_score_lbl.setText(f"{fg:.1f} / 100")
            if fg >= 70:
                self.fg_score_lbl.setStyleSheet("color: #00e676; font-size: 20px; font-weight: bold;")
                self.fg_label_lbl.setText("Extreme Greed / Euphoria")
            elif fg >= 55:
                self.fg_score_lbl.setStyleSheet("color: #69f0ae; font-size: 20px; font-weight: bold;")
                self.fg_label_lbl.setText("Bullish Greed")
            elif fg <= 30:
                self.fg_score_lbl.setStyleSheet("color: #ff5252; font-size: 20px; font-weight: bold;")
                self.fg_label_lbl.setText("Extreme Fear / Panic")
            elif fg <= 45:
                self.fg_score_lbl.setStyleSheet("color: #ff8a80; font-size: 20px; font-weight: bold;")
                self.fg_label_lbl.setText("Bearish Fear")
            else:
                self.fg_score_lbl.setStyleSheet("color: #ffd54f; font-size: 20px; font-weight: bold;")
                self.fg_label_lbl.setText("Neutral Market")

            self.breadth_counts_lbl.setText(f"🟢 Advances: {adv} | 🔴 Declines: {dec} | ⚪ Unchanged: {unc}")
            self.breadth_ratio_lbl.setText(f"Market Breadth Ratio (A/D): {ad_r:.2f}")

            self.circuit_counts_lbl.setText(f"Upper (+10%): {c_high} | Lower (-10%): {c_low}")
            self.turnover_lbl.setText(f"Session Turnover: Rs. {t_over:,.2f}")

            # Populate table
            self.psychology_table.setRowCount(len(df))
            for r_idx, row in df.iterrows():
                d_str = str(row.get("date", ""))
                fg_val = f"{row.get('fear_greed_score', 0):.1f}"
                ad_cnt = str(row.get("advances", 0))
                dc_cnt = str(row.get("declines", 0))
                un_cnt = str(row.get("unchanged", 0))
                ad_rat = f"{row.get('ad_ratio', 0):.2f}"
                cir_h = str(row.get("circuit_high_count", 0))
                turn_s = f"Rs. {float(row.get('total_turnover', 0)):,.0f}"

                for c_idx, val in enumerate([d_str, fg_val, ad_cnt, dc_cnt, un_cnt, ad_rat, cir_h, turn_s]):
                    item = QTableWidgetItem(val)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.psychology_table.setItem(r_idx, c_idx, item)
        except Exception as e:
            logger.warning(f"Failed to populate psychology tab: {e}")

    def _handle_refresh_psychology(self):
        self.status_bar.showMessage("Calculating market breadth & sentiment...", 3000)
        from model.engine import NepsePsychologyEngine
        engine = NepsePsychologyEngine(self.controller.db)
        engine.backfill_history(limit_days=30)
        self._populate_psychology_tab()
        self.status_bar.showMessage("Market psychology refreshed.", 4000)

    def _populate_news_tab(self):
        """Populates Financial News & Policy Announcements table."""
        try:
            df = self.controller.db.get_recent_news(limit=50)
            if df.empty:
                return

            self.news_table.setRowCount(len(df))
            for r_idx, row in df.iterrows():
                ts = str(row.get("timestamp", ""))
                src = str(row.get("source", ""))
                cat = str(row.get("category", "General"))
                sent = float(row.get("sentiment_score", 0.0))
                sent_str = f"{sent:+.2f}"
                title = str(row.get("title", ""))

                item_ts = QTableWidgetItem(ts)
                item_src = QTableWidgetItem(src)
                item_cat = QTableWidgetItem(cat)
                item_sent = QTableWidgetItem(sent_str)
                item_title = QTableWidgetItem(title)

                item_sent.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if sent > 0.15:
                    item_sent.setForeground(QBrush(QColor("#00e676")))
                elif sent < -0.15:
                    item_sent.setForeground(QBrush(QColor("#ff5252")))

                for c_idx, item in enumerate([item_ts, item_src, item_cat, item_sent, item_title]):
                    self.news_table.setItem(r_idx, c_idx, item)
        except Exception as e:
            logger.warning(f"Failed to populate news tab: {e}")

    def _handle_fetch_news(self):
        self.news_refresh_btn.setEnabled(False)
        self.status_bar.showMessage("Fetching latest financial news...")

        def run_fetch():
            from model.market_scraper import NepseNewsScraper
            scraper = NepseNewsScraper(self.controller.db)
            count = scraper.scrape_and_save_all_news()
            self._populate_news_tab()
            self.status_bar.showMessage(f"News refreshed: {count} articles stored.", 4000)
            self.news_refresh_btn.setEnabled(True)

        QTimer.singleShot(100, run_fetch)


class CLIViewer:
    """Console / Terminal viewer used for headless environments and daemon modes."""
    @staticmethod
    def render_dashboard(controller, all_stocks: bool = False):
        import tabulate
        print("\n" + "=" * 90)
        print("   NEPSE ALGORITHMIC SCREENER & QUANTITATIVE SUITE (CLI DASHBOARD)")
        print("=" * 90)

        now_npt = controller.calendar.now_npt()
        is_open, reason = controller.get_market_status()
        status_tag = "🟢 OPEN" if is_open else "🔴 CLOSED"
        print(f"Current NPT Time: {now_npt.strftime('%A, %Y-%m-%d %I:%M:%S %p')} NPT | Market Status: {status_tag}")
        print(f"Operational Window: 10:45 AM - 02:45 PM NPT (Monday - Friday) | Reason: {reason}")
        print("-" * 90)

        if all_stocks:
            print("Syncing all NEPSE securities (300+ listed securities)...")
            count, msg = controller.sync_all_nepse_stocks()
            print(f"-> {msg}")
            _, p_msg = controller.sync_daily_market_psychology()
            print(f"-> [Psychology Index] {p_msg}")
            _, n_msg = controller.sync_daily_news()
            print(f"-> [Daily News] {n_msg}")

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
        target_sym = triggered[0] if triggered else (watchlist[0] if watchlist else "NHPC")

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
        print("\n" + "=" * 80)
        print(f"Starting NEPSE Scraper Daemon (Interval: {poll_interval_minutes}m)")
        print("=" * 80)

        def on_status(msg):
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

        def on_ticker(sym, res):
            pass

        def on_cycle_finished(results):
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Cycle finished: {len(results)} stocks evaluated.")

        def on_holiday(msg):
            print(f"[Holiday Notice] {msg}")

        controller.start_scheduler(
            poll_interval_minutes=poll_interval_minutes,
            on_status=on_status,
            on_ticker=on_ticker,
            on_cycle_finished=on_cycle_finished,
            on_holiday=on_holiday
        )

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down scheduler daemon...")
            controller.stop_scheduler()
            print("Daemon safely stopped.")
