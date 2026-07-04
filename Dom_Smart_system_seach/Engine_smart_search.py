#!/usr/bin/env python3

#[@GHOST]{[@file<Engine_smart_search.py>][@state<active>][@date<2026-06-22>][@ver<1.0>][@auth<Cascade>]}
#[@VBSTYLE]{[@auth<system>][@role<search_engine>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded_paths|abc|inheritance>]}

"""
Smart Search Engine Domain.
Searches MySQL vb_shared (all tables, all text columns) and EFL DB.
No classification — classification is handled by Classifier_smart_system.py.
No GUI — GUI is handled by Gui_Smart_search.py.
"""

import os
import re
import sys
import math
import sqlite3
import importlib.util

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Config_smart_system import *

TEXT_TYPES_SET = frozenset({
    TEXT_TYPE_CHAR, TEXT_TYPE_VARCHAR, TEXT_TYPE_TEXT,
    TEXT_TYPE_TINYTEXT, TEXT_TYPE_MEDIUMTEXT, TEXT_TYPE_LONGTEXT,
})



from collections import Counter, defaultdict


def _debug(msg: str):
    sys.stderr.write(f"{DEBUG_PREFIX} {msg}\n")
    sys.stderr.flush()

# --- MySQL search source (vb_shared database) --------------------------------
# Smart search across ALL text columns in ALL tables — same pattern as
# mysql_cli_search.py but returns compact hit strings for the results list.
# Also loads token_master for ghost-text autocomplete in the search bar.
import mysql.connector as _mysql

_MYSQL_CFG = dict(
    user=DB_USER_ROOT,
    database=DB_NAME_VB_SHARED,
    autocommit=MYSQL_AUTOCOMMIT,
)
_TOKEN_DB_CFG = dict(
    user=DB_USER_ROOT,
    database=DB_NAME_TOKEN_REGISTRY,
    autocommit=MYSQL_AUTOCOMMIT,
)
_TEXT_TYPES = TEXT_TYPES_SET
_AC_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), AUTOCOMPLETE_DB_NAME)
_BIGRAM_DB = _AC_DB
_WORDFREQ_DB = _AC_DB

_STOP_WORDS = STOP_WORDS


def _tokenize(text: str):
    """Tokenize text using the same rules as tokenized_context_search.py:
    - lowercase
    - word-boundary alphanumeric + underscores
    - exclude stop words
    - exclude words with len <= 2
    """
    words = re.findall(r'\b[a-zA-Z0-9_]+\b', text.lower())
    return [w for w in words if w not in _STOP_WORDS and len(w) > 2]


def _apply_build_pragmas(cur):
    cur.execute(PRAGMA_BUILD_WAL)
    cur.execute(PRAGMA_BUILD_SYNC)
    cur.execute(PRAGMA_BUILD_TEMP)
    cur.execute(PRAGMA_BUILD_CACHE)
    cur.execute(PRAGMA_BUILD_MMAP)


def _apply_runtime_pragmas(cur):
    cur.execute(PRAGMA_BUILD_WAL)
    cur.execute(PRAGMA_RUNTIME_SYNC)
    cur.execute(PRAGMA_RUNTIME_CACHE)


def AcRuntimeConn():
    conn = sqlite3.connect(_AC_DB)
    _apply_runtime_pragmas(conn.cursor())
    return conn


def AcPrefixSearch(conn, prefix, limit=AUTOCOMPLETE_PREFIX_LIMIT):
    cur = conn.cursor()
    cur.execute(SQL_SELECT_WORD_PREFIX, (prefix + '%',))
    return cur.fetchall()


def AcBigramNext(conn, word, limit=AUTOCOMPLETE_NEXT_LIMIT):
    cur = conn.cursor()
    cur.execute(SQL_SELECT_BIGRAM_NEXT, (word,))
    return cur.fetchall()


def AcTrigramNext(conn, w1, w2, limit=AUTOCOMPLETE_NEXT_LIMIT):
    cur = conn.cursor()
    cur.execute(SQL_SELECT_TRIGRAM_NEXT, (w1, w2))
    return cur.fetchall()


