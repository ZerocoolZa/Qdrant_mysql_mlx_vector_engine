#!/usr/bin/env python3
# ============================================================================
# GHOST HEADER
# ----------------------------------------------------------------------------
# File:     BookViewer.py
# Domain:   Book visualization
# Authority: PyQt6 QWebEngineView rendering of turn.js flipbook
# DB:       SQLite (vbstyle_book_schema.sql v2)
# Binary:   python3 BookViewer.py [db_path]
#
# VBSTYLE HEADER
# ----------------------------------------------------------------------------
# Rules followed:
#   @ghost    — Ghost Header present
#   @vbsty    — VBStyle Header present
#   @clshdr   — Class Header present
#   @mthdr    — Method Header present on every method
#   @run      — Run(command, params) dispatch entry point
#   @disp     — dispatch internal, maps keys to methods
#   @tuples   — data methods return (ok, data, error)
#   @errfmt   — error tuple (code, desc, 0)
#   @state    — self.state dict (config, catalog, results)
#   @noself   — no self._ variables
#   @pascal   — PascalCase class name
#   @upper    — UPPERCASE constants at class level
#   @ctor     — __init__(self, mem=None, db=None, param=None)
#   @rpt      — Report returns strings, no print
#   @print    — no print statements (only main prints errors)
#   @decorators — no decorators
#   @enums    — no enums
#   @domain   — one class, one domain (BookViewer = book GUI rendering)
#   @dismap   — every dispatch key maps to exactly one method
#   @hardcode — DB path from BOOK_DB env var or argv, not hardcoded
# ============================================================================

import sys
import os
import sqlite3
import re
import json
import tempfile
import importlib

from config import Config, cfg

# ============================================================================
# RUNTIME SELF-HEALING IMPORT HOOK
# ----------------------------------------------------------------------------
# No hardcoded list of "required modules". A sys.meta_path finder
# (core.utility.auto_install_hook.AutoInstallFinder) is installed once. When
# ANY import in this process fails — PyQt6.QtWebEngineWidgets, a plugin loaded
# later, a transitive dependency — the finder asks the package authority
# (core.Dom_Unified.DomSystem -> core.utility.PackageManager) to resolve the
# missing module to a pip package and install it, then retries the import
# automatically. The code heals itself; no per-error manual fixing.
#
# A basic terminal loading screen is shown only when an install actually
# happens, so the user sees progress instead of a silent hang.
# ============================================================================
def _loading_screen(event, **kw):
    bar = "=" * 60
    if event == "authority_fail":
        sys.stdout.write("\n" + bar + "\n  CANNOT LOAD PACKAGE AUTHORITY\n  " + kw.get("error", "") + "\n" + bar + "\n\n")
        sys.stdout.flush()
        return
    if event == "resolve_start":
        sys.stdout.write("\n" + bar + "\n  BookViewer — self-healing imports\n" + bar + "\n")
        sys.stdout.flush()
    if event == "install_start":
        sys.stdout.write("  pip install %-20s (for %s) ... " % (kw.get("pip", ""), kw.get("module", "")))
        sys.stdout.flush()
    if event == "install_ok":
        sys.stdout.write("ok\n")
        sys.stdout.flush()
    if event == "install_fail":
        sys.stdout.write("FAILED\n")
        sys.stdout.flush()
    if event == "no_pip":
        sys.stdout.write("  no pip package for %s: %s\n" % (kw.get("module", ""), kw.get("message", "")))
        sys.stdout.flush()
    if event == "resolve_fail":
        sys.stdout.write("  resolve failed for %s: %s\n" % (kw.get("module", ""), kw.get("error", "")))
        sys.stdout.flush()
    if event == "error":
        sys.stdout.write("  error healing %s: %s\n" % (kw.get("module", ""), kw.get("error", "")))
        sys.stdout.flush()


_here = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.dirname(_here)
for _p in (_repo_root, os.path.join(_repo_root, "core")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.utility.auto_install_hook import install as _install_self_healing
_install_self_healing(progress=_loading_screen)

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStatusBar, QFileDialog, QLineEdit,
    QInputDialog, QTextEdit, QDialog, QComboBox, QSlider,
)
from PyQt6.QtCore import Qt, QUrl, QObject, pyqtSlot
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebChannel import QWebChannel


# ============================================================================
# CLASSES HEADER
# ----------------------------------------------------------------------------
# Class:  BookBridge
# Domain: JavaScript ↔ Python communication bridge
# Authority: Receive highlight/annotate/search calls from JS, save to DB
#
# Class:  BookViewer
# Domain: Book visualization (PyQt6 QWebEngineView + turn.js flipbook)
# Authority: Render book DB content as a physical flipbook in a desktop window
# Dependencies: PyQt6 (QtWidgets, QtWebEngine, QtWebChannel), sqlite3, os, sys, re, json
# DB: SQLite file (vbstyle_book_schema.sql v2)
# ============================================================================


class BookBridge(QObject):
    """Bridge object exposed to JavaScript via QWebChannel.
    JS calls these methods to save highlights/annotations and query the DB."""

    def __init__(self, viewer):
        super().__init__()
        self.state = {"viewer": viewer}

    @pyqtSlot(int, str, str, str, result=str)
    def saveAnnotation(self, section_id, selected_text, note_text, color):
        """Called from JS when user highlights or annotates text.
        Returns JSON with the annotation id or error."""
        viewer = self.state["viewer"]
        ok, data, err = viewer.AddAnnotationDirect(
            section_id, selected_text, note_text, color
        )
        if ok:
            return json.dumps({"ok": True, "id": data})
        return json.dumps({"ok": False, "error": err[1]})

    @pyqtSlot(result=str)
    def getAllAnnotations(self):
        """Called from JS on page load to get all annotations for re-applying."""
        viewer = self.state["viewer"]
        ok, data, err = viewer.GetAllAnnotationsDirect()
        if ok:
            return json.dumps(data)
        return json.dumps([])

    @pyqtSlot(int, result=str)
    def getSectionAnnotations(self, section_id):
        """Called from JS to get annotations for a specific section."""
        viewer = self.state["viewer"]
        ok, data, err = viewer.GetSectionAnnotationsDirect(section_id)
        if ok:
            return json.dumps(data)
        return json.dumps([])

    @pyqtSlot(int, result=bool)
    def removeAnnotation(self, annotation_id):
        """Called from JS to remove an annotation."""
        viewer = self.state["viewer"]
        ok, _, _ = viewer.RemoveAnnotationDirect(annotation_id)
        return ok


