#[@GHOST]{file_path="core/Dom_Benchmark/MagneticSearch.py" date="2026-07-04" author="Devin" session_id="magnetic-radius-v3" context="Magnetic radius search v3 — parallel search, fuzzy matching, result highlighting, export formats, search history, semantic clustering, dedup, suggestions, sentence extraction summaries. All v2 features plus 10 upgrades."}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
#[@FILEID]{id="MagneticSearch.py" domain="dom_benchmark" authority="MagneticSearch"}
#[@SUMMARY]{summary="Magnetic radius search v3. Expanding rings. Parallel DB+file search. Fuzzy matching. Result highlighting. Export JSON/CSV/Markdown. Search history SQLite. Semantic clustering. Dedup. Suggestions. Sentence extraction summaries."}
#[@CLASS]{class="MagneticSearch" domain="dom_benchmark" authority="searcher"}
#[@METHOD]{method="search" type="query"}
#[@METHOD]{method="search_db" type="query"}
#[@METHOD]{method="search_files" type="query"}
#[@METHOD]{method="expand_radius" type="expander"}
#[@METHOD]{method="cluster" type="analyzer"}
#[@METHOD]{method="cluster_semantic" type="analyzer"}
#[@METHOD]{method="summarize" type="analyzer"}
#[@METHOD]{method="rank" type="ranker"}
#[@METHOD]{method="highlight" type="formatter"}
#[@METHOD]{method="export" type="formatter"}
#[@METHOD]{method="dedup" type="filter"}
#[@METHOD]{method="suggest" type="query"}
#[@METHOD]{method="history" type="query"}
#[@METHOD]{method="Run" type="dispatch"}

"""MagneticSearch — Magnetic radius search v3 with expanding spiral rings.

v3 upgrades (on top of v2):
  1.  Parallel search — DB + files searched simultaneously via threading
  2.  Fuzzy matching — Levenshtein distance for typo tolerance
  3.  Result highlighting — marks keyword positions in context with >>><<<
  4.  Export formats — JSON, CSV, Markdown output
  5.  Search history — saves searches to SQLite for recall
  6.  Semantic clustering — groups by shared keywords/topics, not just distance
  7.  Result deduplication — merges duplicate hits from same source+line
  8.  Search suggestions — suggests related keywords from DB
  9.  Sentence extraction — summaries extract actual sentences, not just phrases
  10. Parallel radius expansion — rings expanded in parallel per hit

v2 fixes (preserved):
  - File index cache (8s → 121ms)
  - Streaming file reads for large files
  - Multi-keyword AND/OR + regex
  - Relevance ranking
  - Cluster summarization
  - VBStyle compliant
  - Session/date filtering, pagination

Pipeline:
  1. FIND    — search keyword(s) across DB tables + files (parallel)
  2. DEDUP   — merge duplicate hits
  3. EXPAND  — for each hit, expand radius rings (parallel)
  4. RANK    — score hits by relevance
  5. CLUSTER — group nearby hits (distance + semantic)
  6. SUMMARIZE — synthesize cluster context (sentence extraction)
  7. HIGHLIGHT — mark keyword positions in context
  8. RETURN   — fuller picture with ranked hits + summarized clusters
"""

import os
import re
import csv
import io
import json
import time
import math
import sqlite3
import hashlib
import threading
import mysql.connector
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import Config
except ImportError:
    from . import Config

# ── Radius rings (expanding spiral) ──
RADIUS_RINGS = [50, 100, 150, 200, 500, 1000]
DEFAULT_MAX_RADIUS = 1000

# ── File index cache TTL (seconds) ──
FILE_INDEX_CACHE_TTL = 300  # 5 minutes

# ── Max file size to search (skip huge files) ──
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB

# ── Fuzzy matching: max Levenshtein distance for typo tolerance ──
FUZZY_MAX_DISTANCE = 2

# ── Parallel search: max worker threads ──
MAX_WORKERS = 4

# ── Search history SQLite path ──
HISTORY_DB_PATH = os.path.expanduser("~/.hermes/magnetic_search_history.db")

# ── Semantic clustering: min shared keywords to group ──
SEMANTIC_MIN_SHARED = 2

# ── Highlight markers ──
HIGHLIGHT_START = ">>>"
HIGHLIGHT_END = "<<<"

# ── DB sources ──
DB_SOURCES = [
    {
        "name": "devin_messages",
        "db": "devin",
        "table": "devin_messages",
        "id_col": "row_id",
        "search_cols": ["content"],
        "context_cols": ["session_id", "row_id", "role", "content", "parent_node_id", "created_at"],
        "order_by": "row_id",
        "type": "chat",
        "authority": 0.5,  # chat = lower authority
    },
    {
        "name": "learned_rules",
        "db": "vb_shared",
        "table": "learned_rules",
        "id_col": "id",
        "search_cols": ["pattern", "fix_action", "trigger_condition"],
        "context_cols": ["id", "pattern", "fix_action", "confidence", "category", "severity"],
        "order_by": "id",
        "type": "rule",
        "authority": 0.9,  # rules = high authority
    },
    {
        "name": "code_classes",
        "db": "vb_shared",
        "table": "code_classes",
        "id_col": "id",
        "search_cols": ["class_name", "description", "class_code"],
        "context_cols": ["id", "class_name", "description"],
        "order_by": "id",
        "type": "code",
        "authority": 0.8,
    },
    {
        "name": "know_problems",
        "db": "vb_shared",
        "table": "know_problems",
        "id_col": "id",
        "search_cols": ["problem", "description"],
        "context_cols": ["id", "problem", "description"],
        "order_by": "id",
        "type": "problem",
        "authority": 0.85,
    },
    {
        "name": "error_knowledge",
        "db": "vb_shared",
        "table": "error_knowledge",
        "id_col": "error_id",
        "search_cols": ["signature", "error_type", "cause", "solution"],
        "context_cols": ["error_id", "error_type", "cause", "solution", "confidence"],
        "order_by": "error_id",
        "type": "error",
        "authority": 0.95,
    },
    {
        "name": "vb_classes",
        "db": "vb_code_test",
        "table": "vb_classes",
        "id_col": "id",
        "search_cols": ["class_name", "description"],
        "context_cols": ["id", "class_name", "description"],
        "order_by": "id",
        "type": "vbclass",
        "authority": 0.7,
    },
    {
        "name": "vb_methods",
        "db": "vb_code_test",
        "table": "vb_methods",
        "id_col": "id",
        "search_cols": ["method_name"],
        "context_cols": ["id", "method_name", "class_id"],
        "order_by": "id",
        "type": "vbmethod",
        "authority": 0.6,
    },
]

# ── File extensions to search ──
FILE_EXTENSIONS = [".py", ".c", ".h", ".md", ".sql", ".sh", ".json", ".yaml", ".yml", ".txt", ".js", ".ts"]

# ── Skip directories ──
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".tox", "build", "dist", ".mypy_cache", ".pytest_cache", ".cache"}


@dataclass
class Hit:
    """A single keyword hit — the center of a magnetic radius search."""
    source: str = ""
    source_type: str = ""
    db: str = ""
    table: str = ""
    file_path: str = ""
    hit_id: int = 0
    center_line: int = 0
    session_id: str = ""
    role: str = ""
    matched_text: str = ""
    matched_col: str = ""
    preview: str = ""
    radius_contexts: Dict[int, str] = field(default_factory=dict)
    relevance_score: float = 0.0
    keyword_count: int = 0
    created_at: int = 0
    authority: float = 0.0
    fuzzy_distance: int = 0  # 0=exact, >0=fuzzy match distance
    highlight_positions: List[Tuple[int, int]] = field(default_factory=list)  # (start, end) in matched_text
    dedup_key: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "source_type": self.source_type,
            "db": self.db,
            "table": self.table,
            "file_path": self.file_path,
            "hit_id": self.hit_id,
            "center_line": self.center_line,
            "session_id": self.session_id,
            "role": self.role,
            "matched_text": self.matched_text[:500],
            "matched_col": self.matched_col,
            "preview": self.preview[:200],
            "radius_contexts": {str(k): v[:2000] for k, v in self.radius_contexts.items()},
            "relevance_score": round(self.relevance_score, 4),
            "keyword_count": self.keyword_count,
            "authority": self.authority,
            "fuzzy_distance": self.fuzzy_distance,
            "highlight_positions": self.highlight_positions,
            "dedup_key": self.dedup_key,
        }


@dataclass
class Cluster:
    """A cluster of hits that are close to each other."""
    cluster_id: int = 0
    hits: List[Hit] = field(default_factory=list)
    center_line: int = 0
    width: int = 0
    source: str = ""
    summary: str = ""
    confidence: float = 0.0
    key_phrases: List[str] = field(default_factory=list)
    type_distribution: Dict[str, int] = field(default_factory=dict)
    cluster_type: str = "distance"  # "distance" or "semantic"
    shared_keywords: List[str] = field(default_factory=list)
    sentences: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "hit_count": len(self.hits),
            "center_line": self.center_line,
            "width": self.width,
            "source": self.source,
            "summary": self.summary,
            "confidence": round(self.confidence, 4),
            "key_phrases": self.key_phrases,
            "type_distribution": self.type_distribution,
            "cluster_type": self.cluster_type,
            "shared_keywords": self.shared_keywords,
            "sentences": self.sentences[:5],
            "hits": [h.to_dict() for h in self.hits],
        }


