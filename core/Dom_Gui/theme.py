# [@GHOST]{[@file<theme.py>][@domain<Dom_Gui>][@role<theme>][@auth<cascade>][@date<2026-06-27>][@ver<1.1.0>]}
# [@VBSTYLE]{[@auth<system>][@role<theme_manager>][@return<tuple3>][@orch<builder>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{Theme manager — loads palettes from DB, builds stylesheets, applies to widgets}
# [@WCL]{[@no_db_imports<true>][@no_mysql<true>][@no_sqlite<true>][@delegates_to<db.py>]}

from . import config


class ThemeLoader:
    """Theme manager — only handles themes.

    Does NOT handle database connections. All DB access is delegated to GuiDB.
    ThemeLoader asks GuiDB for palette data, then builds stylesheets and
    applies them to widgets.

    Usage:
        db = GuiDB()
        theme = ThemeLoader(db)
        theme.apply(widget, "forest")
    """

    def __init__(self, db=None):
        self.db = db
        self._cache = {}

    def Run(self, command, params=None):
        if command == "load":
            return self.load((params or {}).get("name"))
        elif command == "apply":
            return self.apply(
                (params or {}).get("widget"),
                (params or {}).get("name")
            )
        elif command == "list_themes":
            return self.list_themes()
        elif command == "refresh":
            return self.refresh()
        elif command == "read_state":
            return self.read_state()
        return (0, None, ("unknown_command", command, 0))

    def load(self, name):
        """Load a theme palette by name. Returns dict of {key: value}."""
        if name in self._cache:
            return (1, self._cache[name], None)

        if self.db:
            code, palette, err = self.db.Run("load_theme", {"name": name})
            if code == 1 and palette:
                self._cache[name] = palette
                return (1, palette, None)

        palette = dict(config.THEMES.get(
            name, config.THEMES[config.DEFAULT_THEME]
        ))
        self._cache[name] = palette
        return (1, palette, None)

    def apply(self, widget, name):
        """Apply a theme to a QWidget by setting its stylesheet."""
        code, p, err = self.load(name)
        if code != 1 or not p:
            return (0, None, ("load_failed", name, 0))

        font_family = p.get("font", "Menlo")
        widget.setStyleSheet(f"""
            QMainWindow {{ background-color: {p['bg']}; }}
            QLabel {{ color: {p['text']}; font-size: 12px; }}
            QTabWidget::pane {{ border: 0.5px solid {p['border']}; background: {p['bg']}; }}
            QTabBar::tab {{ background: {p['bg_alt']}; color: {p['muted']};
                padding: 6px 16px; border: none; font-family: {font_family}; font-size: 10px; font-weight: bold; }}
            QTabBar::tab:selected {{ background: {p['bg_alt']}; color: {p['accent']}; }}
            QTextEdit {{ background: {p['bg']}; color: {p['text']};
                border: 0.5px solid {p['border']}; font-family: {font_family}; font-size: 10px; }}
            QPushButton {{ background: {p['bg_alt']}; color: {p['muted']};
                border: 0.5px solid {p['border']}; padding: 5px 14px; border-radius: 6px;
                font-family: {font_family}; font-size: 10px; }}
            QPushButton:hover {{ background: {p['border']}; color: {p['accent']}; }}
            QTableWidget {{ background: {p['bg']}; color: {p['text']};
                border: 0.5px solid {p['border']}; font-family: {font_family}; font-size: 10px;
                gridline-color: {p['bg_alt']}; }}
            QHeaderView::section {{ background: {p['bg_alt']}; color: {p['muted']};
                border: none; padding: 3px; font-family: {font_family}; font-weight: bold; }}
            QStatusBar {{ background: {p['bg']}; color: {p['muted']};
                font-family: {font_family}; font-size: 10px; }}
            QComboBox {{ background: {p['bg_alt']}; color: {p['muted']};
                border: 0.5px solid {p['border']}; padding: 3px 8px;
                font-family: {font_family}; font-size: 10px; border-radius: 4px; }}
            QCheckBox {{ color: {p['muted']}; font-family: {font_family}; font-size: 10px; }}
            QMenuBar {{ background: {p['bg']}; color: {p['muted']}; }}
            QMenuBar::item:selected {{ background: {p['bg_alt']}; color: {p['accent']}; }}
            QMenu {{ background: {p['bg_alt']}; color: {p['text']};
                border: 0.5px solid {p['border']}; }}
            QMenu::item:selected {{ background: {p['border']}; color: {p['accent']}; }}
        """)
        return (1, {"applied": name}, None)

    def list_themes(self):
        """Return list of available theme names."""
        if self.db:
            code, names, err = self.db.Run("list_themes")
            if code == 1 and names:
                return (1, names, None)
        return (1, list(config.THEMES.keys()), None)

    def refresh(self):
        """Clear cache so next load fetches from DB again."""
        self._cache.clear()
        return (1, {"cleared": True}, None)

    def read_state(self):
        return (1, {
            "has_db": self.db is not None,
            "cached_themes": list(self._cache.keys()),
        }, None)
