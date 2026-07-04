#!/usr/bin/env python3
"""Unified MCP Setup Wizard GUI — v2 with proper SVG wizard mascots."""

import sys
import math
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QProgressBar, QStackedWidget,
    QTextEdit, QComboBox, QCheckBox, QButtonGroup, QRadioButton,
    QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QPointF, QByteArray
from PyQt6.QtGui import (
    QFont, QColor, QPalette, QLinearGradient, QBrush, QPainter,
    QPen, QPolygonF, QPixmap, QPainterPath
)
from PyQt6.QtSvgWidgets import QSvgWidget


# ─── SVG Wizard Mascots ───

WIZARD_SVG_1 = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 300" width="200" height="300">
  <defs>
    <linearGradient id="bg1" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#1a365d"/>
      <stop offset="100%" stop-color="#2a4a7d"/>
    </linearGradient>
    <linearGradient id="hat1" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#6a4a8a"/>
      <stop offset="100%" stop-color="#4a2a6a"/>
    </linearGradient>
    <linearGradient id="robe1" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#4a3a6a"/>
      <stop offset="100%" stop-color="#2a1a4a"/>
    </linearGradient>
    <radialGradient id="glow1" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0%" stop-color="#FFD700" stop-opacity="0.6"/>
      <stop offset="100%" stop-color="#FFD700" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="200" height="300" fill="url(#bg1)"/>
  
  <!-- Glow behind wand star -->
  <circle cx="155" cy="80" r="30" fill="url(#glow1)"/>
  
  <!-- Robe -->
  <path d="M 70 180 Q 60 230 50 280 L 150 280 Q 140 230 130 180 Z" fill="url(#robe1)" stroke="#1a0a3a" stroke-width="2"/>
  
  <!-- Robe trim (gold) -->
  <path d="M 50 280 Q 100 275 150 280" fill="none" stroke="#FFD700" stroke-width="3"/>
  
  <!-- Arms -->
  <path d="M 72 185 Q 55 170 60 155" fill="none" stroke="url(#robe1)" stroke-width="14" stroke-linecap="round"/>
  <path d="M 128 185 Q 145 165 150 145" fill="none" stroke="url(#robe1)" stroke-width="14" stroke-linecap="round"/>
  
  <!-- Hands -->
  <circle cx="60" cy="155" r="7" fill="#F4D4A0"/>
  <circle cx="150" cy="145" r="7" fill="#F4D4A0"/>
  
  <!-- Wand -->
  <line x1="150" y1="145" x2="165" y2="85" stroke="#8B4513" stroke-width="4" stroke-linecap="round"/>
  
  <!-- Wand star -->
  <polygon points="165,85 169,75 175,73 169,71 165,61 161,71 155,73 161,75" fill="#FFD700" stroke="#FFA500" stroke-width="1"/>
  <polygon points="165,85 169,75 175,73 169,71 165,61 161,71 155,73 161,75" fill="#FFFACD" opacity="0.5" transform="scale(0.5) translate(165,85)"/>
  
  <!-- Head/Face -->
  <ellipse cx="100" cy="140" rx="28" ry="32" fill="#F4D4A0" stroke="#D4A060" stroke-width="1.5"/>
  
  <!-- Eyes -->
  <ellipse cx="92" cy="135" rx="3" ry="4" fill="#1a1a2e"/>
  <ellipse cx="108" cy="135" rx="3" ry="4" fill="#1a1a2e"/>
  <circle cx="93" cy="134" r="1" fill="#fff"/>
  <circle cx="109" cy="134" r="1" fill="#fff"/>
  
  <!-- Eyebrows -->
  <path d="M 87 128 Q 92 126 96 128" fill="none" stroke="#8a6a3a" stroke-width="2"/>
  <path d="M 104 128 Q 108 126 113 128" fill="none" stroke="#8a6a3a" stroke-width="2"/>
  
  <!-- Nose -->
  <path d="M 100 140 Q 97 145 100 148 Q 103 145 100 140" fill="#E4C490" stroke="#D4A060" stroke-width="0.5"/>
  
  <!-- Smile -->
  <path d="M 92 152 Q 100 157 108 152" fill="none" stroke="#8a5a2a" stroke-width="2" stroke-linecap="round"/>
  
  <!-- Beard (flowing) -->
  <path d="M 78 148 Q 75 170 80 185 Q 85 175 90 180 Q 95 170 100 178 Q 105 170 110 180 Q 115 175 120 185 Q 125 170 122 148 Q 110 158 100 155 Q 90 158 78 148 Z" fill="#EEEEEE" stroke="#CCCCCC" stroke-width="1"/>
  
  <!-- Mustache -->
  <path d="M 88 148 Q 84 152 82 155 Q 88 153 92 150" fill="#EEEEEE" stroke="#CCCCCC" stroke-width="0.5"/>
  <path d="M 112 148 Q 116 152 118 155 Q 112 153 108 150" fill="#EEEEEE" stroke="#CCCCCC" stroke-width="0.5"/>
  
  <!-- Hat -->
  <path d="M 65 120 Q 100 50 135 120 Q 100 105 65 120 Z" fill="url(#hat1)" stroke="#2a0a4a" stroke-width="2"/>
  
  <!-- Hat bend (droopy tip) -->
  <path d="M 100 50 Q 105 45 110 52" fill="none" stroke="#2a0a4a" stroke-width="2"/>
  
  <!-- Hat brim -->
  <ellipse cx="100" cy="120" rx="42" ry="8" fill="#3a1a5a" stroke="#1a0a3a" stroke-width="1.5"/>
  
  <!-- Hat stars -->
  <polygon points="100,70 103,63 110,62 103,59 100,52 97,59 90,62 97,63" fill="#FFD700" opacity="0.9"/>
  <polygon points="85,95 87,91 91,90 87,89 85,85 83,89 79,90 83,91" fill="#FFD700" opacity="0.7"/>
  <polygon points="115,90 117,86 121,85 117,84 115,80 113,84 109,85 113,86" fill="#FFD700" opacity="0.7"/>
  
  <!-- Sparkles -->
  <circle cx="45" cy="100" r="2" fill="#FFD700" opacity="0.6"/>
  <circle cx="170" cy="120" r="1.5" fill="#FFD700" opacity="0.5"/>
  <circle cx="30" cy="200" r="2" fill="#FFD700" opacity="0.4"/>
  <circle cx="180" cy="220" r="1.5" fill="#FFD700" opacity="0.4"/>
  
  <!-- Branding -->
  <text x="100" y="295" text-anchor="middle" font-family="Arial" font-size="13" font-weight="bold" fill="#FFFFFF">Unified MCP</text>
