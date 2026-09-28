import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

"""
Utility script to read and inspect SQLite database tables, run audits, crawl news, and export AI datasets.
"""
import sqlite3
import argparse
import pandas as pd
from config import DB_PATH

def get_connection():
    fallback = Path("/tmp/nepse_data/nepse_cache.db")
    if fallback.exists():
        return sqlite3.connect(str(fallback))
    if Path(DB_PATH).exists():
        return sqlite3.connect(str(DB_PATH))
    print(f"Error: Database file not found at {DB_PATH} or {fallback}")
    return None

def show_overview():
    conn = get_connection()
    if not conn:
        return
    cur = conn.cursor()
    tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
    print("\n" + "=" * 65)
    print("                NEPSE DATABASE OVERVIEW")
    print("=" * 65)
    for (t_name,) in tables:
        count = cur.execute(f"SELECT count(*) FROM {t_name}").fetchone()[0]
        print(f"• Table: {t_name:<22} | Total Records: {count:,}")
    print("=" * 65 + "\n")
    conn.close()

def show_stock_history(symbol: str, limit: int = 10):
    conn = get_connection()
    if not conn:
        return
    df = pd.read_sql(
        f"SELECT date, open, high, low, close, volume, turnover FROM eod_prices WHERE symbol='{symbol}' ORDER BY date DESC LIMIT {limit}",
        conn
    )
    if df.empty:
        print(f"No EOD data found for symbol: {symbol}")
    else:
        print(f"\n--- Recent Daily History for {symbol} (Latest {len(df)} days) ---")
        print(df.to_string(index=False))
    conn.close()

def show_signals(limit: int = 15):
    conn = get_connection()
    if not conn:
        return
    df = pd.read_sql(
        f"SELECT symbol, date, close, rsi_14, vol_zscore, is_entry_signal, confirmation_notes FROM signals ORDER BY is_entry_signal DESC, date DESC, symbol ASC LIMIT {limit}",
        conn
    )
    if df.empty:
        print("No signals currently calculated in database.")
    else:
        print(f"\n--- Latest Calculated Screener Signals (Top {len(df)}) ---")
        print(df.to_string(index=False))
    conn.close()

def show_psychology(limit: int = 10):
    conn = get_connection()
    if not conn:
        return
    df = pd.read_sql(f"SELECT * FROM market_psychology ORDER BY date DESC LIMIT {limit}", conn)
    if df.empty:
        print("No market psychology records found in database.")
    else:
        print(f"\n--- Market Psychology & Breadth History (Latest {len(df)} sessions) ---")
        print(df.to_string(index=False))
    conn.close()

def show_news(limit: int = 15):
    conn = get_connection()
    if not conn:
        return
    df = pd.read_sql(f"SELECT date, category, source, title, sentiment_score FROM daily_news ORDER BY date DESC, timestamp DESC LIMIT {limit}", conn)
    if df.empty:
        print("No news records found in database.")
    else:
        print(f"\n--- Latest Multi-Domain News, Disaster, & Policy Headlines ({len(df)} articles) ---")
        for _, r in df.iterrows():
            sent = r['sentiment_score']
            sent_str = f"{sent:+.2f}" if pd.notna(sent) else " 0.00"
            tag = "🟢" if sent and sent > 0.1 else ("🔴" if sent and sent < -0.1 else "⚪")
            print(f"• [{r['category']}] ({r['source']}) {r['date']}")
            print(f"  {r['title']}")
            print(f"  Sentiment: {tag} {sent_str}\n")
    conn.close()

def scrape_and_update_news():
    from model.database import DatabaseManager
    from model.market_scraper import NepseNewsScraper
    db = DatabaseManager(DB_PATH)
    scraper = NepseNewsScraper(db)
    print("\n" + "=" * 70)
    print("   SCRAPING NATIONAL PORTALS, CABINET DECISIONS & DISASTER FEEDS")
    print("=" * 70)
    count = scraper.scrape_and_save_all_news()
    print(f"✓ Completed crawl: Processed and saved {count} articles into database.\n")
    show_news(limit=15)

def export_to_csv(table_name: str, output_file: str = None):
    conn = get_connection()
    if not conn:
        return
    out = output_file or f"{table_name}.csv"
    df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
    df.to_csv(out, index=False)
    print(f"✓ Exported {len(df):,} records from '{table_name}' to {out}")
    conn.close()

def run_audit():
    from model.screener import SignalAuditor
    auditor = SignalAuditor()
    print("\n" + "=" * 70)
    print("       RUNNING FULL HISTORICAL SIGNAL AUDIT & AI EXPORT")
    print("=" * 70)
    audit_res = auditor.run_historical_audit()
    summary = audit_res["summary"]
    print(f"• Total Historical Signals:      {summary['total_signals']}")
    print(f"• Overall Win Rate / Accuracy:    {summary['overall_accuracy_pct']}%")
    print(f"• Buy Signals:                   {summary['buy_signals']['count']} | Win Rate: {summary['buy_signals']['win_rate_pct']}%")
    print(f"• Sell Signals:                  {summary['sell_signals']['count']} | Exit Accuracy: {summary['sell_signals']['accuracy_pct']}%")
    print("\n--- Top Failure Modes (Root Causes) ---")
    for mode, count in summary["failure_mode_breakdown"].items():
        print(f"  - {mode:<35}: {count} trades")

    j_path = auditor.export_ai_training_dataset_jsonl()
    c_path = auditor.export_csv_dataset()
    m_path = auditor.generate_markdown_report()
    print("\n--- Generated Exports for AI Training ---")
    print(f"✓ AI JSONL Dataset:    {j_path}")
    print(f"✓ Tabular Audit CSV:   {c_path}")
    print(f"✓ Diagnostic Report:   {m_path}")
    print("=" * 70 + "\n")

def main():
    parser = argparse.ArgumentParser(description="NEPSE Data Reader, Multi-Domain News Crawler & Inspector")
    parser.add_argument("--overview", action="store_true", help="Show summary of all tables and record counts")
    parser.add_argument("--stock", type=str, help="View daily historical prices for a specific stock (e.g. --stock NABIL)")
    parser.add_argument("--signals", action="store_true", help="View latest calculated technical indicator signals")
    parser.add_argument("--audit", action="store_true", help="Run complete historical signal accuracy audit and export AI training dataset")
    parser.add_argument("--psychology", action="store_true", help="View latest market breadth and fear & greed score")
    parser.add_argument("--news", action="store_true", help="View recent multi-domain news, flood disaster & policy headlines")
    parser.add_argument("--scrape-news", action="store_true", help="Trigger full multi-channel crawl across national feeds, government portals, and flood bulletins")
    parser.add_argument("--export", type=str, choices=["eod_prices", "intraday_prices", "signals", "tickers", "market_psychology", "daily_news"], help="Export a table to CSV")
    args = parser.parse_args()

    if args.stock:
        show_stock_history(args.stock)
    elif args.audit:
        run_audit()
    elif args.scrape_news:
        scrape_and_update_news()
    elif args.signals:
        show_signals()
    elif args.psychology:
        show_psychology()
    elif args.news:
        show_news()
    elif args.export:
        export_to_csv(args.export)
    else:
        show_overview()

if __name__ == "__main__":
    main()
