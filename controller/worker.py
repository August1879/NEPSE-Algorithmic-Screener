"""
Asynchronous Worker Threads.
Includes:
1. ScreenerWorker: Evaluates technical calculations for given tickers.
2. NepseMarketScheduler: Runs Monday to Friday at 11:00 AM NST, checks market status,
   scrapes live data of all stocks continuously until market close (3:00 PM NST),
   and synchronizes the database to GitHub.
"""
import time
import threading
import logging
from typing import List, Dict, Any, Callable, Optional
from datetime import datetime

from config import LIVE_POLL_INTERVAL_MINUTES, SESSION_CLOSE_HOUR, SESSION_CLOSE_MINUTE
from model.ingestion import NepseMarketCalendar, FullMarketScraper, GitSyncManager

logger = logging.getLogger(__name__)

try:
    from PyQt6.QtCore import QThread, pyqtSignal
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    class QThread:
        def __init__(self):
            self._thread = None
        def start(self):
            self._thread = threading.Thread(target=self.run, daemon=True)
            self._thread.start()
        def isRunning(self):
            return self._thread.is_alive() if self._thread else False

    class _MockSignal:
        def __init__(self):
            self._callbacks = []
        def connect(self, callback: Callable):
            self._callbacks.append(callback)
        def emit(self, *args, **kwargs):
            for cb in self._callbacks:
                try:
                    cb(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Signal callback error: {e}")

    def pyqtSignal(*types):
        return _MockSignal()


class ScreenerWorker(QThread):
    if PYQT_AVAILABLE:
        started_screening = pyqtSignal()
        ticker_processed = pyqtSignal(str, dict)
        progress_updated = pyqtSignal(int, int)
        finished_screening = pyqtSignal(list)
        error_occurred = pyqtSignal(str)
    else:
        def __init__(self, watchlist, pipeline_func):
            super().__init__()
            self.watchlist = watchlist
            self.pipeline_func = pipeline_func
            self.started_screening = _MockSignal()
            self.ticker_processed = _MockSignal()
            self.progress_updated = _MockSignal()
            self.finished_screening = _MockSignal()
            self.error_occurred = _MockSignal()

    def __init__(self, watchlist: List[str], pipeline_func: Callable[[str], Dict[str, Any]]):
        super().__init__()
        self.watchlist = watchlist
        self.pipeline_func = pipeline_func
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            self.started_screening.emit()
            total = len(self.watchlist)
            results = []

            for idx, symbol in enumerate(self.watchlist, start=1):
                if self._is_cancelled:
                    logger.info("Screener worker cancelled by user.")
                    break

                try:
                    result = self.pipeline_func(symbol)
                    results.append(result)
                    self.ticker_processed.emit(symbol, result)
                except Exception as e:
                    logger.error(f"Error processing {symbol}: {e}")
                    self.error_occurred.emit(f"Failed {symbol}: {str(e)}")

                self.progress_updated.emit(idx, total)

            self.finished_screening.emit(results)
        except Exception as e:
            logger.exception("Fatal worker thread exception")
            self.error_occurred.emit(str(e))


class NepseMarketScheduler(QThread):
    """
    Automated daemon:
    - Triggers Monday - Friday at 11:00 AM NST.
    - Checks holiday calendar and live portal closure announcements.
    - If market is open, continuously scrapes live prices across all stocks until close (3:00 PM NST).
    - Upon market close, commits and pushes the updated database and summaries to GitHub.
    """
    if PYQT_AVAILABLE:
        status_updated = pyqtSignal(str)
        cycle_started = pyqtSignal()
        ticker_scraped = pyqtSignal(str, dict)
        cycle_finished = pyqtSignal(list)
        holiday_or_closed = pyqtSignal(str)
        git_sync_completed = pyqtSignal(str)

    def __init__(self, controller, poll_interval_minutes: int = LIVE_POLL_INTERVAL_MINUTES):
        super().__init__()
        self.controller = controller
        self.poll_interval_seconds = poll_interval_minutes * 60
        self.calendar = NepseMarketCalendar()
        self.market_scraper = FullMarketScraper(controller.db)
        self.git_sync = GitSyncManager()
        self._running = False
        self._force_scrape_event = threading.Event()

        if not PYQT_AVAILABLE:
            self.status_updated = _MockSignal()
            self.cycle_started = _MockSignal()
            self.ticker_scraped = _MockSignal()
            self.cycle_finished = _MockSignal()
            self.holiday_or_closed = _MockSignal()
            self.git_sync_completed = _MockSignal()

    def stop(self):
        self._running = False
        self._force_scrape_event.set()

    def force_scrape_now(self):
        self._force_scrape_event.set()

    def run(self):
        self._running = True
        logger.info("NEPSE Market-Session Scheduler started.")

        while self._running:
            now_npt = self.calendar.now_npt()
            is_open, reason = self.calendar.is_market_open_now()

            # If market is not in session (weekend, holiday, before 11am, or after 3pm)
            if not is_open:
                next_trigger = self.calendar.get_next_11am_trigger_datetime(now_npt)
                status_msg = f"Market Inactive: {reason}. Next Check: {next_trigger.strftime('%a %Y-%m-%d 11:00 AM')} NST"
                self.status_updated.emit(status_msg)
                self.holiday_or_closed.emit(status_msg)
                logger.info(status_msg)

                # Wait for 30s or until forced/stopped
                if self._force_scrape_event.wait(timeout=30.0):
                    self._force_scrape_event.clear()
                    if not self._running:
                        break
                    # Force run single cycle
                    self._execute_live_scrape_cycle()
                continue

            # Market IS OPEN at/after 11:00 AM NST!
            logger.info("Market session is LIVE. Commencing continuous live scraping until 3:00 PM close...")
            self.status_updated.emit(f"Market LIVE ({now_npt.strftime('%I:%M %p NST')}). Scraping all stocks...")

            # Run continuous live polling loop until market closes
            while self._running and self.calendar.is_within_market_hours():
                loop_now = self.calendar.now_npt()
                self.status_updated.emit(f"Scraping live market: {loop_now.strftime('%I:%M:%S %p NST')}...")
                self._execute_live_scrape_cycle()

                # Check if market has closed
                if self.calendar.is_after_market_close():
                    break

                # Wait for poll interval (e.g. 5 minutes)
                logger.info(f"Live poll round completed. Next live refresh in {self.poll_interval_seconds // 60}m.")
                self.status_updated.emit(f"Market Active. Next live sync in {self.poll_interval_seconds // 60}m.")
                if self._force_scrape_event.wait(timeout=self.poll_interval_seconds):
                    self._force_scrape_event.clear()

            # Market has closed for the day (>= 3:00 PM NST or closed notice)
            close_time_str = self.calendar.now_npt().strftime("%I:%M %p NST")
            close_msg = f"Trading session ended at {close_time_str}. Finalizing EOD data & syncing to GitHub..."
            self.status_updated.emit(close_msg)
            logger.info(close_msg)

            # Post-market GitHub Repository Sync
            success, git_msg = self.git_sync.commit_and_push(self.controller.db)
            self.git_sync_completed.emit(git_msg)
            logger.info(f"GitHub Sync Result: {git_msg}")
            self.status_updated.emit(f"EOD Complete. {git_msg}")

            # Sleep until next day 11:00 AM
            next_session = self.calendar.get_next_11am_trigger_datetime()
            logger.info(f"Session finished. Next 11:00 AM check at: {next_session}")
            time.sleep(60)

        logger.info("NEPSE Market Scheduler stopped.")

    def _execute_live_scrape_cycle(self):
        """Scrapes all stocks and evaluates indicators."""
        self.cycle_started.emit()
        try:
            count, sync_msg = self.market_scraper.sync_all_stocks_to_database(self.controller.db)
            logger.info(sync_msg)

            all_symbols = self.controller.db.get_watchlist()
            results = []

            for sym in all_symbols:
                if not self._running:
                    break
                try:
                    res = self.controller.process_single_ticker_pipeline(sym)
                    results.append(res)
                    self.ticker_scraped.emit(sym, res)
                except Exception as e:
                    logger.error(f"Error screening {sym}: {e}")

            self.cycle_finished.emit(results)
            logger.info(f"Live market cycle completed: {len(results)} stocks updated.")

        except Exception as e:
            err = f"Error during live market scrape: {e}"
            logger.exception(err)
            self.status_updated.emit(err)
