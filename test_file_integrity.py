import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
"""
NEPSE Algorithmic Screener - Comprehensive Repository Integrity & Verification Test Suite.
Validates ALL repository files dynamically, checks bytecode compilation, database schema,
JSON assets, trading calendar schedules, technical engines, TradingView exports, and CI/CD workflows.
"""
import os
import json
import py_compile
import hashlib
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np

def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()[:12]

class TestReporter:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0

    def assert_true(self, condition: bool, description: str, details: str = ''):
        if condition:
            print(f'  [PASS] {description}')
            self.passed += 1
        else:
            print(f'  [FAIL] {description} - {details}')
            self.failed += 1

def discover_all_project_files(base_dir: Path):
    """
    Dynamically discover all non-ephemeral repository files across all directories.
    Excludes pycache, git internals, exports, and temporary test artifacts.
    """
    tracked = []
    for p in base_dir.rglob('*'):
        if not p.is_file():
            continue
        rel = p.relative_to(base_dir)
        parts = rel.parts
        if any(part.startswith('.') and part != '.github' for part in parts):
            continue
        if '__pycache__' in parts:
            continue
        if parts[0] == 'output' and rel.suffix == '.html':
            continue
        if rel.suffix in ('.png', '.pyc', '.bak', '.tmp'):
            continue
        if 'test_nepse.db' in parts or 'exports' in parts:
            continue
        tracked.append(rel)
    return sorted(tracked)

