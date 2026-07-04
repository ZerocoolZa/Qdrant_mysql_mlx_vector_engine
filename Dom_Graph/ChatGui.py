#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/ChatGui.py"
# date="2026-06-27" author="Devin" session_id="chat-gui"
# context="GUI chat window that connects to Devin CLI agent as backend, with MySQL knowledge base search"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="ChatGui.py" domain="chat_gui" authority="ChatGui"}
# [@SUMMARY]{summary="PyQt6 chat GUI. Sends messages to Devin CLI in non-interactive mode. Includes MySQL knowledge base search panel (learned_rules, know_problems, know_solutions). Chat history stored in devin.devin_chat_turns."}
# [@CLASS]{class="ChatGui" domain="chat_gui" authority="single"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<fail>][@notes<PyQt6 chat GUI connecting to Devin CLI with MySQL KB search. Multiple classes in file (DevinWorker QThread, ChatGui QMainWindow, and likely more). Uses pyqtSignal decorators. No Run dispatch visible in headers. No Tuple3 returns for GUI class. Has hardcoded paths. Missing @METHOD header.>][@todos<Split QThread worker classes into separate files. Add Run dispatch and Tuple3. Add @METHOD header. Remove hardcoded paths. Move to Config.py.>]}
import sys
import os
import re
import json
import sqlite3
import subprocess
import threading
import time
from collections import Counter
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QSplitter,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QStatusBar, QListWidget, QListWidgetItem, QMenu,
    QCompleter, QListView, QScrollArea, QFrame,
    QDialog, QFormLayout, QSpinBox, QDoubleSpinBox, QSlider, QCheckBox, QGroupBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer, QStringListModel, QSortFilterProxyModel
from PyQt6.QtGui import QFont, QColor, QTextCursor, QKeySequence, QShortcut, QAction, QPainter

try:
    import mysql.connector
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from Config_ChatGui import *
from VoiceEngine import VoiceEngine


class DevinWorker(QThread):
    """Runs Devin CLI in a background thread."""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, prompt, cwd=None, session_id=None):
        super().__init__()
        self.prompt = prompt
        self.cwd = cwd or os.getcwd()
        self.session_id = session_id

    def run(self):
        try:
            cmd = [DEVIN_CMD, "-p"]
            if self.session_id:
                cmd.extend(["--resume", self.session_id])
            cmd.extend(["--", self.prompt])
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.cwd,
                text=True
            )
            stdout, stderr = proc.communicate(timeout=120)
            if proc.returncode == 0:
                output = stdout.strip()
                if not output and stderr:
                    output = stderr.strip()
                self.finished.emit(output)
            else:
                msg = stderr.strip() if stderr else "Unknown error"
                self.error.emit(msg)
        except subprocess.TimeoutExpired:
            proc.kill()
            self.error.emit("Devin CLI timed out (120s)")
        except Exception as e:
            self.error.emit(str(e))


class MysqlSearchWorker(QThread):
    """Searches MySQL knowledge base in background."""
    finished = pyqtSignal(list, str)
    error = pyqtSignal(str)

    def __init__(self, query, table):
        super().__init__()
        self.query = query
        self.table = table

    def run(self):
        try:
            conn = mysql.connector.connect(
                user=DB_USER, password=DB_PASSWORD,
                host=DB_HOST, database=DB_SHARED
            )
            cursor = conn.cursor(dictionary=True)
            if self.table == "learned_rules":
                sql = "SELECT pattern, fix_action, confidence, created_at FROM learned_rules WHERE pattern LIKE %s OR fix_action LIKE %s ORDER BY confidence DESC LIMIT 50"
                val = ("%" + self.query + "%", "%" + self.query + "%")
            elif self.table == "know_problems":
                sql = "SELECT problem, description, category FROM know_problems WHERE problem LIKE %s OR description LIKE %s LIMIT 50"
                val = ("%" + self.query + "%", "%" + self.query + "%")
            elif self.table == "know_solutions":
                sql = "SELECT solution, description, problem_id FROM know_solutions WHERE solution LIKE %s OR description LIKE %s LIMIT 50"
                val = ("%" + self.query + "%", "%" + self.query + "%")
            elif self.table == "vb_classes":
                conn.close()
                conn = mysql.connector.connect(
                    user=DB_USER, password=DB_PASSWORD,
                    host=DB_HOST, database=DB_CODE_TEST
                )
                cursor = conn.cursor(dictionary=True)
                sql = "SELECT class_name, domain, role FROM vb_classes WHERE class_name LIKE %s LIMIT 50"
                val = ("%" + self.query + "%",)
            elif self.table == "vb_methods":
                conn.close()
                conn = mysql.connector.connect(
                    user=DB_USER, password=DB_PASSWORD,
                    host=DB_HOST, database=DB_CODE_TEST
                )
                cursor = conn.cursor(dictionary=True)
                sql = "SELECT method_name, class_name FROM vb_methods JOIN vb_classes ON vb_methods.class_id = vb_classes.id WHERE method_name LIKE %s LIMIT 50"
                val = ("%" + self.query + "%",)
            else:
                self.error.emit("Unknown table")
                return
            cursor.execute(sql, val)
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            self.finished.emit(rows, self.table)
        except Exception as e:
            self.error.emit(str(e))


