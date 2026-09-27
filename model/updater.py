"""
Auto-Updater Engine for NEPSE Algorithmic Screener.
Checks GitHub Releases API, downloads assets in background, and self-restarts on Windows.
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

APP_VERSION = "1.5.1"
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
    Extracts downloaded zip to a staging directory, generates an updater script,
    and restarts the application.
    """
    is_frozen = getattr(sys, "frozen", False)
    if not is_frozen:
        logger.info("Application is running from source, not a frozen executable. Skipping batch restart.")
        return False, "Auto-update restart is only applicable to packaged Windows executables."

    exe_path = Path(sys.executable).resolve()
    app_dir = exe_path.parent

    # Staging directory
    staging_dir = Path(tempfile.mkdtemp(prefix="nepse_update_stage_"))
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(staging_dir)

    # Check if files are nested inside a subfolder
    subdirs = [p for p in staging_dir.iterdir() if p.is_dir()]
    source_dir = staging_dir
    if len(subdirs) == 1 and (subdirs[0] / exe_path.name).exists():
        source_dir = subdirs[0]

    # Create updater batch script
    batch_file = app_dir.parent / "nepse_updater.bat"
    bat_content = f"""@echo off
title NEPSE Screener Auto-Updater
echo Updating application to the latest version...
timeout /t 2 /nobreak > nul

xcopy /E /Y /I "{source_dir}" "{app_dir}" > nul
if exist "{staging_dir}" rmdir /S /Q "{staging_dir}"
if exist "{zip_path}" del /F /Q "{zip_path}"

echo Starting new version...
start "" "{exe_path}"
(goto) 2>nul & del "%~f0"
exit
"""
    with open(batch_file, "w", encoding="utf-8") as f:
        f.write(bat_content)

    # Launch detached batch process and exit
    subprocess.Popen(["cmd.exe", "/c", str(batch_file)], shell=True)
    return True, "Update script initialized. Restarting..."
