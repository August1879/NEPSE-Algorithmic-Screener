"""
Interactive Data Reader & Inspector for NEPSE SQLite Database.
"""
import argparse
import sqlite3
import pandas as pd
from pathlib import Path
from config import DB_PATH

def get_connection():
    from model.database import DatabaseManager
    db = DatabaseManager(DB_PATH)
    return sqlite3.connect(db._effective_path)

def show_overview():
    conn = get_connection()
    if not conn:
        return
    print("\n" + "=" * 65)
    print("                NEPSE DATABASE OVERVIEW")
    print("=" * 65)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in cursor.fetchall() if not t[0].startswith("_") and t[0] != "sqlite_sequence"]
    
    for t in tables:
        count = cursor.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"• Table: {t:<22} | Total Records: {count:,}")
    print("=" * 65 + "\n")
    conn.close()

def show_stock_history(symbol: str, limit: int = 10):
    conn = get_connection()
    if not conn:
        return
    sym = symbol.upper().strip()
    df = pd.read_sql("""
        SELECT date, open, high, low, close, volume, turnover 
        FROM eod_prices 
        WHERE symbol = ? 
        ORDER BY date DESC 
        LIMIT ?
    """, conn, params=[sym, limit])
    
    if df.empty:
        print(f"No EOD history found for {sym}.")
    else:
        print(f"\n--- Recent Daily History for {sym} (Latest {len(df)} days) ---")
        print(df.to_string(index=False))
    conn.close()

def show_signals(limit: int = 15):
    conn = get_connection()
    if not conn:
        return
    df = pd.read_sql("""
        SELECT symbol, date, close, rsi_14, vol_zscore, is_entry_signal, confirmation_notes 
        FROM signals 
        ORDER BY is_entry_signal DESC, date DESC, symbol ASC 
        LIMIT ?
    """, conn, params=[limit])
    
    if df.empty:
        print("No signals calculated yet.")
    else:
        print(f"\n--- Latest Calculated Screener Signals (Top {len(df)}) ---")
        print(df.to_string(index=False))
    conn.close()

def show_psychology(limit: int = 10):
    conn = get_connection()
    if not conn:
        return
    df = pd.read_sql("""
        SELECT date, total_turnover, advances, declines, unchanged, ad_ratio, circuit_high_count, fear_greed_score 
        FROM market_psychology 
        ORDER BY date DESC 
        LIMIT ?
    """, conn, params=[limit])
    if df.empty:
        print("No market psychology records found yet.")
    else:
        print(f"\n--- Recent Market Psychology & Breadth Index (Latest {len(df)} sessions) ---")
        print(df.to_string(index=False))
    conn.close()

def show_news(limit: int = 15):
    conn = get_connection()
    if not conn:
        return
    df = pd.read_sql("""
        SELECT date, timestamp, source, category, title 
        FROM daily_news 
        ORDER BY timestamp DESC 
        LIMIT ?
    """, conn, params=[limit])
    if df.empty:
        print("No daily news articles collected yet.")
    else:
        print(f"\n--- Latest Financial News & Policy Headlines ({len(df)} articles) ---")
        print(df.to_string(index=False))
    conn.close()

def export_to_csv(table_name: str, output_file: str = None):
    conn = get_connection()
    if not conn:
        return
    out = output_file or f"{table_name}.csv"
    df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
    df.to_csv(out, index=False)
    print(f"✓ Exported {len(df):,} records from '{table_name}' to {out}")
    conn.close()

def main():
    parser = argparse.ArgumentParser(description="NEPSE Data Reader & Inspector")
    parser.add_argument("--overview", action="store_true", help="Show summary of all tables and record counts")
    parser.add_argument("--stock", type=str, help="View daily historical prices for a specific stock (e.g. --stock NABIL)")
    parser.add_argument("--signals", action="store_true", help="View latest calculated technical indicator signals")
    parser.add_argument("--psychology", action="store_true", help="View latest market breadth and fear & greed score")
    parser.add_argument("--news", action="store_true", help="View recent financial news headlines")
    parser.add_argument("--export", type=str, choices=["eod_prices", "intraday_prices", "signals", "tickers", "market_psychology", "daily_news"], help="Export a table to CSV")
    args = parser.parse_args()

    if args.stock:
        show_stock_history(args.stock)
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