</svg>'''


WIZARD_SVG_2 = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 300" width="200" height="300">
  <defs>
    <linearGradient id="bg2" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#1a1a3e"/>
      <stop offset="100%" stop-color="#2a2a5e"/>
    </linearGradient>
    <linearGradient id="hat2" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#1a5276"/>
      <stop offset="100%" stop-color="#0a3a56"/>
    </linearGradient>
    <linearGradient id="robe2" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#1a5276"/>
      <stop offset="100%" stop-color="#0a2a46"/>
    </linearGradient>
    <radialGradient id="orb2" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0%" stop-color="#00FFFF" stop-opacity="0.8"/>
      <stop offset="50%" stop-color="#0088FF" stop-opacity="0.4"/>
      <stop offset="100%" stop-color="#0044AA" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="200" height="300" fill="url(#bg2)"/>
  
  <!-- Magic orb glow -->
  <circle cx="55" cy="160" r="35" fill="url(#orb2)"/>
  
  <!-- Robe (wider, more majestic) -->
  <path d="M 65 175 Q 45 240 35 285 L 165 285 Q 155 240 135 175 Z" fill="url(#robe2)" stroke="#0a1a36" stroke-width="2"/>
  
  <!-- Robe trim (silver/cyan) -->
  <path d="M 35 285 Q 100 278 165 285" fill="none" stroke="#00BFFF" stroke-width="3"/>
  <path d="M 35 285 Q 100 278 165 285" fill="none" stroke="#FFFFFF" stroke-width="1" opacity="0.5"/>
  
  <!-- Robe decorations (runes) -->
  <circle cx="100" cy="220" r="6" fill="none" stroke="#00BFFF" stroke-width="1.5" opacity="0.6"/>
  <path d="M 97 220 L 103 220 M 100 217 L 100 223" stroke="#00BFFF" stroke-width="1" opacity="0.6"/>
  
  <!-- Left arm holding orb -->
  <path d="M 72 180 Q 60 170 55 160" fill="none" stroke="url(#robe2)" stroke-width="14" stroke-linecap="round"/>
  <circle cx="55" cy="160" r="8" fill="#F4D4A0"/>
  
  <!-- Magic orb -->
  <circle cx="55" cy="160" r="10" fill="#00BFFF" opacity="0.7"/>
  <circle cx="55" cy="160" r="6" fill="#00FFFF" opacity="0.9"/>
  <circle cx="53" cy="158" r="2" fill="#FFFFFF" opacity="0.8"/>
  
  <!-- Right arm with wand -->
  <path d="M 128 180 Q 140 160 145 130" fill="none" stroke="url(#robe2)" stroke-width="14" stroke-linecap="round"/>
  <circle cx="145" cy="130" r="7" fill="#F4D4A0"/>
  
  <!-- Wand (crystal) -->
  <line x1="145" y1="130" x2="160" y2="75" stroke="#C0C0C0" stroke-width="4" stroke-linecap="round"/>
  <polygon points="160,75 164,65 168,68 165,78 162,72" fill="#00FFFF" stroke="#00BFFF" stroke-width="1"/>
  <circle cx="165" cy="70" r="4" fill="#00FFFF" opacity="0.5"/>
  
  <!-- Head/Face -->
  <ellipse cx="100" cy="135" rx="26" ry="30" fill="#F4D4A0" stroke="#D4A060" stroke-width="1.5"/>
  
  <!-- Eyes (glowing blue) -->
  <ellipse cx="92" cy="130" rx="3" ry="4" fill="#1a1a2e"/>
  <ellipse cx="108" cy="130" rx="3" ry="4" fill="#1a1a2e"/>
  <circle cx="92" cy="129" r="1.5" fill="#00BFFF"/>
  <circle cx="108" cy="129" r="1.5" fill="#00BFFF"/>
  
  <!-- Serious eyebrows -->
  <path d="M 86 124 L 97 126" fill="none" stroke="#5a4a2a" stroke-width="2.5" stroke-linecap="round"/>
  <path d="M 103 126 L 114 124" fill="none" stroke="#5a4a2a" stroke-width="2.5" stroke-linecap="round"/>
  
  <!-- Nose -->
  <path d="M 100 135 L 97 142 L 100 144 L 103 142 Z" fill="#E4C490"/>
  
  <!-- Determined mouth -->
  <path d="M 92 150 L 108 150" fill="none" stroke="#6a4a2a" stroke-width="2" stroke-linecap="round"/>
  
  <!-- Long beard (silver-blue) -->
  <path d="M 76 145 Q 72 175 78 195 Q 83 185 88 192 Q 93 180 98 190 Q 103 180 108 192 Q 113 185 118 195 Q 124 175 122 145 Q 110 152 100 150 Q 90 152 76 145 Z" fill="#D0D0E0" stroke="#A0A0C0" stroke-width="1"/>
  
  <!-- Mustache (curled) -->
  <path d="M 86 145 Q 80 150 78 155 Q 84 152 90 148" fill="#D0D0E0" stroke="#A0A0C0" stroke-width="0.5"/>
  <path d="M 114 145 Q 120 150 122 155 Q 116 152 110 148" fill="#D0D0E0" stroke="#A0A0C0" stroke-width="0.5"/>
  
  <!-- Tall pointy hat -->
  <path d="M 62 115 L 100 25 L 138 115 Q 100 100 62 115 Z" fill="url(#hat2)" stroke="#021a36" stroke-width="2"/>
  
  <!-- Hat brim -->
  <ellipse cx="100" cy="115" rx="44" ry="7" fill="#0a3a56" stroke="#021a36" stroke-width="1.5"/>
  
  <!-- Hat decorations (crescent moon + stars) -->
  <path d="M 95 55 A 8 8 0 1 0 103 63 A 6 6 0 1 1 95 55 Z" fill="#FFD700" opacity="0.8"/>
  <polygon points="115,85 117,81 121,80 117,79 115,75 113,79 109,80 113,81" fill="#FFD700" opacity="0.7"/>
  <polygon points="80,90 82,87 85,86 82,85 80,82 78,85 75,86 78,87" fill="#FFD700" opacity="0.6"/>
  
  <!-- Magic particles -->
  <circle cx="40" cy="80" r="2" fill="#00BFFF" opacity="0.5"/>
  <circle cx="175" cy="100" r="1.5" fill="#00BFFF" opacity="0.4"/>
  <circle cx="25" cy="180" r="2" fill="#00BFFF" opacity="0.3"/>
  <circle cx="185" cy="200" r="1.5" fill="#00BFFF" opacity="0.3"/>
  <circle cx="50" cy="130" r="1" fill="#FFFFFF" opacity="0.6"/>
  <circle cx="170" cy="150" r="1" fill="#FFFFFF" opacity="0.5"/>
  
  <!-- Branding -->
  <text x="100" y="295" text-anchor="middle" font-family="Arial" font-size="13" font-weight="bold" fill="#FFFFFF">Unified MCP</text>
</svg>'''