def AcSymbolSearch(prefix, limit=AUTOCOMPLETE_PREFIX_LIMIT):
    if not os.path.exists(EFL_DB_PATH):
        return []
    results = []
    try:
        conn = sqlite3.connect(EFL_DB_PATH)
        cur = conn.cursor()
        cur.execute(SQL_SELECT_CLASSES_BY_PREFIX, (prefix + '%',))
        for class_name, method_count in cur.fetchall():
            results.append((class_name, 'class', method_count))
        cur.execute(SQL_SELECT_METHODS_BY_PREFIX, (prefix + '%',))
        for method_name, class_name in cur.fetchall():
            results.append((method_name, 'method', class_name))
        conn.close()
    except Exception as ex:
        _debug(f"symbol search failed: {ex}")
    return results[:limit]


def AcUserHistoryPrefix(conn, prefix, context=''):
    cur = conn.cursor()
    cur.execute(SQL_SELECT_USER_HISTORY_PREFIX, (prefix + '%', context))
    return cur.fetchall()


def AcUserHistoryBigram(conn, prev_word):
    cur = conn.cursor()
    cur.execute(SQL_SELECT_USER_HISTORY_BIGRAM, (prev_word,))
    return cur.fetchall()


def AcRecordAccept(conn, word, context=''):
    cur = conn.cursor()
    cur.execute(SQL_UPSERT_USER_HISTORY, (word, context))
    conn.commit()


def AcInitHistory(conn):
    cur = conn.cursor()
    cur.execute(SQL_CREATE_USER_HISTORY)
    conn.commit()


def AcRankedSuggestions(conn, current_word, prev_words=None):
    if prev_words is None:
        prev_words = []
    scored = {}

    if current_word:
        ctx = prev_words[-1] if prev_words else ''
        for word, freq in AcUserHistoryPrefix(conn, current_word, ctx):
            if word.lower() != current_word.lower():
                s, _ = scored.get(word, (0, ''))
                scored[word] = (s + RANK_WEIGHT_USER_HISTORY * freq, 'history')

    if current_word:
        for sym, sym_type, extra in AcSymbolSearch(current_word):
            if sym.lower() != current_word.lower():
                s, _ = scored.get(sym, (0, ''))
                scored[sym] = (s + RANK_WEIGHT_SYMBOL, 'symbol')

    if len(prev_words) >= 2:
        for word, freq in AcTrigramNext(conn, prev_words[-2], prev_words[-1]):
            s, _ = scored.get(word, (0, ''))
            scored[word] = (s + RANK_WEIGHT_TRIGRAM * freq, 'trigram')

    if len(prev_words) >= 1:
        for word, freq in AcBigramNext(conn, prev_words[-1]):
            s, _ = scored.get(word, (0, ''))
            scored[word] = (s + RANK_WEIGHT_BIGRAM * freq, 'bigram')

    if current_word:
        for word, freq in AcPrefixSearch(conn, current_word.lower()):
            if word.lower() != current_word.lower():
                s, _ = scored.get(word, (0, ''))
                scored[word] = (s + RANK_WEIGHT_PREFIX * freq, 'prefix')

    ranked = [(word, score, source) for word, (score, source) in scored.items()]
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked[:AUTOCOMPLETE_PREFIX_LIMIT]


