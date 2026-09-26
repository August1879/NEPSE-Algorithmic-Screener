import sys
from pathlib import Path

def audit():
    print("=" * 70)
    print("  NEPSE SCREENER: CODEBASE REVISION AUDITOR")
    print("=" * 70)

    checks = {
        "view/loading_screen.py": [
            ("Main-thread GUI hand-off", "def _on_finished(self, controller):"),
            ("Tuple unpacking for tips", "self.tip_body_label = QLabel(init_body)"),
            ("Watchlist pre-caching", "for sym in controller.get_watchlist():"),
        ],
        "view/gui.py": [
            ("Synchronous table population on launch", "self._populate_table_from_cache()"),
            ("Both chart engines in dropdown", 'self.chart_mode_combo.addItems(["Classic (Matplotlib)", "TradingView (Interactive)"])'),
            ("Open in Browser button", "self.browser_btn = QPushButton("),
            ("Resilient auto-seed for charts", "seed_df = self.controller.ingestion.generate_synthetic_history(sym"),
        ],
        "main.py": [
            ("Sub-0.2s instant GUI boot", "loading_screen = GameLoadingWindow(cli_args=args)"),
            ("Chromium security bypass flags", 'os.environ["QTWEBENGINE_CHROMIUM_FLAGS"]'),
            ("Safe CLI argument parsing", "args, _ = parser.parse_known_args()"),
        ],
        "controller/controller.py": [
            ("Self-healing watchlist", "self._init_system()"),
            ("Auto-seed missing price bars", "self.ingestion.generate_synthetic_history("),
        ],
        "model/engine.py": [
            ("Lazy scipy import for fast startup", "# from scipy.signal import find_peaks (lazy)"),
        ],
        ".github/workflows/build_windows_exe.yml": [
            ("No-console flag", "--noconsole"),
            ("ASCII Windows runner smoke-test", "SUCCESS: Executable successfully launched GUI and is running cleanly!"),
        ]
    }

    outdated_files = []
    print("\n[Auditing Current Files in Repository]")
    for filepath, file_checks in checks.items():
        p = Path(filepath)
        if not p.exists():
            print(f"  ❌ {filepath}: File does NOT exist!")
            outdated_files.append(filepath)
            continue

        text = p.read_text(encoding="utf-8", errors="replace")
        missing_features = []
        for name, snippet in file_checks:
            if snippet not in text:
                missing_features.append(name)

        if missing_features:
            print(f"  ❌ {filepath}: OUTDATED! (Missing: {', '.join(missing_features)})")
            outdated_files.append(filepath)
        else:
            print(f"  ✓ {filepath}: 100% UP TO DATE.")

    print("\n" + "=" * 70)
    if not outdated_files:
        print("  RESULT: ALL REPOSITORY FILES ARE 100% UP TO DATE!")
    else:
        print(f"  RESULT: {len(outdated_files)} file(s) are outdated or out of sync.")
    print("=" * 70)
    return len(outdated_files) == 0

if __name__ == "__main__":
    audit()
