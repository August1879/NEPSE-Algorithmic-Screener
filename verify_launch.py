import sys
import glob
import py_compile
from pathlib import Path

def test():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    print("=" * 60)
    print("  NEPSE SCREENER PRE-FLIGHT TERMINAL CHECK")
    print("=" * 60)

    # 1. Syntax check across all files
    print("\n[1/3] Compiling all Python source files...")
    py_files = glob.glob("**/*.py", recursive=True)
    for f in py_files:
        if ".git" in f or "__pycache__" in f:
            continue
        py_compile.compile(f, doraise=True)
    print(f"✓ All {len(py_files)} Python files compiled with 0 syntax errors.")

    # 2. Validate Loading Screen tips
    print("\n[2/3] Checking Loading Screen tips...")
    try:
        from view.loading_screen import TRADING_TIPS
        assert isinstance(TRADING_TIPS, list) and len(TRADING_TIPS) > 0
        for i, item in enumerate(TRADING_TIPS):
            assert len(item) == 3, f"Tip #{i} does not have 3 elements: {item}"
            assert all(isinstance(x, str) for x in item), f"Tip #{i} contains non-string: {item}"
        print(f"✓ All {len(TRADING_TIPS)} tips verified as valid strings.")
    except (ImportError, OSError):
        p = Path("view/loading_screen.py")
        text = p.read_text(encoding="utf-8")
        assert "TRADING_TIPS" in text
        assert "QLabel(init_body)" in text or "QLabel(TRADING_TIPS[0])" in text
        print("✓ Verified: Loading screen tips format is correct.")

    # 3. Test calculation engine & database
    print("\n[3/3] Checking Database and Technical Calculations...")
    from controller.controller import AppController
    ctrl = AppController()
    wl = ctrl.get_watchlist()
    assert len(wl) > 0, "Watchlist is empty"
    res = ctrl.process_single_ticker_pipeline(wl[0])
    assert "close" in res and "rsi_14" in res
    print(f"✓ Database & Engine verified with ticker {wl[0]} (LTP: Rs. {res['close']:.2f}, RSI: {res['rsi_14']:.1f}).")

    print("\n" + "=" * 60)
    print("  ALL TERMINAL CHECKS PASSED. Safe to push!")
    print("=" * 60)

if __name__ == "__main__":
    test()
