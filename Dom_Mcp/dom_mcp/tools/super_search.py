#!/usr/bin/env python3
#[@GHOST]{[@file<super_search.py>][@state<active>][@ver<v1.0>][@auth<Devin>][@date<2026-07-04>]}
#[@VBSTYLE]{[@auth<Devin>][@role<super_search>][@return<json>][@no<print|hardcoded>]}
#[@FILEID]{super_search}
#[@SUMMARY]{Multi-word semantic proximity search engine. Accepts comma-separated words, searches across MySQL cascade_chats.messages, vb_shared.learned_rules, vb_shared.know_problems, vb_shared.know_answers. Scores by coverage + proximity + TF-IDF. Returns ranked results with snippets.}
#[@CLASS]{SuperSearch}
#[@METHOD]{__init__, search_all, search_table, score_proximity, extract_snippet, run}

"""
Super Search — Multi-word semantic proximity search.

Accepts comma-separated words: "kokoro,voice,pipeline,config"
Searches across:
  - cascade_chats.messages (94K chat messages)
  - vb_shared.learned_rules (10K learned rules)
  - vb_shared.know_problems (218 known problems)
  - vb_shared.know_answers (336 known answers)
  - vb_shared.know_solutions (336 solutions)

Scoring (multi-dimensional):
  1. Coverage:    how many query words appear in the text (0.0-1.0)
  2. Proximity:   how close together the matched words are (smaller window = higher)
  3. TF-IDF:      how rare/informative the matched words are
  4. Semantic:    Qdrant vector similarity (finds related messages even without exact words)
  5. Length norm:  prefer shorter texts that contain all words

Final score = coverage_weight × coverage + proximity_weight × proximity
             + tfidf_weight × tfidf + semantic_weight × semantic
             (then × length_norm)

Input (stdin JSON):
  {
    "query": "kokoro,voice,pipeline",   # comma-separated words
    "limit": 20,                         # max results (default 20)
    "scope": "all",                      # all|chats|rules|problems|answers|solutions
    "min_coverage": 0.3,                 # min fraction of words that must match
    "proximity_window": 200              # max char distance for proximity bonus
  }

Output (stdout JSON):
  {
    "query_words": ["kokoro", "voice", "pipeline"],
    "total_results": 42,
    "results": [
      {
        "source": "cascade_chats.messages",
        "id": 12345,
        "trajectory_id": "abc-123",
        "role": "assistant",
        "score": 0.95,
        "coverage": 1.0,
        "proximity": 0.85,
        "tfidf": 0.72,
        "snippet": "...configured the **kokoro** **voice** **pipeline** with..."
      }
    ]
  }
"""

import sys
import json
import re
import math
import mysql.connector
from collections import defaultdict

# ── Configuration ────────────────────────────────────────────
MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
}

# Tables to search, with their configs
SEARCH_TABLES = {
    "chats": {
        "db": "cascade_chats",
        "table": "messages",
        "columns": {"id": "id", "text": "content", "meta1": "trajectory_id", "meta2": "role"},
        "where": "content IS NOT NULL AND LENGTH(content) > 20",
    },
    "rules": {
        "db": "vb_shared",
        "table": "learned_rules",
        "columns": {"id": "id", "text": "pattern", "meta1": "fix_action", "meta2": None},
        "where": "pattern IS NOT NULL AND LENGTH(pattern) > 5",
    },
    "problems": {
        "db": "vb_shared",
        "table": "know_problems",
        "columns": {"id": "id", "text": "problem", "meta1": "description", "meta2": None},
        "where": "problem IS NOT NULL",
    },
    "answers": {
        "db": "vb_shared",
        "table": "know_answers",
        "columns": {"id": "id", "text": "answer", "meta1": "question_id", "meta2": None},
        "where": "answer IS NOT NULL AND LENGTH(answer) > 50",
    },
    "solutions": {
        "db": "vb_shared",
        "table": "know_solutions",
        "columns": {"id": "id", "text": "solution", "meta1": "problem_id", "meta2": None},
        "where": "solution IS NOT NULL AND LENGTH(solution) > 20",
    },
}