def DetectStyleMode(text):
    """Detect writing style mode from text patterns.
    Uses token entropy, punctuation spikes, repeat ratio, sentence length variance.
    Returns (mode, scores) where mode is 'calm', 'neutral', or 'frustrated'.
    """
    if not text or len(text.strip()) < 10:
        return ("neutral", {})
    words = _tokenize(text)
    if not words:
        return ("neutral", {})
    total = len(words)
    freq = Counter(words)
    entropy = 0.0
    for w, c in freq.items():
        p = c / total
        entropy -= p * math.log2(p)
    sentences = re.split(r'[.!?]+', text)
    lengths = [len(_tokenize(s)) for s in sentences if s.strip()]
    if len(lengths) >= 2:
        mean_len = sum(lengths) / len(lengths)
        variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths)
        length_var = math.sqrt(variance)
    else:
        length_var = 0.0
    punct_count = len(re.findall(r'[!?]{2,}|\.{3,}', text))
    caps_ratio = sum(1 for w in words if w.isupper() and len(w) > 2) / max(total, 1)
    punct_spike = punct_count + caps_ratio * 10
    repeat_count = sum(1 for w, c in freq.items() if c > 2)
    repeat_ratio = repeat_count / max(len(freq), 1)
    frustration_score = 0
    if punct_spike > 0:
        frustration_score += punct_spike * 10
    if repeat_ratio > 0.3 and total > 10:
        frustration_score += (repeat_ratio - 0.3) * 50
    if entropy < 4.0 and total > 15:
        frustration_score += (4.0 - entropy) * 5
    calm_score = 0
    if entropy > 6.0 and total > 15:
        calm_score += (entropy - 6.0) * 10
    if length_var < 3.0 and len(lengths) >= 3:
        calm_score += 10
    if punct_spike == 0 and total > 20:
        calm_score += 5
    scores = {
        "entropy": round(entropy, 2),
        "words": total,
        "length_var": round(length_var, 2),
        "punct_spike": round(punct_spike, 2),
        "repeat_ratio": round(repeat_ratio, 2),
        "frustration": round(frustration_score, 1),
        "calm": round(calm_score, 1),
    }
    if frustration_score > 15:
        mode = "frustrated"
    elif calm_score > 15:
        mode = "calm"
    else:
        mode = "neutral"
    return (mode, scores)


STYLE_WINDOW_SIZE = 5
STYLE_DECAY = 0.7
STYLE_SPIKE_THRESHOLD = 15.0


class StyleWindow:
    """Sliding window over recent messages with exponential decay smoothing.
    Tracks frustration/calm trends across multiple messages so one angry
    message does not false-spike the detector.
    """

    def __init__(self, size=STYLE_WINDOW_SIZE, decay=STYLE_DECAY):
        self._size = size
        self._decay = decay
        self._history = []
        self._smoothed_frustration = 0.0
        self._smoothed_calm = 0.0
        self._current_mode = "neutral"

    def Push(self, text):
        """Add a message to the window. Returns (mode, scores, smoothed_frustration)."""
        mode, scores = DetectStyleMode(text)
        self._history.append(scores)
        if len(self._history) > self._size:
            self._history.pop(0)
        self._smoothed_frustration = (
            self._smoothed_frustration * self._decay +
            scores.get("frustration", 0) * (1 - self._decay)
        )
        self._smoothed_calm = (
            self._smoothed_calm * self._decay +
            scores.get("calm", 0) * (1 - self._decay)
        )
        if self._smoothed_frustration > STYLE_SPIKE_THRESHOLD:
            self._current_mode = "frustrated"
        elif self._smoothed_calm > 15.0:
            self._current_mode = "calm"
        else:
            self._current_mode = "neutral"
        return (
            self._current_mode,
            scores,
            round(self._smoothed_frustration, 1),
        )

    def Mode(self):
        return self._current_mode

    def Reset(self):
        self._history = []
        self._smoothed_frustration = 0.0
        self._smoothed_calm = 0.0
        self._current_mode = "neutral"


def LoadWordFreqChunked():
    """Generator — streams MySQL → batch Counter → SQLite UPSERT.
    Yields ('word_freq_progress', rows) per batch, ('word_freq_done', path) when complete."""
    if os.path.exists(_AC_DB):
        try:
            sconn = sqlite3.connect(_AC_DB)
            scur = sconn.cursor()
            scur.execute("SELECT COUNT(*) FROM word_freq")
            count = scur.fetchone()[0]
            sconn.close()
            if count > 0:
                _debug(f"loaded {count} words from SQLite cache")
                yield ("word_freq_done", _AC_DB)
                return
        except Exception:
            pass

    try:
        sconn = sqlite3.connect(_AC_DB)
        scur = sconn.cursor()
        _apply_build_pragmas(scur)
        scur.execute(SQL_CREATE_WORDFREQ)
        scur.execute(SQL_INDEX_WORD_PREFIX)
        scur.execute(SQL_DELETE_WORDFREQ)
        sconn.commit()

        conn = _mysql.connect(**_TOKEN_DB_CFG, buffered=False)
        cur = conn.cursor()
        cur.execute(SQL_SELECT_WORDS)
        batch = Counter()
        for row in cur.fetchall():
            batch[row[0]] = row[1]
        conn.close()
        if batch:
            scur.executemany(SQL_UPSERT_WORDFREQ, [(w, f) for w, f in batch.items()])
            sconn.commit()
        sconn.close()
        _debug(f"built word_freq: {len(batch)} words")
        yield ("word_freq_done", _AC_DB)
    except Exception as ex:
        _debug(f"word freq build failed: {ex}")
        yield ("word_freq_done", None)