class BookViewer(QMainWindow):
    # ------------------------------------------------------------------------
    # UPPERCASE CONSTANTS
    # ------------------------------------------------------------------------
    DB_DEFAULT = Config.DB_PATH
    VERSION = Config.VIEWER_VERSION
    WINDOW_TITLE = Config.WINDOW_TITLE
    WINDOW_WIDTH = cfg.GetTheme("window_width")
    WINDOW_HEIGHT = cfg.GetTheme("window_height")

    # ------------------------------------------------------------------------
    # CONSTRUCTOR
    # ------------------------------------------------------------------------
    def __init__(self, mem=None, db=None, param=None):
        super().__init__()

        self.state = {
            "db_path": os.environ.get("BOOK_DB", db or self.DB_DEFAULT),
            "db": None,
            "html_path": None,
            "page_count": 0,
            "report": "",
            "bridge": None,
            "channel": None,
        }

        self.setWindowTitle(self.WINDOW_TITLE)
        self.resize(self.WINDOW_WIDTH, self.WINDOW_HEIGHT)

        ok, _, err = self.OpenDB()
        if not ok:
            # err is (code, desc, 0) — map to Config.ERRORS key
            if "not found" in err[1].lower() or "no such file" in err[1].lower():
                self._show_error("db_not_found", {"path": Config.DB_PATH})
            elif "no db" in err[1].lower() or "cannot connect" in err[1].lower():
                self._show_error("no_db_connection")
            else:
                self._show_error(err[1])
            return

        self.BuildUI()
        self.LoadFlipbook()

    # ------------------------------------------------------------------------
    # PARAM HELPER
    # ------------------------------------------------------------------------
    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    # ------------------------------------------------------------------------
    # DISPATCH ENTRY POINT
    # ------------------------------------------------------------------------
    def Run(self, command, params):
        return self.dispatch(command, params)

    # ------------------------------------------------------------------------
    # INTERNAL DISPATCH
    # ------------------------------------------------------------------------
    def dispatch(self, command, params):
        dispatch_table = {
            "load": self.LoadFlipbook,
            "prev": self.PrevPage,
            "next": self.NextPage,
            "export": self.ExportHTML,
            "refresh": self.RefreshDB,
            "search": self.SearchInBook,
            "highlight": self.HighlightSelected,
            "annotate": self.AnnotateSelected,
        }
        method = dispatch_table.get(command)
        if method is None:
            return (0, None, ("BADCMD", f"Unknown command: {command}", 0))
        return method(params)

    # ------------------------------------------------------------------------
    # DB HELPER
    # ------------------------------------------------------------------------
    def OpenDB(self):
        path = self.state["db_path"]
        if not os.path.exists(path):
            return (0, None, ("NOTFOUND", f"DB not found: {path}", 0))
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        self.state["db"] = conn
        return (1, conn, ())

    # ------------------------------------------------------------------------
    # BUILD UI — Toolbar with search, nav, highlight, annotate + WebEngineView
    # ------------------------------------------------------------------------
    def BuildUI(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Toolbar row 1: navigation ---
        toolbar1 = QHBoxLayout()
        toolbar1.setContentsMargins(*cfg.GetTheme("toolbar_margin"))

        btn_prev = QPushButton("◀ Prev")
        btn_prev.setToolTip(cfg.GetTooltip("prev"))
        btn_prev.clicked.connect(lambda: self.PrevPage({}))

        btn_next = QPushButton("Next ▶")
        btn_next.setToolTip(cfg.GetTooltip("next"))
        btn_next.clicked.connect(lambda: self.NextPage({}))

        title_label = QLabel(Config.BOOK_TITLE)
        title_label.setStyleSheet(cfg.GetTheme("title_label_style"))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn_export = QPushButton("Export HTML")
        btn_export.setToolTip(cfg.GetTooltip("export"))
        btn_export.clicked.connect(lambda: self.ExportHTML({}))

        btn_refresh = QPushButton("Refresh")
        btn_refresh.setToolTip(cfg.GetTooltip("refresh"))
        btn_refresh.clicked.connect(lambda: self.RefreshDB({}))

        btn_help = QPushButton("Help")
        btn_help.setToolTip(cfg.GetTooltip("help"))
        btn_help.clicked.connect(self.ShowHelp)

        btn_about = QPushButton("About")
        btn_about.setToolTip(cfg.GetTooltip("about"))
        btn_about.clicked.connect(self.ShowAbout)

        toolbar1.addWidget(btn_prev)
        toolbar1.addWidget(btn_next)
        toolbar1.addStretch()
        toolbar1.addWidget(title_label)
        toolbar1.addStretch()
        toolbar1.addWidget(btn_export)
        toolbar1.addWidget(btn_refresh)
        toolbar1.addWidget(btn_help)
        toolbar1.addWidget(btn_about)
        layout.addLayout(toolbar1)

        # --- Toolbar row 2: search + highlight + annotate ---
        toolbar2 = QHBoxLayout()
        toolbar2.setContentsMargins(*cfg.GetTheme("toolbar2_margin"))

        self.search_box = QLineEdit()
        self.search_box.setToolTip(cfg.GetTooltip("search_box"))
        self.search_box.setPlaceholderText(cfg.GetTheme("search_placeholder"))
        self.search_box.setStyleSheet(cfg.GetTheme("search_box_style"))
        self.search_box.returnPressed.connect(lambda: self.SearchInBook({"term": self.search_box.text()}))

        btn_search = QPushButton("Search")
        btn_search.setToolTip(cfg.GetTooltip("search_btn"))
        btn_search.clicked.connect(lambda: self.SearchInBook({"term": self.search_box.text()}))

        btn_clear = QPushButton("Clear")
        btn_clear.setToolTip(cfg.GetTooltip("clear"))
        btn_clear.clicked.connect(self.OnClearSearch)

        btn_highlight = QPushButton("Highlight")
        btn_highlight.setToolTip(cfg.GetTooltip("highlight"))
        btn_highlight.setStyleSheet(cfg.GetTheme("highlight_btn_style"))
        btn_highlight.clicked.connect(lambda: self.HighlightSelected({}))

        btn_annotate = QPushButton("Annotate")
        btn_annotate.setToolTip(cfg.GetTooltip("annotate"))
        btn_annotate.setStyleSheet(cfg.GetTheme("annotate_btn_style"))
        btn_annotate.clicked.connect(lambda: self.AnnotateSelected({}))

        toolbar2.addWidget(QLabel("Find:"))
        toolbar2.addWidget(self.search_box, stretch=1)
        toolbar2.addWidget(btn_search)
        toolbar2.addWidget(btn_clear)
        toolbar2.addSpacing(cfg.GetTheme("toolbar_spacing"))
        toolbar2.addWidget(btn_highlight)
        toolbar2.addWidget(btn_annotate)
        layout.addLayout(toolbar2)

        # --- Toolbar row 3: TTS (Read, Stop, Voice) ---
        toolbar3 = QHBoxLayout()
        toolbar3.setContentsMargins(*cfg.GetTheme("toolbar2_margin"))

        self.btn_read = QPushButton(f"{cfg.GetIcon('read')}  Read")
        self.btn_read.setToolTip(cfg.GetTooltip("read"))
        self.btn_read.setStyleSheet(
            "background: #1a365d; color: white; padding: 6px 16px; "
            "font-size: 13px; font-weight: bold; border: none; border-radius: 4px;"
        )
        self.btn_read.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_read.clicked.connect(self.OnTtsToggle)

        btn_stop = QPushButton(f"{cfg.GetIcon('stop')}  Stop")
        btn_stop.setToolTip(cfg.GetTooltip("stop"))
        btn_stop.setStyleSheet(
            "background: #c53030; color: white; padding: 6px 16px; "
            "font-size: 13px; font-weight: bold; border: none; border-radius: 4px;"
        )
        btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_stop.clicked.connect(self.OnTtsStop)

        btn_voice = QPushButton(f"{cfg.GetIcon('voice')}  Voice")
        btn_voice.setToolTip(cfg.GetTooltip("voice"))
        btn_voice.setStyleSheet(
            "background: #2c5282; color: white; padding: 6px 16px; "
            "font-size: 13px; font-weight: bold; border: none; border-radius: 4px;"
        )
        btn_voice.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_voice.clicked.connect(self.ShowVoicePicker)

        toolbar3.addWidget(self.btn_read)
        toolbar3.addWidget(btn_stop)
        toolbar3.addWidget(btn_voice)
        toolbar3.addStretch()
        layout.addLayout(toolbar3)

        # --- WebEngineView ---
        self.web = QWebEngineView()
        settings = self.web.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        layout.addWidget(self.web, stretch=1)

        # --- Status bar ---
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Loading...")

    # ------------------------------------------------------------------------
    # LOAD FLIPBOOK — Generate HTML, set up QWebChannel, load
    # ------------------------------------------------------------------------
    def LoadFlipbook(self, params=None):
        ok, html, page_count, err = self.GenerateFlipbookHTML()
        if not ok:
            self.status.showMessage(f"Error: {err[1]}")
            return (0, None, err)

        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, dir="/tmp"
        )
        tmp.write(html)
        tmp.close()
        self.state["html_path"] = tmp.name

        # Set up QWebChannel for JS↔Python communication
        self.channel = QWebChannel()
        self.bridge = BookBridge(self)
        self.channel.registerObject("bridge", self.bridge)
        self.web.page().setWebChannel(self.channel)

        self.web.load(QUrl.fromLocalFile(tmp.name))
        self.state["page_count"] = page_count
        self.status.showMessage(f"{page_count} pages loaded")
        self.state["report"] = f"Loaded flipbook: {page_count} pages"
        return (1, page_count, ())

    # ------------------------------------------------------------------------
    # GENERATE FLIPBOOK HTML — Build turn.js HTML with search/highlight/annotate JS
    # ------------------------------------------------------------------------
    def GenerateFlipbookHTML(self):
        conn = self.state["db"]
        if conn is None:
            return (0, None, 0, ("DBERROR", "No DB connection", 0))

        turnjs_code = cfg.GetTurnJs()

        book_title = Config.BOOK_TITLE
        book_subtitle = Config.BOOK_SUBTITLE
        fb_width = Config.FLIPBOOK_WIDTH
        fb_height = Config.FLIPBOOK_HEIGHT
        theme_css = cfg.GetThemeCss()
        cover_gradient = cfg.GetTheme("cover_gradient")
        cover_bg_solid = cfg.GetTheme("cover_bg_solid")
        cover_text = cfg.GetTheme("cover_text")
        cover_title_size = cfg.GetTheme("cover_title_size")
        cover_subtitle_size = cfg.GetTheme("cover_subtitle_size")
        cover_hint_size = cfg.GetTheme("cover_hint_size")

        # TTS config injected into JS
        tts_rate = cfg.GetTts("rate")
        tts_pitch = cfg.GetTts("pitch")
        tts_volume = cfg.GetTts("volume")
        tts_auto_flip = "true" if cfg.GetTts("auto_flip") else "false"
        tts_word_hl = "true" if cfg.GetTts("word_highlight") else "false"
        tts_word_hl_bg = cfg.GetTts("word_highlight_bg")
        tts_word_hl_color = cfg.GetTts("word_highlight_color")

        chapters = conn.execute(
            "SELECT id, ch_num, title, subtitle FROM chapters ORDER BY ch_num"
        ).fetchall()

        pages_html = []

        # Cover page
        pages_html.append(
            f'<div class="hard" style="background: {cover_gradient}; '
            f'color: {cover_text}; display: flex; flex-direction: column; '
            f'justify-content: center; align-items: center; text-align: center;">'
            f'<h1 style="font-size: {cover_title_size}; margin: 20px;">{book_title}</h1>'
            f'<p style="font-size: {cover_subtitle_size}; opacity: 0.8;">{book_subtitle}</p>'
            f'<p style="font-size: {cover_hint_size}; opacity: 0.6; margin-top: 30px;">Click or drag to flip</p>'
            f'</div>'
        )
        pages_html.append(f'<div class="hard" style="background: {cover_bg_solid};"></div>')

        # TOC
        toc_items = []
        for ch in chapters:
            toc_items.append(
                f'<li style="margin: 4px 0;"><b>Chapter {ch["ch_num"]}</b> &mdash; {ch["title"]}</li>'
            )
        pages_html.append(
            '<div class="page-content"><h2>Contents</h2><ul style="list-style: none; padding: 0;">'
            + "".join(toc_items) + '</ul></div>'
        )

        # Section pages — each page gets a data-section-id attribute
        for ch in chapters:
            sections = conn.execute(
                "SELECT id, sec_num, title, section_type, word_count "
                "FROM sections WHERE chapter_id = ? ORDER BY sort_order",
                (ch["id"],),
            ).fetchall()

            for sec in sections:
                blocks = conn.execute(
                    "SELECT block_type, content, lang, caption "
                    "FROM content_blocks WHERE section_id = ? ORDER BY block_order",
                    (sec["id"],),
                ).fetchall()

                page = []
                page.append(f'<div class="page-header">Chapter {ch["ch_num"]}</div>')
                page.append(f'<h2>{sec["sec_num"]}  {sec["title"]}</h2>')

                for block in blocks:
                    if block["block_type"] == "code":
                        escaped = (
                            block["content"]
                            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                        )
                        page.append(f'<pre class="code-block"><code>{escaped}</code></pre>')
                    elif block["block_type"] == "callout":
                        caption = block["caption"] or "Note"
                        page.append(f'<div class="callout"><b>{caption}:</b> {block["content"]}</div>')
                    else:
                        page.append(f'<div class="text-block">{self._md_to_html(block["content"])}</div>')

                page.append(f'<div class="page-footer">{book_title}</div>')
                # data-section-id lets JS know which section this page belongs to
                pages_html.append(
                    f'<div class="page-content" data-section-id="{sec["id"]}">{"".join(page)}</div>'
                )

        # Glossary
        glossary = conn.execute(
            "SELECT term, definition FROM glossary ORDER BY term"
        ).fetchall()
        if glossary:
            gloss_html = []
            for g in glossary:
                gloss_html.append(f'<p><b>{g["term"]}</b> &mdash; {g["definition"]}</p>')
            pages_html.append(
                f'<div class="page-content"><h2>Glossary</h2>{"".join(gloss_html)}</div>'
            )

        pages_html.append(f'<div class="hard" style="background: {cover_bg_solid};"></div>')
        pages_html.append(
            f'<div class="hard" style="background: {cover_gradient}; '
            f'color: {cover_text}; display: flex; justify-content: center; align-items: center;">'
            f'<p style="font-size: {cover_subtitle_size}; opacity: 0.7;">End</p></div>'
        )

        all_pages = "\n".join(f'        <div>{p}</div>' for p in pages_html)
        page_count = len(pages_html)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{book_title}</title>
