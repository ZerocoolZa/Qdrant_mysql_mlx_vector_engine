#!/usr/bin/env python3
"""
Mini Search GUI — PyQt6 (macOS M1 tested)
- Bottom search bar, top results (QSplitter)
- Always on top
- Minimize to a floating ball (click ball to restore)

Run: python3 mini_search_gui.py
"""

import sys
import os
import re
import sqlite3
from collections import Counter, defaultdict

from PyQt6.QtCore import Qt, QPoint, QTimer, pyqtSignal, QEvent
from PyQt6.QtGui import QColor, QPainter, QPen, QFont, QMouseEvent, QShortcut, QKeySequence, QBrush
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QSplitter, QLineEdit,
    QListWidget, QListWidgetItem, QLabel, QFrame,
    QDialog, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from Engine_smart_search import SmartSearch, search_source, FetchTableContents, _tokenize, _STOP_WORDS, LoadAutocomplete, AcRuntimeConn, AcPrefixSearch, AcBigramNext, AcTrigramNext, AcSymbolSearch, AcRankedSuggestions, AcRecordAccept, AcInitHistory
from Config_smart_system import *

_GHOST_COLOR = QColor(COLOR_GHOST_TEXT_R, COLOR_GHOST_TEXT_G, COLOR_GHOST_TEXT_B)

# --- macOS native window setup (via ctypes → objc_msgSend) ------------------
# Pattern ported from Pindrop's DotFloatingIndicator.swift:
#   NSPanel with .nonactivatingPanel, .borderless
#   level = .mainMenu + 1  (= NSStatusWindowLevel = 25)
#   collectionBehavior = [.canJoinAllSpaces, .stationary, .fullScreenAuxiliary, .ignoresCycle]
#   orderFrontRegardless()
#
# pyobjc's objc.objc_object() can't convert PyQt6's sip.voidptr on M1,
# so we use ctypes calling objc_msgSend directly.
import ctypes as _ctypes
import ctypes.util as _ctypes_util

try:
    _OBJC_LIB = _ctypes.CDLL(_ctypes_util.find_library("objc"))
    _OBJC_LIB.objc_msgSend.restype = _ctypes.c_void_p
    _OBJC_LIB.objc_msgSend.argtypes = [_ctypes.c_void_p, _ctypes.c_void_p]
    _OBJC_LIB.sel_registerName.restype = _ctypes.c_void_p
    _OBJC_LIB.sel_registerName.argtypes = [_ctypes.c_char_p]
    _NATIVE_LEVEL_AVAILABLE = True
    # NSStatusWindowLevel = 25 — above all normal app windows
    _NS_STATUS_LEVEL = 25
    # NSWindowCollectionBehavior flags (from AppKit/NSWindow.h)
    #   canJoinAllSpaces      = 1 << 0  = 1
    #   stationary            = 1 << 4  = 16
    #   ignoresCycle          = 1 << 6  = 64
    #   fullScreenAuxiliary   = 1 << 8  = 256
    _NS_COLLECTION_BEHAVIOR = 1 | 16 | 64 | 256  # = 337
except Exception:
    _NATIVE_LEVEL_AVAILABLE = False
    _NS_STATUS_LEVEL = None
    _NS_COLLECTION_BEHAVIOR = None


def _debug(msg: str):
    sys.stderr.write(f"{DEBUG_PREFIX} {msg}\n")
    sys.stderr.flush()


def _get_nswindow(widget):
    """Get the raw NSWindow pointer from a QWidget via ctypes."""
    if not _NATIVE_LEVEL_AVAILABLE:
        return 0
    handle = widget.windowHandle()
    if handle is None:
        return 0
    wid = int(handle.winId())
    if wid == 0:
        return 0
    ns_view = _ctypes.c_void_p(wid)
    sel_window = _OBJC_LIB.sel_registerName(b"window")
    _OBJC_LIB.objc_msgSend.restype = _ctypes.c_void_p
    _OBJC_LIB.objc_msgSend.argtypes = [_ctypes.c_void_p, _ctypes.c_void_p]
    ns_window = _OBJC_LIB.objc_msgSend(ns_view, sel_window)
    return ns_window