def LoadBigramsChunked():
    """Generator — streams MySQL → tokenize → batch Counter → SQLite UPSERT.
    O(batch_size) RAM. Yields ('bigrams_progress', rows) per batch, ('bigrams_done', path)."""
    if os.path.exists(_AC_DB):
        try:
            sconn = sqlite3.connect(_AC_DB)
            scur = sconn.cursor()
            scur.execute(SQL_COUNT_BIGRAMS)
            count = scur.fetchone()[0]
            sconn.close()
            if count > 0:
                _debug(f"loaded {count} bigrams from SQLite cache")
                yield ("bigrams_done", _AC_DB)
                return
        except Exception:
            pass

    try:
        sconn = sqlite3.connect(_AC_DB)
        scur = sconn.cursor()
        _apply_build_pragmas(scur)
        scur.execute(SQL_CREATE_BIGRAMS)
        scur.execute(SQL_DELETE_BIGRAMS)
        scur.execute(SQL_INDEX_BIGRAM_W1)
        scur.execute(SQL_INDEX_BIGRAM_W1_FREQ)
        sconn.commit()

        conn = _mysql.connect(**_TOKEN_DB_CFG, buffered=False)
        cur = conn.cursor()
        cur.execute(SQL_SELECT_LINE_TEXT)
        _debug("building bigram SQLite cache (streaming UPSERT)…")
        rows_fetched = 0
        while True:
            rows = cur.fetchmany(MYSQL_FETCH_BATCH)
            if not rows:
                break
            batch = Counter()
            for (line_text,) in rows:
                if not line_text:
                    continue
                words = _tokenize(line_text)
                for i in range(len(words) - 1):
                    batch[(words[i], words[i + 1])] += 1
                rows_fetched += 1
            if batch:
                scur.executemany(SQL_UPSERT_BIGRAM,
                                 [(w1, w2, f) for (w1, w2), f in batch.items()])
                sconn.commit()
            yield ("bigrams_progress", rows_fetched)
        conn.close()
        sconn.close()
        _debug(f"streamed bigrams from {rows_fetched} lines to SQLite")
        yield ("bigrams_done", _AC_DB)
    except Exception as ex:
        _debug(f"bigram build failed: {ex}")
        yield ("bigrams_done", None)


def LoadTrigramsChunked():
    """Generator — streams MySQL → tokenize → batch Counter → SQLite UPSERT trigrams.
    Yields ('trigrams_progress', rows) per batch, ('trigrams_done', path)."""
    if os.path.exists(_AC_DB):
        try:
            sconn = sqlite3.connect(_AC_DB)
            scur = sconn.cursor()
            scur.execute(SQL_COUNT_TRIGRAMS)
            count = scur.fetchone()[0]
            sconn.close()
            if count > 0:
                _debug(f"loaded {count} trigrams from SQLite cache")
                return
        except Exception:
            pass

    try:
        sconn = sqlite3.connect(_AC_DB)
        scur = sconn.cursor()
        _apply_build_pragmas(scur)
        scur.execute(SQL_CREATE_TRIGRAMS)
        scur.execute(SQL_DELETE_TRIGRAMS)
        scur.execute(SQL_INDEX_TRIGRAM)
        sconn.commit()

        conn = _mysql.connect(**_TOKEN_DB_CFG, buffered=False)
        cur = conn.cursor()
        cur.execute(SQL_SELECT_LINE_TEXT)
        _debug("building trigram SQLite cache (streaming UPSERT)…")
        rows_fetched = 0
        while True:
            rows = cur.fetchmany(MYSQL_FETCH_BATCH)
            if not rows:
                break
            batch = Counter()
            for (line_text,) in rows:
                if not line_text:
                    continue
                words = _tokenize(line_text)
                for i in range(len(words) - 2):
                    batch[(words[i], words[i + 1], words[i + 2])] += 1
                rows_fetched += 1
            if batch:
                scur.executemany(SQL_UPSERT_TRIGRAM,
                                 [(w1, w2, w3, f) for (w1, w2, w3), f in batch.items()])
                sconn.commit()
            yield ("trigrams_progress", rows_fetched)
        conn.close()
        sconn.close()
        _debug(f"streamed trigrams from {rows_fetched} lines to SQLite")
        yield ("trigrams_done", _AC_DB)
    except Exception as ex:
        _debug(f"trigram build failed: {ex}")
        yield ("trigrams_done", None)