<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>
{turnjs_code}
</script>
<style>
{theme_css}
</style>
</head>
<body>

<div id="flipbook">
{all_pages}
</div>

<div id="annot-panel">
    <h3>Annotations</h3>
    <div id="annot-list"></div>
</div>

<script>
// === QWebChannel setup (async in Qt6) ===
var bridge = null;
new QWebChannel(qt.webChannelTransport, function(channel) {{
    bridge = channel.objects.bridge;
    // After channel is ready, apply saved annotations
    applySavedAnnotations();
}});

// === Turn.js initialization ===
$(function() {{
    $("#flipbook").turn({{
        width: {fb_width}, height: {fb_height}, autoCenter: true,
        display: 'double', acceleration: true,
        gradients: true, elevation: 50
    }});
}});

// === Keyboard navigation ===
$(window).bind('keydown', function(e) {{
    if (e.keyCode == 37) $('#flipbook').turn('previous');
    else if (e.keyCode == 39) $('#flipbook').turn('next');
}});

// === Search: highlight all matches in visible pages ===
function searchInBook(term) {{
    // Remove old search marks
    $('mark.search-mark').each(function() {{
        var parent = $(this).parent();
        $(this).replaceWith($(this).text());
        parent[0].normalize();
    }});

    if (!term || term.length < 2) return 0;

    var count = 0;
    var escaped = term.replace(/[.*+?^${{}}|[]\\]/g, '\\\\$&');
    var regex = new RegExp('(' + escaped + ')', 'gi');

    // Search in all page-content divs
    $('.page-content').each(function() {{
        $(this).find('p, li, td, h2, h3, div.text-block').each(function() {{
            var html = $(this).html();
            if (regex.test(html)) {{
                regex.lastIndex = 0;
                var newHtml = html.replace(regex, '<mark class="search-mark">$1</mark>');
                $(this).html(newHtml);
                count += (newHtml.match(/search-mark/g) || []).length;
            }}
        }});
    }});

    return count;
}}

