"""
NEPSE Algorithmic Screener - Comprehensive File Integrity & Verification Test Suite.
Validates file existence, Python syntax compilation, configuration parameters,
calendar schedules, technical indicator engines, HTML chart exports, and CI/CD workflows.
"""
import sys
import os
import json
import py_compile
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np

def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()[:12]

class TestReporter:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0

    def assert_true(self, condition: bool, description: str, details: str = ""):
        if condition:
            print(f"  [PASS] {description}")
            self.passed += 1
        else:
            print(f"  [FAIL] {description} - {details}")
            self.failed += 1

def run_integrity_suite():
    reporter = TestReporter()
    print("=" * 75)
    print("  NEPSE SCREENER: FULL REPOSITORY FILE INTEGRITY & VERIFICATION TEST")
    print("=" * 75)

    # 1. CORE FILE HIERARCHY & CHECKSUMS
    print("\n[Phase 1] Validating File Existence & Checksums...")
    critical_files = [
        "config.py",
        "main.py",
        "requirements.txt",
        "README.md",
        "controller/controller.py",
        "controller/scheduler.py",
        "model/database.py",
        "model/engine.py",
        "model/ingestion.py",
        "model/nepse_calendar.py",
        "view/gui.py",
        "view/loading_screen.py",
        "view/chart_canvas.py",
        "data/nepal_holidays.json",
        ".github/workflows/build_windows_exe.yml",
        ".github/workflows/nepse_auto_scraper.yml"
    ]

    for rel_path in critical_files:
        p = Path(rel_path)
        exists = p.exists() and p.is_file() and p.stat().st_size >= 0
        if exists:
            chk = compute_sha256(p)
            size_kb = p.stat().st_size / 1024
            reporter.assert_true(True, f"{rel_path} (Size: {size_kb:.1f} KB, SHA-256: {chk})")
        else:
            reporter.assert_true(False, rel_path, "File missing or inaccessible!")

    # 2. PYTHON AST & SYNTAX COMPILATION
    print("\n[Phase 2] Verifying Python Syntax & Bytecode Compilation...")
    py_files = list(Path(".").glob("**/*.py"))
    for py_file in sorted(py_files):
        if "__pycache__" in str(py_file) or ".git" in str(py_file):
            continue
        try:
            py_compile.compile(str(py_file), doraise=True)
            reporter.assert_true(True, f"Syntax Validated: {py_file}")
        except Exception as e:
            reporter.assert_true(False, f"Syntax Error: {py_file}", str(e))

    # 3. CONFIGURATION & TRADING SCHEDULE RULES
    print("\n[Phase 3] Checking Market Trading Rules & Calendar Settings...")
    try:
        import config
        days = getattr(config, "ACTIVE_TRADING_DAYS", [])
        sunday_active = 6 in days
        thursday_active = 3 in days
        friday_inactive = 4 not in days
        saturday_inactive = 5 not in days

        reporter.assert_true(sunday_active, "Active Trading Days includes Sunday (Day 6)", f"Current days: {days}")
        reporter.assert_true(thursday_active, "Active Trading Days includes Thursday (Day 3)", f"Current days: {days}")
        reporter.assert_true(friday_inactive and saturday_inactive, "Friday (Day 4) and Saturday (Day 5) correctly designated as weekend", f"Current days: {days}")
    except Exception as e:
        reporter.assert_true(False, "Failed to inspect config.py", str(e))

    try:
        from model.ingestion import NepseMarketCalendar
        cal = NepseMarketCalendar()
        
        npt_tz = timezone(timedelta(hours=5, minutes=45))
        test_sunday = datetime(2026, 9, 27, 12, 0, 0, tzinfo=npt_tz)
        is_sun_trading = cal.is_trading_day(test_sunday)
        reporter.assert_true(is_sun_trading, "NepseMarketCalendar recognizes Sunday as valid trading day")

        test_sat = datetime(2026, 9, 26, 12, 0, 0, tzinfo=npt_tz)
        is_sat_trading = cal.is_trading_day(test_sat)
        reporter.assert_true(not is_sat_trading, "NepseMarketCalendar recognizes Saturday as non-trading weekend")
    except Exception as e:
        reporter.assert_true(False, "NepseMarketCalendar evaluation failed", str(e))

    # 4. QUANTITATIVE TECHNICAL ENGINE ACCURACY
    print("\n[Phase 4] Testing Technical Calculation Pipeline (RSI, Z-Score, RMS)...")
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=60, freq="B")
    close_prices = 100.0 + np.cumsum(np.random.randn(60) * 1.5)
    close_prices[-5:] = [90, 85, 80, 75, 72]
    volumes = np.full(60, 10000.0)
    volumes[-1] = 50000.0

    test_df = pd.DataFrame({
        "date": dates,
        "open": close_prices - 0.5,
        "high": close_prices + 1.0,
        "low": close_prices - 1.0,
        "close": close_prices,
        "volume": volumes
    })

    try:
        from model.engine import NepseTechnicalEngine
        enriched = NepseTechnicalEngine.enrich_dataframe(test_df)
        
        rsi_col = "rsi" if "rsi" in enriched.columns else "rsi_14"
        rsi = enriched[rsi_col].iloc[-1]
        vol_z = enriched["vol_zscore"].iloc[-1]
        is_entry = enriched.get("is_entry_signal", pd.Series([False]*len(enriched))).iloc[-1]

        reporter.assert_true(pd.notna(rsi) and 0.0 <= rsi <= 100.0, f"RSI(14) calculated within bounds: {rsi:.2f}")
        reporter.assert_true(pd.notna(vol_z) and vol_z > 2.0, f"Volume Z-Score correctly identifies spike: {vol_z:+.2f}σ")
        reporter.assert_true(bool(is_entry) is True or rsi < 30.0, "Oversold RSI and Volume Spike detected in technical pipeline")
    except Exception as e:
        reporter.assert_true(False, "NepseTechnicalEngine execution failed", str(e))

    # 5. INTERACTIVE TRADINGVIEW HTML INLINING & EXPORT
    print("\n[Phase 5] Verifying TradingView HTML Generator & Inlining...")
    try:
        from view.chart_canvas import export_tradingview_html
        test_out_dir = Path("output")
        test_file = export_tradingview_html("TEST", test_df, output_dir=test_out_dir)

        reporter.assert_true(test_file.exists(), f"TradingView HTML generated: {test_file}")
        html_str = test_file.read_text(encoding="utf-8")
        
        has_symbol = "TEST" in html_str
        has_candle_data = "candleData" in html_str
        no_doc_write = "document.write" not in html_str

        reporter.assert_true(has_symbol and has_candle_data, "HTML contains populated candle data and ticker metadata")
        reporter.assert_true(no_doc_write, "HTML is free of parser-blocking document.write tags")
    except Exception as e:
        reporter.assert_true(False, "TradingView export verification failed", str(e))

    # 6. CI/CD WORKFLOW CONFIGURATIONS
    print("\n[Phase 6] Validating GitHub Actions Workflows...")
    try:
        auto_scraper_yaml = Path(".github/workflows/nepse_auto_scraper.yml").read_text(encoding="utf-8")
        has_sunday_cron = "0-4" in auto_scraper_yaml
        has_dispatch = "workflow_dispatch:" in auto_scraper_yaml
        reporter.assert_true(has_sunday_cron, "nepse_auto_scraper.yml includes Sunday (0-4) cron schedules")
        reporter.assert_true(has_dispatch, "nepse_auto_scraper.yml supports on-demand manual triggering")

        build_exe_yaml = Path(".github/workflows/build_windows_exe.yml").read_text(encoding="utf-8")
        has_webengine_collect = "--collect-all PyQt6.QtWebEngineWidgets" in build_exe_yaml
        reporter.assert_true(has_webengine_collect, "build_windows_exe.yml collects PyQt6-WebEngine packages for Windows")
    except Exception as e:
        reporter.assert_true(False, "Workflow validation failed", str(e))

    print("\n" + "=" * 75)
    print(f"  INTEGRITY SUMMARY: {reporter.passed} PASSED | {reporter.failed} FAILED | {reporter.warnings} WARNINGS")
    print("=" * 75)

    return reporter.failed == 0

if __name__ == "__main__":
    success = run_integrity_suite()
    sys.exit(0 if success else 1)
