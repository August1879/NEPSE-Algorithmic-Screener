"""
Auto-Updater Engine for NEPSE Algorithmic Screener.
Checks GitHub Releases API, downloads assets in background, terminates child processes,
overwrites application directory safely, and self-restarts on Windows.
"""
import os
import sys
import json
import logging
import tempfile
import zipfile
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import urllib.request

logger = logging.getLogger(__name__)

APP_VERSION = "1.6.2"
GITHUB_REPO = "August1879/NEPSE-Algorithmic-Screener"
RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def parse_version_tuple(v_str: str) -> Tuple[int, ...]:
    clean = v_str.strip().lstrip("v").split("-")[0]
    parts = []
    for p in clean.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def check_for_updates() -> Tuple[bool, Dict[str, Any]]:
    """
    Queries GitHub API for the latest release.
    Returns (has_update, release_info_dict).
    """
    try:
        req = urllib.request.Request(
            RELEASES_API_URL,
            headers={
                "User-Agent": "NEPSE-Algorithmic-Screener-Updater",
                "Accept": "application/vnd.github.v3+json"
            }
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                tag = data.get("tag_name", "")
                latest_ver = parse_version_tuple(tag)
                curr_ver = parse_version_tuple(APP_VERSION)

                # Look for Windows zip asset
                zip_asset = None
                for asset in data.get("assets", []):
                    name = asset.get("name", "").lower()
                    if name.endswith(".zip") or "windows" in name:
                        zip_asset = asset
                        break

                has_update = (latest_ver > curr_ver) and (zip_asset is not None)
                return has_update, {
                    "tag_name": tag,
                    "name": data.get("name", tag),
                    "body": data.get("body", "No release notes provided."),
                    "asset_name": zip_asset.get("name") if zip_asset else None,
                    "download_url": zip_asset.get("browser_download_url") if zip_asset else None,
                    "size_mb": round((zip_asset.get("size", 0) / (1024 * 1024)), 2) if zip_asset else 0,
                    "published_at": data.get("published_at", "")
                }
    except Exception as e:
        logger.warning(f"Failed to check for updates: {e}")
        return False, {"error": str(e)}

    return False, {}


def apply_update_and_restart(zip_path: Path):
    """
    Extracts downloaded zip, locates the directory containing the executable,
    generates a batch script that terminates lingering processes, overwrites
    all files cleanly, and restarts the application.
    """
    is_frozen = getattr(sys, "frozen", False)
    if not is_frozen:
        logger.info("Application running from source. Auto-update only restarts frozen Windows executables.")
        return False, "Auto-update restart is only applicable to packaged Windows executables."

    exe_path = Path(sys.executable).resolve()
    app_dir = exe_path.parent
    current_pid = os.getpid()

    staging_dir = Path(tempfile.mkdtemp(prefix="nepse_update_stage_"))
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(staging_dir)

    # Automatically find the exact directory containing the executable inside the zip
    matches = [p.parent for p in staging_dir.rglob(exe_path.name)]
    source_dir = matches[0] if matches else staging_dir

    # Write updater batch to %TEMP% to prevent Program Files UAC permission failures
    batch_file = Path(tempfile.gettempdir()) / "nepse_updater.bat"
    bat_content = f"""@echo off
title NEPSE Screener Auto-Updater
echo Waiting for all NEPSE Screener processes to close...

:: Kill main PID and any lingering Chromium rendering child processes
taskkill /F /PID {current_pid} >nul 2>&1
taskkill /F /IM QtWebEngineProcess.exe >nul 2>&1
timeout /t 2 /nobreak > nul

:wait_loop
tasklist /FI "PID eq {current_pid}" 2>NUL | find /I "{current_pid}" >NUL
if "%ERRORLEVEL%"=="0" (
    timeout /t 1 /nobreak > nul
    goto wait_loop
)

echo Applying update files to: {app_dir}
timeout /t 1 /nobreak > nul

:: Overwrite all binaries and folders
xcopy /E /Y /I /R /H "{source_dir}" "{app_dir}" > "%TEMP%\\nepse_update_log.txt" 2>&1
if "%ERRORLEVEL%" NEQ "0" (
    robocopy "{source_dir}" "{app_dir}" /E /IS /IT /NP /R:3 /W:1 > "%TEMP%\\nepse_update_log.txt" 2>&1
)

:: Cleanup staging
if exist "{staging_dir}" rmdir /S /Q "{staging_dir}"
if exist "{zip_path}" del /F /Q "{zip_path}"

echo Starting updated NEPSE Screener...
start "" "{exe_path}"
(goto) 2>nul & del "%~f0"
exit
"""
    with open(batch_file, "w", encoding="utf-8") as f:
        f.write(bat_content)

    subprocess.Popen(["cmd.exe", "/c", str(batch_file)], shell=True)
    return True, "Update script initialized. Restarting..."
