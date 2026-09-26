"""
Game-style Loading Screen for NEPSE Algorithmic Screener.
Opens instantaneously (< 0.2s) upon launch, showing a dynamic progress bar,
system initialization stages, and a rotating slideshow of trading tips and market wisdom
while heavy dependencies and models load asynchronously in the background.
"""
import sys
import time
from typing import Optional, List, Tuple
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QFrame, QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer

TRADING_TIPS: List[Tuple[str, str, str]] = [
    (
        "RISK MANAGEMENT",
        "The 2% Golden Rule",
        "Never risk more than 1% to 2% of your portfolio on any single NEPSE position. Capital preservation is prerequisite to longevity in equity trading."
    ),
    (
        "VOLUME CONVICTION",
        "Volume Precedes Price",
        "A breakout with volume Z-score > +2.0σ confirms institutional accumulation. Breakouts on thin volume frequently trap retail breakout buyers."
    ),
    (
        "MOMENTUM & PULLBACKS",
        "RSI Divergence Setup",
        "RSI(14) dropping below 30 signals oversold exhaustion. Look for price to form a higher low with an expanding MACD histogram before triggering entries."
    ),
    (
        "MOVING AVERAGE HIERARCHY",
        "The 200 SMA Anchor",
        "Only trade aggressive long swings when price trades above the 200-day Simple Moving Average. Trading below the 200 SMA carries negative expectancy."
    ),
    (
        "STATISTICAL VOLATILITY",
        "Relative Volatility Bands (RMS ±2σ)",
        "When price touches the lower 2-sigma RMS volatility band while RSI is oversold, the probability of mean-reversion toward the 20-day SMA is statistically maximized."
    ),
    (
        "NEPSE TIMING",
        "Market Hours & Liquidity Windows",
        "NEPSE operates Sunday–Thursday 11:00 AM to 3:00 PM NPT. Institutional volume clusters between 11:15 AM - 1:00 PM; avoid chasing illiquid opening ticks."
    ),
    (
        "PSYCHOLOGY & DISCIPLINE",
        "Algorithmic Objectivity",
        "Follow your systematic screening criteria without emotion. Hope is not an investment strategy; predefined stop losses eliminate catastrophic drawdowns."
    ),
    (
        "PROFIT ASYMMETRY",
        "Cut Losers, Let Winners Run",
        "A 10% loss takes an 11% gain to recover, but a 50% loss requires a 100% gain. Keep stop-losses tight and trail winning runners along the 20 SMA."
    ),
]

class InitializationWorker(QThread):
    progress_signal = pyqtSignal(int, str)
    finished_signal = pyqtSignal(object)
    error_signal = pyqtSignal(str)

    def __init__(self, cli_args=None):
        super().__init__()
        self.cli_args = cli_args

    def run(self):
        try:
            self.progress_signal.emit(10, "Mounting SQLite database cache...")
            time.sleep(0.12)

            self.progress_signal.emit(25, "Loading technical calculation libraries...")
            from controller.controller import AppController
            from view.gui import NepseScreenerMainWindow
            time.sleep(0.15)

            self.progress_signal.emit(50, "Calibrating NEPSE trading calendar (NPT)...")
            controller = AppController()
            if self.cli_args and getattr(self.cli_args, "add", None):
                controller.add_ticker_to_watchlist(self.cli_args.add)
            time.sleep(0.15)

            self.progress_signal.emit(75, "Validating core watchlist & technical indicators...")
            time.sleep(0.12)

            self.progress_signal.emit(90, "Assembling dark-mode desktop dashboard...")
            window = NepseScreenerMainWindow(controller)
            time.sleep(0.12)

            self.progress_signal.emit(100, "System ready. Welcome to NEPSE Screener.")
            time.sleep(0.1)

            self.finished_signal.emit(window)
        except Exception as e:
            import traceback
            self.error_signal.emit(traceback.format_exc())

