#!/usr/bin/env python3
"""
Procedural Wizard SVG Scheme Generator — MAX EDITION
Generates infinite wizard mascot variants with full customization.
Features: 16 themes, 4 hat styles, 4 beard styles, 4 wand types, 4 expressions,
accessories, background modes, CSS animations, gallery, PNG/base64/Go export.
"""

import sys
import random
import base64
import math
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSpinBox, QComboBox, QCheckBox, QGroupBox, QFormLayout, QScrollArea,
    QGridLayout, QFrame, QFileDialog, QSlider, QLineEdit
)
from PyQt6.QtCore import Qt, QByteArray
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtGui import QFont, QPainter, QImage
from PyQt6.QtSvg import QSvgRenderer


# ─── Theme Definitions ───

THEMES = {
    "Classic Blue":    {"base": "#1e5eff", "accent": "#7ec8ff", "coat": "#2b2b2b", "hat_band": "#0b2a7a", "bg_top": "#0d1117", "bg_bot": "#161b22"},
    "Deep Purple":     {"base": "#6a4a8a", "accent": "#FFD700", "coat": "#2a1a4a", "hat_band": "#1a0a3a", "bg_top": "#1a0a2e", "bg_bot": "#2a1a4e"},
    "Arcane Cyan":     {"base": "#1a5276", "accent": "#00BFFF", "coat": "#0a2a46", "hat_band": "#021a36", "bg_top": "#021a36", "bg_bot": "#0a2a46"},
    "Fire Mage":       {"base": "#8B0000", "accent": "#FF4500", "coat": "#3B1B00", "hat_band": "#2B0000", "bg_top": "#1a0500", "bg_bot": "#2a0a00"},
    "Forest Druid":    {"base": "#2d6a4f", "accent": "#95d5b2", "coat": "#1b4332", "hat_band": "#081c11", "bg_top": "#081c11", "bg_bot": "#1b4332"},
    "Shadow Mage":     {"base": "#1a1a2e", "accent": "#e94560", "coat": "#0f0f1e", "hat_band": "#000000", "bg_top": "#000000", "bg_bot": "#1a1a2e"},
    "Sun Gold":        {"base": "#d4a017", "accent": "#FFFACD", "coat": "#8B6914", "hat_band": "#5B4500", "bg_top": "#1a1000", "bg_bot": "#2a2000"},
    "Ice Queen":       {"base": "#a8dadc", "accent": "#f1faee", "coat": "#457b9d", "hat_band": "#1d3557", "bg_top": "#0a1020", "bg_bot": "#1a2040"},
    "Blood Mage":      {"base": "#c1121f", "accent": "#ffd60a", "coat": "#3a0a0a", "hat_band": "#1a0000", "bg_top": "#0a0000", "bg_bot": "#1a0505"},
    "Storm Caller":    {"base": "#3a0ca3", "accent": "#4cc9f0", "coat": "#10002b", "hat_band": "#240046", "bg_top": "#10002b", "bg_bot": "#240046"},
    "Necromancer":     {"base": "#2d3a3a", "accent": "#00ff9f", "coat": "#1a1a1a", "hat_band": "#0a0a0a", "bg_top": "#0a0a0a", "bg_bot": "#1a1a1a"},
    "Sunset Sage":     {"base": "#e76f51", "accent": "#f4a261", "coat": "#264653", "hat_band": "#1a3540", "bg_top": "#1a1a2e", "bg_bot": "#264653"},
    "Emerald Seer":    {"base": "#2a9d8f", "accent": "#e9c46a", "coat": "#1a3a35", "hat_band": "#0a2a25", "bg_top": "#0a1a18", "bg_bot": "#1a3a35"},
    "Void Walker":     {"base": "#7209b7", "accent": "#f72585", "coat": "#10002b", "hat_band": "#000000", "bg_top": "#000000", "bg_bot": "#10002b"},
    "Mystic Teal":     {"base": "#006d77", "accent": "#83c5be", "coat": "#1a3a3e", "hat_band": "#0a2a2e", "bg_top": "#0a1a1e", "bg_bot": "#1a3a3e"},
    "Crimson War":     {"base": "#9e0059", "accent": "#ffbe0b", "coat": "#3a0020", "hat_band": "#1a0010", "bg_top": "#1a0010", "bg_bot": "#3a0020"},
}

HAT_STYLES = ["Pointed", "Wide Brim", "Droopy", "Crown"]
BEARD_STYLES = ["Long Flowing", "Short", "Braided", "None"]
WAND_TYPES = ["Classic Wand", "Crystal Staff", "Fire Orb", "Lightning"]
EXPRESSIONS = ["Smile", "Serious", "Smirk", "Surprised"]
BACKGROUNDS = ["Stars", "Runes", "Nebula", "Circles", "Plain"]
ACCESSORIES = ["None", "Crystal Ball", "Spell Book", "Familiar Owl", "Scroll"]


def star_polygon_pts(cx, cy, size):
    """Generate SVG polygon points string for a 5-pointed star."""
    pts = []
    for i in range(10):
        angle = i * math.pi / 5 - math.pi / 2
        r = size if i % 2 == 0 else size * 0.4
        pts.append(f"{cx + r * math.cos(angle):.1f},{cy + r * math.sin(angle):.1f}")
    return " ".join(pts)