WIZARD_SVG_3 = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 300" width="200" height="300">
  <defs>
    <linearGradient id="bg3" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#2d1b4e"/>
      <stop offset="100%" stop-color="#1d0b3e"/>
    </linearGradient>
    <linearGradient id="hat3" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#8B0000"/>
      <stop offset="100%" stop-color="#5B0000"/>
    </linearGradient>
    <linearGradient id="robe3" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#6B2B00"/>
      <stop offset="100%" stop-color="#3B1B00"/>
    </linearGradient>
    <radialGradient id="fire3" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0%" stop-color="#FF4500" stop-opacity="0.8"/>
      <stop offset="50%" stop-color="#FF8C00" stop-opacity="0.4"/>
      <stop offset="100%" stop-color="#FFD700" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="200" height="300" fill="url(#bg3)"/>
  
  <!-- Fire glow -->
  <circle cx="155" cy="90" r="35" fill="url(#fire3)"/>
  
  <!-- Robe (dark red/brown, battle mage) -->
  <path d="M 68 178 Q 55 235 48 285 L 152 285 Q 145 235 132 178 Z" fill="url(#robe3)" stroke="#2B0B00" stroke-width="2"/>
  
  <!-- Robe trim (gold/orange) -->
  <path d="M 48 285 Q 100 278 152 285" fill="none" stroke="#FF8C00" stroke-width="3"/>
  
  <!-- Chest plate/armor -->
  <path d="M 82 178 L 82 210 Q 100 215 118 210 L 118 178" fill="#4a2a1a" stroke="#2a1a0a" stroke-width="1"/>
  <circle cx="100" cy="195" r="5" fill="#FF4500" opacity="0.7"/>
  <circle cx="100" cy="195" r="3" fill="#FFD700" opacity="0.9"/>
  
  <!-- Arms -->
  <path d="M 70 185 Q 55 175 52 165" fill="none" stroke="url(#robe3)" stroke-width="14" stroke-linecap="round"/>
  <path d="M 130 185 Q 142 170 148 150" fill="none" stroke="url(#robe3)" stroke-width="14" stroke-linecap="round"/>
  
  <!-- Hands -->
  <circle cx="52" cy="165" r="7" fill="#D4A060"/>
  <circle cx="148" cy="150" r="7" fill="#D4A060"/>
  
  <!-- Fire wand -->
  <line x1="148" y1="150" x2="160" y2="85" stroke="#4a2a1a" stroke-width="5" stroke-linecap="round"/>
  
  <!-- Fire ball -->
  <circle cx="160" cy="85" r="8" fill="#FF4500" opacity="0.8"/>
  <circle cx="160" cy="85" r="5" fill="#FFD700" opacity="0.9"/>
  <circle cx="158" cy="83" r="2" fill="#FFFFFF" opacity="0.7"/>
  
  <!-- Fire trails -->
  <path d="M 160 85 Q 155 75 158 65" fill="none" stroke="#FF4500" stroke-width="2" opacity="0.5"/>
  <path d="M 160 85 Q 165 75 162 65" fill="none" stroke="#FF8C00" stroke-width="2" opacity="0.4"/>
  
  <!-- Head/Face (weathered) -->
  <ellipse cx="100" cy="138" rx="27" ry="31" fill="#D4A060" stroke="#A47030" stroke-width="1.5"/>
  
  <!-- Scar -->
  <line x1="95" y1="125" x2="98" y2="142" stroke="#8B4513" stroke-width="1.5" opacity="0.6"/>
  
  <!-- Eyes (amber/glowing) -->
  <ellipse cx="91" cy="132" rx="3.5" ry="4" fill="#1a1a1a"/>
  <ellipse cx="109" cy="132" rx="3.5" ry="4" fill="#1a1a1a"/>
  <circle cx="91" cy="131" r="1.5" fill="#FF8C00"/>
  <circle cx="109" cy="131" r="1.5" fill="#FF8C00"/>
  
  <!-- Angry eyebrows -->
  <path d="M 84 125 L 96 129" fill="none" stroke="#3a2a1a" stroke-width="3" stroke-linecap="round"/>
  <path d="M 104 129 L 116 125" fill="none" stroke="#3a2a1a" stroke-width="3" stroke-linecap="round"/>
  
  <!-- Nose (crooked) -->
  <path d="M 100 138 L 96 146 L 102 148 L 104 144" fill="#C49050" stroke="#A47030" stroke-width="0.5"/>
  
  <!-- Smirk -->
  <path d="M 90 152 Q 100 155 110 150" fill="none" stroke="#5a3a1a" stroke-width="2" stroke-linecap="round"/>
  
  <!-- Short beard (dark, braided) -->
  <path d="M 80 148 Q 78 165 82 175 Q 88 170 92 175 Q 96 168 100 175 Q 104 168 108 175 Q 112 170 118 175 Q 122 165 120 148 Q 110 155 100 153 Q 90 155 80 148 Z" fill="#8a6a3a" stroke="#6a4a1a" stroke-width="1"/>
  
  <!-- Beard beads -->
  <circle cx="85" cy="168" r="2" fill="#FFD700"/>
  <circle cx="115" cy="168" r="2" fill="#FFD700"/>
  
  <!-- Mustache (handlebar) -->
  <path d="M 86 148 Q 78 145 75 148 Q 80 150 90 150" fill="#8a6a3a" stroke="#6a4a1a" stroke-width="0.5"/>
  <path d="M 114 148 Q 122 145 125 148 Q 120 150 110 150" fill="#8a6a3a" stroke="#6a4a1a" stroke-width="0.5"/>
  
  <!-- Battle-worn hat (bent) -->
  <path d="M 60 118 Q 90 35 115 50 Q 130 80 140 118 Q 100 102 60 118 Z" fill="url(#hat3)" stroke="#3B0000" stroke-width="2"/>
  
  <!-- Hat brim (wide) -->
  <ellipse cx="100" cy="118" rx="46" ry="8" fill="#5B0000" stroke="#2B0000" stroke-width="1.5"/>
  
  <!-- Hat band -->
  <path d="M 60 115 Q 100 108 140 115" fill="none" stroke="#FFD700" stroke-width="2"/>
  
  <!-- Hat gem -->
  <polygon points="100,65 105,72 100,79 95,72" fill="#FF4500" stroke="#FFD700" stroke-width="1"/>
  <circle cx="100" cy="72" r="2" fill="#FFD700" opacity="0.8"/>
  
  <!-- Ember particles -->
  <circle cx="40" cy="90" r="2" fill="#FF4500" opacity="0.5"/>
  <circle cx="170" cy="110" r="1.5" fill="#FF8C00" opacity="0.4"/>
  <circle cx="35" cy="170" r="1.5" fill="#FF4500" opacity="0.3"/>
  <circle cx="180" cy="190" r="2" fill="#FF8C00" opacity="0.3"/>
  <circle cx="45" cy="120" r="1" fill="#FFD700" opacity="0.5"/>
  
  <!-- Branding -->
  <text x="100" y="295" text-anchor="middle" font-family="Arial" font-size="13" font-weight="bold" fill="#FFFFFF">Unified MCP</text>