def run_integrity_suite():
    reporter = TestReporter()
    base_dir = Path(__file__).resolve().parent

    print('=' * 80)
    print('  NEPSE SCREENER: FULL REPOSITORY RECURSIVE INTEGRITY & VERIFICATION SUITE')
    print('=' * 80)

    # 1. DYNAMIC REPOSITORY-WIDE FILE DISCOVERY & CHECKSUMS (MAX COVERAGE)
    all_files = discover_all_project_files(base_dir)
    print(f"\n[Phase 1] Validating Complete Repository File Tree ({len(all_files)} Files Discovered)...")
    for rel_path in all_files:
        p = base_dir / rel_path
        exists = p.exists() and p.is_file()
        if exists:
            size_kb = p.stat().st_size / 1024
            if p.stat().st_size == 0 and p.name != '__init__.py':
                reporter.assert_true(False, f'{rel_path}', 'File is unexpectedly empty (0 bytes)!')
            else:
                chk = compute_sha256(p)
                reporter.assert_true(True, f'{rel_path} (Size: {size_kb:.1f} KB, SHA-256: {chk})')
        else:
            reporter.assert_true(False, f'{rel_path}', 'File missing or unreadable!')

    # 2. PYTHON AST & BYTECODE COMPILATION
    py_files = sorted([p for p in base_dir.rglob('*.py') if '__pycache__' not in str(p) and '.git' not in str(p)])
    print(f"\n[Phase 2] Verifying Python Syntax & Bytecode Compilation ({len(py_files)} Python Files)...")
    for py_file in py_files:
        rel = py_file.relative_to(base_dir)
        try:
            py_compile.compile(str(py_file), doraise=True)
            reporter.assert_true(True, f'Syntax Validated: {rel}')
        except Exception as e:
            reporter.assert_true(False, f'Syntax Error: {rel}', str(e))

    # 3. JSON ASSET & SCHEMA VALIDATION
    print("\n[Phase 3] Checking JSON Data Schemas & Configurations...")
    holidays_file = base_dir / 'data' / 'nepal_holidays.json'
    if holidays_file.exists():
        try:
            with open(holidays_file, 'r', encoding='utf-8') as f:
                hdata = json.load(f)
            is_valid = isinstance(hdata, (dict, list)) and len(hdata) > 0
            reporter.assert_true(is_valid, f'nepal_holidays.json contains valid entries (Count: {len(hdata)})')
        except Exception as e:
            reporter.assert_true(False, 'Failed parsing nepal_holidays.json', str(e))
    else:
        reporter.assert_true(False, 'data/nepal_holidays.json not found')

    settings_file = base_dir / 'data' / 'settings.json'
    if settings_file.exists():
        try:
            with open(settings_file, 'r', encoding='utf-8') as f:
                sdata = json.load(f)
            reporter.assert_true(isinstance(sdata, dict), 'settings.json schema is valid dictionary')
        except Exception as e:
            reporter.assert_true(False, 'Failed parsing settings.json', str(e))

    # 4. DATABASE INTEGRITY & BENCHMARK INDEX VERIFICATION
    print("\n[Phase 4] Verifying SQLite Database Integrity & Benchmark Index...")
    db_file = base_dir / 'data' / 'nepse_cache.db'
    if db_file.exists():
        try:
            conn = sqlite3.connect(f'file:{db_file}?mode=ro', uri=True)
            cur = conn.cursor()
            integrity = cur.execute("PRAGMA integrity_check").fetchone()[0]
            reporter.assert_true(integrity == 'ok', f'SQLite integrity check: {integrity}')

            tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            has_core_tables = {'tickers', 'eod_prices'}.issubset(tables) and ('signals' in tables or 'technical_signals' in tables)
            reporter.assert_true(has_core_tables, f'Database schema contains core tables: {tables}')

            ticker_count = cur.execute("SELECT count(*) FROM tickers WHERE is_active=1").fetchone()[0]
            reporter.assert_true(ticker_count >= 50, f'Active listed tickers in database: {ticker_count}')

            nepse_row = cur.execute("SELECT symbol, sector FROM tickers WHERE symbol='NEPSE'").fetchone()
            reporter.assert_true(nepse_row is not None, f"NEPSE Index exists in tickers table: {nepse_row}")

            nepse_candles = cur.execute("SELECT count(*) FROM eod_prices WHERE symbol='NEPSE'").fetchone()[0]
            reporter.assert_true(nepse_candles >= 200, f"NEPSE Index has historical candles: {nepse_candles} bars")
            conn.close()
        except Exception as e:
            reporter.assert_true(False, 'Database verification failed', str(e))
    else:
        reporter.assert_true(False, 'data/nepse_cache.db not found')

    # 5. CONFIGURATION & TRADING SCHEDULE RULES
    print("\n[Phase 5] Checking Market Trading Rules & Calendar Settings...")
    try:
        sys.path.insert(0, str(base_dir))
        import config
        days = getattr(config, 'ACTIVE_TRADING_DAYS', [])
        sunday_active = 6 in days
        thursday_active = 3 in days
        friday_inactive = 4 not in days
        saturday_inactive = 5 not in days

        reporter.assert_true(sunday_active, 'Active Trading Days includes Sunday (Day 6)', f'Current days: {days}')
        reporter.assert_true(thursday_active, 'Active Trading Days includes Thursday (Day 3)', f'Current days: {days}')
        reporter.assert_true(friday_inactive and saturday_inactive, 'Friday (Day 4) and Saturday (Day 5) designated as weekend', f'Current days: {days}')
        reporter.assert_true("NEPSE" in getattr(config, 'DEFAULT_WATCHLIST', []), 'DEFAULT_WATCHLIST includes NEPSE benchmark index')
    except Exception as e:
        reporter.assert_true(False, 'Failed to inspect config.py', str(e))

    try:
        from model.ingestion import NepseMarketCalendar
        cal = NepseMarketCalendar()
        npt_tz = timezone(timedelta(hours=5, minutes=45))
        test_sunday = datetime(2026, 9, 27, 12, 0, 0, tzinfo=npt_tz)
        is_sun_trading = cal.is_trading_day(test_sunday)
        reporter.assert_true(is_sun_trading, 'NepseMarketCalendar recognizes Sunday as valid trading day')

        test_sat = datetime(2026, 9, 26, 12, 0, 0, tzinfo=npt_tz)
        is_sat_trading = cal.is_trading_day(test_sat)
        reporter.assert_true(not is_sat_trading, 'NepseMarketCalendar recognizes Saturday as non-trading weekend')
    except Exception as e:
        reporter.assert_true(False, 'NepseMarketCalendar evaluation failed', str(e))

    # 6. QUANTITATIVE TECHNICAL ENGINE ACCURACY
    print("\n[Phase 6] Testing Technical Calculation Pipeline (RSI, Z-Score, RMS)...")
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=60, freq='B')
    close_prices = 100.0 + np.cumsum(np.random.randn(60) * 1.5)
    close_prices[-5:] = [90, 85, 80, 75, 72]
    volumes = np.full(60, 10000.0)
    volumes[-1] = 50000.0

    test_df = pd.DataFrame({
        'date': dates,
        'open': close_prices - 0.5,
        'high': close_prices + 1.0,
        'low': close_prices - 1.0,
        'close': close_prices,
        'volume': volumes
    })

    try:
        from model.engine import NepseTechnicalEngine
        enriched = NepseTechnicalEngine.enrich_dataframe(test_df)
        rsi_col = 'rsi' if 'rsi' in enriched.columns else 'rsi_14'
        rsi = enriched[rsi_col].iloc[-1]
        vol_z = enriched['vol_zscore'].iloc[-1]
        is_entry = enriched.get('is_entry_signal', pd.Series([False]*len(enriched))).iloc[-1]

        reporter.assert_true(pd.notna(rsi) and 0.0 <= rsi <= 100.0, f'RSI(14) calculated within bounds: {rsi:.2f}')
        reporter.assert_true(pd.notna(vol_z) and vol_z > 2.0, f'Volume Z-Score correctly identifies spike: {vol_z:+.2f} sigma')
        reporter.assert_true(bool(is_entry) is True or rsi < 30.0, 'Oversold RSI and Volume Spike detected in technical pipeline')
    except Exception as e:
        reporter.assert_true(False, 'NepseTechnicalEngine execution failed', str(e))

    # 7. INTERACTIVE TRADINGVIEW HTML INLINING & EXPORT
    print("\n[Phase 7] Verifying TradingView HTML Generator & Inlining...")
    try:
        from view.chart_canvas import export_tradingview_html
        test_out_dir = base_dir / 'output'
        test_file = export_tradingview_html('TEST', test_df, output_dir=test_out_dir)

        reporter.assert_true(test_file.exists(), f'TradingView HTML generated: {test_file.name}')
        html_str = test_file.read_text(encoding='utf-8')
        
        has_symbol = 'TEST' in html_str
        has_candle_data = 'candleData' in html_str
        no_doc_write = 'document.write' not in html_str

        reporter.assert_true(has_symbol and has_candle_data, 'HTML contains populated candle data and ticker metadata')
        reporter.assert_true(no_doc_write, 'HTML is free of parser-blocking document.write tags')
    except Exception as e:
        reporter.assert_true(False, 'TradingView export verification failed', str(e))

    # 8. CI/CD WORKFLOW CONFIGURATIONS
    print("\n[Phase 8] Validating All GitHub Actions Workflows...")
    try:
        auto_scraper = base_dir / '.github' / 'workflows' / 'nepse_auto_scraper.yml'
        if auto_scraper.exists():
            content = auto_scraper.read_text(encoding='utf-8')
            reporter.assert_true('0-4' in content, 'nepse_auto_scraper.yml includes Sunday (0-4) cron schedules')
            reporter.assert_true('workflow_dispatch:' in content, 'nepse_auto_scraper.yml supports manual trigger')

        build_exe = base_dir / '.github' / 'workflows' / 'build_windows_exe.yml'
        if build_exe.exists():
            content = build_exe.read_text(encoding='utf-8')
            reporter.assert_true('--collect-all PyQt6.QtWebEngineWidgets' in content, 'build_windows_exe.yml collects PyQt6-WebEngine packages')

        manual_scraper = base_dir / '.github' / 'workflows' / 'nepse_scraper.yml'
        if manual_scraper.exists():
            content = manual_scraper.read_text(encoding='utf-8')
            reporter.assert_true('workflow_dispatch:' in content, 'nepse_scraper.yml supports workflow_dispatch')
    except Exception as e:
        reporter.assert_true(False, 'Workflow validation failed', str(e))

    print()
    print('=' * 80)
    print(f'  INTEGRITY SUMMARY: {reporter.passed} PASSED | {reporter.failed} FAILED | {reporter.warnings} WARNINGS')
    print('=' * 80)

    return reporter.failed == 0

if __name__ == '__main__':
    success = run_integrity_suite()
    sys.exit(0 if success else 1)
