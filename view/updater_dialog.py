"""
PyQt6 In-App Auto-Update Dialog and Background Download Worker.
"""
import os
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Dict, Any

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from model.updater import (
    APP_VERSION, check_for_updates, apply_update_and_restart
)


class UpdateCheckWorker(QThread):
    result_signal = pyqtSignal(bool, dict)

    def run(self):
        has_update, info = check_for_updates()
        self.result_signal.emit(has_update, info)


class UpdateDownloadWorker(QThread):
    progress_signal = pyqtSignal(int, str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, url: str):
        super().__init__()
        self.url = url
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            temp_zip = Path(tempfile.gettempdir()) / "nepse_update.zip"
            req = urllib.request.Request(self.url, headers={"User-Agent": "NEPSE-Updater"})
            with urllib.request.urlopen(req, timeout=30) as response:
                total_size = int(response.headers.get("content-length", 0))
                downloaded = 0
                chunk_size = 65536

                with open(temp_zip, "wb") as f:
                    while True:
                        if self._is_cancelled:
                            return
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = int((downloaded / total_size) * 100)
                            mb_down = downloaded / (1024 * 1024)
                            mb_total = total_size / (1024 * 1024)
                            msg = f"Downloading update: {mb_down:.1f} MB / {mb_total:.1f} MB ({percent}%)"
                            self.progress_signal.emit(percent, msg)

            self.finished_signal.emit(True, str(temp_zip))
        except Exception as e:
            self.finished_signal.emit(False, str(e))


class UpdateDialog(QDialog):
    def __init__(self, release_info: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.release_info = release_info
        self.download_worker = None
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("Software Update Available")
        self.setFixedSize(520, 380)
        self.setStyleSheet("""
            QDialog { background-color: #1a1a1a; color: #ffffff; }
            QLabel { color: #ffffff; }
            QTextEdit {
                background-color: #242424;
                color: #dddddd;
                border: 1px solid #333333;
                border-radius: 4px;
                padding: 6px;
                font-family: Consolas, monospace;
                font-size: 11px;
            }
            QProgressBar {
                border: 1px solid #444444;
                border-radius: 4px;
                text-align: center;
                color: white;
                background-color: #242424;
            }
            QProgressBar::chunk { background-color: #26a69a; }
            QPushButton {
                padding: 6px 14px;
                border-radius: 4px;
                font-weight: bold;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Title
        title_lbl = QLabel("🚀 A New Version is Available!")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #26a69a;")
        layout.addWidget(title_lbl)

        # Version tags
        ver_text = f"Installed: <b>v{APP_VERSION}</b>  ➜  Available: <b>{self.release_info.get('tag_name')}</b> ({self.release_info.get('size_mb', 0)} MB)"
        ver_lbl = QLabel(ver_text)
        ver_lbl.setStyleSheet("font-size: 12px; color: #bbdefb;")
        layout.addWidget(ver_lbl)

        # Release notes
        layout.addWidget(QLabel("Release Highlights:"))
        self.notes_box = QTextEdit()
        self.notes_box.setReadOnly(True)
        self.notes_box.setPlainText(self.release_info.get("body", "No changelog provided."))
        layout.addWidget(self.notes_box)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #81c784; font-size: 11px;")
        self.status_lbl.setVisible(False)
        layout.addWidget(self.status_lbl)
        layout.addWidget(self.progress_bar)

        # Buttons
        btn_layout = QHBoxLayout()
        self.update_btn = QPushButton("Update & Restart Now")
        self.update_btn.setStyleSheet("background-color: #00897b; color: white;")
        self.update_btn.clicked.connect(self._start_download)

        self.close_btn = QPushButton("Remind Me Later")
        self.close_btn.setStyleSheet("background-color: #424242; color: #ffffff;")
        self.close_btn.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)
        btn_layout.addWidget(self.update_btn)
        layout.addLayout(btn_layout)

    def _start_download(self):
        url = self.release_info.get("download_url")
        if not url:
            QMessageBox.warning(self, "Download Error", "No compatible Windows download package found in this release.")
            return

        self.update_btn.setEnabled(False)
        self.close_btn.setText("Cancel")
        self.progress_bar.setVisible(True)
        self.status_lbl.setVisible(True)
        self.status_lbl.setText("Connecting to server...")

        self.download_worker = UpdateDownloadWorker(url)
        self.download_worker.progress_signal.connect(self._on_progress)
        self.download_worker.finished_signal.connect(self._on_download_finished)
        self.download_worker.start()

    def _on_progress(self, percent: int, msg: str):
        self.progress_bar.setValue(percent)
        self.status_lbl.setText(msg)

    def _on_download_finished(self, success: bool, path_or_err: str):
        if not success:
            QMessageBox.critical(self, "Update Failed", "Could not download update:\n" + str(path_or_err))
            self.progress_bar.setVisible(False)
            self.status_lbl.setVisible(False)
            self.update_btn.setEnabled(True)
            self.close_btn.setText("Close")
            return

        self.status_lbl.setText("Extracting update and preparing restart...")
        try:
            success, msg = apply_update_and_restart(Path(path_or_err))
            if success:
                QMessageBox.information(
                    self,
                    "Restarting",
                    "Update downloaded successfully!\n\nThe application will now close and restart with the latest version."
                )
                import os
                os._exit(0)
            else:
                QMessageBox.warning(self, "Restart Notice", "Update downloaded:\n\n" + str(msg))
                self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Update Error", "Failed to execute update restart script:\n" + str(e) + "\n\nPlease extract manually from %TEMP%.")
            self.update_btn.setEnabled(True)
            self.close_btn.setText("Close")