# Stop words for TF-IDF
STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "can", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "up", "down", "out", "off",
    "over", "under", "again", "further", "then", "once", "here", "there",
    "when", "where", "why", "how", "all", "each", "every", "both",
    "few", "more", "most", "other", "some", "such", "no", "nor", "not",
    "only", "own", "same", "so", "than", "too", "very", "just", "but",
    "and", "or", "if", "while", "about", "this", "that", "these", "those",
    "i", "me", "my", "we", "our", "you", "your", "he", "she", "it",
    "its", "they", "them", "their", "what", "which", "who", "whom",
    "use", "using", "used", "like", "need", "want", "get", "got",
    "make", "made", "go", "going", "one", "two", "also", "well",
}


class SuperSearch:
    def __init__(self):
        self.idf_cache = {}
        self.total_docs = 0
        self.qdrant_semantic = {}  # message_id → semantic_score (from Qdrant)
        self.qdrant_available = False

    def _get_conn(self, db):
        cfg = dict(MYSQL_CONFIG)
        cfg["database"] = db
        return mysql.connector.connect(**cfg)

    def _tokenize(self, text):
        """Split text into lowercase word tokens."""
        if not text:
            return []
        return re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', text.lower())

    def _find_word_positions(self, text, words):
        """Find all character positions of each word in the text.

        Returns: {word: [pos1, pos2, ...], ...}
        """
        positions = defaultdict(list)
        text_lower = text.lower()
        for word in words:
            word_lower = word.lower()
            # Use regex to find word boundaries
            for m in re.finditer(r'\b' + re.escape(word_lower) + r'\b', text_lower):
                positions[word].append(m.start())
        return positions

    def _calc_proximity(self, positions, num_query_words):
        """Calculate proximity score from word positions.

        Finds the minimum window that contains the most distinct query words.
        Returns (coverage, proximity_score).

        coverage = distinct_words_found / total_query_words
        proximity = 1.0 / (1.0 + window_size / 100)  — smaller window = higher score
        """
        if not positions:
            return 0.0, 0.0

        coverage = len(positions) / num_query_words

        if len(positions) == 1:
            # Only one word found — proximity is neutral
            return coverage, 0.5

        # Collect all (position, word) pairs
        all_pos = []
        for word, pos_list in positions.items():
            for p in pos_list:
                all_pos.append((p, word))

        # Sort by position
        all_pos.sort(key=lambda x: x[0])

        # Sliding window to find minimum window containing all distinct words
        distinct_words = set(positions.keys())
        best_window = float('inf')

        # Use sliding window approach
        word_count = defaultdict(int)
        words_in_window = 0
        left = 0

        for right in range(len(all_pos)):
            pos_r, word_r = all_pos[right]
            if word_count[word_r] == 0:
                words_in_window += 1
            word_count[word_r] += 1

            # Try to shrink window from left
            while words_in_window == len(distinct_words):
                window_size = all_pos[right][0] - all_pos[left][0]
                if window_size < best_window:
                    best_window = window_size

                pos_l, word_l = all_pos[left]
                word_count[word_l] -= 1
                if word_count[word_l] == 0:
                    words_in_window -= 1
                left += 1

        if best_window == float('inf'):
            # Words found but can't all be in one window (shouldn't happen)
            return coverage, 0.3

        # Proximity score: 1.0 for window=0, decreasing as window grows
        # 100 chars → 0.5, 200 chars → 0.33, 500 chars → 0.17
        proximity = 1.0 / (1.0 + best_window / 100.0)

        return coverage, proximity

    def _calc_tfidf(self, positions, text_len):
        """Calculate TF-IDF score for matched words."""
        if not positions or text_len == 0:
            return 0.0

        total_score = 0.0
        for word, pos_list in positions.items():
            tf = len(pos_list) / max(1, text_len / 1000)  # term frequency per 1000 chars
            idf = self.idf_cache.get(word.lower(), 5.0)  # default IDF for unknown words
            total_score += tf * idf

        # Normalize
        return min(total_score / 10.0, 1.0)

    def _compute_idf(self, scope="all"):
        """Compute IDF for all query words across the corpus."""
        # Count documents containing each word
        doc_freq = defaultdict(int)
        total_docs = 0

        tables = SEARCH_TABLES if scope == "all" else {scope: SEARCH_TABLES[scope]}

        for tname, tcfg in tables.items():
            try:
                conn = self._get_conn(tcfg["db"])
                cursor = conn.cursor()
                text_col = tcfg["columns"]["text"]
                cursor.execute(
                    f"SELECT {text_col} FROM {tcfg['table']} WHERE {tcfg['where']} LIMIT 5000"
                )
                for (text,) in cursor:
                    if not text:
                        continue
                    total_docs += 1
                    tokens = set(self._tokenize(text))
                    for tok in tokens:
                        if tok not in STOP_WORDS and len(tok) > 2:
                            doc_freq[tok] += 1
                cursor.close()
                conn.close()
            except Exception:
                continue

        self.total_docs = total_docs
        # IDF = log(N / df)
        for word, df in doc_freq.items():
            self.idf_cache[word] = math.log(max(1, total_docs) / max(1, df))

    def _extract_snippet(self, text, words, max_len=300):
        """Extract a snippet around the first matched word, highlighting all matches."""
        if not text or not words:
            return ""

        positions = self._find_word_positions(text, words)
        if not positions:
            return text[:max_len] + "..." if len(text) > max_len else text

        # Find the earliest match position
        earliest = min(min(ps) for ps in positions.values())

        # Center the snippet around the earliest match
        start = max(0, earliest - max_len // 3)
        end = min(len(text), start + max_len)

        snippet = text[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."

        # Highlight matched words
        for word in words:
            snippet = re.sub(
                r'\b(' + re.escape(word) + r')\b',
                r'**\1**',
                snippet,
                flags=re.IGNORECASE
            )

        return snippet

    def search_table(self, tname, tcfg, query_words, limit, min_coverage, prox_window):
        """Search one table and return scored results."""
        results = []

        try:
            conn = self._get_conn(tcfg["db"])
            cursor = conn.cursor()
            cols = tcfg["columns"]
            text_col = cols["text"]

            # Build WHERE clause with LIKE for each word
            # This pre-filters to rows that contain at least one query word
            like_clauses = " OR ".join(
                f"{text_col} LIKE %s" for _ in query_words
            )
            like_params = [f"%{w}%" for w in query_words]

            select_cols = cols["id"]
            if cols.get("meta1"):
                select_cols += f", {cols['meta1']}"
            if cols.get("meta2"):
                select_cols += f", {cols['meta2']}"
            select_cols += f", {text_col}"

            query = (
                f"SELECT {select_cols} FROM {tcfg['table']} "
                f"WHERE ({like_clauses}) AND {tcfg['where']} "
                f"LIMIT 500"
            )

            cursor.execute(query, like_params)
            rows = cursor.fetchall()

            for row in rows:
                idx = 0
                row_id = row[idx]; idx += 1
                meta1 = row[idx] if cols.get("meta1") else None; idx += 1 if cols.get("meta1") else 0
                meta2 = row[idx] if cols.get("meta2") else None; idx += 1 if cols.get("meta2") else 0
                text = row[-1] if row else ""

                if not text or len(text) < 5:
                    continue

                # Find word positions
                positions = self._find_word_positions(text, query_words)
                if not positions:
                    continue

                # Calculate scores
                coverage, proximity = self._calc_proximity(positions, len(query_words))
                tfidf = self._calc_tfidf(positions, len(text))

                # Skip if coverage too low
                if coverage < min_coverage:
                    continue

                # Combined score — 4 dimensions
                # Weights: coverage most important, then proximity, then tfidf, then semantic
                semantic = 0.0
                if self.qdrant_available and tname == "chats":
                    semantic = self.qdrant_semantic.get(int(row_id), 0.0)

                score = (0.35 * coverage +
                         0.30 * proximity +
                         0.20 * tfidf +
                         0.15 * semantic)

                # Length normalization — prefer shorter texts with all words
                len_norm = 1.0 / (1.0 + len(text) / 5000.0)
                score *= len_norm

                snippet = self._extract_snippet(text, query_words)

                results.append({
                    "source": f"{tcfg['db']}.{tcfg['table']}",
                    "id": row_id,
                    "meta1": str(meta1) if meta1 else "",
                    "meta2": str(meta2) if meta2 else "",
                    "score": round(score, 4),
                    "coverage": round(coverage, 3),
                    "proximity": round(proximity, 3),
                    "tfidf": round(tfidf, 3),
                    "semantic": round(semantic, 3),
                    "text_length": len(text),
                    "snippet": snippet,
                })

            cursor.close()
            conn.close()
        except Exception as e:
            results.append({
                "source": f"{tcfg['db']}.{tcfg['table']}",
                "error": str(e),
            })

        return results

    def _query_qdrant(self, query_words, limit=100):
        """Query Qdrant for semantic matches and populate qdrant_semantic dict.

        This finds messages that are semantically related even if they don't
        contain the exact query words (e.g. "tts" matches "voice synthesis").
        """
        self.qdrant_semantic = {}
        self.qdrant_available = False

        try:
            import urllib.request
            import urllib.error

            # Check if Qdrant is running
            try:
                req = urllib.request.urlopen("http://localhost:6333/collections/chat_messages", timeout=2)
                if req.status != 200:
                    return
            except Exception:
                return  # Qdrant not running — semantic dimension disabled

            # Query Qdrant via the search script
            import subprocess
            script = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Mcp/dom_mcp/tools/qdrant_search.py"
            payload = json.dumps({"query": ",".join(query_words), "limit": limit})

            proc = subprocess.run(
                [sys.executable, script],
                input=payload,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if proc.returncode != 0:
                return

            data = json.loads(proc.stdout)
            for result in data.get("results", []):
                msg_id = result.get("id")
                score = result.get("score", 0)
                if msg_id:
                    self.qdrant_semantic[int(msg_id)] = score
                    self.qdrant_available = True

        except Exception:
            pass  # Semantic search is optional — fail silently

    def search_all(self, query, limit=20, scope="all", min_coverage=0.3, prox_window=200):
        """Search across all configured tables."""
        # Parse query words
        query_words = [w.strip().lower() for w in query.split(",") if w.strip()]
        if not query_words:
            return {"error": "no query words provided"}

        # Compute IDF for scoring
        self._compute_idf(scope)

        # Query Qdrant for semantic matches (4th dimension)
        self._query_qdrant(query_words, limit=200)

        all_results = []
        tables = SEARCH_TABLES if scope == "all" else {scope: SEARCH_TABLES.get(scope)}
        if not tables:
            return {"error": f"unknown scope: {scope}"}

        for tname, tcfg in tables.items():
            results = self.search_table(
                tname, tcfg, query_words, limit, min_coverage, prox_window
            )
            all_results.extend(results)

        # Also add Qdrant-only results (semantic matches that don't have exact word hits)
        if self.qdrant_available and scope in ("all", "chats"):
            existing_ids = {r["id"] for r in all_results if "id" in r}
            for msg_id, sem_score in sorted(self.qdrant_semantic.items(), key=lambda x: -x[1]):
                if msg_id in existing_ids:
                    continue
                # Fetch the message from MySQL
                try:
                    conn = self._get_conn("cascade_chats")
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id, trajectory_id, role, content FROM messages WHERE id = %s",
                        (msg_id,)
                    )
                    row = cursor.fetchone()
                    cursor.close()
                    conn.close()
                    if row and row[3]:
                        text = row[3]
                        snippet = self._extract_snippet(text, query_words)
                        all_results.append({
                            "source": "cascade_chats.messages (semantic)",
                            "id": row[0],
                            "meta1": str(row[1]) if row[1] else "",
                            "meta2": str(row[2]) if row[2] else "",
                            "score": sem_score * 0.5,  # semantic-only gets lower weight
                            "coverage": 0.0,
                            "proximity": 0.0,
                            "tfidf": 0.0,
                            "semantic": round(sem_score, 3),
                            "text_length": len(text),
                            "snippet": snippet,
                        })
                        existing_ids.add(msg_id)
                except Exception:
                    pass

        # Sort by score descending
        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)

        # Trim to limit
        all_results = all_results[:limit]

        return {
            "query_words": query_words,
            "total_results": len(all_results),
            "semantic_enabled": self.qdrant_available,
            "results": all_results,
        }

    def run(self, params):
        """Run search from params dict."""
        query = params.get("query", "")
        limit = int(params.get("limit", 20))
        scope = params.get("scope", "all")
        min_coverage = float(params.get("min_coverage", 0.3))
        prox_window = int(params.get("proximity_window", 200))

        return self.search_all(query, limit, scope, min_coverage, prox_window)


def main():
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        print(json.dumps({"error": "invalid JSON input"}))
        sys.exit(1)

    searcher = SuperSearch()
    result = searcher.run(data)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