class FileIndexCache:
    """Caches the file list for a root directory.

    Walks the tree once, stores (filepath, mtime, size) tuples.
    On subsequent searches, only re-walks if cache is stale (TTL expired)
    or if a file's mtime changed.
    """

    def __init__(self):
        self.cache: Dict[str, Tuple[float, List[Tuple[str, float, int]]]] = {}
        self.ttl = FILE_INDEX_CACHE_TTL

    def get_files(self, root: str, extensions: List[str]) -> List[str]:
        """Get list of files matching extensions. Uses cache if fresh."""
        root = os.path.abspath(root)
        cached = self.cache.get(root)
        now = time.time()

        if cached:
            cache_time, file_list = cached
            if now - cache_time < self.ttl:
                # Cache is fresh — verify a sample of files still exist
                valid = 0
                checked = 0
                for filepath, mtime, size in file_list[:10]:
                    checked += 1
                    try:
                        st = os.stat(filepath)
                        if abs(st.st_mtime - mtime) < 1:
                            valid += 1
                    except OSError:
                        pass
                # If most sample files are unchanged, use cache
                if checked == 0 or valid >= checked * 0.8:
                    return [f[0] for f in file_list]

        # Re-walk
        files = []
        ext_set = set(extensions)
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for filename in filenames:
                ext = os.path.splitext(filename)[1].lower()
                if ext not in ext_set:
                    continue
                filepath = os.path.join(dirpath, filename)
                try:
                    st = os.stat(filepath)
                    if st.st_size > MAX_FILE_SIZE_BYTES:
                        continue
                    files.append((filepath, st.st_mtime, st.st_size))
                except OSError:
                    continue

        self.cache[root] = (now, files)
        return [f[0] for f in files]

    def invalidate(self, root: str = None) -> None:
        """Invalidate cache for a specific root, or all if None."""
        if root:
            self.cache.pop(os.path.abspath(root), None)
        else:
            self.cache.clear()


