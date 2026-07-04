#!/usr/bin/env python3
"""
Mac Control Panel — PyQt6 GUI to enable/disable macOS background daemons.
Gives the user real control over what runs on their machine.
"""

import os
import subprocess
import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QCheckBox, QPushButton as QBtn, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor

UID = os.getuid()

SERVICES = [
    {
        "label": "photolibraryd",
        "domain": "com.apple.photolibraryd",
        "desc": "Photo library indexing — known RAM hog (46GB reported)",
        "kill": "photolibraryd",
        "category": "Photos",
    },
    {
        "label": "photoanalysisd",
        "domain": "com.apple.photoanalysisd",
        "desc": "Face/object analysis for Photos app",
        "kill": "photoanalysisd",
        "category": "Photos",
    },
    {
        "label": "PodcastsWidget",
        "domain": "com.apple.podcasts.PodcastsWidget",
        "desc": "Podcasts notification center widget",
        "kill": "PodcastsWidget",
        "category": "Widgets",
    },
    {
        "label": "StocksWidget",
        "domain": "com.apple.stocks.StocksWidget",
        "desc": "Stocks notification center widget",
        "kill": "StocksWidget",
        "category": "Widgets",
    },
    {
        "label": "WeatherWidget",
        "domain": "com.apple.weather.WeatherWidget",
        "desc": "Weather notification center widget",
        "kill": "WeatherWidget",
        "category": "Widgets",
    },
    {
        "label": "CalendarWidget",
        "domain": "com.apple.calendar.CalendarWidget",
        "desc": "Calendar notification center widget",
        "kill": "CalendarWidget",
        "category": "Widgets",
    },
    {
        "label": "screen time agent",
        "domain": "com.apple.ScreenTimeAgent",
        "desc": "Screen Time monitoring daemon",
        "kill": "ScreenTimeAgent",
        "category": "System",
    },
    {
        "label": "familycontrols",
        "domain": "com.apple.familycontrols.process",
        "desc": "Family controls / parental controls daemon",
        "kill": "familycontrols",
        "category": "System",
    },
    {
        "label": "AppleSpell",
        "domain": "com.apple.AppleSpell",
        "desc": "Spell checker daemon",
        "kill": "AppleSpell",
        "category": "System",
    },
    {
        "label": "chronod",
        "domain": "com.apple.chronod",
        "desc": "Chronological sync daemon (Calendar/Reminders)",
        "kill": "chronod",
        "category": "System",
    },
    {
        "label": "duetexpertd",
        "domain": "com.apple.duetexpertd",
        "desc": "Siri intelligence / suggestions daemon",
        "kill": "duetexpertd",
        "category": "Siri",
    },
    {
        "label": "siriactionsd",
        "domain": "com.apple.siriactionsd",
        "desc": "Siri actions daemon",
        "kill": "siriactionsd",
        "category": "Siri",
    },
    {
        "label": "suggestionsd",
        "domain": "com.apple.suggestionsd",
        "desc": "Siri suggestions indexer",
        "kill": "suggestionsd",
        "category": "Siri",
    },
    {
        "label": "amsengagementd",
        "domain": "com.apple.amsengagementd",
        "desc": "App Store engagement tracking daemon",
        "kill": "amsengagementd",
        "category": "App Store",
    },
    {
        "label": "appstoreagent",
        "domain": "com.apple.appstoreagent",
        "desc": "App Store background agent",
        "kill": "appstoreagent",
        "category": "App Store",
    },
    {
        "label": "routined",
        "domain": "com.apple.routined",
        "desc": "Location routines / significant locations daemon",
        "kill": "routined",
        "category": "Location",
    },
    {
        "label": "callservicesd",
        "domain": "com.apple.callservicesd",
        "desc": "Continuity / phone call relay daemon",
        "kill": "callservicesd",
        "category": "Continuity",
    },
    {
        "label": "identityservicesd",
        "domain": "com.apple.identityservicesd",
        "desc": "iCloud identity / device trust daemon",
        "kill": "identityservicesd",
        "category": "iCloud",
    },
    {
        "label": "fileproviderd",
        "domain": "com.apple.fileproviderd",
        "desc": "iCloud Drive file provider daemon",
        "kill": "fileproviderd",
        "category": "iCloud",
    },
    {
        "label": "sharingd",
        "domain": "com.apple.sharingd",
        "desc": "AirDrop / sharing services daemon",
        "kill": "sharingd",
        "category": "Sharing",
    },
]


