#!/usr/bin/env python3
"""Mockup of the Unified MCP Setup Wizard GUI.
This is a visual prototype only — the real version will be built in Go with Fyne.
"""

import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QProgressBar, QStackedWidget,
    QFrame, QSizePolicy, QTextEdit, QComboBox, QCheckBox, QGridLayout,
    QMessageBox, QSpacerItem, QSizePolicy as QS
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QPointF
from PyQt6.QtGui import (
    QFont, QColor, QPalette, QLinearGradient, QBrush, QPainter,
    QPixmap, QPen, QPolygonF, QPainterPath
)
from PyQt6.QtGui import QGradient


class WizardMascot(QWidget):
    """Draws a simple wizard character with a wand."""

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Gradient background
        gradient = QLinearGradient(0, 0, 0, h)
        gradient.setColorAt(0, QColor("#1a365d"))
        gradient.setColorAt(1, QColor("#2a4a7d"))
        painter.fillRect(self.rect(), QBrush(gradient))

        # Draw wizard hat (triangle)
        cx = w // 2
        hat_top = int(h * 0.15)
        hat_bottom = int(h * 0.38)
        hat_width = int(w * 0.35)

        painter.setBrush(QBrush(QColor("#4a3a6a")))
        painter.setPen(QPen(QColor("#2a1a4a"), 2))
        hat = QPolygonF([
            QPointF(cx, hat_top),
            QPointF(cx - hat_width // 2, hat_bottom),
            QPointF(cx + hat_width // 2, hat_bottom),
        ])
        painter.drawPolygon(hat)

        # Hat star
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#FFD700")))
        star_size = 8
        sx, sy = cx, int(h * 0.28)
        self._draw_star(painter, sx, sy, star_size)

        # Wizard face (circle)
        face_y = int(h * 0.45)
        face_r = int(h * 0.08)
        painter.setBrush(QBrush(QColor("#F4D4A0")))
        painter.setPen(QPen(QColor("#D4A060"), 2))
        painter.drawEllipse(int(cx - face_r), int(face_y - face_r), face_r * 2, face_r * 2)

        # Eyes
        painter.setBrush(QBrush(QColor("#1a1a1a")))
        painter.setPen(Qt.PenStyle.NoPen)
        eye_offset = int(face_r * 0.35)
        eye_r = 3
        painter.drawEllipse(int(cx - eye_offset - eye_r), int(face_y - 3), eye_r * 2, eye_r * 2)
        painter.drawEllipse(int(cx + eye_offset - eye_r), int(face_y - 3), eye_r * 2, eye_r * 2)

        # Smile
        painter.setPen(QPen(QColor("#8a5a2a"), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(int(cx - face_r * 0.5), int(face_y + 2), int(face_r), int(face_r * 0.6), 0, -180 * 16)

        # Beard (white trapezoid)
        painter.setBrush(QBrush(QColor("#EEEEEE")))
        painter.setPen(QPen(QColor("#CCCCCC"), 1))
        beard = QPolygonF([
            QPointF(cx - face_r * 0.8, face_y + face_r * 0.3),
            QPointF(cx + face_r * 0.8, face_y + face_r * 0.3),
            QPointF(cx + face_r * 1.2, int(h * 0.62)),
            QPointF(cx - face_r * 1.2, int(h * 0.62)),
        ])
        painter.drawPolygon(beard)

        # Robe (trapezoid)
        robe_top = int(h * 0.58)
        robe_bottom = int(h * 0.88)
        robe_top_w = int(w * 0.25)
        robe_bottom_w = int(w * 0.45)
        painter.setBrush(QBrush(QColor("#3a2a5a")))
        painter.setPen(QPen(QColor("#2a1a4a"), 2))
        robe = QPolygonF([
            QPointF(cx - robe_top_w // 2, robe_top),
            QPointF(cx + robe_top_w // 2, robe_top),
            QPointF(cx + robe_bottom_w // 2, robe_bottom),
            QPointF(cx - robe_bottom_w // 2, robe_bottom),
        ])
        painter.drawPolygon(robe)

        # Wand (diagonal line with star tip)
        wand_start_x = cx + robe_top_w // 2
        wand_start_y = robe_top - 10
        wand_end_x = wand_start_x + int(w * 0.15)
        wand_end_y = wand_start_y - int(h * 0.12)
        painter.setPen(QPen(QColor("#8B4513"), 4))
        painter.drawLine(wand_start_x, wand_start_y, wand_end_x, wand_end_y)
        # Wand star tip
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#FFD700")))
        self._draw_star(painter, wand_end_x, wand_end_y, 6)

        # Branding text
        painter.setPen(QPen(QColor("#FFFFFF")))
        font = QFont("Arial", 14, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(self.rect().adjusted(0, int(h * 0.90), 0, 0), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, "Unified MCP")

    def _draw_star(self, painter, cx, cy, size):
        """Draw a simple 5-pointed star."""
        import math
        points = []
        for i in range(10):
            angle = i * math.pi / 5 - math.pi / 2
            r = size if i % 2 == 0 else size * 0.4
            points.append(QPointF(cx + r * math.cos(angle), cy + r * math.sin(angle)))
        star = QPolygonF(points)
        painter.drawPolygon(star)


class StepIndicator(QWidget):
    """Vertical step indicator showing all wizard steps."""

    step_changed = pyqtSignal(int)

    def __init__(self, steps, current=0):
        super().__init__()
        self.steps = steps
        self.current = current
        self.completed = set()
        self.labels = []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)

        for i, step_name in enumerate(self.steps):
            row = QHBoxLayout()
            row.setSpacing(8)

            icon = QLabel()
            icon.setFixedSize(20, 20)
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

            text = QLabel(step_name)
            text.setFont(QFont("Arial", 10))

            row.addWidget(icon)
            row.addWidget(text)
            row.addStretch()

            wrapper = QWidget()
            wrapper.setLayout(row)
            layout.addWidget(wrapper)

            self.labels.append((icon, text, wrapper))

        layout.addStretch()

    def set_current(self, step):
        self.current = step
        if step > 0:
            self.completed.add(step - 1)
        self._update()

    def _update(self):
        for i, (icon, text, wrapper) in enumerate(self.labels):
            if i in self.completed:
                icon.setText("✓")
                icon.setStyleSheet("color: #4CAF50; font-size: 14px; font-weight: bold;")
                text.setStyleSheet("color: #AAAAAA;")
            elif i == self.current:
                icon.setText("●")
                icon.setStyleSheet("color: #2196F3; font-size: 14px; font-weight: bold;")
                text.setStyleSheet("color: #FFFFFF; font-weight: bold;")
            else:
                icon.setText("○")
                icon.setStyleSheet("color: #555555; font-size: 14px;")
                text.setStyleSheet("color: #666666;")


class WizardPage(QWidget):
    """Base class for wizard pages."""

    def __init__(self, title, description=""):
        super().__init__()
        self.title = title
        self.description = description
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title_label = QLabel(self.title)
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(title_label)

        if self.description:
            desc_label = QLabel(self.description)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("color: #AAAAAA; font-size: 11px;")
            layout.addWidget(desc_label)

        # Content area — subclasses add widgets here
        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(10)
        layout.addLayout(self.content_layout)

        layout.addStretch()

    def add_widget(self, widget):
        self.content_layout.addWidget(widget)

    def add_layout(self, layout):
        self.content_layout.addLayout(layout)

    def is_valid(self):
        return True


class WelcomePage(WizardPage):
    def __init__(self):
        super().__init__(
            "Welcome to Unified MCP Setup Wizard",
            "This wizard will configure all your MCP services securely."
        )

        features = QLabel(
            "This wizard will configure:\n"
            "  •  Google Drive MCP (OAuth2)\n"
            "  •  Gmail MCP (OAuth2 + IMAP)\n"
            "  •  Yahoo Mail MCP (IMAP)\n"
            "  •  Chrome Integration\n"
            "  •  Model Configuration (OpenAI, Anthropic, Ollama, etc.)\n"
            "  •  Encrypted Credential Vault\n\n"
            "All credentials are encrypted with AES-256-GCM.\n"
            "You can re-run this wizard anytime to reconfigure."
        )
        features.setStyleSheet("color: #CCCCCC; font-size: 12px; line-height: 1.6;")
        self.add_widget(features)

        checks_label = QLabel("System Checks:")
        checks_label.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 12px;")
        self.add_widget(checks_label)

        self.checks_text = QTextEdit()
        self.checks_text.setReadOnly(True)
        self.checks_text.setMaximumHeight(120)
        self.checks_text.setStyleSheet(
            "QTextEdit { background: #1a1a2e; color: #4CAF50; font-family: monospace; font-size: 11px; border: 1px solid #333; }"
        )
        self.checks_text.setPlainText(
            "✓ Operating System: macOS (arm64)\n"
            "✓ Architecture: arm64\n"
            "✓ Permissions: ~/Library/Application Support/ writable\n"
            "✓ Disk Space: 482 GB available"
        )
        self.add_widget(self.checks_text)


class PasswordPage(WizardPage):
    def __init__(self):
        super().__init__(
            "Create Master Password",
            "This password encrypts ALL your credentials. There is NO recovery if you forget it."
        )

        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_input.setPlaceholderText("Enter password (min 12 chars)")
        self.pwd_input.setStyleSheet(self._input_style())
        self.add_widget(self.pwd_input)

        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_input.setPlaceholderText("Confirm password")
        self.confirm_input.setStyleSheet(self._input_style())
        self.add_widget(self.confirm_input)

        self.strength_bar = QProgressBar()
        self.strength_bar.setRange(0, 100)
        self.strength_bar.setValue(0)
        self.strength_bar.setTextVisible(False)
        self.strength_bar.setFixedHeight(12)
        self.strength_bar.setStyleSheet("QProgressBar { background: #333; border: none; } QProgressBar::chunk { background: #f44336; }")
        self.add_widget(self.strength_bar)

        self.strength_label = QLabel("Password strength: —")
        self.strength_label.setStyleSheet("color: #888; font-size: 11px;")
        self.add_widget(self.strength_label)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #f44336; font-size: 11px;")
        self.add_widget(self.error_label)

        self.pwd_input.textChanged.connect(self._check_strength)
        self.confirm_input.textChanged.connect(self._check_match)

    def _input_style(self):
        return "QLineEdit { background: #1a1a2e; color: #fff; border: 2px solid #333; padding: 8px; border-radius: 4px; font-size: 13px; } QLineEdit:focus { border-color: #2196F3; }"

    def _check_strength(self):
        pwd = self.pwd_input.text()
        score = 0
        if len(pwd) >= 12: score += 25
        if any(c.isupper() for c in pwd): score += 20
        if any(c.islower() for c in pwd): score += 20
        if any(c.isdigit() for c in pwd): score += 15
        if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in pwd): score += 20
        score = min(score, 100)

        self.strength_bar.setValue(score)
        if score < 40:
            self.strength_bar.setStyleSheet("QProgressBar { background: #333; border: none; } QProgressBar::chunk { background: #f44336; }")
            self.strength_label.setText("Password strength: Weak")
            self.strength_label.setStyleSheet("color: #f44336; font-size: 11px;")
        elif score < 70:
            self.strength_bar.setStyleSheet("QProgressBar { background: #333; border: none; } QProgressBar::chunk { background: #FF9800; }")
            self.strength_label.setText("Password strength: Fair")
            self.strength_label.setStyleSheet("color: #FF9800; font-size: 11px;")
        elif score < 90:
            self.strength_bar.setStyleSheet("QProgressBar { background: #333; border: none; } QProgressBar::chunk { background: #2196F3; }")
            self.strength_label.setText("Password strength: Good")
            self.strength_label.setStyleSheet("color: #2196F3; font-size: 11px;")
        else:
            self.strength_bar.setStyleSheet("QProgressBar { background: #333; border: none; } QProgressBar::chunk { background: #4CAF50; }")
            self.strength_label.setText("Password strength: Strong")
            self.strength_label.setStyleSheet("color: #4CAF50; font-size: 11px;")

        self._check_match()

    def _check_match(self):
        pwd = self.pwd_input.text()
        confirm = self.confirm_input.text()
        if confirm and pwd != confirm:
            self.error_label.setText("✗ Passwords do not match")
        elif confirm and pwd == confirm and len(pwd) >= 12:
            self.error_label.setText("✓ Passwords match")
            self.error_label.setStyleSheet("color: #4CAF50; font-size: 11px;")
        else:
            self.error_label.setText("")
            self.error_label.setStyleSheet("color: #f44336; font-size: 11px;")

    def is_valid(self):
        pwd = self.pwd_input.text()
        confirm = self.confirm_input.text()
        return len(pwd) >= 12 and pwd == confirm and any(c.isupper() for c in pwd) and any(c.isdigit() for c in pwd)


class VaultPage(WizardPage):
    def __init__(self):
        super().__init__(
            "Creating Encrypted Vault",
            "Generating secure vault with Argon2id key derivation and AES-256-GCM encryption."
        )

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.progress.setTextVisible(True)
        self.progress.setFormat("Vault created successfully")
        self.progress.setFixedHeight(24)
        self.progress.setStyleSheet("QProgressBar { background: #1a1a2e; border: 1px solid #333; text-align: center; color: #4CAF50; } QProgressBar::chunk { background: #4CAF50; }")
        self.add_widget(self.progress)

        info = QLabel(
            "✓ 32-byte random salt generated\n"
            "✓ Argon2id key derived (time=3, memory=64MB, parallelism=2)\n"
            "✓ 12-byte GCM nonce generated\n"
            "✓ Vault structure created\n\n"
            "Vault path: ~/Library/Application Support/MacConfig/vault.enc"
        )
        info.setStyleSheet("color: #4CAF50; font-family: monospace; font-size: 11px;")
        self.add_widget(info)


class ChromePage(WizardPage):
    def __init__(self):
        super().__init__(
            "Chrome Integration Check",
            "Chrome is recommended for OAuth flows."
        )

        self.status = QLabel(
            "✓ Chrome found at: /Applications/Google Chrome.app\n"
            "✓ Default browser: Google Chrome\n\n"
            "Chrome is ready for OAuth flows."
        )
        self.status.setStyleSheet("color: #4CAF50; font-size: 12px;")
        self.add_widget(self.status)

        btn_row = QHBoxLayout()
        self.download_btn = QPushButton("Download Chrome")
        self.download_btn.setStyleSheet(self._btn_style())
        self.locate_btn = QPushButton("Locate Chrome")
        self.locate_btn.setStyleSheet(self._btn_style())
        btn_row.addWidget(self.download_btn)
        btn_row.addWidget(self.locate_btn)
        btn_row.addStretch()
        self.add_layout(btn_row)

    def _btn_style(self):
        return "QPushButton { background: #333; color: #fff; border: 1px solid #555; padding: 6px 16px; border-radius: 4px; } QPushButton:hover { background: #444; }"


class GoogleAccountPage(WizardPage):
    def __init__(self):
        super().__init__(
            "Google Account Setup",
            "Click 'Authorize' to open your browser for Google consent."
        )

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("your.email@gmail.com")
        self.email_input.setText("wplundall@gmail.com")
        self.email_input.setStyleSheet(self._input_style())
        self.add_widget(QLabel("Google Email:"))
        self.add_widget(self.email_input)

        self.client_combo = QComboBox()
        self.client_combo.addItems(["cascadewayne", "backup_498022_a", "backup_498022_b"])
        self.client_combo.setStyleSheet(self._combo_style())
        self.add_widget(QLabel("OAuth Client:"))
        self.add_widget(self.client_combo)

        self.client_id_input = QLineEdit()
        self.client_id_input.setText("768426539127-anlok2ht6pcuh9p854nlh012ncv087r7.apps.googleusercontent.com")
        self.client_id_input.setStyleSheet(self._input_style())
        self.add_widget(QLabel("Client ID:"))
        self.add_widget(self.client_id_input)

        self.client_secret_input = QLineEdit()
        self.client_secret_input.setText("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")
        self.client_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.client_secret_input.setStyleSheet(self._input_style())
        self.add_widget(QLabel("Client Secret:"))
        self.add_widget(self.client_secret_input)

        self.auth_btn = QPushButton("🔐  Authorize Google Account")
        self.auth_btn.setStyleSheet(
            "QPushButton { background: #4285F4; color: white; border: none; padding: 10px 20px; "
            "border-radius: 4px; font-size: 13px; font-weight: bold; } QPushButton:hover { background: #3367D6; }"
        )
        self.auth_btn.setMinimumHeight(40)
        self.add_widget(self.auth_btn)

        self.auth_status = QLabel("⚠ Not yet authorized")
        self.auth_status.setStyleSheet("color: #FF9800; font-size: 12px;")
        self.add_widget(self.auth_status)

    def _input_style(self):
        return "QLineEdit { background: #1a1a2e; color: #fff; border: 2px solid #333; padding: 8px; border-radius: 4px; font-size: 12px; } QLineEdit:focus { border-color: #4285F4; }"

    def _combo_style(self):
        return "QComboBox { background: #1a1a2e; color: #fff; border: 2px solid #333; padding: 6px; border-radius: 4px; } QComboBox::drop-down { border: none; } QComboBox QAbstractItemView { background: #1a1a2e; color: #fff; selection-background-color: #4285F4; }"


class DrivePage(WizardPage):
    def __init__(self):
        super().__init__(
            "Google Drive MCP Configuration",
            "Google Drive is configured using the Google account from the previous step."
        )

        self.oauth_status = QLabel("✓ OAuth token: Authorized (expires in 59 minutes)")
        self.oauth_status.setStyleSheet("color: #4CAF50; font-size: 12px;")
        self.add_widget(self.oauth_status)

        for test_name, result in [("Test Read", "✓ 5 files found (Untitled19.ipynb, FreeCreditReport.pdf, ...)"),
                                    ("Test Write", "✓ Test file created and deleted"),
                                    ("Test List", "✓ 12 folders found")]:
            row = QHBoxLayout()
            btn = QPushButton(test_name)
            btn.setStyleSheet("QPushButton { background: #333; color: #fff; border: 1px solid #555; padding: 6px 16px; border-radius: 4px; min-width: 100px; } QPushButton:hover { background: #444; }")
            label = QLabel(result)
            label.setStyleSheet("color: #4CAF50; font-size: 11px;")
            label.setWordWrap(True)
            row.addWidget(btn)
            row.addWidget(label, 1)
            self.add_layout(row)


class GmailPage(WizardPage):
    def __init__(self):
        super().__init__(
            "Gmail MCP Configuration",
            "Gmail uses the same OAuth token. Testing IMAP XOAUTH2 authentication."
        )

        self.oauth_status = QLabel("✓ OAuth token: Authorized (scope: https://mail.google.com/)")
        self.oauth_status.setStyleSheet("color: #4CAF50; font-size: 12px;")
        self.add_widget(self.oauth_status)

        for test_name, result in [("Test Auth", "✓ IMAP XOAUTH2 login to imap.gmail.com:993 — OK"),
                                    ("Test Inbox", "✓ 5 recent emails retrieved"),
                                    ("Test Send", "✓ Test email sent to wplundall@gmail.com")]:
            row = QHBoxLayout()
            btn = QPushButton(test_name)
            btn.setStyleSheet("QPushButton { background: #333; color: #fff; border: 1px solid #555; padding: 6px 16px; border-radius: 4px; min-width: 100px; } QPushButton:hover { background: #444; }")
            label = QLabel(result)
            label.setStyleSheet("color: #4CAF50; font-size: 11px;")
            label.setWordWrap(True)
            row.addWidget(btn)
            row.addWidget(label, 1)
            self.add_layout(row)


class YahooPage(WizardPage):
    def __init__(self):
        super().__init__(
            "Yahoo Mail Configuration",
            "Enter your Yahoo Mail credentials. You need an App Password."
        )

        help_label = QLabel(
            "Generate one at: https://login.yahoo.com/account/security/app-passwords\n"
            "1. Go to Yahoo Account Security\n"
            "2. Click 'Generate app password'\n"
            "3. Select 'Other App' and enter 'MCP Server'\n"
            "4. Copy the 16-character password"
        )
        help_label.setStyleSheet("color: #888; font-size: 11px;")
        help_label.setWordWrap(True)
        self.add_widget(help_label)

        self.open_btn = QPushButton("🔗 Open Yahoo App Passwords")
        self.open_btn.setStyleSheet("QPushButton { background: #6001D2; color: white; border: none; padding: 8px 16px; border-radius: 4px; } QPushButton:hover { background: #7801E6; }")
        self.add_widget(self.open_btn)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("your.email@yahoo.com")
        self.email_input.setText("wlundall@yahoo.com")
        self.email_input.setStyleSheet("QLineEdit { background: #1a1a2e; color: #fff; border: 2px solid #333; padding: 8px; border-radius: 4px; font-size: 12px; }")
        self.add_widget(QLabel("Yahoo Email:"))
        self.add_widget(self.email_input)

        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_input.setPlaceholderText("16-character app password")
        self.pwd_input.setStyleSheet("QLineEdit { background: #1a1a2e; color: #fff; border: 2px solid #333; padding: 8px; border-radius: 4px; font-size: 12px; }")
        self.add_widget(QLabel("App Password:"))
        self.add_widget(self.pwd_input)

        self.test_btn = QPushButton("🔌 Test Connection")
        self.test_btn.setStyleSheet("QPushButton { background: #333; color: #fff; border: 1px solid #555; padding: 8px 16px; border-radius: 4px; } QPushButton:hover { background: #444; }")
        self.add_widget(self.test_btn)

        self.test_result = QLabel("✓ Connected! Inbox has 1,234 emails")
        self.test_result.setStyleSheet("color: #4CAF50; font-size: 12px;")
        self.add_widget(self.test_result)


class ModelConfigPage(WizardPage):
    def __init__(self):
        super().__init__(
            "AI Model Configuration",
            "Configure AI model providers. All API keys are encrypted in the vault."
        )

        providers = [
            ("OpenAI", "https://api.openai.com/v1", "gpt-4o", True),
            ("Anthropic", "https://api.anthropic.com", "claude-sonnet-4-20250514", True),
            ("Ollama", "http://localhost:11434", "llama3", False),
            ("OpenRouter", "https://openrouter.ai/api/v1", "auto", False),
            ("HuggingFace", "https://huggingface.co", "mistralai/Mistral-7B", False),
        ]

        for name, endpoint, model, enabled in providers:
            row = QHBoxLayout()

            checkbox = QCheckBox(name)
            checkbox.setChecked(enabled)
            checkbox.setStyleSheet("QCheckBox { color: #fff; font-weight: bold; }")

            api_key = QLineEdit()
            api_key.setEchoMode(QLineEdit.EchoMode.Password)
            api_key.setPlaceholderText("API key (masked)")
            api_key.setStyleSheet("QLineEdit { background: #1a1a2e; color: #fff; border: 1px solid #333; padding: 4px; border-radius: 3px; font-size: 11px; }")
            api_key.setEnabled(enabled)

            model_label = QLabel(f"{model}")
            model_label.setStyleSheet("color: #888; font-size: 10px;")
            model_label.setMinimumWidth(120)

            test_btn = QPushButton("Test")
            test_btn.setStyleSheet("QPushButton { background: #333; color: #aaa; border: 1px solid #444; padding: 4px 10px; border-radius: 3px; font-size: 11px; }")
            test_btn.setFixedWidth(50)

            row.addWidget(checkbox)
            row.addWidget(api_key, 1)
            row.addWidget(model_label)
            row.addWidget(test_btn)

            self.add_layout(row)


class VerificationPage(WizardPage):
    def __init__(self):
        super().__init__(
            "Final Verification",
            "Running full system validation..."
        )

        results = [
            ("Google Drive MCP", True, "5 files listed, write/delete OK"),
            ("Gmail MCP", True, "IMAP auth OK, 5 emails listed"),
            ("Yahoo MCP", True, "IMAP auth OK, 5 emails listed"),
            ("Chrome Integration", True, "Chrome found at /Applications/..."),
            ("Model Configuration", True, "2 providers configured"),
            ("Vault", True, "AES-256-GCM, Argon2id"),
            ("Encryption", True, "Config encrypted at ~/Library/.../vault.enc"),
            ("Permissions", True, "All paths writable"),
        ]

        for name, passed, details in results:
            row = QHBoxLayout()
            icon = QLabel("✅" if passed else "❌")
            icon.setFixedSize(24, 24)
            name_label = QLabel(name)
            name_label.setStyleSheet(f"color: {'#4CAF50' if passed else '#f44336'}; font-weight: bold; font-size: 12px;")
            details_label = QLabel(details)
            details_label.setStyleSheet("color: #888; font-size: 11px;")
            row.addWidget(icon)
            row.addWidget(name_label)
            row.addWidget(details_label, 1)
            self.add_layout(row)

        self.save_btn = QPushButton("💾  Save & Apply")
        self.save_btn.setStyleSheet(
            "QPushButton { background: #4CAF50; color: white; border: none; padding: 12px 24px; "
            "border-radius: 4px; font-size: 14px; font-weight: bold; } QPushButton:hover { background: #45a049; }"
        )
        self.save_btn.setMinimumHeight(44)
        self.add_widget(self.save_btn)


class FinishPage(WizardPage):
    def __init__(self):
        super().__init__(
            "Setup Complete!",
            "All services configured and encrypted."
        )

        summary = QLabel(
            "✓ Google Drive — ready (OAuth2 auto-refresh)\n"
            "✓ Gmail — ready (OAuth2 auto-refresh)\n"
            "✓ Yahoo Mail — ready (IMAP)\n"
            "✓ Chrome — detected\n"
            "✓ Models — 2 providers configured\n"
            "✓ Vault — AES-256-GCM encrypted\n\n"
            "Config: ~/Library/Application Support/MacConfig/vault.enc\n\n"
            "To start MCP email server:\n"
            "  EMAIL_CONFIG_FILE=~/.config/mcp-email/accounts.json \\\n"
            "    mcp-server-email\n\n"
            "To reconfigure: Run this wizard again.\n"
            "To manage: Use the Control Center (system tray)."
        )
        summary.setStyleSheet("color: #CCCCCC; font-size: 12px; line-height: 1.6;")
        summary.setWordWrap(True)
        self.add_widget(summary)

        report_btn = QPushButton("📄  Generate System Report")
        report_btn.setStyleSheet("QPushButton { background: #333; color: #fff; border: 1px solid #555; padding: 8px 16px; border-radius: 4px; } QPushButton:hover { background: #444; }")
        self.add_widget(report_btn)


class WizardWindow(QMainWindow):
    """Main wizard window with left panel (mascot + steps) and right panel (content)."""

    STEPS = [
        "Welcome",
        "Master Password",
        "Vault Creation",
        "Chrome Verification",
        "Google Account",
        "Google Drive",
        "Gmail",
        "Yahoo Mail",
        "Model Configuration",
        "Final Verification",
        "Finish",
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Unified MCP Setup Wizard")
        self.setFixedSize(800, 600)
        self._apply_dark_theme()

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Left panel
        left_panel = QWidget()
        left_panel.setFixedWidth(280)
        left_panel.setStyleSheet("background: #0d1117;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # Wizard mascot
        self.mascot = WizardMascot()
        self.mascot.setFixedHeight(280)
        left_layout.addWidget(self.mascot)

        # Step indicator
        self.step_indicator = StepIndicator(self.STEPS, current=0)
        self.step_indicator.setStyleSheet("background: #0d1117;")
        left_layout.addWidget(self.step_indicator, 1)

        main_layout.addWidget(left_panel)

        # Right panel
        right_panel = QWidget()
        right_panel.setStyleSheet("background: #161b22;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Page stack
        self.stack = QStackedWidget()
        self.pages = [
            WelcomePage(),
            PasswordPage(),
            VaultPage(),
            ChromePage(),
            GoogleAccountPage(),
            DrivePage(),
            GmailPage(),
            YahooPage(),
            ModelConfigPage(),
            VerificationPage(),
            FinishPage(),
        ]
        for page in self.pages:
            self.stack.addWidget(page)
        right_layout.addWidget(self.stack, 1)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, len(self.STEPS) - 1)
        self.progress.setValue(0)
        self.progress.setFormat(f"Step 1 of {len(self.STEPS)} — {int(1/len(self.STEPS)*100)}%")
        self.progress.setFixedHeight(20)
        self.progress.setStyleSheet("QProgressBar { background: #0d1117; border: none; text-align: center; color: #888; font-size: 11px; } QProgressBar::chunk { background: #2196F3; }")
        right_layout.addWidget(self.progress)

        # Navigation bar
        nav = QWidget()
        nav.setFixedHeight(50)
        nav.setStyleSheet("background: #0d1117;")
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(20, 8, 20, 8)

        self.back_btn = QPushButton("←  Back")
        self.back_btn.setStyleSheet(self._nav_btn_style(enabled=False))
        self.back_btn.setEnabled(False)
        self.back_btn.setFixedHeight(34)
        self.back_btn.clicked.connect(self.go_back)

        self.next_btn = QPushButton("Next  →")
        self.next_btn.setStyleSheet(self._nav_btn_style(enabled=True))
        self.next_btn.setFixedHeight(34)
        self.next_btn.clicked.connect(self.go_next)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet(self._nav_btn_style(enabled=True, danger=True))
        self.cancel_btn.setFixedHeight(34)
        self.cancel_btn.clicked.connect(self.close)

        nav_layout.addWidget(self.back_btn)
        nav_layout.addStretch()
        nav_layout.addWidget(self.cancel_btn)
        nav_layout.addWidget(self.next_btn)

        right_layout.addWidget(nav)

        main_layout.addWidget(right_panel, 1)

        self.current_step = 0
        self._update_ui()

    def _apply_dark_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#161b22"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#FFFFFF"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#1a1a2e"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#FFFFFF"))
        palette.setColor(QPalette.ColorRole.Button, QColor("#333333"))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("#FFFFFF"))
        self.setPalette(palette)
        self.setStyleSheet("QMainWindow { background: #161b22; }")

    def _nav_btn_style(self, enabled=True, danger=False):
        bg = "#333" if enabled else "#222"
        hover = "#444" if enabled else "#222"
        color = "#f44336" if danger else "#fff"
        return f"QPushButton {{ background: {bg}; color: {color}; border: 1px solid #555; padding: 6px 20px; border-radius: 4px; font-size: 13px; }} QPushButton:hover {{ background: {hover}; }} QPushButton:disabled {{ background: #222; color: #555; }}"

    def _update_ui(self):
        self.stack.setCurrentIndex(self.current_step)
        self.step_indicator.set_current(self.current_step)

        pct = int((self.current_step + 1) / len(self.STEPS) * 100)
        self.progress.setValue(self.current_step)
        self.progress.setFormat(f"Step {self.current_step + 1} of {len(self.STEPS)} — {pct}%")

        self.back_btn.setEnabled(self.current_step > 0)
        self.back_btn.setStyleSheet(self._nav_btn_style(enabled=self.current_step > 0))

        if self.current_step == len(self.STEPS) - 1:
            self.next_btn.setText("Finish  ✓")
        else:
            self.next_btn.setText("Next  →")

    def go_next(self):
        if self.current_step < len(self.STEPS) - 1:
            self.current_step += 1
            self._update_ui()
        else:
            self.close()

    def go_back(self):
        if self.current_step > 0:
            self.current_step -= 1
            self._update_ui()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Unified MCP Setup Wizard")

    window = WizardWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