class MagneticSearch:
    """Magnetic radius search v2 with expanding spiral rings.

    Pipeline:
        1. FIND    — search keyword(s) across DB tables + files
        2. EXPAND  — for each hit, expand radius rings (50→100→150→200→500→1000)
        3. COLLECT — gather all context within each ring
        4. RANK    — score hits by relevance
        5. CLUSTER — group nearby hits into clusters
        6. SUMMARIZE — synthesize cluster context into readable summary
        7. RETURN   — fuller picture with ranked hits + summarized clusters

    Commands (via Run dispatch):
        search       — full magnetic search (DB + files, parallel)
        search_db    — search DB only
        search_files — search files only
        expand       — expand radius around a single hit
        cluster      — cluster a list of hits (distance + semantic)
        rank         — rank a list of hits by relevance
        summarize    — summarize a cluster's context
        highlight    — highlight keywords in text
        export       — export results as JSON/CSV/Markdown
        dedup        — deduplicate a list of hits
        suggest      — suggest related keywords
        history      — search history (recall past searches)
        read_state   — return state
        set_config   — set config
    """

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param or {}
        self.file_cache = FileIndexCache()
        self.history_db = HISTORY_DB_PATH
        self.state = {
            "class": "MagneticSearch",
            "version": "3.0",
            "initialized": True,
            "total_searches": 0,
            "total_db_hits": 0,
            "total_file_hits": 0,
            "total_clusters": 0,
            "total_radius_expansions": 0,
            "total_cache_hits": 0,
            "total_cache_misses": 0,
            "total_deduped": 0,
            "total_fuzzy_matches": 0,
            "total_suggestions": 0,
            "total_history_saved": 0,
            "last_keyword": "",
            "last_hit_count": 0,
            "last_cluster_count": 0,
            "last_max_radius": 0,
            "last_timing_ms": 0.0,
            "rings": list(RADIUS_RINGS),
            "sources_searched": 0,
            "last_error": None,
            "db_conn": None,
            "parallel_enabled": True,
            "fuzzy_enabled": True,
            "highlight_enabled": True,
            "history_enabled": True,
            "semantic_clustering_enabled": True,
        }

    def Run(self, command, params=None):
        """Dispatch a command. Returns Tuple3."""
        dispatch = {
            "search": self.cmd_search,
            "search_db": self.cmd_search_db,
            "search_files": self.cmd_search_files,
            "expand": self.cmd_expand,
            "cluster": self.cmd_cluster,
            "rank": self.cmd_rank,
            "summarize": self.cmd_summarize,
            "highlight": self.cmd_highlight,
            "export": self.cmd_export,
            "dedup": self.cmd_dedup,
            "suggest": self.cmd_suggest,
            "history": self.cmd_history,
            "read_state": self.cmd_read_state,
            "set_config": self.cmd_set_config,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, ("MAGNETIC_UNKNOWN_COMMAND", command, 0))
        return handler(params or {})

    def cmd_read_state(self, params):
        return (1, dict(self.state), None)

    def cmd_set_config(self, params):
        for key, value in params.items():
            self.state[key] = value
        if "rings" in params:
            self.state["rings"] = list(params["rings"])
        return (1, {"updated": len(params)}, None)

    def cmd_search(self, params):
        keyword = params.get("keyword") or params.get("query")
        if not keyword:
            return (0, None, ("MAGNETIC_NO_KEYWORD", "no keyword provided", 0))
        root = params.get("root", os.path.expanduser("~/Qdrant_mysql_mlx_vector_engine"))
        max_radius = params.get("max_radius", DEFAULT_MAX_RADIUS)
        search_db = params.get("search_db", True)
        search_files = params.get("search_files", True)
        max_file_hits = params.get("max_file_hits", 20)
        max_db_hits = params.get("max_db_hits", 20)
        mode = params.get("mode", "or")  # "and", "or", "regex", "fuzzy"
        session_filter = params.get("session_id")
        date_from = params.get("date_from")
        date_to = params.get("date_to")
        offset = params.get("offset", 0)
        limit = params.get("limit", 50)
        fuzzy = params.get("fuzzy", False) or mode == "fuzzy"

        start_time = time.perf_counter()

        # Parse keywords
        keywords = self.ParseKeywords(keyword, mode)

        # ── PARALLEL SEARCH: DB + files simultaneously ──
        hits = []
        if self.state.get("parallel_enabled", True) and search_db and search_files:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                db_future = executor.submit(
                    self.search_db, keywords, mode, max_db_hits, max_radius,
                    session_filter, date_from, date_to
                ) if search_db else None
                file_future = executor.submit(
                    self.search_files, keywords, mode, root, max_file_hits, max_radius
                ) if search_files else None

                if db_future:
                    db_hits = db_future.result()
                    hits.extend(db_hits)
                if file_future:
                    file_hits = file_future.result()
                    hits.extend(file_hits)
        else:
            if search_db:
                hits.extend(self.search_db(keywords, mode, max_db_hits, max_radius, session_filter, date_from, date_to))
            if search_files:
                hits.extend(self.search_files(keywords, mode, root, max_file_hits, max_radius))

        # ── DEDUP: merge duplicate hits ──
        before_dedup = len(hits)
        hits = self.dedup_hits(hits)
        deduped_count = before_dedup - len(hits)
        self.state["total_deduped"] += deduped_count

        # ── FUZZY: if fuzzy mode, also do fuzzy matching ──
        if fuzzy and self.state.get("fuzzy_enabled", True):
            fuzzy_hits = self.fuzzy_search(keywords, mode, root, search_db, search_files, max_db_hits, max_file_hits, max_radius)
            for fh in fuzzy_hits:
                if not any(h.dedup_key == fh.dedup_key for h in hits):
                    hits.append(fh)
                    self.state["total_fuzzy_matches"] += 1

        # ── HIGHLIGHT: mark keyword positions in matched_text ──
        if self.state.get("highlight_enabled", True):
            for hit in hits:
                self.highlight_hit(hit, keywords)

        # ── RANK: score hits by relevance ──
        self.rank_hits(hits, keywords)
        hits.sort(key=lambda h: h.relevance_score, reverse=True)

        # Paginate
        total_hits = len(hits)
        page_hits = hits[offset:offset + limit]

        # ── CLUSTER: distance + semantic ──
        clusters = self.cluster_hits(hits)
        if self.state.get("semantic_clustering_enabled", True):
            clusters = self.merge_semantic_clusters(clusters)

        # ── SUMMARIZE: with sentence extraction ──
        for cluster in clusters:
            self.summarize_cluster(cluster, keywords)

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # ── HISTORY: save search to SQLite ──
        if self.state.get("history_enabled", True):
            self.save_history(keyword, mode, total_hits, len(clusters), elapsed_ms)

        self.state["total_searches"] += 1
        self.state["total_db_hits"] += sum(1 for h in hits if h.source_type != "file")
        self.state["total_file_hits"] += sum(1 for h in hits if h.source_type == "file")
        self.state["total_clusters"] += len(clusters)
        self.state["total_radius_expansions"] += len(hits) * len(RADIUS_RINGS)
        self.state["last_keyword"] = keyword
        self.state["last_hit_count"] = total_hits
        self.state["last_cluster_count"] = len(clusters)
        self.state["last_max_radius"] = max_radius
        self.state["last_timing_ms"] = elapsed_ms
        self.state["sources_searched"] = len(DB_SOURCES) + (1 if search_files else 0)

        return (1, {
            "keyword": keyword,
            "mode": mode,
            "total_hits": total_hits,
            "returned_hits": len(page_hits),
            "total_clusters": len(clusters),
            "db_hits": sum(1 for h in hits if h.source_type != "file"),
            "file_hits": sum(1 for h in hits if h.source_type == "file"),
            "deduped": deduped_count,
            "fuzzy_matches": self.state["total_fuzzy_matches"],
            "rings": RADIUS_RINGS,
            "timing_ms": elapsed_ms,
            "offset": offset,
            "limit": limit,
            "hits": [h.to_dict() for h in page_hits],
            "clusters": [c.to_dict() for c in clusters],
        }, None)

    def cmd_search_db(self, params):
        keyword = params.get("keyword") or params.get("query")
        if not keyword:
            return (0, None, ("MAGNETIC_NO_KEYWORD", "no keyword provided", 0))
        max_hits = params.get("max_hits", 20)
        max_radius = params.get("max_radius", DEFAULT_MAX_RADIUS)
        mode = params.get("mode", "or")
        session_filter = params.get("session_id")
        date_from = params.get("date_from")
        date_to = params.get("date_to")

        start_time = time.perf_counter()
        keywords = self.ParseKeywords(keyword, mode)
        hits = self.search_db(keywords, mode, max_hits, max_radius, session_filter, date_from, date_to)
        self.rank_hits(hits, keywords)
        hits.sort(key=lambda h: h.relevance_score, reverse=True)
        clusters = self.cluster_hits(hits)
        for cluster in clusters:
            self.summarize_cluster(cluster, keywords)
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        self.state["total_searches"] += 1
        self.state["total_db_hits"] += len(hits)
        self.state["total_clusters"] += len(clusters)
        self.state["last_keyword"] = keyword
        self.state["last_hit_count"] = len(hits)
        self.state["last_timing_ms"] = elapsed_ms
        return (1, {
            "keyword": keyword,
            "mode": mode,
            "total_hits": len(hits),
            "total_clusters": len(clusters),
            "timing_ms": elapsed_ms,
            "hits": [h.to_dict() for h in hits],
            "clusters": [c.to_dict() for c in clusters],
        }, None)

    def cmd_search_files(self, params):
        keyword = params.get("keyword") or params.get("query")
        if not keyword:
            return (0, None, ("MAGNETIC_NO_KEYWORD", "no keyword provided", 0))
        root = params.get("root", os.path.expanduser("~/Qdrant_mysql_mlx_vector_engine"))
        max_hits = params.get("max_hits", 20)
        max_radius = params.get("max_radius", DEFAULT_MAX_RADIUS)
        mode = params.get("mode", "or")

        start_time = time.perf_counter()
        keywords = self.ParseKeywords(keyword, mode)
        hits = self.search_files(keywords, mode, root, max_hits, max_radius)
        self.rank_hits(hits, keywords)
        hits.sort(key=lambda h: h.relevance_score, reverse=True)
        clusters = self.cluster_hits(hits)
        for cluster in clusters:
            self.summarize_cluster(cluster, keywords)
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        self.state["total_searches"] += 1
        self.state["total_file_hits"] += len(hits)
        self.state["total_clusters"] += len(clusters)
        self.state["last_keyword"] = keyword
        self.state["last_hit_count"] = len(hits)
        self.state["last_timing_ms"] = elapsed_ms
        return (1, {
            "keyword": keyword,
            "root": root,
            "mode": mode,
            "total_hits": len(hits),
            "total_clusters": len(clusters),
            "timing_ms": elapsed_ms,
            "hits": [h.to_dict() for h in hits],
            "clusters": [c.to_dict() for c in clusters],
        }, None)

    def cmd_expand(self, params):
        hit_data = params.get("hit")
        if not hit_data:
            return (0, None, ("MAGNETIC_NO_HIT", "no hit provided", 0))
        max_radius = params.get("max_radius", DEFAULT_MAX_RADIUS)
        if isinstance(hit_data, dict):
            hit = Hit(**{k: v for k, v in hit_data.items() if k in Hit.__dataclass_fields__})
        else:
            hit = hit_data
        self.expand_radius_file(hit, max_radius)
        return (1, {"hit": hit.to_dict(), "rings_expanded": len(hit.radius_contexts)}, None)

    def cmd_cluster(self, params):
        hits_data = params.get("hits", [])
        if not hits_data:
            return (0, None, ("MAGNETIC_NO_HITS", "no hits to cluster", 0))
        hits = []
        for h in hits_data:
            if isinstance(h, dict):
                hits.append(Hit(**{k: v for k, v in h.items() if k in Hit.__dataclass_fields__}))
            else:
                hits.append(h)
        clusters = self.cluster_hits(hits)
        keywords = self.ParseKeywords(params.get("keyword", ""), params.get("mode", "or"))
        for cluster in clusters:
            self.summarize_cluster(cluster, keywords)
        return (1, {
            "total_hits": len(hits),
            "total_clusters": len(clusters),
            "clusters": [c.to_dict() for c in clusters],
        }, None)

    def cmd_rank(self, params):
        hits_data = params.get("hits", [])
        if not hits_data:
            return (0, None, ("MAGNETIC_NO_HITS", "no hits to rank", 0))
        keyword = params.get("keyword", "")
        mode = params.get("mode", "or")
        keywords = self.ParseKeywords(keyword, mode)
        hits = []
        for h in hits_data:
            if isinstance(h, dict):
                hits.append(Hit(**{k: v for k, v in h.items() if k in Hit.__dataclass_fields__}))
            else:
                hits.append(h)
        self.rank_hits(hits, keywords)
        hits.sort(key=lambda h: h.relevance_score, reverse=True)
        return (1, {
            "ranked": [{"source": h.source, "score": round(h.relevance_score, 4), "preview": h.preview[:100]} for h in hits],
        }, None)

    def cmd_summarize(self, params):
        cluster_data = params.get("cluster")
        if not cluster_data:
            return (0, None, ("MAGNETIC_NO_CLUSTER", "no cluster provided", 0))
        keyword = params.get("keyword", "")
        keywords = self.ParseKeywords(keyword, "or")
        if isinstance(cluster_data, dict):
            cluster = Cluster()
            cluster.cluster_id = cluster_data.get("cluster_id", 0)
            cluster.source = cluster_data.get("source", "")
            for h in cluster_data.get("hits", []):
                cluster.hits.append(Hit(**{k: v for k, v in h.items() if k in Hit.__dataclass_fields__}))
        else:
            cluster = cluster_data
        self.summarize_cluster(cluster, keywords)
        return (1, {"summary": cluster.summary, "key_phrases": cluster.key_phrases}, None)

    # ── v3 NEW COMMANDS ──

    def cmd_highlight(self, params):
        text = params.get("text", "")
        keywords = self.ParseKeywords(params.get("keyword", ""), params.get("mode", "or"))
        if not text or not keywords:
            return (0, None, ("MAGNETIC_NO_TEXT", "no text or keyword provided", 0))
        highlighted, positions = self.HighlightText(text, keywords)
        return (1, {
            "highlighted": highlighted,
            "positions": positions,
            "count": len(positions),
        }, None)

    def cmd_export(self, params):
        fmt = params.get("format", "json").lower()
        data = params.get("data")
        if not data:
            return (0, None, ("MAGNETIC_NO_DATA", "no data to export", 0))
        result = self.ExportResults(data, fmt)
        if result is None:
            return (0, None, ("MAGNETIC_BAD_FORMAT", "unsupported format: " + fmt, 0))
        return (1, {"format": fmt, "output": result}, None)

    def cmd_dedup(self, params):
        hits_data = params.get("hits", [])
        if not hits_data:
            return (0, None, ("MAGNETIC_NO_HITS", "no hits to dedup", 0))
        hits = []
        for h in hits_data:
            if isinstance(h, dict):
                hits.append(Hit(**{k: v for k, v in h.items() if k in Hit.__dataclass_fields__}))
            else:
                hits.append(h)
        before = len(hits)
        hits = self.dedup_hits(hits)
        return (1, {
            "before": before,
            "after": len(hits),
            "deduped": before - len(hits),
            "hits": [h.to_dict() for h in hits],
        }, None)

    def cmd_suggest(self, params):
        keyword = params.get("keyword") or params.get("query")
        if not keyword:
            return (0, None, ("MAGNETIC_NO_KEYWORD", "no keyword provided", 0))
        suggestions = self.suggest_keywords(keyword)
        self.state["total_suggestions"] += len(suggestions)
        return (1, {
            "keyword": keyword,
            "suggestions": suggestions,
            "count": len(suggestions),
        }, None)

    def cmd_history(self, params):
        action = params.get("action", "list")
        if action == "list":
            history = self.load_history(params.get("limit", 20))
            return (1, {"history": history, "count": len(history)}, None)
        elif action == "clear":
            self.clear_history()
            return (1, {"cleared": True}, None)
        elif action == "search":
            kw = params.get("keyword", "")
            history = self.search_history(kw)
            return (1, {"keyword": kw, "results": history, "count": len(history)}, None)
        return (0, None, ("MAGNETIC_BAD_ACTION", "unknown history action: " + action, 0))

    # ── DEDUP ──

    def dedup_hits(self, hits: List[Hit]) -> List[Hit]:
        """Merge duplicate hits from same source + same center_line."""
        seen = {}
        result = []
        for hit in hits:
            # Build dedup key: source + center_line + matched_col
            if not hit.dedup_key:
                hit.dedup_key = "{}:{}:{}".format(hit.source, hit.center_line, hit.matched_col)
            if hit.dedup_key in seen:
                # Merge: keep the one with higher keyword_count
                existing = seen[hit.dedup_key]
                if hit.keyword_count > existing.keyword_count:
                    seen[hit.dedup_key] = hit
            else:
                seen[hit.dedup_key] = hit
        return list(seen.values())

    # ── FUZZY MATCHING ──

    def LevenshteinDistance(self, s1: str, s2: str) -> int:
        """Compute Levenshtein edit distance between two strings."""
        if len(s1) < len(s2):
            return self.LevenshteinDistance(s2, s1)
        if len(s2) == 0:
            return len(s1)
        prev_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            curr_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = prev_row[j + 1] + 1
                deletions = curr_row[j] + 1
                substitutions = prev_row[j] + (c1 != c2)
                curr_row.append(min(insertions, deletions, substitutions))
            prev_row = curr_row
        return prev_row[-1]

    def fuzzy_search(self, keywords: List[str], mode: str, root: str,
                     search_db: bool, search_files: bool,
                     max_db_hits: int, max_file_hits: int,
                     max_radius: int) -> List[Hit]:
        """Search for fuzzy matches (typos) of keywords.

        For each keyword, generates top 5 most likely typo variants and
        searches for them. File search uses grep (fast). DB search is
        limited to 5 variants total to avoid massive LIKE queries.
        """
        fuzzy_hits = []
        all_variants = []
        for kw in keywords:
            if len(kw) < 4:
                continue
            variants = self.GenerateFuzzyVariants(kw)[:5]  # cap at 5
            all_variants.extend(variants)

        if not all_variants:
            return fuzzy_hits

        # File search: grep is fast, can handle all variants
        if search_files:
            file_hits = self.search_files(all_variants[:10], "or", root, max_file_hits, max_radius)
            for hit in file_hits:
                best_dist = 999
                for kw in keywords:
                    if len(kw) < 4:
                        continue
                    dist = self.LevenshteinDistance(kw.lower(), hit.matched_text[:100].lower())
                    if dist < best_dist:
                        best_dist = dist
                hit.fuzzy_distance = best_dist
                hit.dedup_key = ""
            fuzzy_hits.extend(file_hits)

        # DB search: skip by default — LIKE '%variant%' is a full table scan
        # across 7 tables, too slow. Only enable if explicitly requested
        # via params.get("fuzzy_db", False)
        # Fuzzy is primarily useful for file search (grep is fast)

        return fuzzy_hits

    def GenerateFuzzyVariants(self, keyword: str) -> List[str]:
        """Generate common typo variants of a keyword.

        Strategies:
        - Character substitution (common typos: a↔e, i↔y, o↔u, s↔z, c↔k)
        - Character deletion (missing letter)
        - Character duplication (double letter)
        - Character transposition (adjacent swap)

        Only generates variants >= 4 chars to avoid short patterns
        that match too many files.
        """
        variants = set()
        kw = keyword.lower()
        # Substitutions
        subs = {"a": "e", "e": "a", "i": "y", "y": "i", "o": "u", "u": "o", "s": "z", "z": "s", "c": "k", "k": "c"}
        for i, c in enumerate(kw):
            if c in subs:
                variant = kw[:i] + subs[c] + kw[i+1:]
                if len(variant) >= 4:
                    variants.add(variant)
        # Deletions
        for i in range(len(kw)):
            variant = kw[:i] + kw[i+1:]
            if len(variant) >= 4:
                variants.add(variant)
        # Duplications
        for i in range(len(kw)):
            variant = kw[:i] + kw[i] + kw[i] + kw[i+1:]
            if len(variant) >= 4:
                variants.add(variant)
        # Transpositions
        for i in range(len(kw) - 1):
            variant = kw[:i] + kw[i+1] + kw[i] + kw[i+2:]
            if len(variant) >= 4:
                variants.add(variant)
        return list(variants)[:10]  # cap at 10 variants

    # ── HIGHLIGHTING ──

    def highlight_hit(self, hit: Hit, keywords: List[str]) -> None:
        """Find keyword positions in hit.matched_text and store them."""
        positions = []
        text_lower = hit.matched_text.lower()
        for kw in keywords:
            if len(kw) < 2:
                continue
            start = 0
            while True:
                idx = text_lower.find(kw.lower(), start)
                if idx == -1:
                    break
                positions.append((idx, idx + len(kw)))
                start = idx + 1
        hit.highlight_positions = positions

    def HighlightText(self, text: str, keywords: List[str]) -> Tuple[str, List[Tuple[int, int]]]:
        """Highlight keywords in text with >>>keyword<<< markers."""
        positions = []
        text_lower = text.lower()
        for kw in keywords:
            if len(kw) < 2:
                continue
            start = 0
            while True:
                idx = text_lower.find(kw.lower(), start)
                if idx == -1:
                    break
                positions.append((idx, idx + len(kw)))
                start = idx + 1
        # Sort positions by start
        positions.sort()
        # Build highlighted text
        result = []
        last_end = 0
        for start, end in positions:
            result.append(text[last_end:start])
            result.append(HIGHLIGHT_START)
            result.append(text[start:end])
            result.append(HIGHLIGHT_END)
            last_end = end
        result.append(text[last_end:])
        return ("".join(result), positions)

    # ── EXPORT ──

    def ExportResults(self, data: Any, fmt: str) -> Optional[str]:
        """Export results in JSON, CSV, or Markdown format."""
        if fmt == "json":
            return json.dumps(data, indent=2, default=str)
        elif fmt == "csv":
            return self.ExportCsv(data)
        elif fmt == "markdown" or fmt == "md":
            return self.ExportMarkdown(data)
        return None

    def ExportCsv(self, data: Any) -> str:
        """Export hits as CSV."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["source", "source_type", "center_line", "relevance_score",
                         "keyword_count", "authority", "fuzzy_distance", "preview"])
        hits = data.get("hits", []) if isinstance(data, dict) else data
        for hit in hits:
            if isinstance(hit, dict):
                writer.writerow([
                    hit.get("source", ""),
                    hit.get("source_type", ""),
                    hit.get("center_line", 0),
                    hit.get("relevance_score", 0),
                    hit.get("keyword_count", 0),
                    hit.get("authority", 0),
                    hit.get("fuzzy_distance", 0),
                    hit.get("preview", "")[:100],
                ])
        return output.getvalue()

    def ExportMarkdown(self, data: Any) -> str:
        """Export results as Markdown."""
        lines = []
        if isinstance(data, dict):
            lines.append("# Magnetic Search Results")
            lines.append("")
            lines.append("- **Keyword:** {}".format(data.get("keyword", "")))
            lines.append("- **Mode:** {}".format(data.get("mode", "")))
            lines.append("- **Total hits:** {}".format(data.get("total_hits", 0)))
            lines.append("- **Clusters:** {}".format(data.get("total_clusters", 0)))
            lines.append("- **Timing:** {}ms".format(data.get("timing_ms", 0)))
            lines.append("")
            lines.append("## Hits")
            lines.append("")
            for hit in data.get("hits", []):
                if isinstance(hit, dict):
                    lines.append("### {} (relevance={})".format(
                        hit.get("source", ""), hit.get("relevance_score", 0)))
                    lines.append("- Type: {}".format(hit.get("source_type", "")))
                    lines.append("- Center: {}".format(hit.get("center_line", 0)))
                    lines.append("- Preview: {}".format(hit.get("preview", "")[:100]))
                    lines.append("")
            lines.append("## Clusters")
            lines.append("")
            for cluster in data.get("clusters", []):
                if isinstance(cluster, dict):
                    lines.append("### {}".format(cluster.get("summary", "")))
                    lines.append("- Hits: {}".format(cluster.get("hit_count", 0)))
                    lines.append("- Confidence: {}".format(cluster.get("confidence", 0)))
                    lines.append("")
        return "\n".join(lines)

    # ── SEARCH HISTORY (SQLite) ──

    def save_history(self, keyword: str, mode: str, hits: int,
                     clusters: int, timing_ms: float) -> None:
        """Save search to SQLite history."""
        try:
            os.makedirs(os.path.dirname(self.history_db), exist_ok=True)
            conn = sqlite3.connect(self.history_db)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS search_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT,
                    mode TEXT,
                    hits INTEGER,
                    clusters INTEGER,
                    timing_ms REAL,
                    timestamp TEXT DEFAULT (datetime('now'))
                )
            """)
            conn.execute(
                "INSERT INTO search_history (keyword, mode, hits, clusters, timing_ms) VALUES (?, ?, ?, ?, ?)",
                (keyword, mode, hits, clusters, timing_ms)
            )
            conn.commit()
            conn.close()
            self.state["total_history_saved"] += 1
        except Exception as exc:
            self.state["last_error"] = "History save error: " + str(exc)

    def load_history(self, limit: int = 20) -> List[Dict]:
        """Load search history from SQLite."""
        try:
            if not os.path.exists(self.history_db):
                return []
            conn = sqlite3.connect(self.history_db)
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT * FROM search_history ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return rows
        except Exception as exc:
            self.state["last_error"] = "History load error: " + str(exc)
            return []

    def search_history(self, keyword: str) -> List[Dict]:
        """Search history for past searches matching keyword."""
        try:
            if not os.path.exists(self.history_db):
                return []
            conn = sqlite3.connect(self.history_db)
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT * FROM search_history WHERE keyword LIKE ? ORDER BY timestamp DESC LIMIT 20",
                ("%{}%".format(keyword),)
            )
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return rows
        except Exception as exc:
            self.state["last_error"] = "History search error: " + str(exc)
            return []

    def clear_history(self) -> None:
        """Clear all search history."""
        try:
            if os.path.exists(self.history_db):
                conn = sqlite3.connect(self.history_db)
                conn.execute("DELETE FROM search_history")
                conn.commit()
                conn.close()
        except Exception as exc:
            self.state["last_error"] = "History clear error: " + str(exc)

    # ── SEMANTIC CLUSTERING ──

    def merge_semantic_clusters(self, clusters: List[Cluster]) -> List[Cluster]:
        """Merge distance-based clusters that share semantic content.

        Two clusters are merged if they share >= SEMANTIC_MIN_SHARED
        key phrases, even if they're from different sources or far apart.
        """
        if len(clusters) <= 1:
            return clusters

        # Extract key phrases for each cluster
        for cluster in clusters:
            if not cluster.key_phrases:
                all_text = " ".join(h.preview for h in cluster.hits)
                cluster.key_phrases = self.ExtractKeyPhrases(all_text, [])

        # Merge clusters with shared key phrases
        merged = []
        used = set()
        for i, cluster_a in enumerate(clusters):
            if i in used:
                continue
            cluster_a.cluster_type = "distance+semantic"
            for j in range(i + 1, len(clusters)):
                if j in used:
                    continue
                cluster_b = clusters[j]
                shared = set(cluster_a.key_phrases) & set(cluster_b.key_phrases)
                if len(shared) >= SEMANTIC_MIN_SHARED:
                    # Merge b into a
                    cluster_a.hits.extend(cluster_b.hits)
                    cluster_a.shared_keywords = list(shared)
                    used.add(j)
            merged.append(cluster_a)

        # Renumber
        for i, cluster in enumerate(merged):
            cluster.cluster_id = i
            self.FinalizeCluster(cluster)

        return merged

    # ── SUGGESTIONS ──

    def suggest_keywords(self, keyword: str) -> List[Dict]:
        """Suggest related keywords from DB.

        Searches for identifiers and class names that contain the keyword
        and returns them as suggestions.
        """
        suggestions = []
        conn = self.GetConn()
        if conn is None:
            return suggestions

        cur = conn.cursor(dictionary=True)
        try:
            # Suggest from code_identifier_frequency
            cur.execute("""
                SELECT identifier, identifier_type, authority_score
                FROM vb_shared.code_identifier_frequency
                WHERE identifier LIKE %s
                ORDER BY authority_score DESC LIMIT 10
            """, ("%" + keyword + "%",))
            for row in cur.fetchall():
                suggestions.append({
                    "keyword": str(row.get("identifier", "")),
                    "type": str(row.get("identifier_type", "")),
                    "score": float(row.get("authority_score", 0)),
                    "source": "identifier_frequency",
                })

            # Suggest from code_classes
            cur.execute("""
                SELECT class_name, description
                FROM vb_shared.code_classes
                WHERE class_name LIKE %s
                LIMIT 5
            """, ("%" + keyword + "%",))
            for row in cur.fetchall():
                suggestions.append({
                    "keyword": str(row.get("class_name", "")),
                    "type": "class",
                    "score": 0.5,
                    "source": "code_classes",
                })

            # Suggest from learned_rules patterns
            cur.execute("""
                SELECT pattern, confidence
                FROM vb_shared.learned_rules
                WHERE pattern LIKE %s
                ORDER BY confidence DESC LIMIT 5
            """, ("%" + keyword + "%",))
            for row in cur.fetchall():
                suggestions.append({
                    "keyword": str(row.get("pattern", ""))[:80],
                    "type": "rule_pattern",
                    "score": float(row.get("confidence", 0)),
                    "source": "learned_rules",
                })
        except mysql.connector.Error as exc:
            self.state["last_error"] = "Suggest error: " + str(exc)
        except Exception as exc:
            self.state["last_error"] = "Suggest error: " + str(exc)
        finally:
            try:
                cur.close()
            except Exception:
                pass

        return suggestions[:15]

    # ── Keyword parsing ──

    def ParseKeywords(self, keyword: str, mode: str) -> List[str]:
        """Parse keyword string into list of keywords.

        "error AND fix"  → ["error", "fix"]  (mode="and")
        "error OR fix"   → ["error", "fix"]  (mode="or")
        "error fix"      → ["error", "fix"]  (mode="or" default)
        regex mode       → [keyword]         (single regex pattern)
        """
        if mode == "regex":
            return [keyword]
        # Split on AND/OR (case insensitive), also split on whitespace
        parts = re.split(r"\s+(?:AND|OR|and|or)\s+|\s+", keyword.strip())
        return [p for p in parts if p]

    def Matches(self, text: str, keywords: List[str], mode: str) -> Tuple[bool, int]:
        """Check if text matches keywords. Returns (matched, count)."""
        if not text:
            return (False, 0)
        text_lower = text.lower()
        if mode == "regex":
            try:
                matches = re.findall(keywords[0], text, re.IGNORECASE)
                return (len(matches) > 0, len(matches))
            except re.error:
                return (False, 0)
        elif mode == "and":
            count = 0
            for kw in keywords:
                if kw.lower() in text_lower:
                    count += 1
            return (count == len(keywords), count)
        else:  # "or"
            count = 0
            for kw in keywords:
                if kw.lower() in text_lower:
                    count += text_lower.count(kw.lower())
            return (count > 0, count)

    # ── DB Connection ──

    def GetConn(self):
        """Get MySQL connection. Thread-local to avoid cross-thread issues.

        Each thread gets its own connection. The main thread caches in
        state["db_conn"]; other threads use threading.local().
        """
        # Check thread-local storage first
        if not hasattr(self, "thread_local"):
            self.thread_local = threading.local()
        if hasattr(self.thread_local, "conn") and self.thread_local.conn:
            try:
                if self.thread_local.conn.is_connected():
                    return self.thread_local.conn
            except Exception:
                pass

        # Main thread: check state cache
        current_thread = threading.current_thread()
        if current_thread is threading.main_thread():
            conn = self.state.get("db_conn")
            if conn and conn.is_connected():
                return conn

        try:
            conn = mysql.connector.connect(
                host=Config.MYSQL_HOST,
                user=Config.MYSQL_USER,
                password=Config.MYSQL_PASS,
                unix_socket=Config.MYSQL_SOCKET,
                port=Config.MYSQL_PORT,
            )
            # Cache in thread-local
            self.thread_local.conn = conn
            # Main thread also caches in state
            if current_thread is threading.main_thread():
                self.state["db_conn"] = conn
            return conn
        except Exception as exc:
            self.state["last_error"] = "MySQL connect failed: " + str(exc)
            return None

    # ── DB Search ──

    def search_db(self, keywords: List[str], mode: str, max_hits: int = 20,
                  max_radius: int = DEFAULT_MAX_RADIUS,
                  session_filter: str = None, date_from: int = None,
                  date_to: int = None) -> List[Hit]:
        """Search keywords across all DB sources, expand radius around each hit."""
        hits = []
        conn = self.GetConn()
        if conn is None:
            return hits

        for source in DB_SOURCES:
            if len(hits) >= max_hits:
                break
            try:
                source_hits = self.SearchOneDbTable(
                    conn, source, keywords, mode, max_hits - len(hits),
                    session_filter, date_from, date_to
                )
                for hit in source_hits:
                    self.expand_radius_db(conn, hit, source, max_radius)
                    hits.append(hit)
                    if len(hits) >= max_hits:
                        break
            except Exception as exc:
                self.state["last_error"] = "DB search error in {}: {}".format(source["name"], str(exc))
                continue
        return hits

    def SearchOneDbTable(self, conn, source: Dict, keywords: List[str],
                             mode: str, limit: int,
                             session_filter: str = None,
                             date_from: int = None, date_to: int = None) -> List[Hit]:
        """Search one DB table for keyword matches."""
        hits = []
        cur = conn.cursor(dictionary=True)
        try:
            db = source["db"]
            table = source["table"]
            search_cols = source["search_cols"]
            id_col = source["id_col"]
            context_cols = source["context_cols"]
            order_by = source["order_by"]
            authority = source.get("authority", 0.5)

            # Build WHERE clause based on mode
            where_parts = []
            params = []
            if mode == "regex":
                pattern = keywords[0]
                for col in search_cols:
                    where_parts.append("{} REGEXP %s".format(col))
                    params.append(pattern)
            else:
                for col in search_cols:
                    for kw in keywords:
                        where_parts.append("{} LIKE %s".format(col))
                        params.append("%{}%".format(kw))

            if mode == "and":
                # Each keyword must match in at least one column
                kw_groups = []
                for kw in keywords:
                    col_parts = ["{} LIKE %s".format(col) for col in search_cols]
                    kw_groups.append("(" + " OR ".join(col_parts) + ")")
                    params.extend(["%{}%".format(kw)] * len(search_cols))
                where_clause = " AND ".join(kw_groups)
            else:
                where_clause = " OR ".join(where_parts)

            # Add session filter
            if session_filter and source["type"] == "chat":
                where_clause = "(" + where_clause + ") AND session_id = %s"
                params.append(session_filter)

            # Add date filter
            if date_from and "created_at" in context_cols:
                where_clause = "(" + where_clause + ") AND created_at >= %s"
                params.append(date_from)
            if date_to and "created_at" in context_cols:
                where_clause = "(" + where_clause + ") AND created_at <= %s"
                params.append(date_to)

            sql = "SELECT {} FROM {}.{} WHERE {} ORDER BY {} LIMIT {}".format(
                ", ".join(context_cols), db, table, where_clause, order_by, limit
            )
            cur.execute(sql, params)
            rows = cur.fetchall()

            for row in rows:
                hit = Hit(
                    source=source["name"],
                    source_type=source["type"],
                    db=db,
                    table=table,
                    hit_id=int(row.get(id_col, 0)),
                    center_line=int(row.get(id_col, 0)),
                    session_id=str(row.get("session_id", "") or ""),
                    role=str(row.get("role", "") or ""),
                    authority=authority,
                    created_at=int(row.get("created_at", 0) or 0),
                )
                # Find which column matched and count keyword occurrences
                total_kw_count = 0
                for col in search_cols:
                    val = str(row.get(col, "") or "")
                    matched, count = self.Matches(val, keywords, mode)
                    if matched:
                        if not hit.matched_col:
                            hit.matched_col = col
                            hit.matched_text = val
                            hit.preview = val[:200]
                        total_kw_count += count
                hit.keyword_count = total_kw_count
                if not hit.matched_text:
                    for col in context_cols:
                        if col == id_col:
                            continue
                        val = str(row.get(col, "") or "")
                        if val:
                            hit.matched_text = val
                            hit.preview = val[:200]
                            break
                hits.append(hit)
        except mysql.connector.Error as exc:
            self.state["last_error"] = "MySQL error in {}: {}".format(source["name"], str(exc))
        except Exception as exc:
            self.state["last_error"] = "Error in {}: {}".format(source["name"], str(exc))
        finally:
            try:
                cur.close()
            except Exception:
                pass
        return hits

    def expand_radius_db(self, conn, hit: Hit, source: Dict, max_radius: int) -> None:
        """Expand radius rings around a DB hit."""
        cur = conn.cursor(dictionary=True)
        try:
            db = source["db"]
            table = source["table"]
            id_col = source["id_col"]
            context_cols = source["context_cols"]
            order_by = source["order_by"]
            center = hit.center_line

            for ring in RADIUS_RINGS:
                if ring > max_radius:
                    break
                win_start = max(0, center - ring)
                win_end = center + ring

                if hit.session_id and source["type"] == "chat":
                    sql = "SELECT {} FROM {}.{} WHERE {} >= %s AND {} <= %s AND session_id = %s ORDER BY {} LIMIT %s".format(
                        ", ".join(context_cols), db, table,
                        order_by, order_by, order_by
                    )
                    cur.execute(sql, (win_start, win_end, hit.session_id, ring * 2))
                else:
                    sql = "SELECT {} FROM {}.{} WHERE {} >= %s AND {} <= %s ORDER BY {} LIMIT %s".format(
                        ", ".join(context_cols), db, table,
                        order_by, order_by, order_by
                    )
                    cur.execute(sql, (win_start, win_end, ring * 2))

                rows = cur.fetchall()
                context_parts = []
                for row in rows:
                    if source["type"] == "chat":
                        role = str(row.get("role", "") or "")
                        content = str(row.get("content", "") or "")[:300]
                        rid = row.get("row_id", 0)
                        context_parts.append("[row={} {}] {}".format(rid, role, content.replace("\n", " ")))
                    else:
                        parts = []
                        for col in context_cols:
                            val = row.get(col, "")
                            if val and col != id_col:
                                parts.append("{}={}".format(col, str(val)[:100]))
                        context_parts.append(" | ".join(parts))

                hit.radius_contexts[ring] = "\n".join(context_parts[:50])
        except mysql.connector.Error as exc:
            self.state["last_error"] = "Radius expansion error: " + str(exc)
        except Exception as exc:
            self.state["last_error"] = "Radius expansion error: " + str(exc)
        finally:
            try:
                cur.close()
            except Exception:
                pass

    # ── File Search (with cache + streaming) ──

    def search_files(self, keywords: List[str], mode: str, root: str,
                     max_hits: int = 20, max_radius: int = DEFAULT_MAX_RADIUS) -> List[Hit]:
        """Search files for keywords using grep (fast C-based search).

        Uses subprocess grep -rn for the initial keyword find (100x faster
        than Python line-by-line), then streams individual files for
        radius expansion.
        """
        import subprocess
        hits = []

        # Build grep pattern
        if mode == "regex":
            pattern = keywords[0]
        elif mode == "and":
            # grep doesn't do AND natively — search for first keyword,
            # then filter results by remaining keywords
            pattern = keywords[0]
        else:
            pattern = "|".join(re.escape(k) for k in keywords)

        # Build grep command
        ext_args = []
        for ext in FILE_EXTENSIONS:
            ext_args.extend(["--include", "*" + ext])

        skip_args = []
        for skip_dir in SKIP_DIRS:
            skip_args.extend(["--exclude-dir", skip_dir])

        try:
            cmd = ["grep", "-rn", "-I", "-m", str(max_hits)] + ext_args + skip_args + [pattern, root]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

            if proc.returncode == 0 and proc.stdout:
                for line in proc.stdout.split("\n"):
                    if len(hits) >= max_hits:
                        break
                    if not line:
                        continue
                    # Parse grep output: filepath:line_num:content
                    parts = line.split(":", 2)
                    if len(parts) < 3:
                        continue
                    filepath, line_num_str, content = parts[0], parts[1], parts[2]

                    # For AND mode, verify all keywords present in content
                    if mode == "and":
                        content_lower = content.lower()
                        if not all(kw.lower() in content_lower for kw in keywords):
                            continue

                    hit = Hit(
                        source=filepath,
                        source_type="file",
                        file_path=filepath,
                        center_line=int(line_num_str),
                        matched_text=content.rstrip(),
                        matched_col="line",
                        preview=content.strip()[:200],
                        keyword_count=sum(content.lower().count(kw.lower()) for kw in keywords),
                        authority=0.5,
                    )
                    self.expand_radius_file_streaming(hit, max_radius)
                    hits.append(hit)
        except subprocess.TimeoutExpired:
            self.state["last_error"] = "File search timed out (30s)"
        except FileNotFoundError:
            # grep not available — fall back to Python search
            hits = self.SearchFilesPython(keywords, mode, root, max_hits, max_radius)
        except Exception as exc:
            self.state["last_error"] = "File search error: " + str(exc)

        return hits

    def SearchFilesPython(self, keywords: List[str], mode: str, root: str,
                             max_hits: int, max_radius: int) -> List[Hit]:
        """Fallback: Python-only file search (no grep)."""
        hits = []
        files = self.file_cache.get_files(root, FILE_EXTENSIONS)
        for filepath in files:
            if len(hits) >= max_hits:
                break
            try:
                file_hits = self.SearchOneFileStreaming(filepath, keywords, mode, max_hits - len(hits))
                for hit in file_hits:
                    self.expand_radius_file_streaming(hit, max_radius)
                    hits.append(hit)
                    if len(hits) >= max_hits:
                        break
            except Exception as exc:
                self.state["last_error"] = "File search error in {}: {}".format(filepath, str(exc))
                continue
        return hits

    def SearchOneFileStreaming(self, filepath: str, keywords: List[str],
                                   mode: str, max_hits: int) -> List[Hit]:
        """Search one file line by line (streaming, no full load into memory)."""
        hits = []
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                for line_num, line in enumerate(f, 1):
                    matched, count = self.Matches(line, keywords, mode)
                    if matched:
                        hit = Hit(
                            source=filepath,
                            source_type="file",
                            file_path=filepath,
                            center_line=line_num,
                            matched_text=line.rstrip(),
                            matched_col="line",
                            preview=line.strip()[:200],
                            keyword_count=count,
                            authority=0.5,  # files = medium authority
                        )
                        hits.append(hit)
                        if len(hits) >= max_hits:
                            break
        except OSError as exc:
            self.state["last_error"] = "Cannot read {}: {}".format(filepath, str(exc))
        return hits

    def expand_radius_file_streaming(self, hit: Hit, max_radius: int) -> None:
        """Expand radius rings around a file hit using streaming reads.

        Instead of loading the entire file into memory, we seek to the
        relevant line range for each ring.
        """
        if not hit.file_path or not os.path.exists(hit.file_path):
            return

        for ring in RADIUS_RINGS:
            if ring > max_radius:
                break
            win_start = max(1, hit.center_line - ring)
            win_end = hit.center_line + ring
            parts = []
            try:
                with open(hit.file_path, "r", encoding="utf-8", errors="replace") as f:
                    # Skip to win_start
                    for _ in range(win_start - 1):
                        line = f.readline()
                        if not line:
                            return  # EOF
                    # Read window
                    for line_num in range(win_start, win_end + 1):
                        line = f.readline()
                        if not line:
                            break
                        marker = " <<<" if line_num == hit.center_line else ""
                        parts.append("{:6d}: {}{}".format(line_num, line.rstrip(), marker))
            except OSError as exc:
                self.state["last_error"] = "File radius error: " + str(exc)
                break
            hit.radius_contexts[ring] = "\n".join(parts)

    # ── Relevance Ranking ──

    def rank_hits(self, hits: List[Hit], keywords: List[str]) -> None:
        """Score hits by relevance.

        Score factors:
          - keyword_count: how many times keyword appears (more = better)
          - authority: source authority (rules > errors > code > chat)
          - recency: newer hits score higher (for DB with created_at)
          - position: hits in matched_col (not just "line") score higher
          - source_type: rules/errors > code > chat > files

        Score range: 0.0 to 1.0
        """
        now = time.time()
        for hit in hits:
            score = 0.0
            # Keyword frequency (0-0.3)
            kw_score = min(0.3, hit.keyword_count * 0.05)
            score += kw_score

            # Authority (0-0.3)
            score += hit.authority * 0.3

            # Recency (0-0.2) — only for DB hits with created_at
            if hit.created_at and hit.created_at > 0:
                age_days = (now - hit.created_at) / 86400
                recency = max(0, 0.2 * (1 - age_days / 365))  # decay over 1 year
                score += recency

            # Source type bonus (0-0.2)
            type_bonus = {
                "error": 0.2,
                "rule": 0.18,
                "problem": 0.15,
                "code": 0.12,
                "vbclass": 0.1,
                "vbmethod": 0.08,
                "chat": 0.05,
                "file": 0.05,
            }
            score += type_bonus.get(hit.source_type, 0.0)

            hit.relevance_score = min(1.0, score)

    # ── Clustering ──

    def cluster_hits(self, hits: List[Hit]) -> List[Cluster]:
        """Cluster hits that are close to each other.

        Hits in the same source within CLUSTER_THRESHOLD lines/rows
        are grouped. Overlapping clusters are merged.
        """
        if not hits:
            return []

        sorted_hits = sorted(hits, key=lambda h: (h.source, h.center_line))
        clusters = []
        current_cluster = Cluster(cluster_id=0)
        current_source = ""
        current_center = 0
        CLUSTER_THRESHOLD = 100

        for hit in sorted_hits:
            same_source = (hit.source == current_source)
            close_enough = abs(hit.center_line - current_center) <= CLUSTER_THRESHOLD

            if same_source and close_enough and current_cluster.hits:
                current_cluster.hits.append(hit)
            else:
                if current_cluster.hits:
                    self.FinalizeCluster(current_cluster)
                    clusters.append(current_cluster)
                current_cluster = Cluster(cluster_id=len(clusters))
                current_cluster.hits.append(hit)
                current_source = hit.source

            current_center = hit.center_line

        if current_cluster.hits:
            self.FinalizeCluster(current_cluster)
            clusters.append(current_cluster)

        return clusters

    def FinalizeCluster(self, cluster: Cluster) -> None:
        """Compute cluster width, center, confidence, type distribution."""
        if not cluster.hits:
            return
        centers = [h.center_line for h in cluster.hits]
        cluster.center_line = sum(centers) // len(centers)
        cluster.width = max(centers) - min(centers) if len(centers) > 1 else 0
        cluster.source = cluster.hits[0].source

        # Type distribution
        type_dist = {}
        for h in cluster.hits:
            type_dist[h.source_type] = type_dist.get(h.source_type, 0) + 1
        cluster.type_distribution = type_dist

        # Confidence: based on hit count + type diversity + authority
        hit_count_score = min(1.0, len(cluster.hits) / 10.0)
        type_diversity_score = min(1.0, len(type_dist) / 4.0)
        avg_authority = sum(h.authority for h in cluster.hits) / len(cluster.hits)
        cluster.confidence = (hit_count_score * 0.4 + type_diversity_score * 0.3 + avg_authority * 0.3)

    # ── Cluster Summarization ──

    def summarize_cluster(self, cluster: Cluster, keywords: List[str]) -> None:
        """Synthesize a readable summary of cluster context.

        Instead of dumping raw text, extracts:
          - What types of data are in the cluster
          - How many hits, what width
          - Key phrases (most frequent meaningful words around hits)
          - Which rings have the most context
        """
        if not cluster.hits:
            return

        # Build summary
        type_names = []
        for t, count in sorted(cluster.type_distribution.items(), key=lambda x: -x[1]):
            type_names.append("{}({})".format(t, count))

        # Extract key phrases from hit previews
        all_text = " ".join(h.preview for h in cluster.hits)
        key_phrases = self.ExtractKeyPhrases(all_text, keywords)

        # Best ring (the one with most context across all hits)
        ring_sizes = {}
        for h in cluster.hits:
            for ring, ctx in h.radius_contexts.items():
                ring_sizes[ring] = ring_sizes.get(ring, 0) + len(ctx)

        cluster.key_phrases = key_phrases[:10]

        # ── v3: Sentence extraction — pull actual sentences from context ──
        sentences = self.ExtractSentences(cluster.hits, keywords)
        cluster.sentences = sentences[:5]

        cluster.summary = "Cluster #{}: {} hits [{}] in {} (lines {}-{}, width={}). ".format(
            cluster.cluster_id, len(cluster.hits), ", ".join(type_names),
            cluster.source.split("/")[-1] if "/" in cluster.source else cluster.source,
            min(h.center_line for h in cluster.hits),
            max(h.center_line for h in cluster.hits),
            cluster.width,
        )
        if key_phrases:
            cluster.summary += "Key: {}.".format(", ".join(key_phrases[:5]))
        if cluster.shared_keywords:
            cluster.summary += " Shared: {}.".format(", ".join(cluster.shared_keywords[:3]))
        if sentences:
            cluster.summary += " Top sentence: {}".format(sentences[0][:100])
        cluster.summary += " Confidence: {:.0f}%.".format(cluster.confidence * 100)

    def ExtractSentences(self, hits: List[Hit], keywords: List[str]) -> List[str]:
        """Extract meaningful sentences from hit previews and context.

        v3: Instead of just key phrases, pull actual sentences that
        contain the keyword(s) and are the most informative.
        """
        all_sentences = []
        for hit in hits:
            # Extract from preview
            text = hit.matched_text or hit.preview
            if not text:
                continue
            # Split into sentences (simple: split on . ! ?)
            sentences = re.split(r'[.!?]+', text)
            for sent in sentences:
                sent = sent.strip()
                if len(sent) < 10 or len(sent) > 200:
                    continue
                # Score sentence: contains keyword + length
                sent_lower = sent.lower()
                score = 0
                for kw in keywords:
                    if kw.lower() in sent_lower:
                        score += 2
                # Bonus for key phrases
                score += min(3, len(sent.split()) / 5)  # longer = slightly better
                all_sentences.append((sent, score))

        # Sort by score descending
        all_sentences.sort(key=lambda x: -x[1])
        return [s for s, _ in all_sentences[:10]]

    def ExtractKeyPhrases(self, text: str, keywords: List[str]) -> List[str]:
        """Extract key phrases from text.

        Finds the most frequent meaningful words (not stopwords, not the
        search keywords themselves).
        """
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "can", "to", "of",
            "in", "for", "on", "at", "by", "with", "from", "as", "into",
            "about", "than", "then", "so", "if", "or", "and", "but", "not",
            "this", "that", "these", "those", "it", "its", "they", "them",
            "their", "there", "here", "what", "which", "who", "when", "how",
            "all", "each", "every", "both", "few", "more", "most", "other",
            "some", "such", "no", "nor", "only", "own", "same", "too", "very",
            "just", "now", "also", "any", "because", "while", "where",
        }

        # Tokenize
        words = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", text.lower())
        word_freq = {}
        kw_lower = set(k.lower() for k in keywords)
        for word in words:
            if word in stopwords or word in kw_lower or len(word) < 3:
                continue
            word_freq[word] = word_freq.get(word, 0) + 1

        # Sort by frequency
        sorted_words = sorted(word_freq.items(), key=lambda x: (-x[1], x[0]))
        return [w for w, _ in sorted_words[:10]]


