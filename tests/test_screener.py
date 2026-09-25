"""
Unit and Integration Tests for NEPSE Algorithmic Screener & Scheduler.
"""
import sys
import unittest
from datetime import datetime
import numpy as np
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import NPT_TIMEZONE
from model.database import DatabaseManager
from model.engine import NepseTechnicalEngine
from model.screener import NepseScreener
from model.ingestion import NepseDataIngestion, NepseMarketCalendar, FullMarketScraper
from controller.controller import AppController
from view.chart_canvas import ChartCanvas

class TestNepseScreener(unittest.TestCase):
    def setUp(self):
        self.test_db_path = PROJECT_ROOT / "data" / "test_nepse.db"
        self.db = DatabaseManager(self.test_db_path)
        with self.db._get_connection() as conn:
            conn.execute("DELETE FROM signals;")
            conn.execute("DELETE FROM eod_prices;")
            conn.execute("DELETE FROM tickers;")
            conn.commit()

    def tearDown(self):
        if hasattr(self, "db") and self.db._effective_path.exists():
            try:
                self.db._effective_path.unlink()
            except Exception:
                pass

    def test_nepse_calendar_trading_days_and_hours(self):
        calendar = NepseMarketCalendar()

        # Monday at 11:30 AM NPT -> Trading day and trading hours
        mon_open = datetime(2026, 9, 21, 11, 30, tzinfo=NPT_TIMEZONE)
        self.assertTrue(calendar.is_trading_day(mon_open))
        self.assertTrue(calendar.is_within_market_hours(mon_open))

        # Monday at 09:30 AM NPT -> Trading day, but outside hours (< 10:45)
        mon_early = datetime(2026, 9, 21, 9, 30, tzinfo=NPT_TIMEZONE)
        self.assertTrue(calendar.is_trading_day(mon_early))
        self.assertFalse(calendar.is_within_market_hours(mon_early))

        # Monday at 15:00 NPT -> Trading day, but outside hours (> 14:45)
        mon_late = datetime(2026, 9, 21, 15, 15, tzinfo=NPT_TIMEZONE)
        self.assertTrue(calendar.is_trading_day(mon_late))
        self.assertFalse(calendar.is_within_market_hours(mon_late))

        # Saturday -> Non-trading day
        sat = datetime(2026, 9, 26, 12, 0, tzinfo=NPT_TIMEZONE)
        self.assertFalse(calendar.is_trading_day(sat))

    def test_nepse_public_holidays(self):
        calendar = NepseMarketCalendar()

        # Dashain Vijaya Dashami (2026-10-22)
        dashain = datetime(2026, 10, 22, 12, 0, tzinfo=NPT_TIMEZONE)
        is_hol, hol_name = calendar.is_public_holiday(dashain)
        self.assertTrue(is_hol)
        self.assertIn("Dashain", hol_name)

        # Normal trading day (e.g. 2026-09-21)
        normal_day = datetime(2026, 9, 21, 12, 0, tzinfo=NPT_TIMEZONE)
        is_hol, _ = calendar.is_public_holiday(normal_day)
        self.assertFalse(is_hol)

    def test_market_closure_announcement_detection(self):
        calendar = NepseMarketCalendar()

        html_with_notice = "<html><body><div class='banner'>Market is closed due to emergency holiday</div></body></html>"
        closed, reason = calendar.check_market_closure_announcement(html_with_notice)
        self.assertTrue(closed)
        self.assertIn("market is closed", reason.lower())

        html_normal = "<html><body><div>Live Trading Market Summary</div></body></html>"
        closed, _ = calendar.check_market_closure_announcement(html_normal)
        self.assertFalse(closed)

    def test_full_market_scraper_sync(self):
        scraper = FullMarketScraper(self.db)
        count, msg = scraper.sync_all_stocks_to_database(self.db)
        self.assertGreater(count, 50)

        all_tickers = self.db.get_watchlist()
        self.assertIn("NABIL", all_tickers)
        self.assertIn("NHPC", all_tickers)
        self.assertIn("SHIVM", all_tickers)

    def test_database_crud_and_caching(self):
        self.db.register_tickers(["NHPC", "RSML", "SHIVM", "SARBTM"])
        watchlist = self.db.get_watchlist()
        self.assertEqual(watchlist, ["NHPC", "RSML", "SARBTM", "SHIVM"])

        df = NepseDataIngestion.generate_synthetic_history("NHPC", n_days=50, base_price=300.0)
        self.db.upsert_eod_data("NHPC", df)
        retrieved = self.db.get_historical_eod("NHPC")
        self.assertEqual(len(retrieved), 50)

    def test_technical_engine_indicators(self):
        df = NepseDataIngestion.generate_synthetic_history("SHIVM", n_days=100, base_price=500.0)
        enriched = NepseTechnicalEngine.enrich_dataframe(df)

        self.assertTrue("rsi_14" in enriched.columns)
        self.assertTrue("sma_50" in enriched.columns)
        self.assertTrue("vol_mean_20" in enriched.columns)
        self.assertTrue("vol_zscore" in enriched.columns)
        self.assertTrue("vol_spike" in enriched.columns)

    def test_signal_generation_entry_condition(self):
        df_triggered = NepseDataIngestion.generate_synthetic_history(
            "NHPC", n_days=100, base_price=300.0, trigger_signal=True
        )
        screener = NepseScreener(rsi_threshold=30.0)
        result = screener.evaluate_latest_bar("NHPC", df_triggered)

        self.assertTrue(result["is_entry_signal"])
        self.assertLess(result["rsi_14"], 30.0)
        self.assertTrue(result["vol_spike"])

if __name__ == "__main__":
    unittest.main()