def _ns_msg(window_ptr, sel_name, *args):
    """Send a message to an NSWindow via objc_msgSend."""
    sel = _OBJC_LIB.sel_registerName(sel_name.encode())
    if not args:
        _OBJC_LIB.objc_msgSend.restype = _ctypes.c_void_p
        _OBJC_LIB.objc_msgSend.argtypes = [_ctypes.c_void_p, _ctypes.c_void_p]
        return _OBJC_LIB.objc_msgSend(_ctypes.c_void_p(window_ptr), sel)
    else:
        _OBJC_LIB.objc_msgSend.restype = _ctypes.c_void_p
        _OBJC_LIB.objc_msgSend.argtypes = [_ctypes.c_void_p, _ctypes.c_void_p] + [type(a) for a in args]
        return _OBJC_LIB.objc_msgSend(_ctypes.c_void_p(window_ptr), sel, *args)


def _ns_msg_int(window_ptr, sel_name, value):
    """Send a message with a longlong argument."""
    sel = _OBJC_LIB.sel_registerName(sel_name.encode())
    _OBJC_LIB.objc_msgSend.restype = _ctypes.c_void_p
    _OBJC_LIB.objc_msgSend.argtypes = [_ctypes.c_void_p, _ctypes.c_void_p, _ctypes.c_longlong]
    return _OBJC_LIB.objc_msgSend(_ctypes.c_void_p(window_ptr), sel, _ctypes.c_longlong(value))


def _ns_get_int(window_ptr, sel_name):
    """Get a longlong return value from an NSWindow method."""
    sel = _OBJC_LIB.sel_registerName(sel_name.encode())
    _OBJC_LIB.objc_msgSend.restype = _ctypes.c_longlong
    _OBJC_LIB.objc_msgSend.argtypes = [_ctypes.c_void_p, _ctypes.c_void_p]
    return _OBJC_LIB.objc_msgSend(_ctypes.c_void_p(window_ptr), sel)


def _apply_pindrop_ball_style(widget):
    """Apply Pindrop-style floating panel properties to a QWidget's NSWindow.
    
    Sets:
    - level = NSStatusWindowLevel (25) — above all normal windows
    - collectionBehavior = canJoinAllSpaces | stationary | fullScreenAuxiliary | ignoresCycle
    - orderFrontRegardless — show even if app is not active
    """
    if not _NATIVE_LEVEL_AVAILABLE:
        return False
    try:
        ns_window = _get_nswindow(widget)
        if not ns_window:
            _debug("ball: no NSWindow")
            return False

        # Set level to NSStatusWindowLevel (25)
        _ns_msg_int(ns_window, "setLevel:", _NS_STATUS_LEVEL)
        actual_level = _ns_get_int(ns_window, "level")
        
        # Set collectionBehavior (canJoinAllSpaces | stationary | ignoresCycle | fullScreenAuxiliary)
        _ns_msg_int(ns_window, "setCollectionBehavior:", _NS_COLLECTION_BEHAVIOR)
        actual_cb = _ns_get_int(ns_window, "collectionBehavior")
        
        # orderFrontRegardless — show even if app is not active
        _ns_msg(ns_window, "orderFrontRegardless")
        
        # Make the window non-activating (like NSPanel.nonactivatingPanel)
        # setHidesOnDeactivate: false — don't hide when app loses focus
        _ns_msg_int(ns_window, "setHidesOnDeactivate:", 0)
        
        _debug(f"ball: level={actual_level}, collectionBehavior={actual_cb}")
        return actual_level == _NS_STATUS_LEVEL
    except Exception as ex:
        _debug(f"ball: pindrop style failed: {ex}")
        return False




