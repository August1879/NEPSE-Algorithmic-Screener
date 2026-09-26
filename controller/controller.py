"""
Application Controller for MVC Pattern.
Glues together the Database, Ingestion, Technical Engine, Calendar, Scheduler, and UI events.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd

from config import DB_PATH, DEFAULT_WATCHLIST
from model.database import DatabaseManager
from model.engine import NepseTechnicalEngine
from model.screener import NepseScreener
from model.ingestion import NepseDataIngestion, NepseMarketCalendar, FullMarketScraper
from .worker import ScreenerWorker, NepseMarketScheduler


logger = logging.getLogger(__name__)

class AppController:
    def __init__(self, db_path=DB_PATH):
        self.db = DatabaseManager(db_path)
        self.ingestion = NepseDataIngestion()
        self.screener = NepseScreener()
        self.calendar = NepseMarketCalendar()
        self.full_market_scraper = FullMarketScraper(self.db)
        self.worker: Optional[ScreenerWorker] = None
        self.scheduler: Optional[NepseMarketScheduler] = None
        self._init_system()

    def _init_system(self):
        existing_watchlist = self.db.get_watchlist()
        if not existing_watchlist:
            logger.info("Initializing database with default watchlist: %s", DEFAULT_WATCHLIST)
            self.db.register_tickers(DEFAULT_WATCHLIST)
            for sym in DEFAULT_WATCHLIST:
                should_trigger = (sym in ["SHIVM", "NHPC"])
                seed_df = self.ingestion.generate_synthetic_history(
                    sym, n_days=260, base_price=420.0, trigger_signal=should_trigger
                )
                self.db.upsert_eod_data(sym, seed_df)

    def get_watchlist(self) -> List[str]:
        return self.db.get_watchlist()

    def add_ticker_to_watchlist(self, symbol: str):
        sym = symbol.upper().strip()
        if sym:
            self.db.register_tickers([sym])
            hist = self.db.get_historical_eod(sym)
            if hist.empty:
                seed_df = self.ingestion.generate_synthetic_history(sym, n_days=260, base_price=350.0)
                self.db.upsert_eod_data(sym, seed_df)

    def get_historical_data(self, symbol: str, limit: int = 250) -> pd.DataFrame:
        raw_df = self.db.get_historical_eod(symbol, limit=limit)
        if raw_df.empty:
            return raw_df
        return NepseTechnicalEngine.enrich_dataframe(raw_df)

    def process_single_ticker_pipeline(self, symbol: str) -> Dict[str, Any]:
        df = self.db.get_historical_eod(symbol)
        if df.empty or len(df) < 25:
            last_price = float(df['close'].iloc[-1]) if not df.empty else 300.0
            base_df = self.ingestion.generate_synthetic_history(symbol, n_days=260, base_price=last_price)
            self.db.upsert_eod_data(symbol, base_df)
            df = self.db.get_historical_eod(symbol)

        enriched = NepseTechnicalEngine.enrich_dataframe(df)
        result = self.screener.evaluate_latest_bar(symbol, enriched)
        self.db.save_signals([result])
        return result

    def run_screener_async(
        self,
        symbols: Optional[List[str]] = None,
        on_started: Optional[callable] = None,
        on_ticker_done: Optional[callable] = None,
        on_progress: Optional[callable] = None,
        on_finished: Optional[callable] = None,
        on_error: Optional[callable] = None
    ) -> ScreenerWorker:
        target_symbols = symbols or self.get_watchlist()
        self.worker = ScreenerWorker(target_symbols, self.process_single_ticker_pipeline)

        if on_started:
            self.worker.started_screening.connect(on_started)
        if on_ticker_done:
            self.worker.ticker_processed.connect(on_ticker_done)
        if on_progress:
            self.worker.progress_updated.connect(on_progress)
        if on_finished:
            self.worker.finished_screening.connect(on_finished)
        if on_error:
            self.worker.error_occurred.connect(on_error)

        self.worker.start()
        return self.worker

    def start_automated_scheduler(
        self,
        on_status: Optional[callable] = None,
        on_ticker: Optional[callable] = None,
        on_cycle_finished: Optional[callable] = None,
        on_holiday: Optional[callable] = None,
        poll_interval_minutes: int = 1
    ) -> NepseMarketScheduler:
        if self.scheduler and self.scheduler.isRunning():
            logger.info("Scheduler already active.")
            return self.scheduler

        self.scheduler = NepseMarketScheduler(self, poll_interval_minutes=poll_interval_minutes)

        if on_status:
            self.scheduler.status_updated.connect(on_status)
        if on_ticker:
            self.scheduler.ticker_scraped.connect(on_ticker)
        if on_cycle_finished:
            self.scheduler.cycle_finished.connect(on_cycle_finished)
        if on_holiday:
            self.scheduler.holiday_or_closed.connect(on_holiday)

        self.scheduler.start()
        return self.scheduler

    def stop_automated_scheduler(self):
        if self.scheduler:
            self.scheduler.stop()
            self.scheduler = None

    def get_market_status(self) -> Tuple[bool, str]:
        return self.calendar.is_market_open_now()

    def sync_all_nepse_stocks(self) -> Tuple[int, str]:
        return self.full_market_scraper.sync_all_stocks_to_database(self.db)

    def get_latest_signals_df(self) -> pd.DataFrame:
        return self.db.get_latest_signals()

    def sync_from_cloud(self) -> Tuple[bool, str]:
        """Pulls latest market database from GitHub repository."""
        from config import GITHUB_RAW_DB_URL, DB_PATH
        from model.ingestion import sync_database_from_github
        success, msg = sync_database_from_github(GITHUB_RAW_DB_URL, DB_PATH)
        if success:
            self.db._init_db()
        return success, msg

    def get_auto_sync_startup(self) -> bool:
        from config import get_auto_sync_on_startup
        return get_auto_sync_on_startup()

    def set_auto_sync_startup(self, enabled: bool):
        from config import set_auto_sync_on_startup
        set_auto_sync_on_startup(enabled)