class GameLoadingWindow(QWidget):
    def __init__(self, cli_args=None):
        super().__init__()
        self.cli_args = cli_args
        self.current_tip_index = 0
        self.main_window: Optional[QWidget] = None
        self._init_ui()
        self._start_tips_rotator()
        self._start_worker()

    def _init_ui(self):
        self.setWindowTitle("NEPSE Screener — Loading Engine")
        self.setFixedSize(740, 460)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)

        self.setStyleSheet("""
            QWidget {
                background-color: #0e1217;
                color: #e6edf3;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QFrame#mainCard {
                background-color: #141922;
                border: 2px solid #26a69a;
                border-radius: 12px;
            }
            QFrame#tipBox {
                background-color: #1a2230;
                border: 1px solid #303c50;
                border-radius: 8px;
            }
            QProgressBar {
                background-color: #0b0e14;
                border: 1px solid #283344;
                border-radius: 6px;
                text-align: center;
                color: #00e676;
                font-weight: bold;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00796b, stop:0.5 #26a69a, stop:1 #00e676);
                border-radius: 5px;
            }
        """)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("mainCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 32, 36, 28)
        card_layout.setSpacing(18)

        # Top Header
        top_header = QHBoxLayout()
        header_title = QLabel("NEPSE ALGORITHMIC SCREENER")
        header_title.setStyleSheet("font-size: 19px; font-weight: bold; color: #ffffff; letter-spacing: 1px;")
        
        status_pill = QLabel("SYSTEM BOOT")
        status_pill.setStyleSheet("""
            background-color: #004d40;
            color: #64ffda;
            padding: 4px 10px;
            font-size: 10px;
            font-weight: bold;
            border-radius: 4px;
            border: 1px solid #00bfa5;
        """)
        top_header.addWidget(header_title)
        top_header.addStretch()
        top_header.addWidget(status_pill)
        card_layout.addLayout(top_header)

        sub_header = QLabel("High-Performance Quantitative Screening & Technical Engine for Nepal Stock Exchange")
        sub_header.setStyleSheet("color: #8b949e; font-size: 11px;")
        card_layout.addWidget(sub_header)

        # Middle Section: Rotating Tips Box
        tip_frame = QFrame()
        tip_frame.setObjectName("tipBox")
        tip_layout = QVBoxLayout(tip_frame)
        tip_layout.setContentsMargins(22, 16, 22, 18)
        tip_layout.setSpacing(8)

        self.tip_category_label = QLabel("TRADING PROTOCOL & PSYCHOLOGY")
        self.tip_category_label.setStyleSheet("color: #ffb74d; font-size: 10px; font-weight: bold; letter-spacing: 1.5px;")
        tip_layout.addWidget(self.tip_category_label)

        self.tip_title_label = QLabel("The 2% Golden Rule")
        self.tip_title_label.setStyleSheet("color: #ffffff; font-size: 15px; font-weight: bold;")
        tip_layout.addWidget(self.tip_title_label)

        self.tip_body_label = QLabel(TRADING_TIPS[0])
        self.tip_body_label.setWordWrap(True)
        self.tip_body_label.setStyleSheet("color: #c9d1d9; font-size: 12px; line-height: 1.5;")
        tip_layout.addWidget(self.tip_body_label)

        card_layout.addWidget(tip_frame)

        # Lower Section: Status & Progress
        progress_info = QHBoxLayout()
        self.status_label = QLabel("Initializing core components...")
        self.status_label.setStyleSheet("color: #58a6ff; font-size: 12px; font-weight: bold;")
        
        self.percent_label = QLabel("0%")
        self.percent_label.setStyleSheet("color: #00e676; font-size: 13px; font-weight: bold;")
        
        progress_info.addWidget(self.status_label)
        progress_info.addStretch()
        progress_info.addWidget(self.percent_label)
        card_layout.addLayout(progress_info)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(18)
        self.progress_bar.setTextVisible(False)
        card_layout.addWidget(self.progress_bar)

        # Footer
        footer_layout = QHBoxLayout()
        footer_npt = QLabel("NPT Timezone: UTC+5:45 | Market Window: Sun-Thu 11:00-15:00")
        footer_npt.setStyleSheet("color: #6e7681; font-size: 10px;")
        footer_ver = QLabel("v1.2.1 High-Performance Desktop Release")
        footer_ver.setStyleSheet("color: #6e7681; font-size: 10px;")
        footer_layout.addWidget(footer_npt)
        footer_layout.addStretch()
        footer_layout.addWidget(footer_ver)
        card_layout.addLayout(footer_layout)

        outer_layout.addWidget(card)
        self._center_on_screen()

    def _center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = (geo.width() - self.width()) // 2
            y = (geo.height() - self.height()) // 2
            self.move(x, y)

    def _start_tips_rotator(self):
        self.tip_timer = QTimer(self)
        self.tip_timer.timeout.connect(self._rotate_tip)
        self.tip_timer.start(2500)

    def _rotate_tip(self):
        self.current_tip_index = (self.current_tip_index + 1) % len(TRADING_TIPS)
        category, title, body = TRADING_TIPS[self.current_tip_index]
        self.tip_category_label.setText(f"TRADING WISDOM // {category}")
        self.tip_title_label.setText(title)
        self.tip_body_label.setText(body)

    def _start_worker(self):
        self.worker = InitializationWorker(self.cli_args)
        self.worker.progress_signal.connect(self._on_progress)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.error_signal.connect(self._on_error)
        self.worker.start()

    def _on_progress(self, val: int, message: str):
        self.progress_bar.setValue(val)
        self.percent_label.setText(f"{val}%")
        self.status_label.setText(message)

    def _on_finished(self, main_window):
        self.tip_timer.stop()
        self.main_window = main_window
        self.main_window.show()
        self.close()

    def _on_error(self, err_trace: str):
        self.status_label.setText("Error during initialization.")
        self.status_label.setStyleSheet("color: #ff5252; font-weight: bold;")
        with open("crash_log.txt", "w", encoding="utf-8") as f:
            f.write(err_trace)
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, "Startup Error:\n\n" + err_trace, "NEPSE Screener Error", 0x10)
        except Exception:
            pass