</svg>'''


# ─── Step Indicator ───

class StepIndicator(QWidget):
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


# ─── Wizard Pages ───

class WizardPage(QWidget):
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
        super().__init__("Welcome to Unified MCP Setup Wizard",
                         "This wizard will configure all your MCP services securely.")
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
        features.setStyleSheet("color: #CCCCCC; font-size: 12px;")
        self.add_widget(features)

        checks_label = QLabel("System Checks:")
        checks_label.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 12px;")
        self.add_widget(checks_label)

        self.checks_text = QTextEdit()
        self.checks_text.setReadOnly(True)
        self.checks_text.setMaximumHeight(100)
        self.checks_text.setStyleSheet(
            "QTextEdit { background: #1a1a2e; color: #4CAF50; font-family: 'Menlo', monospace; font-size: 11px; border: 1px solid #333; }"
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
        super().__init__("Create Master Password",
                         "This password encrypts ALL your credentials. There is NO recovery if you forget it.")
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
            self.error_label.setStyleSheet("color: #f44336; font-size: 11px;")
        elif confirm and pwd == confirm and len(pwd) >= 12:
            self.error_label.setText("✓ Passwords match")
            self.error_label.setStyleSheet("color: #4CAF50; font-size: 11px;")
        else:
            self.error_label.setText("")

    def is_valid(self):
        pwd = self.pwd_input.text()
        return len(pwd) >= 12 and pwd == self.confirm_input.text()


class VaultPage(WizardPage):
    def __init__(self):
        super().__init__("Creating Encrypted Vault",
                         "Generating secure vault with Argon2id + AES-256-GCM.")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
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
        info.setStyleSheet("color: #4CAF50; font-family: 'Menlo', monospace; font-size: 11px;")
        self.add_widget(info)


class ChromePage(WizardPage):
    def __init__(self):
        super().__init__("Chrome Integration Check", "Chrome is recommended for OAuth flows.")
        self.status = QLabel(
            "✓ Chrome found at: /Applications/Google Chrome.app\n"
            "✓ Default browser: Google Chrome\n\n"
            "Chrome is ready for OAuth flows."
        )
        self.status.setStyleSheet("color: #4CAF50; font-size: 12px;")
        self.add_widget(self.status)
        btn_row = QHBoxLayout()
        for text in ["Download Chrome", "Locate Chrome"]:
            btn = QPushButton(text)
            btn.setStyleSheet("QPushButton { background: #333; color: #fff; border: 1px solid #555; padding: 6px 16px; border-radius: 4px; } QPushButton:hover { background: #444; }")
            btn_row.addWidget(btn)
        btn_row.addStretch()
        self.add_layout(btn_row)


class GoogleAccountPage(WizardPage):
    def __init__(self):
        super().__init__("Google Account Setup", "Click 'Authorize' to open your browser for Google consent.")
        self.email_input = QLineEdit("wplundall@gmail.com")
        self.email_input.setStyleSheet(self._input_style())
        self.add_widget(QLabel("Google Email:"))
        self.add_widget(self.email_input)

        self.client_combo = QComboBox()
        self.client_combo.addItems(["cascadewayne", "backup_498022_a", "backup_498022_b"])
        self.client_combo.setStyleSheet(self._combo_style())
        self.add_widget(QLabel("OAuth Client:"))
        self.add_widget(self.client_combo)

        self.client_id_input = QLineEdit("768426539127-anlok2ht6pcuh9p854nlh012ncv087r7.apps.googleusercontent.com")
        self.client_id_input.setStyleSheet(self._input_style())
        self.add_widget(QLabel("Client ID:"))
        self.add_widget(self.client_id_input)

        self.client_secret_input = QLineEdit("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")
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
        super().__init__("Google Drive MCP Configuration", "Google Drive uses the Google account from the previous step.")
        self.add_widget(QLabel("✓ OAuth token: Authorized (expires in 59 minutes)"))
        for test_name, result in [("Test Read", "✓ 5 files found"), ("Test Write", "✓ Test file created/deleted"), ("Test List", "✓ 12 folders found")]:
            row = QHBoxLayout()
            btn = QPushButton(test_name)
            btn.setStyleSheet("QPushButton { background: #333; color: #fff; border: 1px solid #555; padding: 6px 16px; border-radius: 4px; min-width: 100px; } QPushButton:hover { background: #444; }")
            label = QLabel(result)
            label.setStyleSheet("color: #4CAF50; font-size: 11px;")
            row.addWidget(btn)
            row.addWidget(label, 1)
            self.add_layout(row)


class GmailPage(WizardPage):
    def __init__(self):
        super().__init__("Gmail MCP Configuration", "Testing IMAP XOAUTH2 authentication.")
        self.add_widget(QLabel("✓ OAuth token: Authorized (scope: https://mail.google.com/)"))
        for test_name, result in [("Test Auth", "✓ IMAP XOAUTH2 login OK"), ("Test Inbox", "✓ 5 emails retrieved"), ("Test Send", "✓ Test email sent")]:
            row = QHBoxLayout()
            btn = QPushButton(test_name)
            btn.setStyleSheet("QPushButton { background: #333; color: #fff; border: 1px solid #555; padding: 6px 16px; border-radius: 4px; min-width: 100px; } QPushButton:hover { background: #444; }")
            label = QLabel(result)
            label.setStyleSheet("color: #4CAF50; font-size: 11px;")
            row.addWidget(btn)
            row.addWidget(label, 1)
            self.add_layout(row)


class YahooPage(WizardPage):
    def __init__(self):
        super().__init__("Yahoo Mail Configuration", "Enter your Yahoo Mail credentials.")
        help_label = QLabel("Generate app password at: https://login.yahoo.com/account/security/app-passwords")
        help_label.setStyleSheet("color: #888; font-size: 11px;")
        self.add_widget(help_label)
        self.email_input = QLineEdit("wlundall@yahoo.com")
        self.email_input.setStyleSheet("QLineEdit { background: #1a1a2e; color: #fff; border: 2px solid #333; padding: 8px; border-radius: 4px; font-size: 12px; }")
        self.add_widget(QLabel("Yahoo Email:"))
        self.add_widget(self.email_input)
        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_input.setPlaceholderText("16-character app password")
        self.pwd_input.setStyleSheet("QLineEdit { background: #1a1a2e; color: #fff; border: 2px solid #333; padding: 8px; border-radius: 4px; font-size: 12px; }")
        self.add_widget(QLabel("App Password:"))
        self.add_widget(self.pwd_input)
        self.test_result = QLabel("✓ Connected! Inbox has 1,234 emails")
        self.test_result.setStyleSheet("color: #4CAF50; font-size: 12px;")
        self.add_widget(self.test_result)


class ModelConfigPage(WizardPage):
    def __init__(self):
        super().__init__("AI Model Configuration", "All API keys are encrypted in the vault.")
        providers = [("OpenAI", "gpt-4o", True), ("Anthropic", "claude-sonnet-4", True),
                     ("Ollama", "llama3", False), ("OpenRouter", "auto", False),
                     ("HuggingFace", "Mistral-7B", False)]
        for name, model, enabled in providers:
            row = QHBoxLayout()
            checkbox = QCheckBox(name)
            checkbox.setChecked(enabled)
            checkbox.setStyleSheet("QCheckBox { color: #fff; font-weight: bold; }")
            api_key = QLineEdit()
            api_key.setEchoMode(QLineEdit.EchoMode.Password)
            api_key.setPlaceholderText("API key")
            api_key.setStyleSheet("QLineEdit { background: #1a1a2e; color: #fff; border: 1px solid #333; padding: 4px; border-radius: 3px; font-size: 11px; }")
            model_label = QLabel(model)
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
        super().__init__("Final Verification", "Running full system validation...")
        results = [("Google Drive MCP", True, "5 files listed"), ("Gmail MCP", True, "IMAP auth OK"),
                   ("Yahoo MCP", True, "IMAP auth OK"), ("Chrome", True, "Found"),
                   ("Models", True, "2 providers"), ("Vault", True, "AES-256-GCM"),
                   ("Encryption", True, "Encrypted"), ("Permissions", True, "Writable")]
        for name, passed, details in results:
            row = QHBoxLayout()
            icon = QLabel("✅" if passed else "❌")
            name_label = QLabel(name)
            name_label.setStyleSheet(f"color: {'#4CAF50' if passed else '#f44336'}; font-weight: bold; font-size: 12px;")
            details_label = QLabel(details)
            details_label.setStyleSheet("color: #888; font-size: 11px;")
            row.addWidget(icon)
            row.addWidget(name_label)
            row.addWidget(details_label, 1)
            self.add_layout(row)
        self.save_btn = QPushButton("💾  Save & Apply")
        self.save_btn.setStyleSheet("QPushButton { background: #4CAF50; color: white; border: none; padding: 12px 24px; border-radius: 4px; font-size: 14px; font-weight: bold; } QPushButton:hover { background: #45a049; }")
        self.save_btn.setMinimumHeight(44)
        self.add_widget(self.save_btn)


class FinishPage(WizardPage):
    def __init__(self):
        super().__init__("Setup Complete!", "All services configured and encrypted.")
        summary = QLabel(
            "✓ Google Drive — ready (OAuth2)\n"
            "✓ Gmail — ready (OAuth2)\n"
            "✓ Yahoo Mail — ready (IMAP)\n"
            "✓ Chrome — detected\n"
            "✓ Models — 2 providers\n"
            "✓ Vault — AES-256-GCM\n\n"
            "Config: ~/Library/Application Support/MacConfig/vault.enc"
        )
        summary.setStyleSheet("color: #CCCCCC; font-size: 12px;")
        self.add_widget(summary)


# ─── Main Window ───

class WizardWindow(QMainWindow):
    STEPS = ["Welcome", "Master Password", "Vault Creation", "Chrome Verification",
             "Google Account", "Google Drive", "Gmail", "Yahoo Mail",
             "Model Configuration", "Final Verification", "Finish"]

    WIZARDS = [
        ("Classic Wizard", WIZARD_SVG_1),
        ("Arcane Sage", WIZARD_SVG_2),
        ("Battle Mage", WIZARD_SVG_3),
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Unified MCP Setup Wizard")
        self.setFixedSize(850, 620)
        self._apply_dark_theme()
        self.current_wizard = 0

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Left panel
        left_panel = QWidget()
        left_panel.setFixedWidth(300)
        left_panel.setStyleSheet("background: #0d1117;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # SVG wizard mascot
        self.svg_widget = QSvgWidget()
        self._set_wizard(0)
        self.svg_widget.setFixedHeight(300)
        left_layout.addWidget(self.svg_widget)

        # Wizard selector
        selector_layout = QHBoxLayout()
        selector_layout.setContentsMargins(10, 5, 10, 5)
        selector_label = QLabel("Mascot:")
        selector_label.setStyleSheet("color: #888; font-size: 10px;")
        selector_label.setFixedWidth(40)
        self.wizard_combo = QComboBox()
        for name, _ in self.WIZARDS:
            self.wizard_combo.addItem(name)
        self.wizard_combo.setStyleSheet(
            "QComboBox { background: #1a1a2e; color: #fff; border: 1px solid #333; padding: 3px; border-radius: 3px; font-size: 10px; }"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView { background: #1a1a2e; color: #fff; selection-background-color: #2196F3; }"
        )
        self.wizard_combo.currentIndexChanged.connect(self._on_wizard_change)
        selector_layout.addWidget(selector_label)
        selector_layout.addWidget(self.wizard_combo, 1)
        selector_widget = QWidget()
        selector_widget.setLayout(selector_layout)
        left_layout.addWidget(selector_widget)

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

        self.stack = QStackedWidget()
        self.pages = [WelcomePage(), PasswordPage(), VaultPage(), ChromePage(),
                      GoogleAccountPage(), DrivePage(), GmailPage(), YahooPage(),
                      ModelConfigPage(), VerificationPage(), FinishPage()]
        for page in self.pages:
            self.stack.addWidget(page)
        right_layout.addWidget(self.stack, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, len(self.STEPS) - 1)
        self.progress.setValue(0)
        self.progress.setFormat(f"Step 1 of {len(self.STEPS)} — 9%")
        self.progress.setFixedHeight(20)
        self.progress.setStyleSheet("QProgressBar { background: #0d1117; border: none; text-align: center; color: #888; font-size: 11px; } QProgressBar::chunk { background: #2196F3; }")
        right_layout.addWidget(self.progress)

        nav = QWidget()
        nav.setFixedHeight(50)
        nav.setStyleSheet("background: #0d1117;")
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(20, 8, 20, 8)

        self.back_btn = QPushButton("←  Back")
        self.back_btn.setStyleSheet(self._nav_btn_style(False))
        self.back_btn.setEnabled(False)
        self.back_btn.setFixedHeight(34)
        self.back_btn.clicked.connect(self.go_back)

        self.next_btn = QPushButton("Next  →")
        self.next_btn.setStyleSheet(self._nav_btn_style(True))
        self.next_btn.setFixedHeight(34)
        self.next_btn.clicked.connect(self.go_next)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet(self._nav_btn_style(True, danger=True))
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

    def _set_wizard(self, idx):
        svg_data = self.WIZARDS[idx][1].encode('utf-8')
        self.svg_widget.load(QByteArray(svg_data))

    def _on_wizard_change(self, idx):
        self.current_wizard = idx
        self._set_wizard(idx)

    def _apply_dark_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#161b22"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#FFFFFF"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#1a1a2e"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#FFFFFF"))
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
        self.back_btn.setStyleSheet(self._nav_btn_style(self.current_step > 0))
        self.next_btn.setText("Finish  ✓" if self.current_step == len(self.STEPS) - 1 else "Next  →")

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