class SessionListWorker(QThread):
    """Fetches Devin session list from MySQL devin.devin_sessions (all sessions, not just current dir)."""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, cwd=None):
        super().__init__()
        self.cwd = cwd or os.getcwd()

    def run(self):
        try:
            conn = mysql.connector.connect(
                user=DB_USER, password=DB_PASSWORD,
                host=DB_HOST, database=DB_DEVIN
            )
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT id, title, last_activity_at FROM devin_sessions "
                "ORDER BY last_activity_at DESC LIMIT 100"
            )
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            sessions = []
            now = int(time.time())
            for r in rows:
                sid = r.get("id", "?")
                title = r.get("title", "untitled")
                if title and len(title) > 80:
                    title = title[:77] + "..."
                last_at = r.get("last_activity_at", 0)
                if last_at:
                    delta = now - int(last_at)
                    if delta < 60:
                        ago = "just now"
                    elif delta < 3600:
                        ago = str(delta // 60) + "m ago"
                    elif delta < 86400:
                        ago = str(delta // 3600) + "h ago"
                    else:
                        ago = str(delta // 86400) + "d ago"
                else:
                    ago = "?"
                sessions.append({
                    "id": sid,
                    "title": title,
                    "last_activity_ago": ago,
                    "working_directory": self.cwd,
                })
            self.finished.emit(sessions)
        except Exception as e:
            self.error.emit(str(e))


class TokenLoaderWorker(QThread):
    """Loads @ tokens from MySQL in background."""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def run(self):
        try:
            conn = mysql.connector.connect(
                user=DB_USER, password=DB_PASSWORD,
                host=DB_HOST, database=DB_SHARED
            )
            cursor = conn.cursor()
            cursor.execute("SELECT name, meaning FROM tokens WHERE name LIKE '@%' LIMIT 200")
            tokens = []
            for row in cursor.fetchall():
                name = row[0]
                meaning = str(row[1])[:60] if row[1] else ""
                tokens.append(name + " - " + meaning)
            cursor.close()
            conn.close()
            if not tokens:
                tokens = list(FALLBACK_TOKENS)
            self.finished.emit(tokens)
        except Exception:
            self.finished.emit(list(FALLBACK_TOKENS))


class AutocompleteLoaderWorker(QThread):
    """Loads word_freq from autocomplete.db into a Counter.
    If word_freq/bigrams/trigrams tables don't exist, builds them from qa_pairs.
    This is the 'model knows me' step — learns vocabulary from 12,487 Q&A pairs.
    """
    finished = pyqtSignal(object, int, str)
    error = pyqtSignal(str)

    SQL_CREATE_WORDFREQ = (
        'CREATE TABLE IF NOT EXISTS word_freq (word TEXT PRIMARY KEY, freq INTEGER)'
    )
    SQL_CREATE_BIGRAMS = (
        'CREATE TABLE IF NOT EXISTS bigrams (w1 TEXT, w2 TEXT, freq INTEGER,'
        ' PRIMARY KEY(w1, w2))'
    )
    SQL_CREATE_TRIGRAMS = (
        'CREATE TABLE IF NOT EXISTS trigrams (w1 TEXT, w2 TEXT, w3 TEXT, freq INTEGER,'
        ' PRIMARY KEY(w1, w2, w3))'
    )
    SQL_INDEX_BIGRAM_W1 = 'CREATE INDEX IF NOT EXISTS idx_bigram_w1 ON bigrams(w1)'
    SQL_INDEX_BIGRAM_W1F = 'CREATE INDEX IF NOT EXISTS idx_bigram_w1_freq ON bigrams(w1, freq DESC)'
    SQL_INDEX_TRIGRAM = 'CREATE INDEX IF NOT EXISTS idx_trigram_w1w2 ON trigrams(w1, w2)'
    SQL_UPSERT_WORDFREQ = (
        'INSERT INTO word_freq (word, freq) VALUES (?, ?) '
        'ON CONFLICT(word) DO UPDATE SET freq = freq + ?'
    )
    SQL_UPSERT_BIGRAM = (
        'INSERT INTO bigrams (w1, w2, freq) VALUES (?, ?, ?) '
        'ON CONFLICT(w1, w2) DO UPDATE SET freq = freq + ?'
    )
    SQL_UPSERT_TRIGRAM = (
        'INSERT INTO trigrams (w1, w2, w3, freq) VALUES (?, ?, ?, ?) '
        'ON CONFLICT(w1, w2, w3) DO UPDATE SET freq = freq + ?'
    )
    SQL_COUNT_WORDFREQ = 'SELECT COUNT(*) FROM word_freq'
    SQL_COUNT_BIGRAMS = 'SELECT COUNT(*) FROM bigrams'
    SQL_COUNT_TRIGRAMS = 'SELECT COUNT(*) FROM trigrams'
    SQL_LOAD_WORDFREQ = 'SELECT word, freq FROM word_freq'
    SQL_SELECT_QA_TEXT = 'SELECT question, answer FROM qa_pairs'

    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path

    def Tokenize(self, text):
        words = re.findall(r"[A-Za-z0-9_]+", text.lower())
        return [w for w in words if w not in STOP_WORDS and len(w) > 2]

    def TablesExist(self, conn):
        cur = conn.cursor()
        for table in ("word_freq", "bigrams", "trigrams"):
            try:
                cur.execute(f'SELECT COUNT(*) FROM {table}')
                count = cur.fetchone()[0]
                if count == 0:
                    return False
            except Exception:
                return False
        return True

    def BuildTables(self, conn):
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=OFF")
        cur.execute(self.SQL_CREATE_WORDFREQ)
        cur.execute(self.SQL_CREATE_BIGRAMS)
        cur.execute(self.SQL_CREATE_TRIGRAMS)
        cur.execute(self.SQL_INDEX_BIGRAM_W1)
        cur.execute(self.SQL_INDEX_BIGRAM_W1F)
        cur.execute(self.SQL_INDEX_TRIGRAM)
        conn.commit()

        cur.execute(self.SQL_SELECT_QA_TEXT)
        rows = cur.fetchall()

        wf = Counter()
        bi = Counter()
        tri = Counter()

        for question, answer in rows:
            text = str(question or "") + " " + str(answer or "")
            words = self.Tokenize(text)
            for w in words:
                wf[w] += 1
            for i in range(len(words) - 1):
                bi[(words[i], words[i + 1])] += 1
            for i in range(len(words) - 2):
                tri[(words[i], words[i + 1], words[i + 2])] += 1

        cur.executemany(
            self.SQL_UPSERT_WORDFREQ,
            [(w, f, f) for w, f in wf.items()]
        )
        cur.executemany(
            self.SQL_UPSERT_BIGRAM,
            [(w1, w2, f, f) for (w1, w2), f in bi.items()]
        )
        cur.executemany(
            self.SQL_UPSERT_TRIGRAM,
            [(w1, w2, w3, f, f) for (w1, w2, w3), f in tri.items()]
        )
        conn.commit()
        return len(wf), len(bi), len(tri)

    def run(self):
        try:
            if not os.path.exists(self.db_path):
                self.error.emit("autocomplete.db not found at " + self.db_path)
                return

            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row

            if not self.TablesExist(conn):
                wf_count, bi_count, tri_count = self.BuildTables(conn)
            else:
                cur = conn.cursor()
                cur.execute(self.SQL_COUNT_WORDFREQ)
                wf_count = cur.fetchone()[0]
                cur.execute(self.SQL_COUNT_BIGRAMS)
                bi_count = cur.fetchone()[0]
                cur.execute(self.SQL_COUNT_TRIGRAMS)
                tri_count = cur.fetchone()[0]

            cur = conn.cursor()
            cur.execute(self.SQL_LOAD_WORDFREQ)
            word_freq = Counter()
            for row in cur.fetchall():
                word_freq[row[0]] = row[1]
            conn.close()

            summary = f"{wf_count} words, {bi_count} bigrams, {tri_count} trigrams"
            self.finished.emit(word_freq, len(word_freq), summary)
        except Exception as e:
            self.error.emit(str(e))


_GHOST_COLOR = QColor(GHOST_TEXT_R, GHOST_TEXT_G, GHOST_TEXT_B)


class GhostChatInput(QLineEdit):
    """Chat input with / slash commands, @ mention autocomplete, and ghost-text
    predictive autocomplete using word frequencies + bigram model from autocomplete.db.

    Three features layered:
    1. Slash command popup — type / to see commands
    2. @ token popup — type @ to see tokens
    3. Ghost text — grey predictive text appears as you type, press Tab to accept
       Mode A: mid-word — prefix match against most frequent words
       Mode B: after space — bigram prediction (most common next word)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont(FONT_FAMILY, FONT_INPUT))
        self.setPlaceholderText("Type / for commands, @ for tags, or just chat...  (Tab = accept ghost text)")
        self.slash_commands = SLASH_COMMANDS
        self.at_tokens = list(FALLBACK_TOKENS)
        self.popup = None
        self.popup_mode = None
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.ShowContextMenu)

        self.ghost_text = ""
        self.word_freq = Counter()
        self.ac_conn = None

        self.ghost_timer = QTimer(self)
        self.ghost_timer.setSingleShot(True)
        self.ghost_timer.setInterval(TIMER_AUTOCOMPLETE)
        self.ghost_timer.timeout.connect(self.UpdateGhost)

        self.textChanged.connect(self.OnTextChanged)

    def ShowContextMenu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: " + COLOR_PANEL + "; color: " + COLOR_TEXT +
            "; border: 1px solid " + COLOR_BORDER + "; font-size: " + str(FONT_BUTTON) + "px; padding: 6px; }"
            "QMenu::item { padding: 8px 24px; border-radius: 4px; }"
            "QMenu::item:selected { background-color: " + COLOR_BUTTON + "; color: white; }"
        )
        act_cut = menu.addAction("Cut  \tCtrl+X")
        act_copy = menu.addAction("Copy  \tCtrl+C")
        act_paste = menu.addAction("Paste  \tCtrl+V")
        menu.addSeparator()
        act_select = menu.addAction("Select All  \tCtrl+A")
        menu.addSeparator()
        act_undo = menu.addAction("Undo  \tCtrl+Z")
        act_redo = menu.addAction("Redo  \tCtrl+Y")
        action = menu.exec(self.mapToGlobal(pos))
        if action == act_cut:
            self.cut()
        elif action == act_copy:
            self.copy()
        elif action == act_paste:
            self.paste()
        elif action == act_select:
            self.selectAll()
        elif action == act_undo:
            self.undo()
        elif action == act_redo:
            self.redo()

    def SetTokens(self, tokens):
        self.at_tokens = tokens

    def SetAutocompleteModel(self, word_freq, ac_db_path):
        """Load word frequencies and open SQLite connection for bigram prediction."""
        self.word_freq = word_freq
        if ac_db_path and os.path.exists(ac_db_path):
            self.ac_conn = sqlite3.connect(ac_db_path)
            self.ac_conn.row_factory = sqlite3.Row
            try:
                self.ac_conn.execute(SQL_CREATE_USER_HISTORY)
                self.ac_conn.commit()
            except Exception:
                pass

    def OnTextChanged(self, text):
        self.ghost_text = ""
        if not text:
            self.HidePopup()
            return
        if text.startswith("/") and " " not in text:
            self.ShowPopup(self.slash_commands, "slash")
            return
        if "@" in text:
            at_pos = text.rfind("@")
            after_at = text[at_pos + 1:]
            if " " not in after_at and len(after_at) >= 0:
                filtered = [t for t in self.at_tokens if after_at.lower() in t.lower()]
                if filtered:
                    self.ShowPopup(filtered, "at")
                else:
                    self.HidePopup()
                return
            else:
                self.HidePopup()
                return
        self.HidePopup()
        self.ghost_timer.start()

    def GetCurrentWord(self):
        """Extract the word being typed (after last space)."""
        text = self.text()
        pos = self.cursorPosition()
        start = pos
        while start > 0 and re.match(r"[A-Za-z0-9_]", text[start - 1]):
            start -= 1
        return text[start:pos], start, pos

    def GetPreviousWord(self):
        """Get the word before the current one (for bigram prediction)."""
        text = self.text()
        pos = self.cursorPosition()
        end = pos
        while end > 0 and text[end - 1].isspace():
            end -= 1
        if end == 0:
            return ""
        start = end
        while start > 0 and re.match(r"[A-Za-z0-9_]", text[start - 1]):
            start -= 1
        word = text[start:end].lower()
        if word in STOP_WORDS or len(word) <= 2:
            return ""
        return word

    def UpdateGhost(self):
        """Compute ghost text — prefix match or bigram prediction."""
        self.ghost_text = ""
        if not self.word_freq:
            self.update()
            return

        current_word, word_start, word_end = self.GetCurrentWord()

        if len(current_word) >= AUTOCOMPLETE_PREFIX_MIN:
            suggestion = None
            for word, _count in self.word_freq.most_common(AUTOCOMPLETE_WORD_SCAN):
                if (word.lower().startswith(current_word.lower())
                        and word.lower() != current_word.lower()
                        and len(word) > len(current_word)):
                    suggestion = word
                    break
            if suggestion:
                self.ghost_text = suggestion[len(current_word):]
        else:
            prev = self.GetPreviousWord()
            if prev and self.ac_conn:
                try:
                    cur = self.ac_conn.cursor()
                    cur.execute(SQL_SELECT_BIGRAM_NEXT, (prev,))
                    row = cur.fetchone()
                    if row:
                        self.ghost_text = row[0]
                except Exception:
                    pass

        self.update()

    def AcceptGhost(self):
        """Tab key — insert ghost text at cursor, record to user_history."""
        if self.ghost_text:
            cur_text = self.text()
            pos = self.cursorPosition()
            self.setText(cur_text[:pos] + self.ghost_text + cur_text[pos:])
            self.setCursorPosition(pos + len(self.ghost_text))
            accepted_word = self.ghost_text
            self.ghost_text = ""
            self.update()
            if self.ac_conn:
                try:
                    prev = self.GetPreviousWord()
                    self.ac_conn.execute(SQL_UPSERT_USER_HISTORY, (accepted_word, prev))
                    self.ac_conn.commit()
                except Exception:
                    pass
            return True
        return False

    def ShowPopup(self, items, mode):
        if self.popup is None:
            self.popup = QListView(self)
            self.popup.setFont(QFont(FONT_FAMILY, FONT_BUTTON))
            self.popup.setStyleSheet(
                "QListView { background-color: " + COLOR_PANEL + "; color: " + COLOR_TEXT +
                "; border: 1px solid " + COLOR_BUTTON + "; border-radius: 4px; padding: 4px; }"
                "QListView::item { padding: 10px; border-bottom: 1px solid " + COLOR_BORDER + "; }"
                "QListView::item:selected { background-color: " + COLOR_BUTTON + "; color: white; }"
            )
            self.popup.setWindowFlags(Qt.WindowType.Popup)
            self.popup.clicked.connect(self.OnPopupSelected)
        model = QStringListModel(items)
        self.popup.setModel(model)
        self.popup_mode = mode
        text = self.text()
        char_width = self.fontMetrics().horizontalAdvance('x')
        popup_width = max(400, len(max(items, key=len)) * char_width * 0.6)
        popup_height = min(len(items) * 45 + 10, 300)
        self.popup.setFixedSize(int(popup_width), popup_height)
        pos = self.mapToGlobal(self.rect().bottomLeft())
        pos.setY(pos.y() + 4)
        self.popup.move(pos)
        self.popup.show()

    def HidePopup(self):
        if self.popup:
            self.popup.hide()
        self.popup_mode = None

    def OnPopupSelected(self, index):
        item = self.popup.model().data(index)
        if self.popup_mode == "slash":
            cmd = item.split(" ")[0]
            self.setText(cmd + " ")
        elif self.popup_mode == "at":
            token = item.split(" ")[0]
            text = self.text()
            at_pos = text.rfind("@")
            self.setText(text[:at_pos] + token + " ")
        self.HidePopup()
        self.setFocus()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Tab and self.ghost_text:
            self.AcceptGhost()
            return
        if self.popup and self.popup.isVisible():
            if event.key() == Qt.Key.Key_Escape:
                self.HidePopup()
                return
            if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                    self.popup.keyPressEvent(event)
                    return
                if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    idx = self.popup.currentIndex()
                    if idx.isValid():
                        self.OnPopupSelected(idx)
                        return
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Home, Qt.Key.Key_End,
                           Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape):
            self.ghost_text = ""
        super().keyPressEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.ghost_text:
            painter = QPainter(self)
            painter.setPen(_GHOST_COLOR)
            painter.setFont(self.font())
            fm = painter.fontMetrics()
            cursor_rect = self.cursorRect()
            x = cursor_rect.x()
            y = (self.height() + fm.ascent() - fm.descent()) // 2
            painter.drawText(x, y, self.ghost_text)
            painter.end()


class ChatGui(QMainWindow):
    """Chat GUI with Devin CLI backend and MySQL knowledge search."""

    def __init__(self):
        super().__init__()
        self.state = {
            "config": {
                "cwd": os.path.expanduser("~/Qdrant_mysql_mlx_vector_engine/Dom_Graph"),
            },
            "chat_history": [],
            "devin_busy": False,
            "current_session_id": None,
            "current_session_title": None,
        }
        self.setWindowTitle("Devin Chat GUI")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.voice = VoiceEngine()
        self.voice.Run("set_config", {
            "enabled": VOICE_ENABLED,
            "voice": VOICE_NAME,
            "rate": VOICE_RATE,
            "stt_language": STT_LANGUAGE,
            "stt_on_device": STT_ON_DEVICE,
            "stt_buffer_size": STT_BUFFER_SIZE,
            "stt_silence_timeout": STT_SILENCE_TIMEOUT,
            "stt_min_listen": STT_MIN_LISTEN,
            "stt_max_timeout": STT_MAX_TIMEOUT,
            "stt_runloop_interval": STT_RUNLOOP_INTERVAL,
        })
        self.voice.ttsFinished.connect(self.OnTtsFinished)
        self.voice.Run("warmup")
        self.listening = False
        self.settings = {}
        self.LoadSettings()
        self.BuildUi()
        self.ApplyTheme()
        self.SizeWindow()
        self.setWindowOpacity(WINDOW_OPACITY)
        self.BuildMenu()
        self.LoadAutocomplete()
        self.LoadTokens()

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def LoadSettings(self):
        global FONT_CHAT, FONT_INPUT, FONT_LIST, CURRENT_THEME, WINDOW_OPACITY
        global COLOR_BG, COLOR_PANEL, COLOR_INPUT, COLOR_TEXT, COLOR_BORDER
        global COLOR_BUTTON, COLOR_BUTTON_HOVER, COLOR_USER, COLOR_ASSISTANT, COLOR_SYSTEM
        global BUBBLE_COLOR_USER, BUBBLE_COLOR_ASSISTANT, BUBBLE_COLOR_SYSTEM
        global BUBBLE_TEXT_COLOR_USER, BUBBLE_TEXT_COLOR_ASSISTANT, BUBBLE_TEXT_COLOR_SYSTEM
        try:
            with open(SETTINGS_FILE, "r") as f:
                self.settings = json.load(f)
        except Exception:
            self.settings = {}
        s = self.settings
        if "voice_enabled" in s:
            self.voice.Run("set_config", {"enabled": s["voice_enabled"]})
        if "voice_name" in s:
            self.voice.Run("set_config", {"voice": s["voice_name"]})
        if "voice_rate" in s:
            self.voice.Run("set_config", {"rate": s["voice_rate"]})
        if "stt_on_device" in s:
            self.voice.Run("set_config", {"stt_on_device": s["stt_on_device"]})
        if "stt_language" in s:
            self.voice.Run("set_config", {"stt_language": s["stt_language"]})
        if "stt_buffer_size" in s:
            self.voice.Run("set_config", {"stt_buffer_size": s["stt_buffer_size"]})
        if "stt_silence_timeout" in s:
            self.voice.Run("set_config", {"stt_silence_timeout": s["stt_silence_timeout"]})
        if "stt_min_listen" in s:
            self.voice.Run("set_config", {"stt_min_listen": s["stt_min_listen"]})
        if "stt_max_timeout" in s:
            self.voice.Run("set_config", {"stt_max_timeout": s["stt_max_timeout"]})
        if "stt_runloop_interval" in s:
            self.voice.Run("set_config", {"stt_runloop_interval": s["stt_runloop_interval"]})
        if "stt_silence_threshold" in s:
            self.voice.Run("set_config", {"stt_silence_threshold": s["stt_silence_threshold"]})
        if "theme" in s and s["theme"] in THEMES:
            CURRENT_THEME = s["theme"]
            t = THEMES[CURRENT_THEME]
            COLOR_BG = t["bg"]
            COLOR_PANEL = t["panel"]
            COLOR_INPUT = t["input"]
            COLOR_TEXT = t["text"]
            COLOR_BORDER = t["border"]
            COLOR_BUTTON = t["button"]
            COLOR_BUTTON_HOVER = t["button_hover"]
            COLOR_USER = t["user"]
            COLOR_ASSISTANT = t["assistant"]
            COLOR_SYSTEM = t["system"]
            BUBBLE_COLOR_USER = t["user_bg"]
            BUBBLE_COLOR_ASSISTANT = t["assistant_bg"]
            BUBBLE_COLOR_SYSTEM = t["system_bg"]
            BUBBLE_TEXT_COLOR_USER = "white"
            BUBBLE_TEXT_COLOR_ASSISTANT = t["assistant"]
            BUBBLE_TEXT_COLOR_SYSTEM = t["system"]
        if "font_chat" in s:
            FONT_CHAT = s["font_chat"]
        if "font_input" in s:
            FONT_INPUT = s["font_input"]
        if "font_list" in s:
            FONT_LIST = s["font_list"]
        if "opacity" in s:
            WINDOW_OPACITY = s["opacity"]
        if "ontop" in s:
            if s["ontop"]:
                self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
            else:
                self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)

    def SaveSettings(self):
        s = {
            "geometry": [self.x(), self.y(), self.width(), self.height()],
            "voice_enabled": self.voice.state["config"]["enabled"],
            "voice_name": self.voice.state["config"]["voice"],
            "voice_rate": self.voice.state["config"]["rate"],
            "stt_on_device": self.voice.state["config"]["stt_on_device"],
            "stt_language": self.voice.state["config"]["stt_language"],
            "stt_buffer_size": self.voice.state["config"]["stt_buffer_size"],
            "stt_silence_timeout": self.voice.state["config"]["stt_silence_timeout"],
            "stt_min_listen": self.voice.state["config"]["stt_min_listen"],
            "stt_max_timeout": self.voice.state["config"]["stt_max_timeout"],
            "stt_runloop_interval": self.voice.state["config"]["stt_runloop_interval"],
            "stt_silence_threshold": self.voice.state["config"].get("stt_silence_threshold", 0.01),
            "ontop": bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint),
            "theme": CURRENT_THEME,
            "font_chat": FONT_CHAT,
            "font_input": FONT_INPUT,
            "font_list": FONT_LIST,
            "opacity": WINDOW_OPACITY,
        }
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(s, f, indent=2)
        except Exception:
            pass

    def closeEvent(self, event):
        self.SaveSettings()
        if self.voice:
            self.voice.Run("stop_speaking")
        event.accept()

    def BuildUi(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        outer = QHBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        layout.addLayout(outer)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.right_visible = True
        self.saved_chat_width = 550

        chat_widget = QWidget()
        chat_layout = QVBoxLayout(chat_widget)
        chat_layout.setContentsMargins(8, 8, 8, 8)
        chat_layout.setSpacing(6)
        chat_layout.setStretch(0, 1)
        chat_layout.setStretch(1, 0)

        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setStyleSheet("border: none; background-color: " + COLOR_BG + ";")
        self.chat_container = QWidget()
        self.chat_container.setStyleSheet("background-color: " + COLOR_BG + ";")
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.chat_layout.setSpacing(10)
        self.chat_layout.setContentsMargins(4, 4, 4, 4)
        self.chat_scroll.setWidget(self.chat_container)
        chat_layout.addWidget(self.chat_scroll, stretch=1)

        input_row = QHBoxLayout()
        input_row.setContentsMargins(0, 8, 0, 0)
        input_row.setSpacing(8)
        self.input_field = GhostChatInput()
        self.input_field.setFont(QFont(FONT_FAMILY, FONT_INPUT))
        self.input_field.setStyleSheet(
            "QLineEdit { background-color: " + COLOR_INPUT + "; color: " + COLOR_TEXT +
            "; border: 2px solid " + COLOR_BORDER + "; border-radius: 8px; padding: 8px 12px; }"
            "QLineEdit:focus { border: 2px solid " + COLOR_BUTTON + "; }"
        )
        self.input_field.returnPressed.connect(self.OnSend)
        input_row.addWidget(self.input_field, stretch=1)

        self.send_btn = QPushButton("Send")
        self.send_btn.setFont(QFont(FONT_FAMILY, FONT_LIST, QFont.Weight.Bold))
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setStyleSheet(
            "QPushButton { background-color: " + COLOR_BUTTON + "; color: white; "
            "border: none; border-radius: 8px; padding: 8px 20px; font-weight: bold; }"
            "QPushButton:hover { background-color: " + COLOR_BUTTON_HOVER + "; }"
            "QPushButton:pressed { background-color: #0a5a8a; }"
            "QPushButton:disabled { background-color: #444; color: #777; }"
        )
        self.send_btn.clicked.connect(self.OnSend)
        input_row.addWidget(self.send_btn)

        chat_layout.addLayout(input_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setFont(QFont(FONT_FAMILY, FONT_BUTTON))
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setStyleSheet(
            "QPushButton { background-color: #333; color: " + COLOR_TEXT +
            "; border: 1px solid " + COLOR_BORDER + "; border-radius: 6px; padding: 6px 16px; }"
            "QPushButton:hover { background-color: #444; border-color: #555; }"
            "QPushButton:pressed { background-color: #2a2a2a; }"
        )
        self.clear_btn.clicked.connect(self.OnClear)
        btn_row.addWidget(self.clear_btn)

        self.voice_btn = QPushButton("\U0001F50A")
        self.voice_btn.setFixedSize(36, 36)
        self.voice_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.voice_btn.setToolTip("Toggle voice (Devin speaks responses)")
        self.voice_btn.setStyleSheet(self.VoiceButtonStyle(self.voice.state["config"]["enabled"]))
        self.voice_btn.clicked.connect(self.ToggleVoice)
        btn_row.addWidget(self.voice_btn)

        self.mic_btn = QPushButton("\U0001F3A4")
        self.mic_btn.setFixedSize(36, 36)
        self.mic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mic_btn.setToolTip("Press to speak (speech-to-text)")
        self.mic_btn.setStyleSheet(self.MicButtonStyle(False))
        self.mic_btn.clicked.connect(self.ToggleMic)
        btn_row.addWidget(self.mic_btn)

        self.cwd_label = QLabel("CWD: " + self.state["config"]["cwd"])
        self.cwd_label.setFont(QFont("Menlo", FONT_STATUS))
        self.cwd_label.setStyleSheet("color: #888;")
        btn_row.addWidget(self.cwd_label, stretch=1, alignment=Qt.AlignmentFlag.AlignRight)
        chat_layout.addLayout(btn_row)

        chat_widget.setMinimumWidth(300)
        self.splitter.addWidget(chat_widget)

        # ── Vertical toolbar (icon toggle buttons) — OUTSIDE splitter ──
        toolbar = QWidget()
        toolbar.setFixedWidth(TOOLBAR_WIDTH)
        toolbar.setStyleSheet(
            "QWidget { background-color: " + COLOR_PANEL + "; border-right: 1px solid " + COLOR_BORDER + "; }"
        )
        toolbar_layout = QVBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(2, 8, 2, 8)
        toolbar_layout.setSpacing(6)

        self.btn_kb_toggle = QPushButton("\U0001F50D")
        self.btn_kb_toggle.setFixedSize(TOOLBAR_BUTTON_SIZE, TOOLBAR_BUTTON_SIZE)
        self.btn_kb_toggle.setToolTip("Toggle Knowledge Base Panel")
        self.btn_kb_toggle.setStyleSheet(self.ToolbarButtonStyle(True))
        self.btn_kb_toggle.clicked.connect(lambda: self.ToggleRightPanel(0))
        toolbar_layout.addWidget(self.btn_kb_toggle)

        self.btn_sessions_toggle = QPushButton("\u2630")
        self.btn_sessions_toggle.setFixedSize(TOOLBAR_BUTTON_SIZE, TOOLBAR_BUTTON_SIZE)
        self.btn_sessions_toggle.setToolTip("Toggle Sessions Panel")
        self.btn_sessions_toggle.setStyleSheet(self.ToolbarButtonStyle(False))
        self.btn_sessions_toggle.clicked.connect(lambda: self.ToggleRightPanel(1))
        toolbar_layout.addWidget(self.btn_sessions_toggle)

        toolbar_layout.addStretch()
        outer.addWidget(toolbar)
        outer.addWidget(self.splitter)

        # ── Right panel container (collapsible) ──
        self.right_container = QWidget()
        right_container_layout = QVBoxLayout(self.right_container)
        right_container_layout.setContentsMargins(0, 0, 0, 0)
        right_container_layout.setSpacing(0)

        self.right_tabs = QTabWidget()
        self.right_tabs.setStyleSheet(
            "QTabWidget::pane { border: none; background: " + COLOR_PANEL + "; }"
            "QTabBar::tab { background: " + COLOR_INPUT + "; color: " + COLOR_TEXT +
            "; padding: 8px 16px; border: none; border-bottom: 2px solid transparent; "
            "font-size: " + str(FONT_BUTTON) + "px; margin-right: 2px; }"
            "QTabBar::tab:selected { background: " + COLOR_PANEL + "; color: " + COLOR_ASSISTANT +
            "; border-bottom: 2px solid " + COLOR_ASSISTANT + "; }"
            "QTabBar::tab:hover:!selected { background: #3c3c3c; }"
        )

        kb_widget = QWidget()
        kb_layout = QVBoxLayout(kb_widget)
        kb_layout.setContentsMargins(8, 8, 8, 8)
        kb_layout.setSpacing(6)

        kb_header = QLabel("Knowledge Base Search")
        kb_header.setFont(QFont("Menlo", FONT_HEADER, QFont.Weight.Bold))
        kb_header.setStyleSheet("color: " + COLOR_SYSTEM + "; padding: 8px;")
        kb_layout.addWidget(kb_header)

        search_row = QHBoxLayout()
        self.search_field = QLineEdit()
        self.search_field.setFont(QFont(FONT_FAMILY, FONT_LIST))
        self.search_field.setPlaceholderText("Search patterns, problems, solutions...")
        self.search_field.setStyleSheet(
            "QLineEdit { background-color: " + COLOR_INPUT + "; color: " + COLOR_TEXT +
            "; border: 2px solid " + COLOR_BORDER + "; border-radius: 8px; padding: 12px; }"
            "QLineEdit:focus { border: 2px solid " + COLOR_BUTTON + "; }"
        )
        self.search_field.returnPressed.connect(self.OnSearch)
        search_row.addWidget(self.search_field, stretch=1)

        self.search_btn = QPushButton("Search")
        self.search_btn.setFont(QFont(FONT_FAMILY, FONT_BUTTON))
        self.search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_btn.setStyleSheet(
            "QPushButton { background-color: " + COLOR_BUTTON + "; color: white; "
            "border: none; border-radius: 8px; padding: 12px 22px; }"
            "QPushButton:hover { background-color: " + COLOR_BUTTON_HOVER + "; }"
            "QPushButton:pressed { background-color: #0a5a8a; }"
        )
        self.search_btn.clicked.connect(self.OnSearch)
        search_row.addWidget(self.search_btn)
        kb_layout.addLayout(search_row)

        self.table_combo = QComboBox()
        self.table_combo.setFont(QFont("Menlo", FONT_BUTTON))
        self.table_combo.addItem("learned_rules (10,590)", "learned_rules")
        self.table_combo.addItem("know_problems (300)", "know_problems")
        self.table_combo.addItem("know_solutions (362)", "know_solutions")
        self.table_combo.addItem("vb_classes (1,394)", "vb_classes")
        self.table_combo.addItem("vb_methods (13,818)", "vb_methods")
        self.table_combo.setStyleSheet(
            "QComboBox { background-color: " + COLOR_INPUT + "; color: " + COLOR_TEXT +
            "; border: 1px solid " + COLOR_BORDER + "; border-radius: 4px; padding: 8px; }"
        )
        kb_layout.addWidget(self.table_combo)

        self.results_table = QTableWidget()
        self.results_table.setFont(QFont("Menlo", FONT_BUTTON))
        self.results_table.setStyleSheet(
            "QTableWidget { background-color: " + COLOR_BG + "; color: " + COLOR_TEXT +
            "; border: 1px solid " + COLOR_BORDER + "; gridline-color: " + COLOR_BORDER + "; }"
            "QHeaderView::section { background-color: " + COLOR_PANEL +
            "; color: " + COLOR_TEXT + "; border: 1px solid " + COLOR_BORDER + "; padding: 8px; }"
        )
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setStyleSheet(
            self.results_table.styleSheet() +
            " QTableWidget:item:alternate { background-color: #252526; }"
        )
        kb_layout.addWidget(self.results_table, stretch=1)

        self.result_count = QLabel("0 results")
        self.result_count.setFont(QFont("Menlo", FONT_STATUS))
        self.result_count.setStyleSheet("color: #888;")
        kb_layout.addWidget(self.result_count)

        self.right_tabs.addTab(kb_widget, "Knowledge Base")

        session_widget = QWidget()
        session_layout = QVBoxLayout(session_widget)
        session_layout.setContentsMargins(8, 8, 8, 8)
        session_layout.setSpacing(6)

        session_header_row = QHBoxLayout()
        session_header = QLabel("Devin Sessions")
        session_header.setFont(QFont("Menlo", FONT_HEADER, QFont.Weight.Bold))
        session_header.setStyleSheet("color: " + COLOR_SYSTEM + "; padding: 8px;")
        session_header_row.addWidget(session_header)
        session_header_row.addStretch()

        self.refresh_sessions_btn = QPushButton("Refresh")
        self.refresh_sessions_btn.setFont(QFont(FONT_FAMILY, FONT_BUTTON))
        self.refresh_sessions_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_sessions_btn.setStyleSheet(
            "QPushButton { background-color: " + COLOR_BUTTON + "; color: white; "
            "border: none; border-radius: 8px; padding: 10px 20px; }"
            "QPushButton:hover { background-color: " + COLOR_BUTTON_HOVER + "; }"
            "QPushButton:pressed { background-color: #0a5a8a; }"
        )
        self.refresh_sessions_btn.clicked.connect(self.OnLoadSessions)
        session_header_row.addWidget(self.refresh_sessions_btn)
        session_layout.addLayout(session_header_row)

        self.current_session_label = QLabel("No session selected (new session)")
        self.current_session_label.setFont(QFont("Menlo", FONT_BUTTON))
        self.current_session_label.setStyleSheet(
            "color: " + COLOR_ASSISTANT + "; padding: 8px; background: " + COLOR_INPUT +
            "; border: 1px solid " + COLOR_BORDER + "; border-radius: 4px;"
        )
        self.current_session_label.setWordWrap(True)
        session_layout.addWidget(self.current_session_label)

        self.session_list = QListWidget()
        self.session_list.setFont(QFont(FONT_FAMILY, FONT_LIST))
        self.session_list.setStyleSheet(
            "QListWidget { background-color: " + COLOR_BG + "; color: " + COLOR_TEXT +
            "; border: 1px solid " + COLOR_BORDER + "; border-radius: 8px; padding: 4px; }"
            "QListWidget::item { padding: 14px 12px; border-bottom: 1px solid " + COLOR_BORDER + "; }"
            "QListWidget::item:selected { background-color: " + COLOR_BUTTON + "; color: white; border-radius: 4px; }"
            "QListWidget::item:hover { background-color: " + COLOR_INPUT + "; border-radius: 4px; }"
        )
        self.session_list.itemDoubleClicked.connect(self.OnSessionSelected)
        self.session_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.session_list.customContextMenuRequested.connect(self.OnSessionContextMenu)
        session_layout.addWidget(self.session_list, stretch=1)

        new_session_btn = QPushButton("+ New Session")
        new_session_btn.setFont(QFont(FONT_FAMILY, FONT_BUTTON))
        new_session_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_session_btn.setStyleSheet(
            "QPushButton { background-color: #333; color: " + COLOR_TEXT +
            "; border: 1px solid " + COLOR_BORDER + "; border-radius: 8px; padding: 12px 20px; }"
            "QPushButton:hover { background-color: #444; border-color: #555; }"
            "QPushButton:pressed { background-color: #2a2a2a; }"
        )
        new_session_btn.clicked.connect(self.OnNewSession)
        session_layout.addWidget(new_session_btn)

        self.session_count = QLabel("0 sessions")
        self.session_count.setFont(QFont("Menlo", FONT_STATUS))
        self.session_count.setStyleSheet("color: #888;")
        session_layout.addWidget(self.session_count)

        self.right_tabs.addTab(session_widget, "Sessions")

        right_container_layout.addWidget(self.right_tabs)
        self.splitter.addWidget(self.right_container)
        self.splitter.setSizes([550, 450])

        self.status_bar = QStatusBar()
        self.status_bar.setFont(QFont(FONT_FAMILY, FONT_STATUS))
        self.status_bar.setStyleSheet(
            "QStatusBar { background-color: " + COLOR_PANEL + "; color: " + COLOR_TEXT + "; "
            "border-top: 1px solid " + COLOR_BORDER + "; }"
            "QStatusBar::item { border: none; }"
        )
        self.setStatusBar(self.status_bar)
        self.status_dot = QLabel("\u25CF")
        self.status_dot.setFont(QFont(FONT_FAMILY, FONT_STATUS))
        self.status_dot.setStyleSheet("color: " + COLOR_READY + "; padding: 0 6px;")
        self.status_bar.addPermanentWidget(self.status_dot)
        self.status_bar.showMessage("Ready")

        self.AppendSystem("Devin Chat GUI started. Type a message to chat with Devin CLI agent.")
        self.AppendSystem("Knowledge base search: 10,590 learned rules, 300 problems, 362 solutions.")
        self.AppendSystem("Sessions tab: double-click a session to resume it. Right-click for options.")
        QTimer.singleShot(500, self.OnLoadSessions)
        QTimer.singleShot(800, self.OnLoadTokens)

    def ToolbarButtonStyle(self, active):
        bg = COLOR_BUTTON if active else COLOR_INPUT
        hover = COLOR_BUTTON_HOVER if active else "#3c3c3c"
        return (
            "QPushButton { background-color: " + bg + "; color: white; "
            "border: none; border-radius: 10px; font-size: 22px; }"
            "QPushButton:hover { background-color: " + hover + "; }"
            "QPushButton:pressed { background-color: #0a5a8a; }"
        )

    def VoiceButtonStyle(self, active):
        bg = "#238636" if active else "#333"
        hover = "#2ea043" if active else "#444"
        return (
            "QPushButton { background-color: " + bg + "; color: white; "
            "border: 1px solid " + COLOR_BORDER + "; border-radius: 10px; font-size: 22px; }"
            "QPushButton:hover { background-color: " + hover + "; }"
        )

    def MicButtonStyle(self, listening):
        if listening:
            bg = "#f44747"
            hover = "#ff6b6b"
        else:
            bg = "#333"
            hover = "#444"
        return (
            "QPushButton { background-color: " + bg + "; color: white; "
            "border: 1px solid " + COLOR_BORDER + "; border-radius: 10px; font-size: 22px; }"
            "QPushButton:hover { background-color: " + hover + "; }"
        )

    def ToggleVoice(self):
        new_enabled = not self.voice.state["config"]["enabled"]
        self.voice.Run("set_config", {"enabled": new_enabled})
        self.voice_btn.setStyleSheet(self.VoiceButtonStyle(new_enabled))
        if new_enabled:
            self.AppendSystem("Voice ON — Devin will speak responses. Voice: " + self.voice.state["config"]["voice"])
            self.voice.Run("speak", {"text": "Voice activated. I am Devin."})
        else:
            self.voice.Run("stop_speaking")
            self.AppendSystem("Voice OFF")

    def SpeakLastResponse(self):
        last_text = ""
        for i in range(self.chat_layout.count() - 1, -1, -1):
            item = self.chat_layout.itemAt(i)
            if item and item.widget():
                bubble = item.widget()
                labels = bubble.findChildren(QLabel)
                for lbl in labels:
                    txt = lbl.text()
                    if txt and not txt.startswith("DEVIN") and not txt.startswith("YOU") and not txt.startswith("SYSTEM") and ":" not in txt[:8]:
                        last_text = txt
                        break
                if last_text:
                    break
        if last_text:
            self.voice.Run("speak", {"text": last_text})
            self.AppendSystem("Speaking last response...")
        else:
            self.AppendSystem("No response found to speak.")

    def ToggleMic(self):
        if self.listening:
            self.StopListening()
        else:
            self.StartListening()

    def StartListening(self):
        ok, data, err = self.voice.Run("is_speaking")
        if data and data.get("speaking"):
            self.AppendSystem("Waiting for AI to finish speaking...")
            self.listening = True
            self.mic_btn.setStyleSheet(self.MicButtonStyle(True))
            self.SetStatus("busy", "Waiting for AI to finish...")
            return
        self.listening = True
        self.mic_btn.setStyleSheet(self.MicButtonStyle(True))
        self.SetStatus("busy", "Listening... speak now")
        self.voice.Run("listen", {
            "on_partial": self.OnSttPartial,
            "on_finished": self.OnSttFinished,
            "on_error": self.OnSttError,
        })

    def StopListening(self):
        self.listening = False
        self.mic_btn.setStyleSheet(self.MicButtonStyle(False))
        self.voice.Run("stop_listening")
        self.SetStatus("ready", "Ready")

    def OnTtsFinished(self):
        """Called when TTS finishes. Resume STT if user was listening."""
        stt_worker = self.voice.state.get("stt_worker")
        if self.listening and not (stt_worker and stt_worker.isRunning()):
            self.SetStatus("busy", "Listening... speak now")
            self.voice.Run("listen", {
                "on_partial": self.OnSttPartial,
                "on_finished": self.OnSttFinished,
                "on_error": self.OnSttError,
            })

    def OnSttPartial(self, text):
        self.input_field.setText(text)

    def OnSttFinished(self, text):
        self.listening = False
        self.mic_btn.setStyleSheet(self.MicButtonStyle(False))
        if text.strip():
            self.input_field.setText(text.strip())
            self.input_field.setFocus()
        self.SetStatus("ready", "Ready")

    def OnSttError(self, err):
        self.listening = False
        self.mic_btn.setStyleSheet(self.MicButtonStyle(False))
        self.AppendError("Speech recognition error: " + err)
        self.SetStatus("error", "STT error")

    def ToggleRightPanel(self, tab_index):
        if not self.right_visible:
            self.right_container.setVisible(True)
            self.right_tabs.setCurrentIndex(tab_index)
            self.right_visible = True
            self.splitter.setSizes([self.saved_chat_width, 450])
        elif self.right_tabs.currentIndex() == tab_index:
            self.saved_chat_width = self.splitter.sizes()[0]
            self.right_container.setVisible(False)
            self.right_visible = False
        else:
            self.right_tabs.setCurrentIndex(tab_index)
        self.btn_kb_toggle.setStyleSheet(self.ToolbarButtonStyle(self.right_visible and self.right_tabs.currentIndex() == 0))
        self.btn_sessions_toggle.setStyleSheet(self.ToolbarButtonStyle(self.right_visible and self.right_tabs.currentIndex() == 1))

    def ApplyTheme(self):
        self.setStyleSheet(
            "QMainWindow { background-color: " + COLOR_PANEL + "; }"
            "QWidget { background-color: " + COLOR_PANEL + "; }"
            "QMenuBar { background-color: " + COLOR_PANEL + "; color: " + COLOR_TEXT +
            "; font-size: " + str(FONT_BUTTON) + "px; padding: 4px; }"
            "QMenuBar::item { padding: 6px 16px; border-radius: 4px; }"
            "QMenuBar::item:selected { background-color: " + COLOR_BUTTON + "; color: white; }"
            "QMenu { background-color: " + COLOR_PANEL + "; color: " + COLOR_TEXT +
            "; border: 1px solid " + COLOR_BORDER + "; font-size: " + str(FONT_BUTTON) + "px; padding: 6px; }"
            "QMenu::item { padding: 8px 24px; border-radius: 4px; }"
            "QMenu::item:selected { background-color: " + COLOR_BUTTON + "; color: white; }"
            "QMenu::separator { height: 1px; background: " + COLOR_BORDER + "; margin: 6px 8px; }"
            # Custom scrollbars — thin, modern
            "QScrollBar:vertical { background: " + COLOR_BG + "; width: 10px; border: none; border-radius: 5px; }"
            "QScrollBar::handle:vertical { background: " + COLOR_BORDER + "; min-height: 30px; border-radius: 5px; }"
            "QScrollBar::handle:vertical:hover { background: #555; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }"
            "QScrollBar:horizontal { background: " + COLOR_BG + "; height: 10px; border: none; border-radius: 5px; }"
            "QScrollBar::handle:horizontal { background: " + COLOR_BORDER + "; min-width: 30px; border-radius: 5px; }"
            "QScrollBar::handle:horizontal:hover { background: #555; }"
            "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }"
            "QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }"
            # Tooltip
            "QToolTip { background-color: " + COLOR_INPUT + "; color: " + COLOR_TEXT +
            "; border: 1px solid " + COLOR_BORDER + "; border-radius: 4px; padding: 6px; font-size: " +
            str(FONT_SMALL) + "px; }"
        )

    def SizeWindow(self):
        self.setMinimumSize(QSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT))
        s = self.settings
        if "geometry" in s and len(s["geometry"]) == 4:
            x, y, w, h = s["geometry"]
            self.setGeometry(x, y, w, h)
        else:
            screen = QApplication.primaryScreen().geometry()
            w = int(screen.width() * WINDOW_WIDTH_RATIO)
            h = int(screen.height() * WINDOW_HEIGHT_RATIO)
            x = screen.width() - w - 10
            y = (screen.height() - h) // 2
            self.setGeometry(x, y, w, h)

    def BuildMenu(self):
        menubar = self.menuBar()
        menubar.setFont(QFont("Menlo", FONT_BUTTON))

        file_menu = menubar.addMenu("File")
        act_new = QAction("New Session", self)
        act_new.setShortcut(QKeySequence("Ctrl+N"))
        act_new.triggered.connect(self.OnNewSession)
        file_menu.addAction(act_new)
        act_clear = QAction("Clear Chat", self)
        act_clear.setShortcut(QKeySequence("Ctrl+L"))
        act_clear.triggered.connect(self.OnClear)
        file_menu.addAction(act_clear)
        file_menu.addSeparator()
        act_quit = QAction("Quit", self)
        act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        edit_menu = menubar.addMenu("Edit")
        act_undo = QAction("Undo", self)
        act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        act_undo.triggered.connect(lambda: self.input_field.undo() if self.input_field.hasFocus() else None)
        edit_menu.addAction(act_undo)
        act_redo = QAction("Redo", self)
        act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        act_redo.triggered.connect(lambda: self.input_field.redo() if self.input_field.hasFocus() else None)
        edit_menu.addAction(act_redo)
        edit_menu.addSeparator()
        act_cut = QAction("Cut", self)
        act_cut.setShortcut(QKeySequence.StandardKey.Cut)
        act_cut.triggered.connect(lambda: self.input_field.cut() if self.input_field.hasFocus() else None)
        edit_menu.addAction(act_cut)
        act_copy = QAction("Copy", self)
        act_copy.setShortcut(QKeySequence.StandardKey.Copy)
        act_copy.triggered.connect(lambda: self.input_field.copy() if self.input_field.hasFocus() else None)
        edit_menu.addAction(act_copy)
        act_paste = QAction("Paste", self)
        act_paste.setShortcut(QKeySequence.StandardKey.Paste)
        act_paste.triggered.connect(lambda: self.input_field.paste() if self.input_field.hasFocus() else None)
        edit_menu.addAction(act_paste)
        edit_menu.addSeparator()
        act_selectall = QAction("Select All", self)
        act_selectall.setShortcut(QKeySequence.StandardKey.SelectAll)
        act_selectall.triggered.connect(lambda: self.input_field.selectAll() if self.input_field.hasFocus() else None)
        edit_menu.addAction(act_selectall)
        edit_menu.addSeparator()
        act_speak = QAction("Speak Last Response", self)
        act_speak.setShortcut(QKeySequence("Ctrl+Shift+S"))
        act_speak.triggered.connect(self.SpeakLastResponse)
        edit_menu.addAction(act_speak)

        view_menu = menubar.addMenu("View")
        act_kb = QAction("Toggle Knowledge Base", self)
        act_kb.setShortcut(QKeySequence("Ctrl+K"))
        act_kb.triggered.connect(lambda: self.ToggleRightPanel(0))
        view_menu.addAction(act_kb)
        act_sessions = QAction("Toggle Sessions", self)
        act_sessions.setShortcut(QKeySequence("Ctrl+S"))
        act_sessions.triggered.connect(lambda: self.ToggleRightPanel(1))
        view_menu.addAction(act_sessions)
        act_refresh = QAction("Refresh Sessions", self)
        act_refresh.setShortcut(QKeySequence("Ctrl+R"))
        act_refresh.triggered.connect(self.OnLoadSessions)
        view_menu.addAction(act_refresh)

        settings_menu = menubar.addMenu("Settings")
        act_font = QAction("Font Size...", self)
        act_font.triggered.connect(self.OpenSettings)
        settings_menu.addAction(act_font)
        act_ontop = QAction("Toggle Always-on-Top", self)
        act_ontop.triggered.connect(self.ToggleOnTop)
        settings_menu.addAction(act_ontop)

        help_menu = menubar.addMenu("Help")
        act_help = QAction("Show Commands", self)
        act_help.setShortcut(QKeySequence("Ctrl+H"))
        act_help.triggered.connect(lambda: self.HandleSlashCommand("/help"))
        help_menu.addAction(act_help)

    def ToggleOnTop(self):
        flags = self.windowFlags()
        if flags & Qt.WindowType.WindowStaysOnTopHint:
            self.setWindowFlags(flags & ~Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags | Qt.WindowType.WindowStaysOnTopHint)
        self.show()

    def OpenSettings(self):
        global CURRENT_THEME, WINDOW_OPACITY
        dlg = QDialog(self)
        dlg.setWindowTitle("Settings")
        dlg.setMinimumWidth(500)
        dlg.setStyleSheet(
            "QDialog { background-color: " + COLOR_PANEL + "; color: " + COLOR_TEXT + "; }"
            "QLabel { color: " + COLOR_TEXT + "; font-size: " + str(FONT_BUTTON) + "px; }"
            "QSpinBox { background-color: " + COLOR_INPUT + "; color: " + COLOR_TEXT +
            "; font-size: " + str(FONT_BUTTON) + "px; padding: 6px; border: 1px solid " + COLOR_BORDER + "; border-radius: 4px; }"
            "QComboBox { background-color: " + COLOR_INPUT + "; color: " + COLOR_TEXT +
            "; font-size: " + str(FONT_BUTTON) + "px; padding: 6px; border: 1px solid " + COLOR_BORDER + "; border-radius: 4px; }"
            "QPushButton { background-color: " + COLOR_BUTTON + "; color: white; "
            "border: none; border-radius: 6px; padding: 10px 20px; font-size: " + str(FONT_BUTTON) + "px; }"
            "QPushButton:hover { background-color: " + COLOR_BUTTON_HOVER + "; }"
            "QSlider { }"
            "QGroupBox { border: 1px solid " + COLOR_BORDER + "; border-radius: 8px; margin-top: 12px; padding-top: 16px; }"
            "QGroupBox::title { color: " + COLOR_ASSISTANT + "; subcontrol-origin: margin; left: 12px; padding: 0 6px; font-size: " + str(FONT_BUTTON) + "px; }"
            "QCheckBox { color: " + COLOR_TEXT + "; font-size: " + str(FONT_BUTTON) + "px; }"
        )
        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)

        # Theme group
        theme_group = QGroupBox("Theme")
        theme_layout = QVBoxLayout(theme_group)
        theme_combo = QComboBox()
        for name in THEMES.keys():
            theme_combo.addItem(name)
        theme_combo.setCurrentText(CURRENT_THEME)
        theme_layout.addWidget(QLabel("Color scheme:"))
        theme_layout.addWidget(theme_combo)
        layout.addWidget(theme_group)

        # Font group
        font_group = QGroupBox("Font Size")
        font_form = QFormLayout(font_group)
        chat_spin = QSpinBox()
        chat_spin.setRange(12, 40)
        chat_spin.setValue(FONT_CHAT)
        font_form.addRow("Chat text:", chat_spin)
        input_spin = QSpinBox()
        input_spin.setRange(12, 40)
        input_spin.setValue(FONT_INPUT)
        font_form.addRow("Input text:", input_spin)
        list_spin = QSpinBox()
        list_spin.setRange(12, 40)
        list_spin.setValue(FONT_LIST)
        font_form.addRow("Session list:", list_spin)
        layout.addWidget(font_group)

        # Window group
        win_group = QGroupBox("Window")
        win_layout = QVBoxLayout(win_group)
        ontop_check = QCheckBox("Always on top")
        ontop_check.setChecked(bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint))
        win_layout.addWidget(ontop_check)
        opacity_row = QHBoxLayout()
        opacity_lbl = QLabel("Opacity:")
        opacity_slider = QSlider(Qt.Orientation.Horizontal)
        opacity_slider.setRange(50, 100)
        opacity_slider.setValue(int(WINDOW_OPACITY * 100))
        opacity_val = QLabel(str(int(WINDOW_OPACITY * 100)) + "%")
        opacity_val.setStyleSheet("color: " + COLOR_ASSISTANT + ";")
        opacity_slider.valueChanged.connect(lambda v: opacity_val.setText(str(v) + "%"))
        opacity_row.addWidget(opacity_lbl)
        opacity_row.addWidget(opacity_slider, stretch=1)
        opacity_row.addWidget(opacity_val)
        win_layout.addLayout(opacity_row)
        layout.addWidget(win_group)

        # Voice / TTS group
        voice_group = QGroupBox("Voice / TTS")
        voice_layout = QVBoxLayout(voice_group)
        voice_check = QCheckBox("Devin speaks responses (TTS)")
        voice_check.setChecked(self.voice.state["config"]["enabled"])
        voice_layout.addWidget(voice_check)
        voice_form = QFormLayout()
        voice_combo = QComboBox()
        ok, voices, err = self.voice.Run("list_voices")
        for v in (voices or ["Samantha"]):
            voice_combo.addItem(v)
        voice_combo.setCurrentText(self.voice.state["config"]["voice"])
        voice_form.addRow("Voice:", voice_combo)
        rate_spin = QSpinBox()
        rate_spin.setRange(80, 400)
        rate_spin.setValue(self.voice.state["config"]["rate"])
        voice_form.addRow("Rate (wpm):", rate_spin)
        voice_layout.addLayout(voice_form)
        layout.addWidget(voice_group)

        # STT group
        stt_group = QGroupBox("Speech Recognition / STT")
        stt_layout = QVBoxLayout(stt_group)
        stt_form = QFormLayout()

        stt_on_device_check = QCheckBox("On-device recognition (privacy + speed)")
        stt_on_device_check.setChecked(self.voice.state["config"]["stt_on_device"])
        stt_form.addRow("Mode:", stt_on_device_check)

        stt_lang_combo = QComboBox()
        stt_lang_combo.addItem("en-US")
        stt_lang_combo.addItem("en-GB")
        stt_lang_combo.addItem("en-AU")
        stt_lang_combo.addItem("en-IE")
        stt_lang_combo.addItem("en-ZA")
        stt_lang_combo.addItem("en-IN")
        stt_lang_combo.addItem("en-SG")
        stt_lang_combo.setCurrentText(self.voice.state["config"]["stt_language"])
        stt_form.addRow("Language:", stt_lang_combo)

        stt_buffer_spin = QSpinBox()
        stt_buffer_spin.setRange(512, 16384)
        stt_buffer_spin.setSingleStep(512)
        stt_buffer_spin.setValue(self.voice.state["config"]["stt_buffer_size"])
        stt_buffer_spin.setSuffix(" samples")
        stt_form.addRow("Buffer size:", stt_buffer_spin)

        stt_silence_spin = QDoubleSpinBox()
        stt_silence_spin.setRange(0.5, 10.0)
        stt_silence_spin.setSingleStep(0.5)
        stt_silence_spin.setValue(self.voice.state["config"]["stt_silence_timeout"])
        stt_silence_spin.setSuffix(" s")
        stt_form.addRow("Silence timeout:", stt_silence_spin)

        stt_minlisten_spin = QDoubleSpinBox()
        stt_minlisten_spin.setRange(0.1, 10.0)
        stt_minlisten_spin.setSingleStep(0.1)
        stt_minlisten_spin.setValue(self.voice.state["config"]["stt_min_listen"])
        stt_minlisten_spin.setSuffix(" s")
        stt_form.addRow("Min listen time:", stt_minlisten_spin)

        stt_maxtimeout_spin = QSpinBox()
        stt_maxtimeout_spin.setRange(5, 300)
        stt_maxtimeout_spin.setSingleStep(5)
        stt_maxtimeout_spin.setValue(self.voice.state["config"]["stt_max_timeout"])
        stt_maxtimeout_spin.setSuffix(" s")
        stt_form.addRow("Max listen time:", stt_maxtimeout_spin)

        stt_runloop_spin = QDoubleSpinBox()
        stt_runloop_spin.setRange(0.01, 0.5)
        stt_runloop_spin.setSingleStep(0.01)
        stt_runloop_spin.setValue(self.voice.state["config"]["stt_runloop_interval"])
        stt_runloop_spin.setSuffix(" s")
        stt_form.addRow("Runloop interval:", stt_runloop_spin)

        stt_threshold_spin = QDoubleSpinBox()
        stt_threshold_spin.setRange(0.001, 0.1)
        stt_threshold_spin.setSingleStep(0.001)
        stt_threshold_spin.setDecimals(3)
        stt_threshold_spin.setValue(self.voice.state["config"].get("stt_silence_threshold", 0.01))
        stt_form.addRow("Silence threshold (RMS):", stt_threshold_spin)

        stt_layout.addLayout(stt_form)
        layout.addWidget(stt_group)

        # Buttons
        btn_row = QHBoxLayout()
        btn_apply = QPushButton("Apply")
        btn_close = QPushButton("Close")
        btn_row.addWidget(btn_apply)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

        def apply_settings():
            global FONT_CHAT, FONT_INPUT, FONT_LIST, CURRENT_THEME, WINDOW_OPACITY
            global COLOR_BG, COLOR_PANEL, COLOR_INPUT, COLOR_TEXT, COLOR_BORDER
            global COLOR_BUTTON, COLOR_BUTTON_HOVER, COLOR_USER, COLOR_ASSISTANT, COLOR_SYSTEM
            global BUBBLE_COLOR_USER, BUBBLE_COLOR_ASSISTANT, BUBBLE_COLOR_SYSTEM
            global BUBBLE_TEXT_COLOR_USER, BUBBLE_TEXT_COLOR_ASSISTANT, BUBBLE_TEXT_COLOR_SYSTEM

            CURRENT_THEME = theme_combo.currentText()
            t = THEMES[CURRENT_THEME]
            COLOR_BG = t["bg"]
            COLOR_PANEL = t["panel"]
            COLOR_INPUT = t["input"]
            COLOR_TEXT = t["text"]
            COLOR_BORDER = t["border"]
            COLOR_BUTTON = t["button"]
            COLOR_BUTTON_HOVER = t["button_hover"]
            COLOR_USER = t["user"]
            COLOR_ASSISTANT = t["assistant"]
            COLOR_SYSTEM = t["system"]
            BUBBLE_COLOR_USER = t["user_bg"]
            BUBBLE_COLOR_ASSISTANT = t["assistant_bg"]
            BUBBLE_COLOR_SYSTEM = t["system_bg"]
            BUBBLE_TEXT_COLOR_USER = "white"
            BUBBLE_TEXT_COLOR_ASSISTANT = t["assistant"]
            BUBBLE_TEXT_COLOR_SYSTEM = t["system"]

            FONT_CHAT = chat_spin.value()
            FONT_INPUT = input_spin.value()
            FONT_LIST = list_spin.value()
            WINDOW_OPACITY = opacity_slider.value() / 100.0

            self.voice.Run("set_config", {
                "enabled": voice_check.isChecked(),
                "voice": voice_combo.currentText(),
                "rate": rate_spin.value(),
                "stt_on_device": stt_on_device_check.isChecked(),
                "stt_language": stt_lang_combo.currentText(),
                "stt_buffer_size": stt_buffer_spin.value(),
                "stt_silence_timeout": stt_silence_spin.value(),
                "stt_min_listen": stt_minlisten_spin.value(),
                "stt_max_timeout": stt_maxtimeout_spin.value(),
                "stt_runloop_interval": stt_runloop_spin.value(),
                "stt_silence_threshold": stt_threshold_spin.value(),
            })
            self.voice_btn.setStyleSheet(self.VoiceButtonStyle(self.voice.state["config"]["enabled"]))

            self.ApplyTheme()
            self.ApplyFontSize()
            self.setWindowOpacity(WINDOW_OPACITY)
            if ontop_check.isChecked():
                self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
            else:
                self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)
            self.show()
            self.AppendSystem("Settings applied. Theme: " + CURRENT_THEME + " | Voice: " + self.voice.state["config"]["voice"] + " (" + str(self.voice.state["config"]["rate"]) + " wpm) | STT: " + stt_lang_combo.currentText() + " on-device=" + str(stt_on_device_check.isChecked()) + " buffer=" + str(stt_buffer_spin.value()))

        btn_apply.clicked.connect(apply_settings)
        btn_close.clicked.connect(dlg.accept)
        dlg.exec()

    def ApplyFontSize(self):
        self.input_field.setFont(QFont(FONT_FAMILY, FONT_INPUT))
        self.chat_scroll.setFont(QFont(FONT_FAMILY, FONT_CHAT))
        self.session_list.setFont(QFont(FONT_FAMILY, FONT_LIST))
        self.send_btn.setFont(QFont(FONT_FAMILY, FONT_LIST))
        self.clear_btn.setFont(QFont(FONT_FAMILY, FONT_BUTTON))
        self.status_bar.setFont(QFont(FONT_FAMILY, FONT_STATUS))
        self.menuBar().setFont(QFont(FONT_FAMILY, FONT_BUTTON))

    def AddMessage(self, role, text):
        now = datetime.now().strftime("%H:%M:%S")
        if role == "user":
            role_label = ROLE_LABEL_USER
            bg = BUBBLE_COLOR_USER
            fg = BUBBLE_TEXT_COLOR_USER
            align = Qt.AlignmentFlag.AlignRight
            border = ""
        elif role == "assistant":
            role_label = ROLE_LABEL_ASSISTANT
            bg = BUBBLE_COLOR_ASSISTANT
            fg = BUBBLE_TEXT_COLOR_ASSISTANT
            align = Qt.AlignmentFlag.AlignLeft
            border = ""
        elif role == "error":
            role_label = ROLE_LABEL_ERROR
            bg = BUBBLE_COLOR_ERROR
            fg = BUBBLE_TEXT_COLOR_ERROR
            align = Qt.AlignmentFlag.AlignLeft
            border = "border: 1px solid " + COLOR_ERROR + ";"
        else:
            role_label = ROLE_LABEL_SYSTEM
            bg = BUBBLE_COLOR_SYSTEM
            fg = BUBBLE_TEXT_COLOR_SYSTEM
            align = Qt.AlignmentFlag.AlignCenter
            border = "border: 1px solid " + BUBBLE_COLOR_SYSTEM_BORDER + ";"

        bubble = QFrame()
        bubble.setStyleSheet(
            "QFrame { background-color: " + bg + "; border-radius: " +
            str(BUBBLE_RADIUS) + "px; " + border + " }"
        )
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(BUBBLE_PADDING, BUBBLE_PADDING - 2, BUBBLE_PADDING, BUBBLE_PADDING - 4)
        bubble_layout.setSpacing(4)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)

        role_lbl = QLabel(role_label)
        role_lbl.setFont(QFont(FONT_FAMILY, BUBBLE_LABEL_FONT, QFont.Weight.Bold))
        role_lbl.setStyleSheet(
            "color: " + fg + "; background: transparent; font-weight: bold;"
        )
        time_lbl = QLabel(now)
        time_lbl.setFont(QFont(FONT_FAMILY, BUBBLE_TIME_FONT))
        time_lbl.setStyleSheet("color: #64748b; background: transparent;")

        if align == Qt.AlignmentFlag.AlignRight:
            header_row.addWidget(time_lbl)
            header_row.addWidget(role_lbl)
        else:
            header_row.addWidget(role_lbl)
            header_row.addWidget(time_lbl)
        header_row.addStretch()
        bubble_layout.addLayout(header_row)

        text_lbl = QLabel(text)
        text_lbl.setWordWrap(True)
        text_lbl.setTextFormat(Qt.TextFormat.RichText)
        text_lbl.setFont(QFont(FONT_FAMILY, FONT_CHAT))
        text_lbl.setStyleSheet("color: " + fg + "; background: transparent;")
        text_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text_lbl.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        def _CopyBubble(pos, lbl=text_lbl, txt=text):
            menu = QMenu(lbl)
            menu.setStyleSheet(
                "QMenu { background-color: " + COLOR_PANEL + "; color: " + COLOR_TEXT +
                "; border: 1px solid " + COLOR_BORDER + "; font-size: " + str(FONT_BUTTON) + "px; padding: 6px; }"
                "QMenu::item { padding: 8px 24px; border-radius: 4px; }"
                "QMenu::item:selected { background-color: " + COLOR_BUTTON + "; color: white; }"
            )
            act_copy = menu.addAction("Copy message  \tCtrl+C")
            act_speak = menu.addAction("Speak aloud  \U0001F50A")
            action = menu.exec(lbl.mapToGlobal(pos))
            if action == act_copy:
                QApplication.clipboard().setText(txt)
            elif action == act_speak:
                self.voice.Run("speak", {"text": txt})
        text_lbl.customContextMenuRequested.connect(_CopyBubble)
        bubble_layout.addWidget(text_lbl)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        if align == Qt.AlignmentFlag.AlignRight:
            row.addStretch()
            row.addWidget(bubble, stretch=8)
        elif align == Qt.AlignmentFlag.AlignLeft:
            row.addWidget(bubble, stretch=8)
            row.addStretch()
        else:
            row.addStretch()
            row.addWidget(bubble, stretch=6)
            row.addStretch()
        self.chat_layout.addLayout(row)
        QTimer.singleShot(50, lambda: self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()
        ))

    def AppendSystem(self, text):
        self.AddMessage("system", text)

    def AppendUser(self, text):
        self.AddMessage("user", text)

    def AppendAssistant(self, text):
        self.AddMessage("assistant", text)

    def AppendError(self, text):
        self.AddMessage("error", text)

    def SetStatus(self, state, msg):
        color_map = {"ready": COLOR_READY, "busy": COLOR_BUSY, "error": COLOR_ERROR}
        self.status_dot.setStyleSheet("color: " + color_map.get(state, COLOR_READY) + "; padding: 0 6px;")
        self.status_bar.showMessage(msg)

    def OnSend(self):
        text = self.input_field.text().strip()
        if not text:
            return
        if text.startswith("/"):
            handled = self.HandleSlashCommand(text)
            if handled:
                self.input_field.clear()
                return
        if self.state["devin_busy"]:
            self.AppendError("Devin is still processing previous message. Wait...")
            return
        self.AppendUser(text)
        self.input_field.clear()
        self.state["devin_busy"] = True
        self.send_btn.setEnabled(False)
        self.send_btn.setText("Working...")
        session_id = self.state["current_session_id"]
        if session_id:
            self.SetStatus("busy", "Sending to Devin CLI (resuming " + session_id + ")...")
        else:
            self.SetStatus("busy", "Sending to Devin CLI (new session)...")
        self.worker = DevinWorker(text, self.state["config"]["cwd"], session_id)
        self.worker.finished.connect(self.OnDevinResponse)
        self.worker.error.connect(self.OnDevinError)
        self.worker.start()

    def HandleSlashCommand(self, text):
        cmd = text.split(" ")[0].lower()
        arg = text[len(cmd):].strip()
        if cmd == "/help":
            cmds = "\n".join(SLASH_COMMANDS)
            self.AppendSystem("Available commands:\n" + cmds)
            return True
        if cmd == "/clear":
            self.ClearChat()
            self.AppendSystem("Chat cleared.")
            return True
        if cmd == "/sessions":
            self.right_tabs.setCurrentIndex(1)
            self.OnLoadSessions()
            self.AppendSystem("Switched to Sessions tab.")
            return True
        if cmd == "/search":
            self.right_tabs.setCurrentIndex(0)
            self.AppendSystem("Switched to Knowledge Base tab.")
            return True
        if cmd == "/refresh":
            self.OnLoadSessions()
            self.AppendSystem("Session list refreshed.")
            return True
        if cmd == "/new":
            self.OnNewSession()
            return True
        if cmd == "/status":
            sid = self.state["current_session_id"] or "none"
            title = self.state["current_session_title"] or "new session"
            cwd = self.state["config"]["cwd"]
            self.AppendSystem("Session: " + sid + " | Title: " + title + " | CWD: " + cwd)
            return True
        if cmd == "/cwd":
            self.AppendSystem("Working directory: " + self.state["config"]["cwd"])
            return True
        if cmd == "/tags":
            tokens = self.input_field.at_tokens
            self.AppendSystem("Available @ tokens (" + str(len(tokens)) + "):\n" + "\n".join(tokens[:30]))
            return True
        if cmd == "/rules":
            self.AppendSystem("VBStyle rules: read /Users/wws/contestsystem/.devin/rules/obey.md")
            return True
        if cmd in ("/db", "/code", "/problems", "/solutions", "/rules-db"):
            table_map = {
                "/db": "learned_rules",
                "/code": "vb_classes",
                "/problems": "know_problems",
                "/solutions": "know_solutions",
                "/rules-db": "learned_rules",
            }
            table = table_map.get(cmd, "learned_rules")
            if arg:
                self.search_field.setText(arg)
                idx = self.table_combo.findData(table)
                if idx >= 0:
                    self.table_combo.setCurrentIndex(idx)
                self.right_tabs.setCurrentIndex(0)
                self.OnSearch()
                self.AppendSystem("Searching " + table + " for '" + arg + "'...")
            else:
                self.AppendSystem("Usage: " + cmd + " <search term>")
            return True
        if cmd in ("/memunit", "/bcl", "/stamp", "/gate"):
            self.AppendSystem(cmd + " - forwarding to Devin CLI...")
            return False
        self.AppendError("Unknown command: " + cmd + ". Type /help for list.")
        return True

    def OnDevinResponse(self, text):
        self.AppendAssistant(text)
        self.state["devin_busy"] = False
        self.send_btn.setEnabled(True)
        self.send_btn.setText("Send")
        self.SetStatus("ready", "Ready")
        if self.voice.state["config"]["enabled"]:
            self.voice.Run("speak", {"text": text})
        self.input_field.setFocus()

    def OnDevinError(self, text):
        self.AppendError(text)
        self.state["devin_busy"] = False
        self.send_btn.setEnabled(True)
        self.send_btn.setText("Send")
        self.SetStatus("error", "Error - ready")

    def ClearChat(self):
        while self.chat_layout.count():
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self.ClearLayout(item.layout())

    def ClearLayout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self.ClearLayout(item.layout())

    def OnClear(self):
        self.ClearChat()
        self.AppendSystem("Chat cleared.")

    def OnSearch(self):
        query = self.search_field.text().strip()
        if not query:
            return
        table = self.table_combo.currentData()
        self.status_bar.showMessage("Searching " + table + " for '" + query + "'...")
        self.search_btn.setEnabled(False)
        self.search_worker = MysqlSearchWorker(query, table)
        self.search_worker.finished.connect(self.OnSearchResults)
        self.search_worker.error.connect(self.OnSearchError)
        self.search_worker.start()

    def OnSearchResults(self, rows, table):
        self.search_btn.setEnabled(True)
        if not rows:
            self.results_table.setRowCount(0)
            self.result_count.setText("0 results")
            self.status_bar.showMessage("No results")
            return
        cols = list(rows[0].keys())
        self.results_table.setColumnCount(len(cols))
        self.results_table.setHorizontalHeaderLabels([c.replace("_", " ").title() for c in cols])
        self.results_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, col in enumerate(cols):
                item = QTableWidgetItem(str(row[col] if row[col] is not None else ""))
                item.setFont(QFont("Menlo", FONT_BUTTON))
                self.results_table.setItem(i, j, item)
        self.results_table.resizeColumnsToContents()
        for j in range(self.results_table.columnCount()):
            if self.results_table.columnWidth(j) > 300:
                self.results_table.setColumnWidth(j, 300)
        self.result_count.setText(str(len(rows)) + " results")
        self.status_bar.showMessage("Found " + str(len(rows)) + " results in " + table)

    def OnSearchError(self, text):
        self.AppendError("MySQL search error: " + text)
        self.search_btn.setEnabled(True)
        self.status_bar.showMessage("Search error")

    def OnLoadSessions(self):
        self.status_bar.showMessage("Loading sessions...")
        self.refresh_sessions_btn.setEnabled(False)
        self.session_worker = SessionListWorker(self.state["config"]["cwd"])
        self.session_worker.finished.connect(self.OnSessionsLoaded)
        self.session_worker.error.connect(self.OnSessionsError)
        self.session_worker.start()

    def OnLoadTokens(self):
        self.token_worker = TokenLoaderWorker()
        self.token_worker.finished.connect(self.OnTokensLoaded)
        self.token_worker.error.connect(lambda e: self.AppendError("Token load error: " + e))
        self.token_worker.start()

    def LoadTokens(self):
        self.OnLoadTokens()

    def LoadAutocomplete(self):
        self.ac_worker = AutocompleteLoaderWorker(AUTOCOMPLETE_DB_PATH)
        self.ac_worker.finished.connect(self.OnAutocompleteLoaded)
        self.ac_worker.error.connect(self.OnAutocompleteError)
        self.ac_worker.start()

    def OnAutocompleteLoaded(self, word_freq, word_count, summary):
        self.input_field.SetAutocompleteModel(word_freq, AUTOCOMPLETE_DB_PATH)
        self.AppendSystem("Predictive text loaded (" + summary + "). Type a word and press Tab to accept ghost text.")

    def OnAutocompleteError(self, err):
        self.AppendError("Autocomplete load error: " + err)

    def OnTokensLoaded(self, tokens):
        self.input_field.SetTokens(tokens)
        self.AppendSystem("Loaded " + str(len(tokens)) + " @ tokens from MySQL. Type @ in chat to see them.")

    def OnSessionsLoaded(self, sessions):
        self.refresh_sessions_btn.setEnabled(True)
        self.session_list.clear()
        if not sessions:
            self.session_count.setText("0 sessions")
            self.status_bar.showMessage("No sessions found")
            return
        for s in sessions:
            sid = s.get("id", s.get("short_id", "?"))
            title = s.get("title", "untitled")
            ago = s.get("last_activity_ago", "?")
            display = title + "  [" + ago + "]"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, sid)
            item.setToolTip("Session ID: " + sid + "\nTitle: " + title + "\nLast activity: " + ago)
            self.session_list.addItem(item)
        self.session_count.setText(str(len(sessions)) + " sessions")
        self.status_bar.showMessage("Loaded " + str(len(sessions)) + " sessions")

    def OnSessionsError(self, text):
        self.refresh_sessions_btn.setEnabled(True)
        self.AppendError("Session list error: " + text)
        self.status_bar.showMessage("Session list error")

    def OnSessionSelected(self, item):
        sid = item.data(Qt.ItemDataRole.UserRole)
        title = item.text()
        self.state["current_session_id"] = sid
        self.state["current_session_title"] = title
        self.current_session_label.setText("RESUMING: " + sid + "\n" + title)
        self.AppendSystem("Resuming session: " + sid + " (" + title + ")")
        self.status_bar.showMessage("Resuming session " + sid)
        self.input_field.setFocus()

    def OnSessionContextMenu(self, pos):
        item = self.session_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: " + COLOR_PANEL + "; color: " + COLOR_TEXT +
            "; border: 1px solid " + COLOR_BORDER + "; }"
            "QMenu::item:selected { background-color: " + COLOR_BUTTON + "; }"
        )
        action_resume = menu.addAction("Resume Session")
        action_copy = menu.addAction("Copy Session ID")
        action_new = menu.addAction("New Session (deselect)")
        action = menu.exec(self.session_list.mapToGlobal(pos))
        if action == action_resume:
            self.OnSessionSelected(item)
        elif action == action_copy:
            sid = item.data(Qt.ItemDataRole.UserRole)
            QApplication.clipboard().setText(sid)
            self.status_bar.showMessage("Copied: " + sid)
        elif action == action_new:
            self.OnNewSession()

    def OnNewSession(self):
        self.state["current_session_id"] = None
        self.state["current_session_title"] = None
        self.current_session_label.setText("No session selected (new session)")
        self.session_list.clearSelection()
        self.AppendSystem("New session mode (no resume).")
        self.status_bar.showMessage("New session mode")
        self.input_field.setFocus()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Devin Chat GUI")
    gui = ChatGui()
    gui.show()
    sys.exit(app.exec())