# --- GhostLineEdit (ghost-text autocomplete with bigram prediction) ----------
# Adapted from vbstyle_class_clarifier.py GhostTextEdit, but for QLineEdit
# (single-line). Uses word frequencies + bigram model from token_registry
# for predictive ghost text — not just prefix matching.
class GhostLineEdit(QLineEdit):
    """QLineEdit with inline ghost-text autocomplete from token_registry.

    Two modes:
    1. Mid-word: prefix-match against word_freq (most frequent word that starts
       with what you've typed).
    2. After space: bigram prediction via SQLite query — SELECT the most common
       next word after the previous word.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ghost_text = ""
        self._word_freq = Counter()
        self._bigram_db = None  # path to SQLite bigram cache
        self._bigram_conn = None  # SQLite connection (opened on set_model)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(TIMER_AUTOCOMPLETE)
        self._timer.timeout.connect(self._update_ghost)
        self.textChanged.connect(self._on_text_changed)

    def set_model(self, word_freq, bigram_db_path):
        self._word_freq = word_freq
        self._bigram_db = bigram_db_path
        if bigram_db_path and os.path.exists(bigram_db_path):
            self._bigram_conn = sqlite3.connect(bigram_db_path)
            self._bigram_conn.row_factory = sqlite3.Row

    def _on_text_changed(self, _text):
        self._ghost_text = ""
        self._timer.start()

    def _get_current_word(self):
        """Extract the word being typed (after last space).
        Uses same word-char rules as _tokenize: [a-zA-Z0-9_]."""
        text = self.text()
        pos = self.cursorPosition()
        start = pos
        while start > 0 and re.match(r"[A-Za-z0-9_]", text[start - 1]):
            start -= 1
        return text[start:pos], start, pos

    def _get_previous_word(self):
        """Get the word before the current one (for bigram prediction).
        Uses same word-char rules as _tokenize: [a-zA-Z0-9_]."""
        text = self.text()
        pos = self.cursorPosition()
        # Skip back past whitespace
        end = pos
        while end > 0 and text[end - 1].isspace():
            end -= 1
        if end == 0:
            return ""
        # Now find the word
        start = end
        while start > 0 and re.match(r"[A-Za-z0-9_]", text[start - 1]):
            start -= 1
        word = text[start:end].lower()
        # Skip stop words — they don't have useful bigram predictions
        if word in _STOP_WORDS or len(word) <= 2:
            return ""
        return word

    def _update_ghost(self):
        self._ghost_text = ""
        if not self._word_freq:
            self.update()
            return

        current_word, word_start, word_end = self._get_current_word()

        if len(current_word) >= 1:
            # Mode 1: mid-word — prefix match against most frequent words
            suggestion = None
            for word, _count in self._word_freq.most_common(500):
                if (word.lower().startswith(current_word.lower())
                        and word.lower() != current_word.lower()
                        and len(word) > len(current_word)):
                    suggestion = word
                    break
            if suggestion:
                self._ghost_text = suggestion[len(current_word):]
        else:
            # Mode 2: after space — bigram prediction via SQLite query
            prev = self._get_previous_word()
            if prev and self._bigram_conn:
                # SELECT most frequent next word after prev
                cur = self._bigram_conn.cursor()
                cur.execute(
                    SQL_SELECT_BIGRAM_NEXT,
                    (prev,)
                )
                row = cur.fetchone()
                if row:
                    self._ghost_text = row[0]

        self.update()

    def _accept_ghost(self):
        if self._ghost_text:
            cur_text = self.text()
            pos = self.cursorPosition()
            self.setText(cur_text[:pos] + self._ghost_text + cur_text[pos:])
            self.setCursorPosition(pos + len(self._ghost_text))
            self._ghost_text = ""
            self.update()
            return True
        return False

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Tab and self._ghost_text:
            self._accept_ghost()
            return
        if e.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down,
                       Qt.Key.Key_Home, Qt.Key.Key_End, Qt.Key.Key_Return, Qt.Key.Key_Enter,
                       Qt.Key.Key_Escape):
            self._ghost_text = ""
        super().keyPressEvent(e)

    def paintEvent(self, e):
        super().paintEvent(e)
        if self._ghost_text:
            painter = QPainter(self)
            painter.setPen(_GHOST_COLOR)
            painter.setFont(self.font())
            fm = painter.fontMetrics()
            text = self.text()
            pos = self.cursorPosition()
            # x position: after the cursor position's text
            # Use cursorRect for accurate positioning
            cursor_rect = self.cursorRect()
            x = cursor_rect.x()
            y = (self.height() + fm.ascent() - fm.descent()) // 2
            painter.drawText(x, y, self._ghost_text)
            painter.end()


# --- Floating ball (minimized state) ----------------------------------------
class FloatingBall(QWidget):
    restore_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # SplashScreen is the reliable flag on macOS for frameless + on-top
        # panels.  Qt.Tool without a parent is unreliable on Cocoa.
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.SplashScreen
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(BALL_SIZE, BALL_SIZE)
        self.setToolTip(BALL_TOOLTIP)
        self._drag_offset: QPoint | None = None
        self._press_pos: QPoint | None = None
        self._dragged: bool = False

        # Periodic re-raise so the ball survives app switching on macOS
        self._raise_timer = QTimer(self)
        self._raise_timer.setInterval(TIMER_RAISE_BALL)
        self._raise_timer.timeout.connect(self._reassert_on_top)

    def _reassert_on_top(self):
        """Periodic re-assert Pindrop-style properties (survives app switching)."""
        if self.isVisible():
            _apply_pindrop_ball_style(self)

    def showEvent(self, e):
        self.raise_()
        # Apply Pindrop-style floating panel properties after window handle exists
        QTimer.singleShot(0, lambda: _apply_pindrop_ball_style(self))
        self._raise_timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self._raise_timer.stop()
        super().hideEvent(e)

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self._press_pos = e.globalPosition().toPoint()
            self._drag_offset = self._press_pos - self.frameGeometry().topLeft()
            self._dragged = False
            e.accept()

    def mouseMoveEvent(self, e: QMouseEvent):
        if self._drag_offset is not None and e.buttons() & Qt.MouseButton.LeftButton:
            cur = e.globalPosition().toPoint()
            if (cur - self._press_pos).manhattanLength() > 3:
                self._dragged = True
            self.move(cur - self._drag_offset)
            e.accept()

    def mouseReleaseEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            # Click (no real drag) → restore the main window
            if not self._dragged:
                _debug("ball clicked → restore")
                self.restore_requested.emit()
            self._drag_offset = None
            self._press_pos = None
            self._dragged = False
            e.accept()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # Bright blue circle with glow effect — clearly visible on any background
        # Outer glow
        for i in range(BALL_GLOW_LAYERS, 0, -1):
            alpha = 30 + i * 20
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(COLOR_BALL_OUTER_R, COLOR_BALL_OUTER_G, COLOR_BALL_OUTER_B, alpha))
            p.drawEllipse(2 - i, 2 - i, (BALL_SIZE - 4) + i * 2, (BALL_SIZE - 4) + i * 2)
        # Main circle — bright blue
        p.setPen(QPen(QColor(COLOR_BALL_BORDER), 3))
        p.setBrush(QColor(COLOR_BALL_FILL))
        p.drawEllipse(BALL_CIRCLE_X, BALL_CIRCLE_Y, BALL_CIRCLE_W, BALL_CIRCLE_H)
        # Inner highlight
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(COLOR_HIGHLIGHT_R, COLOR_HIGHLIGHT_G, COLOR_HIGHLIGHT_B, COLOR_HIGHLIGHT_A))
        p.drawEllipse(BALL_HIGHLIGHT_X, BALL_HIGHLIGHT_Y, BALL_HIGHLIGHT_W, BALL_HIGHLIGHT_H)
        # Letter — white, bold, large
        p.setPen(QColor(COLOR_BALL_LETTER))
        f = QFont(FONT_NAME_HELVETICA, FONT_SIZE_BALL, QFont.Weight.Bold)
        p.setFont(f)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, BALL_LETTER)


# --- Table Viewer Dialog (TASK-069) -----------------------------------------
class TableViewerDialog(QDialog):
    """Popup dialog showing MySQL table contents with pagination.

    Fetches TABLE_VIEWER_PAGE_SIZE rows at a time via FetchTableContents.
    Prev/Next buttons page through the table; a status label shows the
    current page and total row count.
    """

    def __init__(self, table_name, parent=None):
        super().__init__(parent)
        self._table = table_name
        self._offset = 0
        self._page_size = TABLE_VIEWER_PAGE_SIZE
        self._total_rows = 0
        self.setWindowTitle(f"Table: {table_name}")
        self.resize(TABLE_VIEWER_MAX_WIDTH, TABLE_VIEWER_MAX_HEIGHT)
        self.setStyleSheet(
            "QDialog { background: #0d1117; color: #c9d1d9; }"
            f"QTableWidget {{ background: {COLOR_BG_INPUT}; border: 1px solid {COLOR_BORDER};"
            "               gridline-color: #30363d; color: #c9d1d9; }"
            "QHeaderView::section { background: #161b22; color: #8b949e;"
            "                       border: 1px solid #30363d; padding: 4px; }"
            f"QPushButton {{ background: {COLOR_BG_INPUT}; border: 1px solid {COLOR_BORDER};"
            "               border-radius: 4px; padding: 6px 16px; color: #c9d1d9; }"
            "QPushButton:disabled { color: #484f58; }"
            "QLabel { color: #8b949e; padding: 4px; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(LAYOUT_MARGIN, LAYOUT_MARGIN, LAYOUT_MARGIN, LAYOUT_MARGIN)
        layout.setSpacing(LAYOUT_SPACING)

        self._status_label = QLabel(f"Loading {table_name}…")
        layout.addWidget(self._status_label)

        self._table_widget = QTableWidget()
        self._table_widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table_widget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table_widget.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table_widget, 1)

        # Pagination controls
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(LAYOUT_SPACING)
        self._btn_prev = QPushButton("◀ Prev")
        self._btn_next = QPushButton("Next ▶")
        self._btn_close = QPushButton("Close")
        self._btn_prev.clicked.connect(self._prev_page)
        self._btn_next.clicked.connect(self._next_page)
        self._btn_close.clicked.connect(self.accept)
        nav_layout.addWidget(self._btn_prev)
        nav_layout.addWidget(self._btn_next)
        nav_layout.addStretch(1)
        nav_layout.addWidget(self._btn_close)
        layout.addLayout(nav_layout)

        # Load first page
        self._load_page()

    def _load_page(self):
        """Fetch and display the current page of rows."""
        self._status_label.setText(f"Loading {self._table} (offset {self._offset})…")
        QApplication.processEvents()
        columns, rows, total = FetchTableContents(
            self._table, offset=self._offset, limit=self._page_size
        )
        self._total_rows = total
        if not columns:
            self._table_widget.setRowCount(0)
            self._table_widget.setColumnCount(0)
            self._status_label.setText(
                f"(could not load '{self._table}' — MySQL error or empty table)"
            )
            self._btn_prev.setEnabled(False)
            self._btn_next.setEnabled(False)
            return

        self._table_widget.setColumnCount(len(columns))
        self._table_widget.setHorizontalHeaderLabels(columns)
        self._table_widget.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                text = "" if val is None else str(val)
                # Truncate very long cell values for display performance
                if len(text) > 200:
                    text = text[:200] + "…"
                self._table_widget.setItem(r, c, QTableWidgetItem(text))
        self._table_widget.resizeColumnsToContents()
        # Cap column widths so the table stays scrollable
        for c in range(self._table_widget.columnCount()):
            if self._table_widget.columnWidth(c) > 300:
                self._table_widget.setColumnWidth(c, 300)

        end = self._offset + len(rows)
        self._status_label.setText(
            f"{self._table}: rows {self._offset + 1}–{end} of {self._total_rows}"
            if self._total_rows > 0
            else f"{self._table}: {len(rows)} row(s)"
        )
        self._btn_prev.setEnabled(self._offset > 0)
        self._btn_next.setEnabled(end < self._total_rows)

    def _prev_page(self):
        if self._offset > 0:
            self._offset = max(0, self._offset - self._page_size)
            self._load_page()

    def _next_page(self):
        if self._offset + self._page_size < self._total_rows:
            self._offset += self._page_size
            self._load_page()


# --- Main window ------------------------------------------------------------
class MiniSearchGui(QWidget):
    def __init__(self):
        super().__init__()
        # NO WindowStaysOnTopHint on the main window!
        # On macOS, Cocoa refuses to minimize always-on-top windows and
        # keeps re-showing them, causing the zoom-down-up-down flicker.
        # Only the BALL needs to be always-on-top.
        self.setWindowTitle("Mini Search")
        self.resize(420, 480)
        self.setStyleSheet(
            "QWidget { background: #0d1117; color: #c9d1d9; }"
            f"QLineEdit {{ background: {COLOR_BG_INPUT}; border: 1px solid {COLOR_BORDER};"
            "           border-radius: 6px; padding: 6px; color: #c9d1d9; }"
            f"QListWidget {{ background: {COLOR_BG_INPUT}; border: 1px solid {COLOR_BORDER};"
            "              border-radius: 6px; }"
            "QLabel { color: #8b949e; padding: 4px; }"
        )

        # Floating ball for minimize-to-ball
        self.ball = FloatingBall()
        self.ball.restore_requested.connect(self._restore_from_ball)

        # Layout: splitter with results on top, search bar at bottom
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(4)

        # Top: results list + status
        top_frame = QFrame()
        top_layout = QVBoxLayout(top_frame)
        top_layout.setContentsMargins(6, 6, 6, 6)
        top_layout.setSpacing(4)
        self.status_label = QLabel("Type to search…")
        self.results = QListWidget()
        self.results.itemDoubleClicked.connect(self._on_item_activated)
        top_layout.addWidget(self.status_label)
        top_layout.addWidget(self.results, 1)
        splitter.addWidget(top_frame)

        # Bottom: search bar
        bottom_frame = QFrame()
        bottom_layout = QVBoxLayout(bottom_frame)
        bottom_layout.setContentsMargins(6, 6, 6, 6)
        bottom_layout.setSpacing(4)
        self.search = GhostLineEdit()
        self.search.setPlaceholderText("Search vb_shared…  (Tab = autocomplete, Esc = ball)")
        self.search.textChanged.connect(self._on_search_debounced)
        self.search.returnPressed.connect(self._on_enter)
        bottom_layout.addWidget(self.search)
        splitter.addWidget(bottom_frame)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([360, 80])

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(splitter)

        # Debounce timer — 200ms delay before MySQL query (per [@SearchBar] token)
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(TIMER_DEBOUNCE)
        self._debounce_timer.timeout.connect(self._do_search)
        self._pending_query = ""

        # Load tokens for autocomplete (async — don't block UI)
        QTimer.singleShot(100, self._init_autocomplete)

        # Initial results (table list)
        self._do_search()

        # Esc shortcut — ApplicationShortcut so it works even when a child
        # widget (QLineEdit) has focus or the window is about to hide.
        self.esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.esc_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.esc_shortcut.activated.connect(self._minimize_to_ball)

        # Guard flag: when WE call hide() to minimize, we set this so our
        # hideEvent doesn't re-trigger the ball show loop.
        self._self_hiding = False
        # Guard: don't react to minimize events until the window has been
        # visible for at least 1 second.  macOS sends spurious WindowMinimized
        # events during startup.
        self._initialized = False
        self._show_time = 0
        # Re-entrancy guard for _minimize_to_ball
        self._minimizing = False
        # macOS: prevent the system from forcing tool windows to always show
        self.setAttribute(
            Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow,
            False
        )

    # --- Search (debounced MySQL) ------------------------------------------
    def _init_autocomplete(self):
        """Load word_freq + bigrams via generator + QTimer chunks.
        Engine yields progress, GUI drives the timer to keep UI responsive."""
        self.status_label.setText(STATUS_LOADING)
        self._ac_gen = LoadAutocomplete()
        self._ac_word_freq = Counter()
        self._ac_timer = QTimer(self)
        self._ac_timer.setSingleShot(True)
        self._ac_timer.setInterval(TIMER_CHUNK_YIELD)
        self._ac_timer.timeout.connect(self._ac_tick)
        self._ac_timer.start()

    def _ac_tick(self):
        """Process one generator yield, then schedule next tick or finish."""
        try:
            phase, data = next(self._ac_gen)
        except StopIteration:
            return
        if phase == "word_freq":
            self._ac_word_freq = data
            self._ac_timer.start()
        elif phase == "bigrams_progress":
            self._ac_timer.start()
        elif phase == "bigrams_done":
            self._ac_timer.stop()
            self._on_autocomplete_loaded(self._ac_word_freq, data)

    def _on_autocomplete_loaded(self, word_freq, ac_db_path):
        """Called when autocomplete build/load finishes.
        word_freq is legacy (ignored). ac_db_path opens SQLite for runtime queries."""
        self.search.set_model(word_freq, ac_db_path)
        if self.search._ac_conn:
            AcInitHistory(self.search._ac_conn)
        if word_freq:
            n_bigrams = 0
            if bigram_db_path and os.path.exists(bigram_db_path):
                try:
                    sconn = sqlite3.connect(bigram_db_path)
                    n_bigrams = sconn.execute(SQL_COUNT_BIGRAMS).fetchone()[0]
                    sconn.close()
                except Exception:
                    pass
            self.status_label.setText(
                f"Ready — {len(word_freq)} words + {n_bigrams} bigrams (SQLite)"
            )

    def _on_search_debounced(self, text: str):
        """Store query and restart debounce timer (200ms per [@SearchBar] token)."""
        self._pending_query = text
        self._debounce_timer.start()

    def _do_search(self):
        """Run the actual MySQL search after debounce delay."""
        query = self._pending_query
        self.status_label.setText("Searching…" if query.strip() else "Loading…")
        QApplication.processEvents()  # update UI before blocking MySQL call
        hits = search_source(query)
        self.results.clear()
        for h in hits:
            QListWidgetItem(h, self.results)
        if query.strip():
            self.status_label.setText(f"{len(hits)} hit(s) for '{query}'")
        else:
            self.status_label.setText(f"{len(hits)} table(s) in vb_shared")

    def _on_enter(self):
        items = self.results.selectedItems()
        if not items and self.results.count() > 0:
            items = [self.results.item(0)]
        for it in items:
            self._activate(it.text())

    def _on_item_activated(self, item):
        self._activate(item.text())

    def _activate(self, text: str):
        # Parse the hit string: "table_name | snippet" or "[table] name"
        if text.startswith("[table] "):
            table = text[8:]
            self.status_label.setText(f"Browsing table: {table}")
            self._show_table_contents(table)
        elif " | " in text:
            table, snippet = text.split(" | ", 1)
            self.status_label.setText(f"Hit in {table}: {snippet[:60]}")
        else:
            self.status_label.setText(f"Activated: {text}")

    def _show_table_contents(self, table: str):
        """Open a TableViewerDialog popup showing the MySQL table contents (TASK-069)."""
        dlg = TableViewerDialog(table, parent=self)
        dlg.exec()

    # --- Minimize to ball ---------------------------------------------------
    def _minimize_to_ball(self):
        _debug("minimize_to_ball called")
        if self._minimizing:
            _debug("already minimizing, skipping")
            return
        self._minimizing = True

        # Save original position for restore
        self._saved_geometry = self.geometry()

        # Position ball at top-right of where the window was
        screen_geo = self.screen().availableGeometry() if self.screen() else None
        bx = self._saved_geometry.right() - self.ball.width()
        by = self._saved_geometry.top()
        if screen_geo is not None:
            bx = max(screen_geo.left(), min(bx, screen_geo.right() - self.ball.width()))
            by = max(screen_geo.top(), min(by, screen_geo.bottom() - self.ball.height()))
        self.ball.move(bx, by)

        # Show the ball with Pindrop-style floating panel properties
        self.ball.show()
        self.ball.raise_()
        _apply_pindrop_ball_style(self.ball)

        # Let macOS minimize the window normally (no hide() call!)
        # Without WindowStaysOnTopHint, Cocoa minimizes properly.
        self.showMinimized()

        # Release guard after 500ms
        QTimer.singleShot(500, lambda: setattr(self, "_minimizing", False))
        _debug(f"minimized → ball at ({bx},{by}), ball visible={self.ball.isVisible()}")

    def showEvent(self, e):
        _debug(f"SHOW (initialized={self._initialized}, minimizing={self._minimizing})")
        if not self._initialized:
            QTimer.singleShot(1000, self._mark_initialized)
        super().showEvent(e)

    def _mark_initialized(self):
        if self.isVisible() and self.windowOpacity() > 0.1:
            self._initialized = True
            _debug(f"window initialized (ready for minimize-to-ball)")

    def hideEvent(self, e):
        _debug("HIDE")
        super().hideEvent(e)

    def changeEvent(self, e):
        _debug(f"CHANGE type={e.type()}")
        if e.type() == QEvent.Type.WindowStateChange:
            state = self.windowState()
            _debug(f"  WindowStateChange state={state} init={self._initialized}")
            # If user minimized via yellow dot/Cmd+M and we haven't shown ball yet
            if self._initialized and not self._minimizing and (state & Qt.WindowState.WindowMinimized):
                _debug("  user minimize → showing ball")
                self._minimize_to_ball()
                return
        super().changeEvent(e)

    def _restore_from_ball(self):
        _debug("restore_from_ball")
        self._minimizing = False
        self.ball.hide()
        # Restore from minimized state
        self.setWindowState(Qt.WindowState.WindowNoState)
        self.showNormal()
        if hasattr(self, "_saved_geometry") and self._saved_geometry:
            self.setGeometry(self._saved_geometry)
        self.raise_()
        self.activateWindow()
        self.search.setFocus()

    def closeEvent(self, e):
        self.ball.close()
        super().closeEvent(e)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MiniSearchGui")
    gui = MiniSearchGui()
    gui.show()
    gui.search.setFocus()
    _debug(f"started; native_level={_NATIVE_LEVEL_AVAILABLE}")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
