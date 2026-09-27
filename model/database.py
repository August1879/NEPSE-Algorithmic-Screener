import numpy as np
"""
SQLite Caching & Persistence Layer.
Minimizes network calls by maintaining local historical baseline data.
Includes robust fallback for network/FUSE mounted filesystems.
"""
import sqlite3
from typing import List, Optional, Dict, Any, Tuple
import pandas as pd
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._effective_path = self.db_path
        self._test_and_fallback_connection()
        self._init_db()

    def _test_and_fallback_connection(self):
        """Tests if path supports SQLite file locking; falls back to /tmp if filesystem lacks POSIX locking."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            test_conn = sqlite3.connect(self.db_path)
            test_conn.execute("CREATE TABLE IF NOT EXISTS _fs_test (id INT);")
            test_conn.execute("DROP TABLE _fs_test;")
            test_conn.close()
            self._effective_path = self.db_path
        except sqlite3.OperationalError as e:
            # Fall back to /tmp on network/FUSE environments
            tmp_path = Path("/tmp") / "nepse_data" / self.db_path.name
            tmp_path.parent.mkdir(parents=True, exist_ok=True)
            logger.warning(f"Filesystem at {self.db_path} does not support SQLite file locking ({e}). Falling back to {tmp_path}")
            self._effective_path = tmp_path

    from contextlib import contextmanager
    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self._effective_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        """Initializes database schema with proper indexes for fast time-series retrieval."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Tickers table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tickers (
                    symbol TEXT PRIMARY KEY,
                    company_name TEXT,
                    sector TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Historical EOD prices
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS eod_prices (
                    symbol TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    turnover REAL,
                    PRIMARY KEY (symbol, date)
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_eod_symbol_date ON eod_prices(symbol, date);")
            # 1-minute intraday ticks
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS intraday_prices (
                    symbol TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    ltp REAL NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    volume REAL,
                    turnover REAL,
                    PRIMARY KEY (symbol, timestamp)
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_intraday_symbol_time ON intraday_prices(symbol, timestamp);")

            # Screener signals log
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    symbol TEXT NOT NULL,
                    date TEXT NOT NULL,
                    close REAL,
                    rsi_14 REAL,
                    volume REAL,
                    vol_mean_20 REAL,
                    vol_std_20 REAL,
                    vol_zscore REAL,
                    sma_50 REAL,
                    sma_200 REAL,
                    is_entry_signal INTEGER NOT NULL,
                    confirmation_notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (symbol, date)
                );
            """)

            # Market Psychology & Daily Breadth
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS market_psychology (
                    date TEXT PRIMARY KEY,
                    total_turnover REAL,
                    total_volume REAL,
                    advances INTEGER,
                    declines INTEGER,
                    unchanged INTEGER,
                    ad_ratio REAL,
                    circuit_high_count INTEGER,
                    circuit_low_count INTEGER,
                    fear_greed_score REAL,
                    sentiment_summary TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Daily Financial & Policy News
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    source TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT,
                    url TEXT UNIQUE,
                    category TEXT,
                    sentiment_score REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_news_date ON daily_news(date);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_news_url ON daily_news(url);")
            conn.commit()

    def register_tickers(self, symbols: List[str]):
        """Ensures watchlist tickers are registered in DB."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for sym in symbols:
                cursor.execute("""
                    INSERT INTO tickers (symbol, is_active)
                    VALUES (?, 1)
                    ON CONFLICT(symbol) DO UPDATE SET is_active=1
                """, (sym.upper().strip(),))
            conn.commit()

    def get_watchlist(self) -> List[str]:
        """Returns list of active watchlist symbols."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT symbol FROM tickers WHERE is_active=1 ORDER BY symbol ASC")
            rows = cursor.fetchall()
            return [row["symbol"] for row in rows]

    def upsert_eod_data(self, symbol: str, df: pd.DataFrame):
        """
        Inserts or replaces historical EOD bars.
        Expects df with columns: date (str or datetime), open, high, low, close, volume.
        """
        if df.empty:
            return

        clean_df = df.copy()
        if "date" in clean_df.columns:
            clean_df["date"] = pd.to_datetime(clean_df["date"]).dt.strftime("%Y-%m-%d")
        else:
            from datetime import datetime
            clean_df["date"] = datetime.now().strftime("%Y-%m-%d")

        def _safe_float(val, fallback=0.0):
            if val is None or pd.isna(val):
                return float(fallback)
            try:
                f = float(val)
                return float(fallback) if np.isnan(f) else f
            except (ValueError, TypeError):
                return float(fallback)

        records = []
        for _, row in clean_df.iterrows():
            c = _safe_float(row.get("close"), 0.0)
            o = _safe_float(row.get("open"), c)
            h = _safe_float(row.get("high"), max(o, c))
            l = _safe_float(row.get("low"), min(o, c))
            v = _safe_float(row.get("volume"), 0.0)
            t = _safe_float(row.get("turnover"), round(c * v, 2))

            records.append((
                symbol.upper().strip(),
                str(row["date"]),
                o,
                h,
                l,
                c,
                v,
                t
            ))

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT INTO eod_prices (symbol, date, open, high, low, close, volume, turnover)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, date) DO UPDATE SET
                    open=excluded.open,
                    high=excluded.high,
                    low=excluded.low,
                    close=excluded.close,
                    volume=excluded.volume,
                    turnover=excluded.turnover
            """, records)
            conn.commit()

    def get_historical_eod(self, symbol: str, limit: Optional[int] = None) -> pd.DataFrame:
        """Retrieves chronological EOD time-series as a pandas DataFrame."""
        with self._get_connection() as conn:
            query = """
                SELECT date, open, high, low, close, volume, turnover
                FROM eod_prices
                WHERE symbol = ?
                ORDER BY date ASC
            """
            params = [symbol.upper().strip()]
            df = pd.read_sql_query(query, conn, params=params)
            
            if not df.empty:
                df["date"] = pd.to_datetime(df["date"])
                if limit and len(df) > limit:
                    df = df.iloc[-limit:].reset_index(drop=True)
            return df

    def save_signals(self, signal_records: List[dict]):
        """Saves calculated signal states."""
        if not signal_records:
            return

        with self._get_connection() as conn:
            cursor = conn.cursor()
            for rec in signal_records:
                cursor.execute("""
                    INSERT INTO signals (
                        symbol, date, close, rsi_14, volume, vol_mean_20,
                        vol_std_20, vol_zscore, sma_50, sma_200, is_entry_signal, confirmation_notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol, date) DO UPDATE SET
                        close=excluded.close,
                        rsi_14=excluded.rsi_14,
                        volume=excluded.volume,
                        vol_mean_20=excluded.vol_mean_20,
                        vol_std_20=excluded.vol_std_20,
                        vol_zscore=excluded.vol_zscore,
                        sma_50=excluded.sma_50,
                        sma_200=excluded.sma_200,
                        is_entry_signal=excluded.is_entry_signal,
                        confirmation_notes=excluded.confirmation_notes
                """, (
                    rec["symbol"],
                    str(rec["date"]),
                    rec.get("close"),
                    rec.get("rsi_14"),
                    rec.get("volume"),
                    rec.get("vol_mean_20"),
                    rec.get("vol_std_20"),
                    rec.get("vol_zscore"),
                    rec.get("sma_50"),
                    rec.get("sma_200"),
                    1 if rec.get("is_entry_signal") else 0,
                    rec.get("confirmation_notes", "")
                ))
            conn.commit()

    def get_latest_signals(self) -> pd.DataFrame:
        """Fetches the most recent signal record for each ticker."""
        with self._get_connection() as conn:
            query = """
                SELECT s.*,
                       COALESCE(ROUND(((e.close - e.open) / e.open) * 100.0, 2), 0.0) AS change_pct
                FROM signals s
                INNER JOIN (
                    SELECT symbol, MAX(date) AS max_date
                    FROM signals
                    GROUP BY symbol
                ) latest ON s.symbol = latest.symbol AND s.date = latest.max_date
                LEFT JOIN eod_prices e ON s.symbol = e.symbol AND s.date = e.date
                ORDER BY s.is_entry_signal DESC, s.symbol ASC
            """
            return pd.read_sql_query(query, conn)

    def insert_intraday_snapshot(self, df: pd.DataFrame, timestamp_str: Optional[str] = None):
        """Stores a minute-by-minute tick snapshot for all stocks."""
        if df.empty or "symbol" not in df.columns:
            return

        from datetime import datetime, timezone, timedelta
        npt_tz = timezone(timedelta(hours=5, minutes=45))
        ts = timestamp_str or datetime.now(npt_tz).strftime("%Y-%m-%d %H:%M:00")

        def _safe_float(val, fallback=0.0):
            if val is None or pd.isna(val):
                return float(fallback)
            try:
                f = float(val)
                return float(fallback) if np.isnan(f) else f
            except (ValueError, TypeError):
                return float(fallback)

        records = []
        for _, row in df.iterrows():
            sym = str(row.get("symbol", "")).upper().strip()
            if not sym:
                continue
            c = _safe_float(row.get("close"), 0.0)
            o = _safe_float(row.get("open"), c)
            h = _safe_float(row.get("high"), max(o, c))
            l = _safe_float(row.get("low"), min(o, c))
            v = _safe_float(row.get("volume"), 0.0)
            t = _safe_float(row.get("turnover"), round(c * v, 2))

            records.append((sym, ts, c, o, h, l, v, t))

        if not records:
            return

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT INTO intraday_prices (symbol, timestamp, ltp, open, high, low, volume, turnover)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, timestamp) DO UPDATE SET
                    ltp=excluded.ltp,
                    open=excluded.open,
                    high=excluded.high,
                    low=excluded.low,
                    volume=excluded.volume,
                    turnover=excluded.turnover
            """, records)
            conn.commit()

    def upsert_market_psychology(self, data: Dict[str, Any]):
        """Inserts or updates daily market breadth and psychology metrics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO market_psychology (
                    date, total_turnover, total_volume, advances, declines, unchanged,
                    ad_ratio, circuit_high_count, circuit_low_count, fear_greed_score, sentiment_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    total_turnover=excluded.total_turnover,
                    total_volume=excluded.total_volume,
                    advances=excluded.advances,
                    declines=excluded.declines,
                    unchanged=excluded.unchanged,
                    ad_ratio=excluded.ad_ratio,
                    circuit_high_count=excluded.circuit_high_count,
                    circuit_low_count=excluded.circuit_low_count,
                    fear_greed_score=excluded.fear_greed_score,
                    sentiment_summary=excluded.sentiment_summary
            """, (
                str(data.get("date")),
                float(data.get("total_turnover", 0.0)),
                float(data.get("total_volume", 0.0)),
                int(data.get("advances", 0)),
                int(data.get("declines", 0)),
                int(data.get("unchanged", 0)),
                float(data.get("ad_ratio", 1.0)),
                int(data.get("circuit_high_count", 0)),
                int(data.get("circuit_low_count", 0)),
                float(data.get("fear_greed_score", 50.0)),
                str(data.get("sentiment_summary", ""))
            ))
            conn.commit()

    def get_market_psychology(self, limit: int = 30) -> pd.DataFrame:
        """Returns historical market psychology and breadth records."""
        with self._get_connection() as conn:
            query = f"SELECT * FROM market_psychology ORDER BY date DESC LIMIT {int(limit)}"
            return pd.read_sql(query, conn)

    def upsert_news_articles(self, articles: List[Dict[str, Any]]) -> int:
        """Inserts new financial articles, ignoring duplicates by URL."""
        if not articles:
            return 0
        inserted = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for art in articles:
                url = art.get("url", "")
                if not url:
                    continue
                cursor.execute("""
                    INSERT INTO daily_news (date, timestamp, source, title, summary, url, category, sentiment_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(url) DO UPDATE SET
                        title=excluded.title,
                        summary=excluded.summary,
                        category=excluded.category,
                        sentiment_score=excluded.sentiment_score
                """, (
                    str(art.get("date")),
                    str(art.get("timestamp")),
                    str(art.get("source")),
                    str(art.get("title")),
                    str(art.get("summary", "")),
                    url,
                    str(art.get("category", "General")),
                    float(art.get("sentiment_score", 0.0)) if art.get("sentiment_score") is not None else None
                ))
                inserted += 1
            conn.commit()
        return inserted

    def get_recent_news(self, date: Optional[str] = None, limit: int = 50) -> pd.DataFrame:
        """Fetches recent news articles."""
        with self._get_connection() as conn:
            if date:
                query = f"SELECT * FROM daily_news WHERE date = ? ORDER BY timestamp DESC LIMIT {int(limit)}"
                return pd.read_sql(query, conn, params=[date])
            else:
                query = f"SELECT * FROM daily_news ORDER BY date DESC, timestamp DESC LIMIT {int(limit)}"
                return pd.read_sql(query, conn)