def LoadAutocomplete():
    """Generator — yields progress for word_freq, bigrams, then trigrams.
    Phases: word_freq_done, bigrams_progress, bigrams_done, trigrams_progress, trigrams_done.
    Runtime never loads tables into RAM — only opens SQLite connection.
    """
    for phase, data in LoadWordFreqChunked():
        yield (phase, data)
    for phase, data in LoadBigramsChunked():
        yield (phase, data)
    for phase, data in LoadTrigramsChunked():
        yield (phase, data)
    yield ("all_done", _AC_DB)


def _mysql_search(keyword: str, limit: int = MYSQL_SEARCH_LIMIT):
    """Search all text columns across all tables in vb_shared.
    Returns list of strings: 'table_name | column | value_snippet'."""
    if not keyword.strip():
        # No query → show table list as starting point
        try:
            conn = _mysql.connect(**_MYSQL_CFG)
            cur = conn.cursor()
            cur.execute(SQL_SHOW_TABLES)
            tables = [r[0] for r in cur.fetchall()]
            conn.close()
            return [f"[table] {t}" for t in sorted(tables)]
        except Exception:
            return ["(mysql not available)"]

    kw = f"%{keyword}%"
    hits = []
    try:
        conn = _mysql.connect(**_MYSQL_CFG)
        cur = conn.cursor()

        # Get all tables
        cur.execute(SQL_SHOW_TABLES)
        tables = [r[0] for r in cur.fetchall()]

        for table in tables:
            if len(hits) >= limit:
                break
            # Get text columns for this table
            cur.execute(
                SQL_SELECT_COLUMNS,
                (DB_NAME_VB_SHARED, table),
            )
            text_cols = [r[0] for r in cur.fetchall()
                         if r[1].lower() in _TEXT_TYPES]
            if not text_cols:
                continue

            # Build LIKE query across all text columns
            like_clause = " OR ".join([f"`{c}` LIKE %s" for c in text_cols])
            sql = (f"SELECT * FROM `{table}` WHERE {like_clause} LIMIT {MYSQL_TABLE_HITS}")
            params = [kw] * len(text_cols)

            try:
                cur.execute(sql, params)
                for row in cur.fetchall():
                    if len(hits) >= limit:
                        break
                    # Find which column matched
                    snippet = ""
                    for i, col in enumerate(text_cols):
                        val = row[i] if i < len(row) else ""
                        if val and keyword.lower() in str(val).lower():
                            snippet = str(val)[:MYSQL_SNIPPET_LENGTH]
                            break
                    hits.append(f"{table} | {snippet}")
            except Exception:
                continue

        conn.close()
    except Exception as ex:
        return [f"(mysql error: {ex})"]

    return hits if hits else ["(no matches)"]


def search_source(query: str):
    """Smart search — scans all MySQL tables like mysql_cli_search.py."""
    return _mysql_search(query)