class WizardSVGSchemeGenerator:
    """Procedural SVG generator for wizard-themed assets — MAX EDITION."""

    def __init__(self, width=512, height=512, theme_name="Classic Blue",
                 star_count=15, seed=None, hat_style="Pointed", beard_style="Long Flowing",
                 wand_type="Classic Wand", expression="Smile", background="Stars",
                 accessory="None", animate=True, branding="Unified MCP"):
        self.width = width
        self.height = height
        self.theme_name = theme_name
        self.theme = THEMES.get(theme_name, THEMES["Classic Blue"])
        self.star_count = star_count
        self.hat_style = hat_style
        self.beard_style = beard_style
        self.wand_type = wand_type
        self.expression = expression
        self.background = background
        self.accessory = accessory
        self.animate = animate
        self.branding = branding
        self.rng = random.Random(seed)
        self.seed = seed

    def _stars(self):
        stars = []
        for _ in range(self.star_count):
            x = self.rng.randint(10, self.width - 10)
            y = self.rng.randint(10, self.height - 10)
            r = self.rng.choice([1, 1.5, 2, 2.5, 3])
            opacity = self.rng.uniform(0.3, 0.9)
            anim = ""
            if self.animate:
                delay = self.rng.uniform(0, 3)
                dur = self.rng.uniform(2, 5)
                anim = f'<animate attributeName="opacity" values="{opacity:.1f};{opacity*0.2:.1f};{opacity:.1f}" dur="{dur:.1f}s" begin="{delay:.1f}s" repeatCount="indefinite"/>'
            stars.append(
                f'<circle cx="{x}" cy="{y}" r="{r}" fill="{self.theme["accent"]}" opacity="{opacity:.1f}">{anim}</circle>'
            )
        return "\n        ".join(stars)

    def _runes(self):
        runes = []
        rune_chars = ["\u16a0", "\u16a2", "\u16a6", "\u16a8", "\u16b1", "\u16b2", "\u16b7", "\u16b9",
                       "\u16ba", "\u16be", "\u16c1", "\u16c3", "\u16c7", "\u16c8", "\u16c9", "\u16ca",
                       "\u16cf", "\u16d2", "\u16d6", "\u16d7", "\u16da", "\u16dc", "\u16df", "\u16de"]
        for _ in range(self.star_count):
            x = self.rng.randint(20, self.width - 20)
            y = self.rng.randint(20, self.height - 20)
            char = self.rng.choice(rune_chars)
            size = self.rng.choice([10, 12, 14, 16])
            opacity = self.rng.uniform(0.15, 0.4)
            runes.append(
                f'<text x="{x}" y="{y}" font-size="{size}" fill="{self.theme["accent"]}" opacity="{opacity:.2f}" font-family="serif">{char}</text>'
            )
        return "\n        ".join(runes)

    def _nebula(self):
        blobs = []
        for _ in range(6):
            x = self.rng.randint(0, self.width)
            y = self.rng.randint(0, self.height)
            r = self.rng.randint(60, 150)
            opacity = self.rng.uniform(0.03, 0.08)
            blobs.append(
                f'<circle cx="{x}" cy="{y}" r="{r}" fill="{self.theme["base"]}" opacity="{opacity:.2f}"/>'
            )
        return "\n        ".join(blobs)

    def _circles(self):
        circles = []
        for _ in range(self.star_count):
            x = self.rng.randint(10, self.width - 10)
            y = self.rng.randint(10, self.height - 10)
            r = self.rng.randint(5, 30)
            opacity = self.rng.uniform(0.05, 0.15)
            circles.append(
                f'<circle cx="{x}" cy="{y}" r="{r}" fill="none" stroke="{self.theme["accent"]}" stroke-width="1" opacity="{opacity:.2f}"/>'
            )
        return "\n        ".join(circles)

    def _background(self):
        if self.background == "Stars":
            return self._stars()
        elif self.background == "Runes":
            return self._runes()
        elif self.background == "Nebula":
            return self._nebula()
        elif self.background == "Circles":
            return self._circles()
        return ""

    def _hat(self):
        base = self.theme["base"]
        band = self.theme["hat_band"]
        accent = self.theme["accent"]
        tilt = self.rng.randint(-5, 5)
        anim = ""
        if self.animate:
            anim = f'<animateTransform attributeName="transform" type="rotate" values="{tilt} 256 140;{tilt+2} 256 140;{tilt} 256 140" dur="4s" repeatCount="indefinite"/>'

        if self.hat_style == "Pointed":
            return f'''<g>{anim}
                <path d="M256 50 L175 225 L337 225 Z" fill="{base}" stroke="{band}" stroke-width="2"/>
                <rect x="165" y="225" width="182" height="32" fill="{band}" rx="4"/>
                <polygon points="{star_polygon_pts(256, 90, 8)}" fill="{accent}" opacity="0.9"/>
                <circle cx="215" cy="180" r="2" fill="{accent}" opacity="0.6"/>
                <circle cx="295" cy="170" r="2" fill="{accent}" opacity="0.6"/>
                <circle cx="255" cy="140" r="1.5" fill="{accent}" opacity="0.5"/>
            </g>'''
        elif self.hat_style == "Wide Brim":
            return f'''<g>{anim}
                <path d="M256 55 L195 210 L317 210 Z" fill="{base}" stroke="{band}" stroke-width="2"/>
                <ellipse cx="256" cy="215" rx="75" ry="14" fill="{band}" stroke="{band}" stroke-width="1"/>
                <polygon points="{star_polygon_pts(256, 95, 7)}" fill="{accent}" opacity="0.9"/>
                <circle cx="225" cy="170" r="2" fill="{accent}" opacity="0.6"/>
                <circle cx="285" cy="165" r="2" fill="{accent}" opacity="0.6"/>
            </g>'''
        elif self.hat_style == "Droopy":
            tip_y = self.rng.randint(35, 55)
            return f'''<g>{anim}
                <path d="M256 {tip_y} Q270 {tip_y+10} 275 {tip_y+25} L330 225 L182 225 Z" fill="{base}" stroke="{band}" stroke-width="2"/>
                <rect x="172" y="225" width="168" height="30" fill="{band}" rx="4"/>
                <polygon points="{star_polygon_pts(260, tip_y+20, 6)}" fill="{accent}" opacity="0.9"/>
                <circle cx="220" cy="180" r="2" fill="{accent}" opacity="0.6"/>
                <circle cx="290" cy="170" r="2" fill="{accent}" opacity="0.6"/>
            </g>'''
        elif self.hat_style == "Crown":
            return f'''<g>{anim}
                <path d="M256 60 L185 220 L327 220 Z" fill="{base}" stroke="{band}" stroke-width="2"/>
                <rect x="175" y="220" width="162" height="28" fill="{band}" rx="4"/>
                <polygon points="200,220 210,195 220,220" fill="{accent}" opacity="0.8"/>
                <polygon points="235,220 245,190 255,220" fill="{accent}" opacity="0.8"/>
                <polygon points="270,220 280,190 290,220" fill="{accent}" opacity="0.8"/>
                <polygon points="305,220 315,195 325,220" fill="{accent}" opacity="0.8"/>
                <circle cx="245" cy="200" r="3" fill="{accent}"/>
                <circle cx="280" cy="200" r="3" fill="{accent}"/>
                <polygon points="{star_polygon_pts(256, 100, 7)}" fill="{accent}" opacity="0.9"/>
            </g>'''
        return ""

    def _beard(self):
        accent = self.theme["accent"]
        if self.beard_style == "None":
            return ""
        if self.beard_style == "Long Flowing":
            return f'''<path d="M218 258 Q210 300 220 330 Q230 318 238 328 Q248 312 256 325 Q264 312 274 328 Q282 318 292 330 Q302 300 294 258 Q272 268 256 264 Q240 268 218 258 Z"
                  fill="#EEEEEE" stroke="#CCCCCC" stroke-width="1"/>
            <path d="M232 258 Q226 265 224 270 Q232 267 238 262" fill="#EEEEEE" stroke="#CCCCCC" stroke-width="0.5"/>
            <path d="M280 258 Q286 265 288 270 Q280 267 274 262" fill="#EEEEEE" stroke="#CCCCCC" stroke-width="0.5"/>'''
        if self.beard_style == "Short":
            return f'''<path d="M224 258 Q222 275 228 285 Q238 278 244 283 Q252 275 256 280 Q260 275 268 283 Q274 278 284 285 Q290 275 288 258 Q272 264 256 262 Q240 264 224 258 Z"
                  fill="#EEEEEE" stroke="#CCCCCC" stroke-width="1"/>
            <path d="M234 258 Q228 262 226 265 Q234 263 240 260" fill="#EEEEEE" stroke="#CCCCCC" stroke-width="0.5"/>
            <path d="M278 258 Q284 262 286 265 Q278 263 272 260" fill="#EEEEEE" stroke="#CCCCCC" stroke-width="0.5"/>'''
        if self.beard_style == "Braided":
            return f'''<path d="M224 258 Q220 280 226 300 Q232 295 236 305 Q244 295 250 305 Q256 295 262 305 Q268 295 276 305 Q280 295 286 300 Q292 280 288 258 Q272 264 256 262 Q240 264 224 258 Z"
                  fill="#8a7a5a" stroke="#6a5a3a" stroke-width="1"/>
            <circle cx="232" cy="275" r="3" fill="{accent}" opacity="0.8"/>
            <circle cx="280" cy="275" r="3" fill="{accent}" opacity="0.8"/>
            <circle cx="234" cy="290" r="2.5" fill="{accent}" opacity="0.6"/>
            <circle cx="278" cy="290" r="2.5" fill="{accent}" opacity="0.6"/>
            <path d="M234 258 Q228 262 226 265 Q234 263 240 260" fill="#8a7a5a" stroke="#6a5a3a" stroke-width="0.5"/>
            <path d="M278 258 Q284 262 286 265 Q278 263 272 260" fill="#8a7a5a" stroke="#6a5a3a" stroke-width="0.5"/>'''
        return ""

    def _face(self):
        accent = self.theme["accent"]
        if self.expression == "Smile":
            mouth = '<path d="M244 266 Q256 274 268 266" fill="none" stroke="#8a5a2a" stroke-width="2.5" stroke-linecap="round"/>'
            brow_l = '<path d="M238 234 Q246 232 252 235" fill="none" stroke="#8a6a3a" stroke-width="2.5"/>'
            brow_r = '<path d="M260 235 Q266 232 274 234" fill="none" stroke="#8a6a3a" stroke-width="2.5"/>'
        elif self.expression == "Serious":
            mouth = '<path d="M246 268 L266 268" fill="none" stroke="#6a4a2a" stroke-width="2.5" stroke-linecap="round"/>'
            brow_l = '<path d="M238 232 L253 236" fill="none" stroke="#5a4a2a" stroke-width="3" stroke-linecap="round"/>'
            brow_r = '<path d="M259 236 L274 232" fill="none" stroke="#5a4a2a" stroke-width="3" stroke-linecap="round"/>'
        elif self.expression == "Smirk":
            mouth = '<path d="M244 267 Q256 270 268 263" fill="none" stroke="#8a5a2a" stroke-width="2.5" stroke-linecap="round"/>'
            brow_l = '<path d="M238 234 Q246 233 252 235" fill="none" stroke="#8a6a3a" stroke-width="2.5"/>'
            brow_r = '<path d="M260 233 Q266 232 274 234" fill="none" stroke="#8a6a3a" stroke-width="2.5"/>'
        elif self.expression == "Surprised":
            mouth = '<ellipse cx="256" cy="268" rx="6" ry="8" fill="#5a3a1a"/>'
            brow_l = '<path d="M238 230 Q246 228 253 232" fill="none" stroke="#8a6a3a" stroke-width="2.5"/>'
            brow_r = '<path d="M259 232 Q266 228 274 230" fill="none" stroke="#8a6a3a" stroke-width="2.5"/>'
        else:
            mouth = '<path d="M246 266 Q256 270 266 266" fill="none" stroke="#8a5a2a" stroke-width="2"/>'
            brow_l = '<path d="M238 234 Q246 232 252 235" fill="none" stroke="#8a6a3a" stroke-width="2"/>'
            brow_r = '<path d="M260 235 Q266 232 274 234" fill="none" stroke="#8a6a3a" stroke-width="2"/>'

        eye_anim_l = ""
        eye_anim_r = ""
        if self.animate:
            eye_anim_l = '<animate attributeName="r" values="1.5;2.5;1.5" dur="3s" repeatCount="indefinite"/>'
            eye_anim_r = '<animate attributeName="r" values="1.5;2.5;1.5" dur="3s" begin="0.5s" repeatCount="indefinite"/>'

        return f'''<ellipse cx="256" cy="250" rx="32" ry="37" fill="#F4D4A0" stroke="#D4A060" stroke-width="1.5"/>
        <ellipse cx="224" cy="252" rx="6" ry="10" fill="#F4D4A0" stroke="#D4A060" stroke-width="1"/>
        <ellipse cx="288" cy="252" rx="6" ry="10" fill="#F4D4A0" stroke="#D4A060" stroke-width="1"/>
        <ellipse cx="246" cy="242" rx="4" ry="5" fill="#1a1a2e"/>
        <ellipse cx="266" cy="242" rx="4" ry="5" fill="#1a1a2e"/>
        <circle cx="247" cy="241" r="1.5" fill="{accent}">{eye_anim_l}</circle>
        <circle cx="267" cy="241" r="1.5" fill="{accent}">{eye_anim_r}</circle>
        {brow_l}
        {brow_r}
        <path d="M256 248 L252 258 Q256 260 260 258 Z" fill="#E4C490" stroke="#D4A060" stroke-width="0.5"/>
        {mouth}
        <circle cx="232" cy="258" r="5" fill="#FF9999" opacity="0.15"/>
        <circle cx="280" cy="258" r="5" fill="#FF9999" opacity="0.15"/>'''

    def _coat(self):
        coat = self.theme["coat"]
        base = self.theme["base"]
        accent = self.theme["accent"]
        return f'''<path d="M170 255 L115 425 L397 425 L342 255 Z" fill="{coat}" stroke="{coat}" stroke-width="1"/>
        <path d="M200 255 L178 425" stroke="#4a4a4a" stroke-width="3" opacity="0.5"/>
        <path d="M312 255 L334 425" stroke="#4a4a4a" stroke-width="3" opacity="0.5"/>
        <path d="M170 255 Q256 270 342 255" fill="none" stroke="{base}" stroke-width="3" opacity="0.6"/>
        <path d="M115 425 Q256 415 397 425" fill="none" stroke="{base}" stroke-width="3" opacity="0.7"/>
        <circle cx="256" cy="345" r="15" fill="none" stroke="{accent}" stroke-width="2" opacity="0.4"/>
        <polygon points="{star_polygon_pts(256, 345, 8)}" fill="{accent}" opacity="0.3"/>
        <circle cx="256" cy="290" r="3" fill="{accent}" opacity="0.6"/>
        <circle cx="256" cy="320" r="3" fill="{accent}" opacity="0.6"/>
        <circle cx="256" cy="380" r="3" fill="{accent}" opacity="0.6"/>'''

    def _wand(self):
        accent = self.theme["accent"]
        angle = self.rng.randint(-15, 15)

        if self.wand_type == "Classic Wand":
            x2 = 460 + self.rng.randint(-15, 15)
            y2 = 180 + self.rng.randint(-15, 15)
            anim = ""
            if self.animate:
                anim = '<animate attributeName="opacity" values="0.9;1;0.9" dur="2s" repeatCount="indefinite"/>'
            return f'''<g transform="rotate({angle} 360 270)">
                <line x1="360" y1="270" x2="{x2}" y2="{y2}" stroke="#caa472" stroke-width="6" stroke-linecap="round"/>
                <circle cx="{x2}" cy="{y2}" r="12" fill="{accent}" opacity="0.9">{anim}</circle>
                <circle cx="{x2}" cy="{y2}" r="7" fill="#FFFFFF" opacity="0.5"/>
                <polygon points="{star_polygon_pts(x2, y2, 5)}" fill="#FFFFFF" opacity="0.6"/>
            </g>'''
        if self.wand_type == "Crystal Staff":
            x2 = 460 + self.rng.randint(-10, 10)
            y2 = 160 + self.rng.randint(-10, 10)
            return f'''<g transform="rotate({angle} 360 270)">
                <line x1="360" y1="270" x2="{x2}" y2="{y2+30}" stroke="#5a4a3a" stroke-width="8" stroke-linecap="round"/>
                <line x1="360" y1="270" x2="{x2}" y2="{y2+30}" stroke="#8a7a6a" stroke-width="4" stroke-linecap="round"/>
                <polygon points="{x2},{y2} {x2+12},{y2+15} {x2},{y2+35} {x2-12},{y2+15}" fill="{accent}" opacity="0.8" stroke="{accent}" stroke-width="1"/>
                <polygon points="{x2},{y2+5} {x2+8},{y2+15} {x2},{y2+30} {x2-8},{y2+15}" fill="#FFFFFF" opacity="0.3"/>
            </g>'''
        if self.wand_type == "Fire Orb":
            x2 = 460 + self.rng.randint(-10, 10)
            y2 = 180 + self.rng.randint(-10, 10)
            anim = ""
            if self.animate:
                anim = '<animate attributeName="r" values="12;16;12" dur="1.5s" repeatCount="indefinite"/>'
            return f'''<g transform="rotate({angle} 360 270)">
                <line x1="360" y1="270" x2="{x2}" y2="{y2}" stroke="#4a2a1a" stroke-width="7" stroke-linecap="round"/>
                <circle cx="{x2}" cy="{y2}" r="14" fill="#FF4500" opacity="0.8">{anim}</circle>
                <circle cx="{x2}" cy="{y2}" r="9" fill="#FFD700" opacity="0.9"/>
                <circle cx="{x2-2}" cy="{y2-2}" r="3" fill="#FFFFFF" opacity="0.7"/>
                <path d="M{x2} {y2} Q{x2-5} {y2-20} {x2} {y2-35}" fill="none" stroke="#FF4500" stroke-width="3" opacity="0.5"/>
                <path d="M{x2} {y2} Q{x2+5} {y2-25} {x2+3} {y2-40}" fill="none" stroke="#FF8C00" stroke-width="2" opacity="0.4"/>
            </g>'''
        if self.wand_type == "Lightning":
            x2 = 460 + self.rng.randint(-10, 10)
            y2 = 170 + self.rng.randint(-10, 10)
            anim = ""
            if self.animate:
                anim = '<animate attributeName="opacity" values="0.4;1;0.4" dur="0.8s" repeatCount="indefinite"/>'
            return f'''<g transform="rotate({angle} 360 270)">
                <line x1="360" y1="270" x2="{x2}" y2="{y2}" stroke="#4a4a6a" stroke-width="6" stroke-linecap="round"/>
                <polygon points="{x2},{y2-15} {x2+8},{y2-5} {x2+3},{y2-5} {x2+10},{y2+10} {x2},{y2} {x2+5},{y2} {x2-3},{y2+8}"
                         fill="{accent}" stroke="#FFFFFF" stroke-width="1" opacity="0.9">{anim}</polygon>
                <circle cx="{x2}" cy="{y2}" r="8" fill="{accent}" opacity="0.3"/>
            </g>'''
        return ""

    def _magic(self):
        accent = self.theme["accent"]
        cx, cy = 460, 180
        anim = ""
        if self.animate:
            anim = '<animate attributeName="opacity" values="0.3;0.9;0.3" dur="2s" repeatCount="indefinite"/>'
        return f'''<g stroke="{accent}" stroke-width="2" opacity="0.7" {anim}>
            <line x1="{cx}" y1="{cy}" x2="{cx+28}" y2="{cy-28}"/>
            <line x1="{cx}" y1="{cy}" x2="{cx+38}" y2="{cy}"/>
            <line x1="{cx}" y1="{cy}" x2="{cx+28}" y2="{cy+28}"/>
            <line x1="{cx}" y1="{cy}" x2="{cx}" y2="{cy-35}"/>
            <line x1="{cx}" y1="{cy}" x2="{cx-25}" y2="{cy-20}"/>
        </g>'''

    def _glow(self):
        base = self.theme["base"]
        anim = ""
        if self.animate:
            anim = '<animate attributeName="r" values="50;60;50" dur="4s" repeatCount="indefinite"/>'
        return f'<circle cx="256" cy="310" r="55" fill="{base}" opacity="0.1">{anim}</circle><circle cx="256" cy="310" r="35" fill="{base}" opacity="0.06"/>'

    def _accessory(self):
        accent = self.theme["accent"]

        if self.accessory == "Crystal Ball":
            anim = ""
            if self.animate:
                anim = '<animate attributeName="opacity" values="0.3;0.7;0.3" dur="3s" repeatCount="indefinite"/>'
            return f'''<ellipse cx="120" cy="380" rx="25" ry="8" fill="#000" opacity="0.3"/>
            <rect x="105" y="370" width="30" height="15" fill="#5a4a3a" rx="3"/>
            <circle cx="120" cy="355" r="22" fill="{accent}" opacity="0.3">{anim}</circle>
            <circle cx="120" cy="355" r="18" fill="{accent}" opacity="0.5"/>
            <circle cx="115" cy="350" r="6" fill="#FFFFFF" opacity="0.4"/>
            <path d="M110 360 Q120 355 130 360 Q125 365 120 362 Q115 365 110 360" fill="{accent}" opacity="0.2"/>'''

        if self.accessory == "Spell Book":
            return f'''<rect x="95" y="355" width="50" height="40" fill="#4a2a1a" rx="2" stroke="#2a1a0a" stroke-width="2"/>
            <rect x="98" y="358" width="44" height="34" fill="#6a4a2a" rx="1"/>
            <polygon points="{star_polygon_pts(120, 375, 6)}" fill="{accent}" opacity="0.7"/>
            <line x1="105" y1="385" x2="135" y2="385" stroke="{accent}" stroke-width="1" opacity="0.5"/>
            <line x1="105" y1="390" x2="130" y2="390" stroke="{accent}" stroke-width="1" opacity="0.5"/>
            <rect x="130" y="355" width="4" height="15" fill="{accent}" opacity="0.8"/>'''

        if self.accessory == "Familiar Owl":
            anim = ""
            if self.animate:
                anim = '<animateTransform attributeName="transform" type="translate" values="0,0;0,-5;0,0" dur="3s" repeatCount="indefinite"/>'
            return f'''<g {anim}>
                <ellipse cx="110" cy="340" rx="18" ry="25" fill="#6a5a4a"/>
                <circle cx="110" cy="320" r="16" fill="#7a6a5a"/>
                <polygon points="98,310 100,295 105,308" fill="#6a5a4a"/>
                <polygon points="122,310 120,295 115,308" fill="#6a5a4a"/>
                <circle cx="104" cy="320" r="6" fill="#FFF"/>
                <circle cx="116" cy="320" r="6" fill="#FFF"/>
                <circle cx="104" cy="320" r="3" fill="#1a1a2e"/>
                <circle cx="116" cy="320" r="3" fill="#1a1a2e"/>
                <circle cx="105" cy="319" r="1" fill="{accent}"/>
                <circle cx="117" cy="319" r="1" fill="{accent}"/>
                <polygon points="110,324 107,328 113,328" fill="#FFD700"/>
                <ellipse cx="96" cy="340" rx="8" ry="15" fill="#5a4a3a" transform="rotate(-15 96 340)"/>
                <ellipse cx="124" cy="340" rx="8" ry="15" fill="#5a4a3a" transform="rotate(15 124 340)"/>
            </g>'''

        if self.accessory == "Scroll":
            return f'''<rect x="95" y="350" width="55" height="30" fill="#f4e4c1" rx="2" stroke="#c4a484" stroke-width="1"/>
            <ellipse cx="95" cy="365" rx="5" ry="18" fill="#8a6a3a"/>
            <ellipse cx="150" cy="365" rx="5" ry="18" fill="#8a6a3a"/>
            <line x1="105" y1="358" x2="140" y2="358" stroke="#5a4a2a" stroke-width="1" opacity="0.5"/>
            <line x1="105" y1="363" x2="135" y2="363" stroke="#5a4a2a" stroke-width="1" opacity="0.5"/>
            <line x1="105" y1="368" x2="140" y2="368" stroke="#5a4a2a" stroke-width="1" opacity="0.5"/>
            <line x1="105" y1="373" x2="130" y2="373" stroke="#5a4a2a" stroke-width="1" opacity="0.5"/>
            <circle cx="122" cy="380" r="5" fill="#c1121f" opacity="0.8"/>
            <polygon points="{star_polygon_pts(122, 380, 3)}" fill="#FFD700" opacity="0.6"/>'''
        return ""

    def build(self):
        bg_top = self.theme["bg_top"]
        bg_bot = self.theme["bg_bot"]
        return f'''<svg width="{self.width}" height="{self.height}"
     viewBox="0 0 {self.width} {self.height}"
     xmlns="http://www.w3.org/2000/svg">
    <defs>
        <linearGradient id="bgGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="{bg_top}"/>
            <stop offset="100%" stop-color="{bg_bot}"/>
        </linearGradient>
        <linearGradient id="hatGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="{self.theme["base"]}"/>
            <stop offset="100%" stop-color="{self.theme["hat_band"]}"/>
        </linearGradient>
        <linearGradient id="coatGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="{self.theme["coat"]}"/>
            <stop offset="100%" stop-color="{self.theme["hat_band"]}"/>
        </linearGradient>
        <filter id="softGlow">
            <feGaussianBlur stdDeviation="3" result="blur"/>
            <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
    </defs>
    <rect width="{self.width}" height="{self.height}" fill="url(#bgGrad)"/>
    <g>{self._background()}</g>
    {self._glow()}
    {self._accessory()}
    {self._coat()}
    {self._beard()}
    {self._face()}
    {self._hat()}
    {self._wand()}
    {self._magic()}
    <text x="256" y="495" text-anchor="middle" font-family="Arial" font-size="20" font-weight="bold" fill="#FFFFFF" opacity="0.9">{self.branding}</text>
</svg>'''

    def to_bytes(self):
        return QByteArray(self.build().encode('utf-8'))

    def to_base64(self):
        return base64.b64encode(self.build().encode('utf-8')).decode('utf-8')

    def save(self, path="wizard_scheme.svg"):
        with open(path, "w") as f:
            f.write(self.build())
        return path

    def save_png(self, path="wizard_scheme.png", size=512):
        renderer = QSvgRenderer(QByteArray(self.build().encode('utf-8')))
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        image.save(path)
        return path

    def save_go_embed(self, path="wizard_embed.go", var_name="WizardSVG"):
        b64 = self.to_base64()
        go_code = f'''package main

// Auto-generated by Wizard Scheme Generator MAX
// DO NOT EDIT — regenerate with the scheme generator tool

const {var_name}Base64 = `{b64}`

func {var_name}Bytes() []byte {{
    data, _ := base64.StdDecodeString({var_name}Base64)
    return data
}}
'''
        with open(path, "w") as f:
            f.write(go_code)
        return path