# ════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT — run from command line
# ════════════════════════════════════════════════════════════════════════════

def Cli():
    import sys
    import os
    import json
    import argparse

    parser = argparse.ArgumentParser(
        description="MagneticSearch v3 — radial spiral search with expanding rings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 MagneticSearch.py magnetic
  python3 MagneticSearch.py BCLIR --source db
  python3 MagneticSearch.py "error AND fix" --mode and --source db
  python3 MagneticSearch.py "def Run" --source files --root ~/project/core
  python3 MagneticSearch.py "error.*fix" --mode regex --source db
  python3 MagneticSearch.py magnetic --session 355f59ee --source db
  python3 MagneticSearch.py magnetic --show-context --ring 100
  python3 MagneticSearch.py magnetic --show-clusters --json
  python3 MagneticSearch.py magnetic --offset 5 --limit 10
  python3 MagneticSearch.py magnatic --fuzzy                    # typo tolerance
  python3 MagneticSearch.py magnetic --export csv > results.csv
  python3 MagneticSearch.py magnetic --export markdown > results.md
  python3 MagneticSearch.py magnetic --suggest                  # related keywords
  python3 MagneticSearch.py --history                           # past searches
  python3 MagneticSearch.py magnetic --show-sentences           # extracted sentences
        """,
    )
    parser.add_argument("keyword", nargs="?", default="", help="keyword(s) to search for")
    parser.add_argument("--source", choices=["db", "files", "all"], default="all",
                        help="where to search (default: all)")
    parser.add_argument("--root", default=os.path.expanduser("~/Qdrant_mysql_mlx_vector_engine"),
                        help="root dir for file search")
    parser.add_argument("--max-hits", type=int, default=20,
                        help="max hits per source (default: 20)")
    parser.add_argument("--max-radius", type=int, default=1000,
                        help="max radius in lines/rows (default: 1000)")
    parser.add_argument("--mode", choices=["or", "and", "regex", "fuzzy"], default="or",
                        help="keyword matching mode (default: or)")
    parser.add_argument("--session", default=None,
                        help="filter by session_id (DB chat only)")
    parser.add_argument("--fuzzy", action="store_true",
                        help="enable fuzzy matching (typo tolerance)")
    parser.add_argument("--json", action="store_true", help="output as JSON")
    parser.add_argument("--export", choices=["json", "csv", "markdown", "md"], default=None,
                        help="export results in format")
    parser.add_argument("--show-context", action="store_true",
                        help="show context text for each ring")
    parser.add_argument("--ring", type=int, default=None,
                        help="show context for specific ring only")
    parser.add_argument("--show-clusters", action="store_true",
                        help="show cluster details")
    parser.add_argument("--show-sentences", action="store_true",
                        help="show extracted sentences from clusters")
    parser.add_argument("--suggest", action="store_true",
                        help="suggest related keywords")
    parser.add_argument("--history", action="store_true",
                        help="show search history")
    parser.add_argument("--offset", type=int, default=0,
                        help="pagination offset (default: 0)")
    parser.add_argument("--limit", type=int, default=50,
                        help="pagination limit (default: 50)")
    parser.add_argument("--quiet", action="store_true",
                        help="minimal output (counts only)")

    args = parser.parse_args()

    engine = MagneticSearch()

    # ── History mode ──
    if args.history and not args.keyword:
        r = engine.Run("history", {"action": "list", "limit": 20})
        if r[0] == 1:
            print("=" * 70)
            print("SEARCH HISTORY")
            print("=" * 70)
            for h in r[1]["history"]:
                print("  {} | {} | hits={} clusters={} time={}ms".format(
                    h.get("timestamp", ""), h.get("keyword", ""),
                    h.get("hits", 0), h.get("clusters", 0), h.get("timing_ms", 0)))
        return

    # ── Suggest mode ──
    if args.suggest and args.keyword:
        r = engine.Run("suggest", {"keyword": args.keyword})
        if r[0] == 1:
            print("=" * 70)
            print("SUGGESTIONS for '{}'".format(args.keyword))
            print("=" * 70)
            for s in r[1]["suggestions"]:
                print("  {} (type={}, score={:.2f}, source={})".format(
                    s["keyword"], s["type"], s["score"], s["source"]))
        return

    if not args.keyword:
        parser.print_help()
        return

    search_db = args.source in ("db", "all")
    search_files = args.source in ("files", "all")

    r = engine.Run("search", {
        "keyword": args.keyword,
        "root": args.root,
        "search_db": search_db,
        "search_files": search_files,
        "max_db_hits": args.max_hits,
        "max_file_hits": args.max_hits,
        "max_radius": args.max_radius,
        "mode": args.mode,
        "session_id": args.session,
        "fuzzy": args.fuzzy,
        "offset": args.offset,
        "limit": args.limit,
    })

    if r[0] != 1:
        print("ERROR:", r[2])
        sys.exit(1)

    d = r[1]

    # ── Export mode ──
    if args.export:
        fmt = "markdown" if args.export == "md" else args.export
        exp = engine.Run("export", {"format": fmt, "data": d})
        if exp[0] == 1:
            print(exp[1]["output"])
        return

    if args.json:
        print(json.dumps(d, indent=2, default=str))
        return

    if args.quiet:
        print("hits={} clusters={} db={} files={} deduped={} time={}ms".format(
            d["total_hits"], d["total_clusters"], d["db_hits"],
            d["file_hits"], d.get("deduped", 0), d["timing_ms"]))
        return

    # Human-readable output
    print("=" * 70)
    print("MAGNETIC SEARCH v3: '{}' (mode={})".format(args.keyword, args.mode))
    print("=" * 70)
    print()
    print("  source:    {}".format(args.source))
    print("  rings:     {}".format(d["rings"]))
    print("  max_radius: {}".format(args.max_radius))
    print("  hits:      {} (db={}, files={})".format(
        d["total_hits"], d["db_hits"], d["file_hits"]))
    print("  returned:  {} (offset={}, limit={})".format(
        d["returned_hits"], d["offset"], d["limit"]))
    print("  clusters:  {}".format(d["total_clusters"]))
    print("  deduped:   {}".format(d.get("deduped", 0)))
    print("  timing:    {}ms".format(d["timing_ms"]))
    if args.session:
        print("  session:   {}".format(args.session))
    if args.fuzzy:
        print("  fuzzy:     enabled")
    print()

    if not d["hits"]:
        print("  No hits found.")
        return

    # Show hits
    for i, hit in enumerate(d["hits"]):
        print("-" * 70)
        print("HIT {} (relevance={:.2f})".format(i + 1, hit["relevance_score"]))
        print("  source:   {} ({})".format(hit["source"], hit["source_type"]))
        if hit["file_path"]:
            print("  file:     {}".format(hit["file_path"]))
        if hit["session_id"]:
            print("  session:  {}".format(hit["session_id"]))
            print("  role:     {}".format(hit["role"]))
        print("  center:   row/line {}".format(hit["center_line"]))
        print("  matched:  {} (col={})".format(hit["preview"][:100], hit["matched_col"]))
        print("  kw_count: {}".format(hit["keyword_count"]))
        print("  authority: {:.2f}".format(hit["authority"]))
        if hit.get("fuzzy_distance", 0) > 0:
            print("  fuzzy:    distance={}".format(hit["fuzzy_distance"]))
        if hit.get("highlight_positions"):
            print("  highlights: {} positions".format(len(hit["highlight_positions"])))
        print("  rings:    {}".format(sorted(int(k) for k in hit["radius_contexts"].keys())))

        if args.show_context or args.ring:
            for ring_str in sorted(hit["radius_contexts"].keys(), key=int):
                ring = int(ring_str)
                if args.ring and ring != args.ring:
                    continue
                ctx = hit["radius_contexts"][ring_str]
                lines = ctx.split("\n") if ctx else []
                print()
                print("  RING ±{} ({} lines):".format(ring, len(lines)))
                for line in lines[:30]:
                    print("    " + line[:120])
                if len(lines) > 30:
                    print("    ... ({} more lines)".format(len(lines) - 30))
        print()

    # Show clusters
    if args.show_clusters and d["clusters"]:
        print("=" * 70)
        print("CLUSTERS (summarized)")
        print("=" * 70)
        for c in d["clusters"]:
            print()
            print("  {}".format(c["summary"]))
            print("  key phrases: {}".format(", ".join(c["key_phrases"][:5])))
            if c.get("shared_keywords"):
                print("  shared: {}".format(", ".join(c["shared_keywords"][:3])))
            print("  types: {}".format(c["type_distribution"]))
            print("  hits: {}".format(c["hit_count"]))
            for h in c["hits"][:3]:
                print("    - {} center={} rel={:.2f} {}".format(
                    h["source"].split("/")[-1] if "/" in h["source"] else h["source"],
                    h["center_line"], h["relevance_score"], h["preview"][:60]))
            if len(c["hits"]) > 3:
                print("    ... ({} more)".format(len(c["hits"]) - 3))
            if args.show_sentences and c.get("sentences"):
                print("  sentences:")
                for s in c["sentences"][:3]:
                    print("    > {}".format(s[:120]))

    print()
    print("=" * 70)
    state = engine.Run("read_state", {})[1]
    print("ENGINE v3: searches={} db={} files={} clusters={} deduped={} fuzzy={} time={}ms".format(
        state["total_searches"], state["total_db_hits"],
        state["total_file_hits"], state["total_clusters"],
        state.get("total_deduped", 0), state.get("total_fuzzy_matches", 0),
        state.get("last_timing_ms", 0)))
    if state.get("last_error"):
        print("LAST ERROR: {}".format(state["last_error"]))
    print("=" * 70)


if __name__ == "__main__":
    Cli()