def FetchTableContents(table, offset=0, limit=TABLE_VIEWER_PAGE_SIZE):
    """Fetch a page of rows from a MySQL table for the GUI table viewer (TASK-069).
    Returns (columns, rows, total_rows) or ([], [], 0) on error.
    - columns: list of column names
    - rows: list of tuples (the fetched page)
    - total_rows: total row count in the table (for pagination)
    """
    if not table or not re.match(r'^[A-Za-z0-9_]+$', table):
        _debug(f"FetchTableContents: invalid table name '{table}'")
        return ([], [], 0)
    try:
        conn = _mysql.connect(**_MYSQL_CFG)
        cur = conn.cursor()
        cur.execute(SQL_COUNT_TABLE_ROWS.format(table=table))
        total_rows = cur.fetchone()[0]
        cur.execute(
            SQL_SELECT_TABLE_CONTENTS.format(table=table, limit=int(limit), offset=int(offset))
        )
        columns = [desc[0] for desc in cur.description] if cur.description else []
        rows = cur.fetchall()
        conn.close()
        return (columns, rows, total_rows)
    except Exception as ex:
        _debug(f"FetchTableContents failed for '{table}': {ex}")
        return ([], [], 0)


class SmartSearch:
    """Smart search engine — MySQL all-table scan + EFL DB search. No classification, no GUI."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "mysql_host": DB_HOST_LOCALHOST,
                "mysql_user": DB_USER_ROOT,
                "mysql_database": DB_NAME_VB_SHARED,
                "mysql_charset": DB_CHARSET_UTF8MB4,
                "token_registry_db": DB_NAME_TOKEN_REGISTRY,
                "efl_db": str(BASE_DIR.parent / DB_PATH_EFL_BRAIN),
                "find_list": str(BASE_DIR.parent / "Sql_Schema_Config" / "Find_list.py"),
            },
            "find_list": None,
            "results": [],
            "memunit": mem,
            "db_manager": db,
        }
        if param and isinstance(param, dict):
            self.state["config"].update(param)

    def Run(self, command, params=None):
        if command == CMD_SEARCH:
            return self.Search(params)
        elif command == CMD_EFL_SEARCH:
            return self.EflSearch(params)
        elif command == CMD_FIND_LIST:
            return self.FindList(params)
        elif command == CMD_REPORT:
            return self.Report(params)
        elif command == CMD_READ_STATE:
            return self.ReadState()
        elif command == CMD_SET_CONFIG:
            return self.SetConfig(params)
        else:
            return (0, None, (ERR_UNKNOWN_COMMAND, f"Unknown: {command}", 0))

    def MysqlConn(self):
        import mysql.connector
        return mysql.connector.connect(
            host=self.state["config"]["mysql_host"],
            user=self.state["config"]["mysql_user"],
            database=self.state["config"]["mysql_database"],
            charset=self.state["config"]["mysql_charset"],
            autocommit=MYSQL_AUTOCOMMIT,
        )

    def Search(self, params):
        """Search all text columns across all tables in vb_shared.
        Returns list of strings: 'table_name | value_snippet'."""
        if not params or "query" not in params:
            return (0, None, (ERR_MISSING_PARAM, "query required", 0))
        query = params["query"]
        limit = params.get("limit", MYSQL_SEARCH_LIMIT)
        try:
            conn = self.MysqlConn()
            cur = conn.cursor()

            if not query.strip():
                cur.execute(SQL_SHOW_TABLES)
                tables = [r[0] for r in cur.fetchall()]
                conn.close()
                results = [f"[table] {t}" for t in sorted(tables)]
                return (1, {"query": query, "count": len(results), "results": results, "source": SOURCE_MYSQL}, None)

            kw = f"%{query}%"
            hits = []
            cur.execute(SQL_SHOW_TABLES)
            tables = [r[0] for r in cur.fetchall()]

            for table in tables:
                if len(hits) >= limit:
                    break
                cur.execute(
                    SQL_SELECT_COLUMNS,
                    (self.state["config"]["mysql_database"], table),
                )
                text_cols = [r[0] for r in cur.fetchall() if r[1].lower() in TEXT_TYPES_SET]
                if not text_cols:
                    continue

                like_clause = " OR ".join([f"`{c}` LIKE %s" for c in text_cols])
                sql = f"SELECT * FROM `{table}` WHERE {like_clause} LIMIT {MYSQL_TABLE_HITS}"
                sql_params = [kw] * len(text_cols)

                try:
                    cur.execute(sql, sql_params)
                    for row in cur.fetchall():
                        if len(hits) >= limit:
                            break
                        snippet = ""
                        for i, col in enumerate(text_cols):
                            val = row[i] if i < len(row) else ""
                            if val and query.lower() in str(val).lower():
                                snippet = str(val)[:MYSQL_SNIPPET_LENGTH]
                                break
                        hits.append(f"{table} | {snippet}")
                except Exception:
                    continue

            conn.close()
            if not hits:
                hits = ["(no matches)"]
            return (1, {"query": query, "count": len(hits), "results": hits, "source": SOURCE_MYSQL}, None)
        except Exception as ex:
            return (0, None, (ERR_MYSQL_ERROR, str(ex), 0))

    def EflSearch(self, params):
        """Search EFL DB classes by keyword. Returns list of {id, class_name, domain, method_count}."""
        if not params or "query" not in params:
            return (0, None, (ERR_MISSING_PARAM, "query required", 0))
        query = params["query"]
        limit = params.get("limit", DEFAULT_EFL_SEARCH_LIMIT)
        db_path = self.state["config"]["efl_db"]
        if not os.path.exists(db_path):
            return (0, None, (ERR_EFL_DB_MISSING, f"Not found: {db_path}", 0))
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            kw = f"%{query}%"
            cur.execute(
                SQL_SELECT_EFL_CLASSES,
                (kw, kw, kw, limit)
            )
            rows = cur.fetchall()
            conn.close()
            results = []
            for row in rows:
                cid, name, domain, mc = row
                results.append({"id": cid, "class_name": name, "domain": domain, "method_count": mc})
            return (1, {"query": query, "count": len(results), "results": results, "source": SOURCE_EFL}, None)
        except Exception as ex:
            return (0, None, (ERR_EFL_DB_ERROR, str(ex), 0))

    def LoadFindList(self):
        """Load Find_list.py as dynamic module."""
        if self.state["find_list"] is not None:
            return self.state["find_list"]
        path = self.state["config"]["find_list"]
        if not os.path.exists(path):
            return None
        spec = importlib.util.spec_from_file_location("Find_list", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.state["find_list"] = mod
        return mod

    def FindList(self, params):
        """Return Find_list.py matches for a query."""
        if not params or "query" not in params:
            return (0, None, (ERR_MISSING_PARAM, "query required", 0))
        query = params["query"]
        fl = self.LoadFindList()
        if fl is None:
            return (0, None, (ERR_LOAD_FAILED, "Could not load Find_list.py", 0))
        matches = []
        all_matches = getattr(fl, "matches", []) + getattr(fl, "search_2_matches", [])
        for m in all_matches:
            if query.lower() in m.get("class_name", "").lower():
                matches.append(m)
        return (1, {"query": query, "count": len(matches), "matches": matches}, None)

    def Report(self, params):
        """Generate a markdown report of search results."""
        if not params or "query" not in params:
            return (0, None, (ERR_MISSING_PARAM, "query required", 0))
        query = params["query"]
        ok, mysql_data, mysql_err = self.Search({"query": query, "limit": MYSQL_SEARCH_LIMIT})
        ok2, efl_data, efl_err = self.EflSearch({"query": query, "limit": DEFAULT_EFL_SEARCH_LIMIT})
        lines = []
        lines.append(f"# Search Report: {query}")
        lines.append("")
        if mysql_err:
            lines.append(f"## MySQL: ERROR — {mysql_err[1]}")
        else:
            lines.append(f"## MySQL ({mysql_data['count']} hits)")
            for r in mysql_data["results"]:
                lines.append(f"- {r}")
        lines.append("")
        if efl_err:
            lines.append(f"## EFL DB: ERROR — {efl_err[1]}")
        else:
            lines.append(f"## EFL DB ({efl_data['count']} hits)")
            for r in efl_data["results"]:
                lines.append(f"- **id={r['id']}** {r['class_name']} (domain={r['domain']}, methods={r['method_count']})")
        return (1, {"query": query, "report": "\n".join(lines)}, None)

    def ReadState(self):
        return (1, {"config": self.state["config"]}, None)

    def SetConfig(self, params):
        if not params:
            return (0, None, (ERR_MISSING_PARAM, "key and value required", 0))
        key = params.get("key", "")
        value = params.get("value", "")
        if not key:
            return (0, None, (ERR_MISSING_KEY, "key required", 0))
        self.state["config"][key] = value
        return (1, {"key": key, "value": value}, None)