def check_disabled(domain):
    try:
        r = subprocess.run(
            ["launchctl", "print", f"gui/{UID}/{domain}"],
            capture_output=True, text=True, timeout=5
        )
        return r.returncode != 0
    except Exception:
        return False


def check_running(kill_name):
    try:
        r = subprocess.run(
            ["pgrep", "-x", kill_name],
            capture_output=True, text=True, timeout=5
        )
        return r.returncode == 0
    except Exception:
        return False


def disable_service(domain):
    try:
        subprocess.run(["launchctl", "disable", f"gui/{UID}/{domain}"], timeout=5)
        subprocess.run(["launchctl", "bootout", f"gui/{UID}/{domain}"],
                       capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def enable_service(domain):
    try:
        subprocess.run(["launchctl", "enable", f"gui/{UID}/{domain}"], timeout=5)
        subprocess.run(["launchctl", "bootstrap", f"gui/{UID}",
                        f"/System/Library/LaunchAgents/{domain}.plist"],
                       capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def kill_process(name):
    try:
        subprocess.run(["sudo", "killall", "-9", name],
                       capture_output=True, timeout=5)
        return True
    except Exception:
        return False


class ControlPanel(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mac Control Panel — Take Back Your Machine")
        self.setMinimumSize(900, 600)
        self.setStyleSheet(self._stylesheet())
        self.service_states = {}
        self._build_ui()
        self._refresh_all()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_all)
        self.timer.start(5000)

    def _stylesheet(self):
        return """
            QMainWindow { background-color: #1a1a2e; }
            QGroupBox {
                color: #e0e0e0;
                font-size: 13px;
                font-weight: bold;
                border: 1px solid #303050;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 16px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
            QLabel { color: #e0e0e0; font-size: 13px; }
            QLabel#header {
                color: #00ff88;
                font-size: 20px;
                font-weight: bold;
                padding: 8px;
            }
            QLabel#subheader {
                color: #888;
                font-size: 12px;
                padding-bottom: 8px;
            }
            QTableWidget {
                background-color: #16162a;
                color: #e0e0e0;
                gridline-color: #252540;
                border: 1px solid #303050;
                border-radius: 4px;
                font-size: 12px;
            }
            QTableWidget::item { padding: 6px; }
            QHeaderView::section {
                background-color: #20203a;
                color: #00ff88;
                border: none;
                padding: 6px;
                font-weight: bold;
            }
            QPushButton {
                background-color: #2a2a4a;
                color: #e0e0e0;
                border: 1px solid #353560;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #353565; }
            QPushButton:pressed { background-color: #1a1a3e; }
            QPushButton#disableAll {
                background-color: #4a1530;
                border-color: #6a2040;
            }
            QPushButton#disableAll:hover { background-color: #6a2040; }
            QPushButton#enableAll {
                background-color: #15304a;
                border-color: #204060;
            }
            QPushButton#enableAll:hover { background-color: #204060; }
            QPushButton#refresh {
                background-color: #1a3a2a;
                border-color: #2a5a3a;
            }
            QPushButton#refresh:hover { background-color: #2a5a3a; }
        """

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel("Mac Control Panel")
        header.setObjectName("header")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        sub = QLabel("Toggle macOS background daemons on/off. Changes persist across reboots.")
        sub.setObjectName("subheader")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)

        self.table = QTableWidget(len(SERVICES), 6)
        self.table.setHorizontalHeaderLabels(
            ["Service", "Category", "Description", "Blocked", "Running", "Action"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        for i, svc in enumerate(SERVICES):
            name_item = QTableWidgetItem(svc["label"])
            name_item.setFont(QFont("Menlo", 12, QFont.Weight.Bold))
            self.table.setItem(i, 0, name_item)

            cat_item = QTableWidgetItem(svc["category"])
            self.table.setItem(i, 1, cat_item)

            desc_item = QTableWidgetItem(svc["desc"])
            desc_item.setForeground(QColor("#888888"))
            self.table.setItem(i, 2, desc_item)

            self.table.setItem(i, 3, QTableWidgetItem("..."))
            self.table.setItem(i, 4, QTableWidgetItem("..."))

            btn = QPushButton("Toggle")
            btn.setFixedWidth(80)
            btn.clicked.connect(lambda checked, idx=i: self._toggle(idx))
            self.table.setCellWidget(i, 5, btn)

        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        btn_disable = QPushButton("DISABLE ALL")
        btn_disable.setObjectName("disableAll")
        btn_disable.clicked.connect(self._disable_all)
        btn_enable = QPushButton("ENABLE ALL")
        btn_enable.setObjectName("enableAll")
        btn_enable.clicked.connect(self._enable_all)
        btn_refresh = QPushButton("REFRESH STATUS")
        btn_refresh.setObjectName("refresh")
        btn_refresh.clicked.connect(self._refresh_all)
        btn_row.addWidget(btn_disable)
        btn_row.addWidget(btn_enable)
        btn_row.addStretch()
        btn_row.addWidget(btn_refresh)
        layout.addLayout(btn_row)

        self.status_label = QLabel("Ready.")
        self.status_label.setStyleSheet("color: #555; font-size: 11px; padding: 4px;")
        layout.addWidget(self.status_label)

    def _set_status(self, msg):
        self.status_label.setText(msg)

    def _refresh_all(self):
        for i, svc in enumerate(SERVICES):
            disabled = check_disabled(svc["domain"])
            running = check_running(svc["kill"])
            self.service_states[svc["domain"]] = {"disabled": disabled, "running": running}

            blocked_item = self.table.item(i, 3)
            if disabled:
                blocked_item.setText("YES")
                blocked_item.setForeground(QColor("#ff4444"))
            else:
                blocked_item.setText("NO")
                blocked_item.setForeground(QColor("#44ff44"))

            running_item = self.table.item(i, 4)
            if running:
                running_item.setText("YES")
                running_item.setForeground(QColor("#ffaa00"))
            else:
                running_item.setText("NO")
                running_item.setForeground(QColor("#555555"))

            btn = self.table.cellWidget(i, 5)
            if disabled:
                btn.setText("Enable")
                btn.setStyleSheet("background-color: #15304a; color: #44aaff;")
            else:
                btn.setText("Disable")
                btn.setStyleSheet("background-color: #4a1530; color: #ff6688;")

        self._set_status(f"Status refreshed — {len(SERVICES)} services monitored.")

    def _toggle(self, idx):
        svc = SERVICES[idx]
        state = self.service_states.get(svc["domain"], {})
        if state.get("disabled"):
            ok = enable_service(svc["domain"])
            if ok:
                self._set_status(f"Enabled: {svc['label']}")
            else:
                self._set_status(f"Failed to enable: {svc['label']}")
        else:
            ok = disable_service(svc["domain"])
            if ok:
                kill_process(svc["kill"])
                self._set_status(f"Disabled + killed: {svc['label']}")
            else:
                self._set_status(f"Failed to disable: {svc['label']}")
        self._refresh_all()

    def _disable_all(self):
        reply = QMessageBox.question(
            self, "Confirm",
            "Disable ALL listed services?\nSome may break iCloud, Siri, or widgets.\n"
            "You can re-enable them anytime.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        count = 0
        for svc in SERVICES:
            if disable_service(svc["domain"]):
                kill_process(svc["kill"])
                count += 1
        self._set_status(f"Disabled {count}/{len(SERVICES)} services.")
        self._refresh_all()

    def _enable_all(self):
        count = 0
        for svc in SERVICES:
            if enable_service(svc["domain"]):
                count += 1
        self._set_status(f"Enabled {count}/{len(SERVICES)} services.")
        self._refresh_all()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("MacControlPanel")
    window = ControlPanel()
    window.show()
    sys.exit(app.exec())