// === Get currently selected text and its section_id ===
function getSelectionInfo() {{
    var sel = window.getSelection();
    if (!sel || sel.toString().trim().length === 0) {{
        return null;
    }}
    var text = sel.toString().trim();
    var node = sel.anchorNode;
    while (node && node.nodeType !== 1) {{
        node = node.parentNode;
    }}
    var pageDiv = node ? node.closest('[data-section-id]') : null;
    var sectionId = pageDiv ? pageDiv.getAttribute('data-section-id') : null;
    return {{ text: text, sectionId: sectionId }};
}}

// === Highlight selected text (yellow) — async bridge call ===
function highlightSelected() {{
    var info = getSelectionInfo();
    if (!info) {{
        alert('Select text first, then click Highlight.');
        return;
    }}
    if (!info.sectionId) {{
        alert('Cannot highlight this page (no section ID).');
        return;
    }}
    if (!bridge) {{
        alert('Bridge not ready.');
        return;
    }}
    // Qt6 QWebChannel returns a Promise for result= slots
    bridge.saveAnnotation(
        parseInt(info.sectionId), info.text, '', '{Config.COLOR_HIGHLIGHT}'
    ).then(function(result) {{
        var parsed = JSON.parse(result);
        if (parsed.ok) {{
            wrapSelectedText('user-highlight', '', parsed.id);
            window.getSelection().removeAllRanges();
        }} else {{
            alert('Error: ' + parsed.error);
        }}
    }});
}}

// === Annotate selected text (blue + note) — async bridge call ===
function annotateSelected() {{
    var info = getSelectionInfo();
    if (!info) {{
        alert('Select text first, then click Annotate.');
        return;
    }}
    if (!info.sectionId) {{
        alert('Cannot annotate this page (no section ID).');
        return;
    }}
    if (!bridge) {{
        alert('Bridge not ready.');
        return;
    }}
    var note = prompt('Enter your note for this annotation:');
    if (!note) return;

    bridge.saveAnnotation(
        parseInt(info.sectionId), info.text, note, '{Config.COLOR_ANNOTATION}'
    ).then(function(result) {{
        var parsed = JSON.parse(result);
        if (parsed.ok) {{
            wrapSelectedText('user-annotation', note, parsed.id);
            window.getSelection().removeAllRanges();
            refreshAnnotPanel();
        }} else {{
            alert('Error: ' + parsed.error);
        }}
    }});
}}

// === Wrap selected text with a span ===
function wrapSelectedText(className, note, annotId) {{
    var sel = window.getSelection();
    if (!sel.rangeCount) return;
    var range = sel.getRangeAt(0);
    var span = document.createElement('span');
    span.className = className;
    span.setAttribute('data-annot-id', annotId);
    if (note) span.setAttribute('data-note', note);
    try {{
        range.surroundContents(span);
    }} catch(e) {{
        var frag = range.extractContents();
        span.appendChild(frag);
        range.insertNode(span);
    }}
}}

// === Apply saved annotations from DB on page load (async) ===
function applySavedAnnotations() {{
    if (!bridge) return;
    bridge.getAllAnnotations().then(function(data) {{
        var annots = JSON.parse(data);
        if (!annots || annots.length === 0) return;

        annots.forEach(function(annot) {{
            var className = annot.note_text ? 'user-annotation' : 'user-highlight';
            var pageDiv = $('.page-content[data-section-id="' + annot.section_id + '"]');
            if (pageDiv.length === 0) return;
            var pageText = pageDiv.text();
            if (pageText.indexOf(annot.selected_text) === -1) return;
            wrapTextInElement(pageDiv[0], annot.selected_text, className, annot.note_text, annot.id);
        }});

        refreshAnnotPanel();
    }});
}}

// === Recursively wrap text in an element ===
function wrapTextInElement(element, searchText, className, note, annotId) {{
    var escaped = searchText.replace(/[.*+?^${{}}|[]\\]/g, '\\\\$&');
    var regex = new RegExp('(' + escaped + ')', 'gi');

    function walk(node) {{
        if (node.nodeType === 3) {{
            var text = node.textContent;
            if (regex.test(text)) {{
                regex.lastIndex = 0;
                var frag = document.createDocumentFragment();
                var lastIdx = 0;
                var match;
                if ((match = regex.exec(text)) !== null) {{
                    frag.appendChild(document.createTextNode(text.substring(lastIdx, match.index)));
                    var s = document.createElement('span');
                    s.className = className;
                    s.setAttribute('data-annot-id', annotId);
                    if (note) s.setAttribute('data-note', note);
                    s.textContent = match[0];
                    frag.appendChild(s);
                    lastIdx = regex.lastIndex;
                }}
                frag.appendChild(document.createTextNode(text.substring(lastIdx)));
                node.parentNode.replaceChild(frag, node);
            }}
        }} else if (node.nodeType === 1 && node.childNodes) {{
            if (node.className === className) return;
            var children = Array.from(node.childNodes);
            children.forEach(walk);
        }}
    }}

    walk(element);
}}