# ─── Gallery Preview Card ───

class WizardPreviewCard(QFrame):
    def __init__(self, gen_params, label="", on_click=None):
        super().__init__()
        self.gen_params = gen_params
        self.on_click = on_click
        self.setFixedSize(180, 210)
        self.setStyleSheet("QFrame { background: #1a1a2e; border: 1px solid #333; border-radius: 8px; } QFrame:hover { border: 2px solid #2196F3; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        self.svg = QSvgWidget()
        self.svg.setFixedSize(170, 170)
        gen = WizardSVGSchemeGenerator(**gen_params)
        self.svg.load(gen.to_bytes())
        layout.addWidget(self.svg, alignment=Qt.AlignmentFlag.AlignCenter)

        self.label = QLabel(label)
        self.label.setStyleSheet("color: #888; font-size: 9px;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)

    def mousePressEvent(self, event):
        if self.on_click:
            self.on_click(self.gen_params)


# ─── Main UI ───

class SchemeGeneratorUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("\U0001f9d9 Wizard Scheme Generator — MAX EDITION")
        self.setMinimumSize(1100, 750)
        self.setStyleSheet("""
            QWidget { background: #0d1117; color: #fff; }
            QGroupBox { border: 1px solid #333; border-radius: 6px; margin-top: 12px; padding-top: 18px; color: #aaa; font-weight: bold; font-size: 11px; }
            QLabel { color: #ccc; }
            QComboBox { background: #1a1a2e; color: #fff; border: 1px solid #333; padding: 5px; border-radius: 4px; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background: #1a1a2e; color: #fff; selection-background-color: #2196F3; }
            QSpinBox { background: #1a1a2e; color: #fff; border: 1px solid #333; padding: 5px; border-radius: 4px; }
            QSlider::groove:horizontal { background: #333; height: 6px; border-radius: 3px; }
            QSlider::handle:horizontal { background: #2196F3; width: 16px; margin: -5px 0; border-radius: 8px; }
            QSlider::sub-page:horizontal { background: #2196F3; border-radius: 3px; }
            QCheckBox { color: #ccc; }
            QScrollArea { border: none; }
            QLineEdit { background: #1a1a2e; color: #fff; border: 1px solid #333; padding: 5px; border-radius: 4px; }
        """)

        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # ─── Left: Controls ───
        left = QWidget()
        left.setFixedWidth(280)
        left_layout = QVBoxLayout(left)
        left_layout.setSpacing(8)

        title = QLabel("\U0001f9d9 Scheme Generator MAX")
        title.setFont(QFont("Arial", 15, QFont.Weight.Bold))
        title.setStyleSheet("color: #FFD700;")
        left_layout.addWidget(title)

        # Theme
        theme_group = QGroupBox("\U0001f3a8 Theme")
        theme_form = QFormLayout(theme_group)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(THEMES.keys())
        self.theme_combo.currentTextChanged.connect(self.regenerate)
        theme_form.addRow("Palette:", self.theme_combo)
        left_layout.addWidget(theme_group)

        # Wizard Style
        style_group = QGroupBox("\U0001f9d9 Wizard Style")
        style_form = QFormLayout(style_group)
        self.hat_combo = QComboBox(); self.hat_combo.addItems(HAT_STYLES)
        self.hat_combo.currentTextChanged.connect(self.regenerate)
        style_form.addRow("Hat:", self.hat_combo)
        self.beard_combo = QComboBox(); self.beard_combo.addItems(BEARD_STYLES)
        self.beard_combo.currentTextChanged.connect(self.regenerate)
        style_form.addRow("Beard:", self.beard_combo)
        self.wand_combo = QComboBox(); self.wand_combo.addItems(WAND_TYPES)
        self.wand_combo.currentTextChanged.connect(self.regenerate)
        style_form.addRow("Wand:", self.wand_combo)
        self.expr_combo = QComboBox(); self.expr_combo.addItems(EXPRESSIONS)
        self.expr_combo.currentTextChanged.connect(self.regenerate)
        style_form.addRow("Face:", self.expr_combo)
        left_layout.addWidget(style_group)

        # Scene
        scene_group = QGroupBox("\u2728 Scene")
        scene_form = QFormLayout(scene_group)
        self.bg_combo = QComboBox(); self.bg_combo.addItems(BACKGROUNDS)
        self.bg_combo.currentTextChanged.connect(self.regenerate)
        scene_form.addRow("Background:", self.bg_combo)
        self.acc_combo = QComboBox(); self.acc_combo.addItems(ACCESSORIES)
        self.acc_combo.currentTextChanged.connect(self.regenerate)
        scene_form.addRow("Accessory:", self.acc_combo)
        self.star_slider = QSlider(Qt.Orientation.Horizontal)
        self.star_slider.setRange(0, 60); self.star_slider.setValue(15)
        self.star_slider.valueChanged.connect(self.regenerate)
        scene_form.addRow("Density:", self.star_slider)
        self.anim_check = QCheckBox("Animations")
        self.anim_check.setChecked(True)
        self.anim_check.stateChanged.connect(self.regenerate)
        scene_form.addRow("", self.anim_check)
        left_layout.addWidget(scene_group)

        # Branding
        brand_group = QGroupBox("\U0001f4dd Branding")
        brand_form = QFormLayout(brand_group)
        self.brand_input = QLineEdit("Unified MCP")
        self.brand_input.textChanged.connect(self.regenerate)
        brand_form.addRow("Text:", self.brand_input)
        left_layout.addWidget(brand_group)

        left_layout.addStretch()

        # Buttons
        btn_blue = "QPushButton { background: #2196F3; color: white; border: none; padding: 8px; border-radius: 4px; font-weight: bold; } QPushButton:hover { background: #1976D2; }"
        btn_green = "QPushButton { background: #4CAF50; color: white; border: none; padding: 8px; border-radius: 4px; font-weight: bold; } QPushButton:hover { background: #388E3C; }"
        btn_orange = "QPushButton { background: #FF9800; color: white; border: none; padding: 8px; border-radius: 4px; font-weight: bold; } QPushButton:hover { background: #F57C00; }"
        btn_purple = "QPushButton { background: #9C27B0; color: white; border: none; padding: 8px; border-radius: 4px; font-weight: bold; } QPushButton:hover { background: #7B1FA2; }"

        self.rand_btn = QPushButton("\U0001f3b2  Randomize")
        self.rand_btn.setStyleSheet(btn_blue)
        self.rand_btn.clicked.connect(self.regenerate)
        left_layout.addWidget(self.rand_btn)

        self.gallery_btn = QPushButton("\U0001f5bc  Generate Gallery")
        self.gallery_btn.setStyleSheet(btn_purple)
        self.gallery_btn.clicked.connect(self.generate_gallery)
        left_layout.addWidget(self.gallery_btn)

        self.save_svg_btn = QPushButton("\U0001f4be  Save SVG")
        self.save_svg_btn.setStyleSheet(btn_green)
        self.save_svg_btn.clicked.connect(self.save_svg)
        left_layout.addWidget(self.save_svg_btn)

        self.save_png_btn = QPushButton("\U0001f4f7  Save PNG")
        self.save_png_btn.setStyleSheet(btn_orange)
        self.save_png_btn.clicked.connect(self.save_png)
        left_layout.addWidget(self.save_png_btn)

        self.save_go_btn = QPushButton("\U0001f428  Export Go Embed")
        self.save_go_btn.setStyleSheet(btn_purple)
        self.save_go_btn.clicked.connect(self.save_go)
        left_layout.addWidget(self.save_go_btn)

        main_layout.addWidget(left)

        # ─── Center: Main Preview ───
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setSpacing(5)

        preview_label = QLabel("Live Preview (512\u00d7512)")
        preview_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        preview_label.setStyleSheet("color: #FFD700;")
        center_layout.addWidget(preview_label)

        self.svg_widget = QSvgWidget()
        self.svg_widget.setFixedSize(512, 512)
        self.svg_widget.setStyleSheet("border: 2px solid #333; border-radius: 12px; background: #000;")
        center_layout.addWidget(self.svg_widget, alignment=Qt.AlignmentFlag.AlignCenter)

        self.status = QLabel("Ready")
        self.status.setStyleSheet("color: #888; font-size: 11px; font-family: 'Menlo', monospace;")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.addWidget(self.status)

        self.b64_label = QLabel("")
        self.b64_label.setStyleSheet("color: #555; font-size: 9px; font-family: 'Menlo', monospace;")
        self.b64_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.b64_label.setWordWrap(True)
        center_layout.addWidget(self.b64_label)

        main_layout.addWidget(center, 1)

        # ─── Right: Gallery ───
        right = QWidget()
        right.setFixedWidth(250)
        right_layout = QVBoxLayout(right)
        right_layout.setSpacing(5)

        gallery_label = QLabel("\U0001f5bc Gallery")
        gallery_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        gallery_label.setStyleSheet("color: #FFD700;")
        right_layout.addWidget(gallery_label)

        gallery_hint = QLabel("Click a card to load it")
        gallery_hint.setStyleSheet("color: #666; font-size: 10px;")
        right_layout.addWidget(gallery_hint)

        self.gallery_scroll = QScrollArea()
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery_content = QWidget()
        self.gallery_grid = QGridLayout(self.gallery_content)
        self.gallery_grid.setSpacing(5)
        self.gallery_scroll.setWidget(self.gallery_content)
        right_layout.addWidget(self.gallery_scroll)

        main_layout.addWidget(right)

        self.current_seed = 42
        self.regenerate()

    def _get_params(self):
        return {
            "theme_name": self.theme_combo.currentText(),
            "star_count": self.star_slider.value(),
            "seed": self.current_seed,
            "hat_style": self.hat_combo.currentText(),
            "beard_style": self.beard_combo.currentText(),
            "wand_type": self.wand_combo.currentText(),
            "expression": self.expr_combo.currentText(),
            "background": self.bg_combo.currentText(),
            "accessory": self.acc_combo.currentText(),
            "animate": self.anim_check.isChecked(),
            "branding": self.brand_input.text() or "Unified MCP",
        }

    def regenerate(self):
        self.current_seed = random.randint(1, 999999)
        params = self._get_params()
        gen = WizardSVGSchemeGenerator(**params)
        self.svg_widget.load(gen.to_bytes())
        b64 = gen.to_base64()
        self.status.setText(
            f"Seed: {self.current_seed}  |  {params['theme_name']}  |  {params['hat_style']}  |  {params['wand_type']}"
        )
        self.b64_label.setText(f"Base64: {b64[:60]}... ({len(b64)} bytes)")

    def generate_gallery(self):
        while self.gallery_grid.count():
            item = self.gallery_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i in range(12):
            params = {
                "theme_name": random.choice(list(THEMES.keys())),
                "star_count": random.randint(8, 25),
                "seed": random.randint(1, 999999),
                "hat_style": random.choice(HAT_STYLES),
                "beard_style": random.choice(BEARD_STYLES),
                "wand_type": random.choice(WAND_TYPES),
                "expression": random.choice(EXPRESSIONS),
                "background": random.choice(BACKGROUNDS),
                "accessory": random.choice(ACCESSORIES),
                "animate": False,
                "branding": "",
            }
            label = f"#{i+1} {params['theme_name'][:10]}"
            card = WizardPreviewCard(params, label, on_click=self._gallery_click)
            self.gallery_grid.addWidget(card, i // 2, i % 2)

    def _gallery_click(self, params):
        self.theme_combo.setCurrentText(params["theme_name"])
        self.hat_combo.setCurrentText(params["hat_style"])
        self.beard_combo.setCurrentText(params["beard_style"])
        self.wand_combo.setCurrentText(params["wand_type"])
        self.expr_combo.setCurrentText(params["expression"])
        self.bg_combo.setCurrentText(params["background"])
        self.acc_combo.setCurrentText(params["accessory"])
        self.star_slider.setValue(params["star_count"])
        self.current_seed = params["seed"]
        full_params = self._get_params()
        full_params["seed"] = params["seed"]
        gen = WizardSVGSchemeGenerator(**full_params)
        self.svg_widget.load(gen.to_bytes())
        self.status.setText(f"Loaded from gallery — Seed: {params['seed']}")

    def save_svg(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save SVG", "wizard_scheme.svg", "SVG files (*.svg)")
        if path:
            gen = WizardSVGSchemeGenerator(**self._get_params())
            gen.save(path)
            self.status.setText(f"Saved SVG: {path}")

    def save_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save PNG", "wizard_scheme.png", "PNG files (*.png)")
        if path:
            gen = WizardSVGSchemeGenerator(**self._get_params())
            gen.save_png(path, 512)
            self.status.setText(f"Saved PNG: {path}")

    def save_go(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Go Embed", "wizard_embed.go", "Go files (*.go)")
        if path:
            gen = WizardSVGSchemeGenerator(**self._get_params())
            gen.save_go_embed(path, "WizardSVG")
            self.status.setText(f"Saved Go embed: {path}")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Wizard Scheme Generator MAX")
    w = SchemeGeneratorUI()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