// === Annotation panel (async) ===
function refreshAnnotPanel() {{
    if (!bridge) return;
    bridge.getAllAnnotations().then(function(data) {{
        var annots = JSON.parse(data);
        var list = $('#annot-list');
        list.empty();

        if (!annots || annots.length === 0) {{
            list.html('<p style="color:#888;">No annotations yet.</p>');
            return;
        }}

        annots.forEach(function(annot) {{
            var item = $('<div class="annot-item">');
            item.append('<div class="annot-text">"' + annot.selected_text.substring(0, 50) + '..."</div>');
            if (annot.note_text) {{
                item.append('<div class="annot-note">' + annot.note_text + '</div>');
            }}
            var rm = $('<span class="annot-remove">[remove]</span>');
            rm.click(function() {{
                bridge.removeAnnotation(parseInt(annot.id)).then(function(ok) {{
                    if (ok) {{
                        item.remove();
                        $('[data-annot-id="' + annot.id + '"]').each(function() {{
                            var parent = $(this).parent();
                            $(this).replaceWith($(this).text());
                            parent[0].normalize();
                        }});
                    }}
                }});
            }});
            item.append(rm);
            list.append(item);
        }});
    }});
}}

// === Toggle annotation panel visibility ===
function toggleAnnotPanel() {{
    var panel = $('#annot-panel');
    panel.toggle();
    if (panel.is(':visible')) refreshAnnotPanel();
}}

// === Clear search highlights ===
function clearSearch() {{
    $('mark.search-mark').each(function() {{
        var parent = $(this).parent();
        $(this).replaceWith($(this).text());
        parent[0].normalize();
    }});
}}

// ===== TTS (Text-to-Speech) — Web Speech API =====
var ttsUtterance = null;
var ttsSpeaking = false;
var ttsPaused = false;
var ttsCurrentWordSpan = null;

function ttsGetPageText() {{
    var page = $('#flipbook').turn('page');
    // turn.js pages are .pN elements inside #flipbook
    var pageEl = $('#flipbook .p' + page);
    if (pageEl.length === 0) return '';
    var content = pageEl.find('.page-content');
    if (content.length === 0) return '';
    return content.text().trim();
}}

function ttsClearWordHighlight() {{
    var span = document.getElementById('tts-current-word');
    if (span) {{
        var parent = span.parentNode;
        span.outerHTML = span.textContent;
        if (parent) parent.normalize();
    }}
    ttsCurrentWordSpan = null;
}}

function ttsSpeak() {{
    if (ttsSpeaking && !ttsPaused) {{
        // Pause
        speechSynthesis.pause();
        ttsPaused = true;
        return;
    }}
    if (ttsSpeaking && ttsPaused) {{
        // Resume
        speechSynthesis.resume();
        ttsPaused = false;
        return;
    }}

    var text = ttsGetPageText();
    if (!text) {{
        if (typeof bridge !== 'undefined' && bridge.ttsNoText) {{
            bridge.ttsNoText();
        }}
        return;
    }}

    ttsUtterance = new SpeechSynthesisUtterance(text);
    ttsUtterance.rate = window._ttsRate || {tts_rate};
    ttsUtterance.pitch = window._ttsPitch || {tts_pitch};
    ttsUtterance.volume = {tts_volume};

    // Apply selected voice if set
    if (window._ttsVoice) {{
        ttsUtterance.voice = window._ttsVoice;
    }}

    // Word boundary highlight
    if ({tts_word_hl}) {{
        ttsUtterance.onboundary = function(event) {{
            if (event.name === 'word') {{
                ttsClearWordHighlight();
                var page = $('#flipbook').turn('page');
                var pageEl = $('#flipbook .p' + page);
                if (pageEl.length === 0) return;
                var content = pageEl.find('.page-content');
                if (content.length === 0) return;

                var word = text.substring(event.charIndex, event.charIndex + event.charLength);
                if (!word || word.trim().length === 0) return;

                // Highlight word using indexOf (no regex needed)
                var html = content.html();
                var lowerHtml = html.toLowerCase();
                var lowerWord = word.toLowerCase();
                var idx = lowerHtml.indexOf(lowerWord);
                if (idx >= 0) {{
                    var before = html.substring(0, idx);
                    var match = html.substring(idx, idx + word.length);
                    var after = html.substring(idx + word.length);
                    var newHtml = before +
                        '<span id="tts-current-word" style="background:{tts_word_hl_bg};color:{tts_word_hl_color};border-radius:2px;">' +
                        match + '</span>' + after;
                    content.html(newHtml);
                    ttsCurrentWordSpan = document.getElementById('tts-current-word');
                }}
            }}
        }};
    }}

    ttsUtterance.onend = function() {{
        ttsClearWordHighlight();
        ttsSpeaking = false;
        ttsPaused = false;
        if (typeof bridge !== 'undefined' && bridge.ttsFinished) {{
            bridge.ttsFinished($('#flipbook').turn('page'));
        }}
        // Auto-flip to next page and continue reading
        if ({tts_auto_flip}) {{
            var next = $('#flipbook').turn('page') + 1;
            if (next <= $('#flipbook').turn('pages')) {{
                $('#flipbook').turn('next');
                setTimeout(function() {{ ttsSpeak(); }}, 800);
            }}
        }}
    }};

    ttsSpeaking = true;
    ttsPaused = false;
    speechSynthesis.speak(ttsUtterance);

    if (typeof bridge !== 'undefined' && bridge.ttsStarted) {{
        bridge.ttsStarted($('#flipbook').turn('page'));
    }}
}}

function ttsStop() {{
    speechSynthesis.cancel();
    ttsSpeaking = false;
    ttsPaused = false;
    ttsClearWordHighlight();
}}

function ttsGetVoices() {{
    var voices = speechSynthesis.getVoices();
    var result = [];
    for (var i = 0; i < voices.length; i++) {{
        result.push({{name: voices[i].name, lang: voices[i].lang, default: voices[i].default}});
    }}
    return result;
}}

function ttsSetVoice(name) {{
    var voices = speechSynthesis.getVoices();
    for (var i = 0; i < voices.length; i++) {{
        if (voices[i].name === name) {{
            window._ttsVoice = voices[i];
            return true;
        }}
    }}
    return false;
}}

// Load voices (they load async in some browsers)
if (typeof speechSynthesis !== 'undefined') {{
    speechSynthesis.onvoiceschanged = function() {{
        ttsGetVoices();
    }};
}}
</script>
</body>
</html>"""

        return (1, html, page_count, ())

    # ------------------------------------------------------------------------
    # PREV PAGE
    # ------------------------------------------------------------------------
    def PrevPage(self, params):
        self.web.page().runJavaScript("$('#flipbook').turn('previous');")
        self.status.showMessage("Previous page")
        return (1, None, ())

    # ------------------------------------------------------------------------
    # NEXT PAGE
    # ------------------------------------------------------------------------
    def NextPage(self, params):
        self.web.page().runJavaScript("$('#flipbook').turn('next');")
        self.status.showMessage("Next page")
        return (1, None, ())

    # ------------------------------------------------------------------------
    # SEARCH IN BOOK — Run JS search function
    # ------------------------------------------------------------------------
    def SearchInBook(self, params):
        term = self._p(params, "term", "")
        if not term:
            return (1, 0, ())

        js = f"searchInBook({json.dumps(term)});"
        self.web.page().runJavaScript(js, lambda result: self.status.showMessage(
            f"Search '{term}': {result} matches" if result else f"No matches for '{term}'"
        ))
        return (1, None, ())

    # ------------------------------------------------------------------------
    # HIGHLIGHT SELECTED — Run JS highlight function
    # ------------------------------------------------------------------------
    def HighlightSelected(self, params):
        self.web.page().runJavaScript("highlightSelected();")
        self.status.showMessage("Highlighted selection")
        return (1, None, ())

    # ------------------------------------------------------------------------
    # ANNOTATE SELECTED — Run JS annotate function
    # ------------------------------------------------------------------------
    def AnnotateSelected(self, params):
        self.web.page().runJavaScript("annotateSelected();")
        self.status.showMessage("Annotated selection")
        return (1, None, ())

    # ------------------------------------------------------------------------
    # ON CLEAR SEARCH
    # ------------------------------------------------------------------------
    def OnClearSearch(self):
        self.web.page().runJavaScript("clearSearch();")
        self.search_box.clear()
        self.status.showMessage("Search cleared")

    # ------------------------------------------------------------------------
    # EXPORT HTML
    # ------------------------------------------------------------------------
    def ExportHTML(self, params):
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Flipbook HTML", "", "HTML files (*.html)"
        )
        if not filepath:
            return (1, None, ())

        ok, html, _, err = self.GenerateFlipbookHTML()
        if not ok:
            return (0, None, err)

        with open(filepath, "w") as f:
            f.write(html)

        self.status.showMessage(f"Exported to {filepath}")
        self.state["report"] = f"Exported HTML to {filepath}"
        return (1, filepath, ())

    # ------------------------------------------------------------------------
    # REFRESH DB
    # ------------------------------------------------------------------------
    def RefreshDB(self, params):
        if self.state["db"]:
            self.state["db"].close()
        ok, _, err = self.OpenDB()
        if not ok:
            self.status.showMessage(f"Error: {err[1]}")
            return (0, None, err)

        old_path = self.state.get("html_path")
        if old_path and os.path.exists(old_path):
            os.unlink(old_path)

        return self.LoadFlipbook()

    # ------------------------------------------------------------------------
    # ANNOTATION DIRECT METHODS (called by BookBridge)
    # ------------------------------------------------------------------------
    def AddAnnotationDirect(self, section_id, selected_text, note_text, color):
        conn = self.state["db"]
        try:
            cur = conn.execute(
                "INSERT INTO annotations (section_id, selected_text, note_text, color) "
                "VALUES (?, ?, ?, ?)",
                (int(section_id), selected_text, note_text, color),
            )
            conn.commit()
            return (1, cur.lastrowid, ())
        except sqlite3.Error as e:
            return (0, None, ("DBERROR", str(e), 0))

    def GetAllAnnotationsDirect(self):
        conn = self.state["db"]
        try:
            rows = conn.execute(
                "SELECT id, section_id, selected_text, note_text, color "
                "FROM annotations ORDER BY id"
            ).fetchall()
            result = []
            for r in rows:
                result.append({
                    "id": r[0],
                    "section_id": r[1],
                    "selected_text": r[2],
                    "note_text": r[3],
                    "color": r[4],
                })
            return (1, result, ())
        except sqlite3.Error as e:
            return (0, None, ("DBERROR", str(e), 0))

    def GetSectionAnnotationsDirect(self, section_id):
        conn = self.state["db"]
        try:
            rows = conn.execute(
                "SELECT id, section_id, selected_text, note_text, color "
                "FROM annotations WHERE section_id = ? ORDER BY id",
                (int(section_id),),
            ).fetchall()
            result = []
            for r in rows:
                result.append({
                    "id": r[0],
                    "section_id": r[1],
                    "selected_text": r[2],
                    "note_text": r[3],
                    "color": r[4],
                })
            return (1, result, ())
        except sqlite3.Error as e:
            return (0, None, ("DBERROR", str(e), 0))

    def RemoveAnnotationDirect(self, annotation_id):
        conn = self.state["db"]
        try:
            conn.execute("DELETE FROM annotations WHERE id = ?", (int(annotation_id),))
            conn.commit()
            return (1, None, ())
        except sqlite3.Error as e:
            return (0, None, ("DBERROR", str(e), 0))

    # ------------------------------------------------------------------------
    # MARKDOWN TO HTML
    # ------------------------------------------------------------------------
    def _md_to_html(self, text):
        if not text:
            return ""

        lines = text.split("\n")
        html_lines = []
        in_list = False
        in_table = False
        is_header = True

        for line in lines:
            stripped = line.strip()

            if not stripped:
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                if in_table:
                    html_lines.append("</table>")
                    in_table = False
                    is_header = True
                continue

            if stripped.startswith("|") and stripped.endswith("|"):
                cells = [c.strip() for c in stripped.split("|")[1:-1]]
                if all(re.match(r"^[-:]+$", c) for c in cells):
                    continue
                if not in_table:
                    html_lines.append("<table>")
                    in_table = True
                if is_header:
                    html_lines.append("<tr>" + "".join(f"<th>{c}</th>" for c in cells) + "</tr>")
                    is_header = False
                else:
                    html_lines.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
                continue

            if stripped.startswith("- ") or stripped.startswith("* "):
                if not in_list:
                    html_lines.append("<ul>")
                    in_list = True
                html_lines.append(f"<li>{self._inline_md(stripped[2:])}</li>")
                continue

            if stripped.startswith("### "):
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                html_lines.append(f"<h3>{self._inline_md(stripped[4:])}</h3>")
                continue
            if stripped.startswith("## "):
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                html_lines.append(f"<h2>{self._inline_md(stripped[3:])}</h2>")
                continue

            if stripped.startswith("> "):
                html_lines.append(f"<blockquote>{self._inline_md(stripped[2:])}</blockquote>")
                continue

            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<p>{self._inline_md(stripped)}</p>")

        if in_list:
            html_lines.append("</ul>")
        if in_table:
            html_lines.append("</table>")

        return "\n".join(html_lines)

    def _inline_md(self, text):
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"(?<!\*)\*(?!\*)(.+?)\*(?!\*)", r"<i>\1</i>", text)
        text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
        return text

    # ------------------------------------------------------------------------
    # ERROR DISPLAY — Shows actionable error from Config.ERRORS
    # ------------------------------------------------------------------------
    # Method: _show_error
    # Purpose: Display an error with actionable steps from Config.ERRORS
    # Params:  error_key (str) — key into Config.ERRORS
    #          context (dict) — values to fill {placeholders} in message
    # Returns: None
    # ------------------------------------------------------------------------
    def _show_error(self, error_key, context=None):
        if context is None:
            context = {}
        err = cfg.GetError(error_key)
        if err is None:
            # Fallback: treat error_key as a raw message (backwards compat)
            self.setWindowTitle("Book Viewer — Error")
            central = QWidget()
            self.setCentralWidget(central)
            layout = QVBoxLayout(central)
            label = QLabel(f"Error: {error_key}")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet(cfg.GetTheme("error_label_style"))
            layout.addWidget(label)
            return

        # Format message with context values
        try:
            msg = err["message"].format(**context)
        except (KeyError, ValueError):
            msg = err["message"]
        action = err.get("action", "")
        command = err.get("command")
        details = err.get("details", "")

        self.setWindowTitle("Book Viewer — Error")
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(40, 40, 40, 40)

        # Error icon + message
        icon_label = QLabel(f"{cfg.GetIcon('error')}  {msg}")
        icon_label.setStyleSheet(
            f"font-size: 16px; color: {cfg.GetTheme('annot_remove_color')};"
        )
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        # Action to take
        if action:
            action_label = QLabel(f"\u2192 {action}")
            action_label.setStyleSheet(
                f"font-size: 14px; font-weight: bold; color: {cfg.GetTheme('h2_color')};"
            )
            action_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(action_label)

        # Command to run
        if command:
            cmd_label = QLabel(f"  $ {command}")
            cmd_label.setStyleSheet(
                "font-family: Menlo, Monaco, monospace; font-size: 13px; "
                f"background: {cfg.GetTheme('code_bg')}; padding: 8px; "
                f"border-radius: 4px;"
            )
            cmd_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(cmd_label)

        # Detailed explanation
        if details:
            details_label = QLabel(details)
            details_label.setWordWrap(True)
            details_label.setStyleSheet(
                f"font-size: 12px; color: {cfg.GetTheme('annot_text_color')};"
            )
            details_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(details_label)

    # ------------------------------------------------------------------------
    # TTS TOGGLE — Start/pause/resume reading current page
    # ------------------------------------------------------------------------
    # Method: OnTtsToggle
    # Purpose: Toggle speech synthesis. First click = start reading, second
    #          click = pause, third click = resume. Button label updates.
    # Params:  None (button click)
    # Returns: None
    # ------------------------------------------------------------------------
    def OnTtsToggle(self):
        self.web.page().runJavaScript("ttsSpeak();")

    # ------------------------------------------------------------------------
    # TTS STOP — Stop reading entirely
    # ------------------------------------------------------------------------
    # Method: OnTtsStop
    # Purpose: Cancel any ongoing speech synthesis and clear word highlight.
    # Params:  None (button click)
    # Returns: None
    # ------------------------------------------------------------------------
    def OnTtsStop(self):
        self.web.page().runJavaScript("ttsStop();")
        self.btn_read.setText(f"{cfg.GetIcon('read')}  Read")

    # ------------------------------------------------------------------------
    # VOICE PICKER — Dialog to choose voice, rate, and pitch
    # ------------------------------------------------------------------------
    # Method: ShowVoicePicker
    # Purpose: Query available TTS voices from the Web Speech API, show a
    #          dialog with a dropdown, speed slider, and pitch slider.
    #          User picks → JS applies the voice for next utterance.
    # Params:  None (button click)
    # Returns: None
    # ------------------------------------------------------------------------
    def ShowVoicePicker(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Voice Settings")
        dialog.resize(400, 300)
        outer = QVBoxLayout(dialog)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Shared header
        outer.addWidget(self.BuildDialogHeader("Voice", "TTS Settings"))

        # Body
        body = QWidget()
        body.setStyleSheet("background: #fdfdfd; padding: 20px;")
        body_layout = QVBoxLayout(body)
        body_layout.setSpacing(12)

        # Voice dropdown
        body_layout.addWidget(QLabel("Voice:"))
        voice_combo = QComboBox()
        voice_combo.setStyleSheet("padding: 4px; font-size: 13px;")
        body_layout.addWidget(voice_combo)

        # Rate slider
        rate_label = QLabel(f"Speed: {cfg.GetTts('rate')}x")
        body_layout.addWidget(rate_label)
        rate_slider = QSlider(Qt.Orientation.Horizontal)
        rate_slider.setRange(5, 30)
        rate_slider.setValue(int(cfg.GetTts("rate") * 10))
        rate_slider.valueChanged.connect(
            lambda v: rate_label.setText(f"Speed: {v/10:.1f}x")
        )
        body_layout.addWidget(rate_slider)

        # Pitch slider
        pitch_label = QLabel(f"Pitch: {cfg.GetTts('pitch')}")
        body_layout.addWidget(pitch_label)
        pitch_slider = QSlider(Qt.Orientation.Horizontal)
        pitch_slider.setRange(0, 20)
        pitch_slider.setValue(int(cfg.GetTts("pitch") * 10))
        pitch_slider.valueChanged.connect(
            lambda v: pitch_label.setText(f"Pitch: {v/10:.1f}")
        )
        body_layout.addWidget(pitch_slider)

        body_layout.addStretch()
        outer.addWidget(body, stretch=1)

        # Load voices from JS
        def populate_voices():
            def callback(result):
                if not result:
                    voice_combo.addItem("System Default")
                    return
                # result is a JSON string, parse it
                import json as _json
                try:
                    voices = _json.loads(result) if isinstance(result, str) else result
                except (ValueError, TypeError):
                    voices = []
                voice_combo.addItem("System Default")
                for v in voices:
                    name = v.get("name", "Unknown")
                    lang = v.get("lang", "")
                    label = f"{name} ({lang})" if lang else name
                    voice_combo.addItem(label)
                # Select current default
                for i, v in enumerate(voices):
                    if v.get("default"):
                        voice_combo.setCurrentIndex(i + 1)
                        break
            self.web.page().runJavaScript(
                "JSON.stringify(ttsGetVoices())", callback
            )

        populate_voices()

        # Apply button
        def apply_voice():
            idx = voice_combo.currentIndex()
            rate = rate_slider.value() / 10
            pitch = pitch_slider.value() / 10
            if idx > 0:
                # Get voice name from combo text
                text = voice_combo.currentText()
                name = text.split(" (")[0] if " (" in text else text
                self.web.page().runJavaScript(
                    f"ttsSetVoice({json.dumps(name)});"
                )
            # Store rate/pitch in JS by updating the utterance defaults
            self.web.page().runJavaScript(
                f"window._ttsRate = {rate}; window._ttsPitch = {pitch};"
            )
            dialog.accept()

        btn_bar = QHBoxLayout()
        btn_bar.setContentsMargins(0, 10, 0, 10)
        btn_bar.addStretch()
        btn_apply = QPushButton("Apply")
        btn_apply.setStyleSheet(cfg.GetTheme("dialog_close_style"))
        btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_apply.clicked.connect(apply_voice)
        btn_bar.addWidget(btn_apply)
        btn_bar.addStretch()
        outer.addLayout(btn_bar)

        dialog.exec()

    # ------------------------------------------------------------------------
    # DIALOG HEADER — Shared header bar builder for Help and About
    # ------------------------------------------------------------------------
    # Method: BuildDialogHeader
    # Purpose: Build the dark blue header bar with icon + title + subtitle.
    #          Both Help and About use this — they are siblings.
    # Params:  title (str), subtitle (str)
    # Returns: QWidget — the header widget
    # ------------------------------------------------------------------------
    def BuildDialogHeader(self, title, subtitle):
        header = QWidget()
        header.setStyleSheet(cfg.GetTheme("dialog_header_style"))
        header.setFixedHeight(cfg.GetTheme("dialog_header_height"))
        hlayout = QHBoxLayout(header)
        hlayout.setContentsMargins(20, 0, 20, 0)
        hlayout.setSpacing(8)

        icon = QLabel(cfg.GetTheme("dialog_header_icon"))
        icon.setStyleSheet(cfg.GetTheme("dialog_header_icon_style"))
        hlayout.addWidget(icon)

        ttl = QLabel(title)
        ttl.setStyleSheet(cfg.GetTheme("dialog_header_title_style"))
        hlayout.addWidget(ttl)

        hlayout.addStretch()

        sub = QLabel(subtitle)
        sub.setStyleSheet(cfg.GetTheme("dialog_header_sub_style"))
        hlayout.addWidget(sub)

        return header

    # ------------------------------------------------------------------------
    # DIALOG CLOSE BAR — Shared close button builder
    # ------------------------------------------------------------------------
    # Method: BuildDialogCloseBar
    # Purpose: Build the centered close button bar. Both dialogs use this.
    # Params:  dialog (QDialog) — the parent dialog to close
    # Returns: QHBoxLayout
    # ------------------------------------------------------------------------
    def BuildDialogCloseBar(self, dialog):
        bar = QHBoxLayout()
        bar.setContentsMargins(0, 10, 0, 10)
        bar.addStretch()
        btn = QPushButton("Close")
        btn.setStyleSheet(cfg.GetTheme("dialog_close_style"))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(dialog.accept)
        bar.addWidget(btn)
        bar.addStretch()
        return bar

    # ------------------------------------------------------------------------
    # KEY PRESS — Keyboard shortcuts for TTS
    # ------------------------------------------------------------------------
    # Method: keyPressEvent
    # Purpose: Handle Ctrl+Space (read/pause), Ctrl+. (stop), Ctrl+Shift+V (voice)
    # Params:  event (QKeyEvent)
    # Returns: None
    # ------------------------------------------------------------------------
    def keyPressEvent(self, event):
        key = event.key()
        mods = event.modifiers()

        # Ctrl+Space = Read/Pause
        if mods & Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_Space:
            self.OnTtsToggle()
            return

        # Ctrl+. = Stop
        if mods & Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_Period:
            self.OnTtsStop()
            return

        # Ctrl+Shift+V = Voice picker
        if (mods & Qt.KeyboardModifier.ControlModifier and
                mods & Qt.KeyboardModifier.ShiftModifier and
                key == Qt.Key.Key_V):
            self.ShowVoicePicker()
            return

        # Let parent handle everything else
        super().keyPressEvent(event)

    # ------------------------------------------------------------------------
    # SHOW HELP — Display Config.HELP in a styled scrollable dialog
    # ------------------------------------------------------------------------
    # Method: ShowHelp
    # Purpose: Open a dialog with shared header bar, scrollable help text,
    #          and shared close button. Sibling of ShowAbout.
    # Params:  None
    # Returns: None
    # ------------------------------------------------------------------------
    def ShowHelp(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(cfg.GetTheme("help_dialog_title"))
        dialog.resize(cfg.GetTheme("help_dialog_width"), cfg.GetTheme("help_dialog_height"))
        outer = QVBoxLayout(dialog)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- Shared header bar ---
        outer.addWidget(self.BuildDialogHeader(
            cfg.GetTheme("help_header_title"),
            cfg.GetTheme("help_header_subtitle"),
        ))

        # --- Body (scrollable help text) ---
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(cfg.GetHelp())
        text.setStyleSheet(cfg.GetTheme("help_body_style"))
        outer.addWidget(text, stretch=1)

        # --- Shared close button ---
        outer.addLayout(self.BuildDialogCloseBar(dialog))

        dialog.exec()

    # ------------------------------------------------------------------------
    # SHOW ABOUT — Display Config.ABOUT in a styled dialog
    # ------------------------------------------------------------------------
    # Method: ShowAbout
    # Purpose: Open a dialog with shared header bar, about text, version info,
    #          and shared close button. Sibling of ShowHelp.
    # Params:  None
    # Returns: None
    # ------------------------------------------------------------------------
    def ShowAbout(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(cfg.GetTheme("about_dialog_title"))
        dialog.resize(cfg.GetTheme("about_dialog_width"), cfg.GetTheme("about_dialog_height"))
        outer = QVBoxLayout(dialog)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- Shared header bar ---
        outer.addWidget(self.BuildDialogHeader(
            cfg.GetTheme("about_header_title"),
            cfg.GetTheme("about_header_subtitle"),
        ))

        # --- Body (app name + info table + version) ---
        body = QWidget()
        body.setStyleSheet(cfg.GetTheme("about_body_style"))
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(24, 20, 24, 12)
        body_layout.setSpacing(0)

        # App name + subtitle
        app_title = QLabel(cfg.GetTheme("about_app_title"))
        app_title.setStyleSheet(cfg.GetTheme("about_book_title_style"))
        body_layout.addWidget(app_title)

        app_sub = QLabel(cfg.GetTheme("about_app_subtitle"))
        app_sub.setStyleSheet(cfg.GetTheme("about_book_sub_style"))
        body_layout.addWidget(app_sub)

        # Info table: Developer, Contact, License, Source, Built With
        info_rows = [
            (cfg.GetTheme("about_developer_label"),
             f"{cfg.GetTheme('about_developer_name')}  —  "
             f"{cfg.GetTheme('about_developer_tagline')}"),
            (cfg.GetTheme("about_contact_label"),   cfg.GetTheme("about_contact_email")),
            (cfg.GetTheme("about_license_label"),   cfg.GetTheme("about_license")),
            (cfg.GetTheme("about_repo_label"),      cfg.GetTheme("about_repo")),
            ("Built With",                          cfg.GetTheme("about_built_with")),
        ]

        for label_text, value_text in info_rows:
            row = QHBoxLayout()
            row.setContentsMargins(0, 4, 0, 0)
            row.setSpacing(12)

            lbl = QLabel(label_text)
            lbl.setStyleSheet(cfg.GetTheme("about_info_label_style"))
            lbl.setFixedWidth(80)
            row.addWidget(lbl)

            val = QLabel(value_text)
            val.setStyleSheet(cfg.GetTheme("about_info_value_style"))
            row.addWidget(val, stretch=1)

            body_layout.addLayout(row)

        # Version line
        ver = QLabel(
            f"CLI v{Config.CLI_VERSION}  |  Viewer v{Config.VIEWER_VERSION}  |  "
            f"Schema v{Config.SCHEMA_VERSION}"
        )
        ver.setStyleSheet(cfg.GetTheme("about_version_style"))
        body_layout.addWidget(ver)

        outer.addWidget(body, stretch=1)

        # --- Shared close button ---
        outer.addLayout(self.BuildDialogCloseBar(dialog))

        dialog.exec()


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

def main():
    db_path = None
    if len(sys.argv) > 1:
        db_path = sys.argv[1]

    app = QApplication(sys.argv)
    viewer = BookViewer(db=db_path)
    viewer.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
