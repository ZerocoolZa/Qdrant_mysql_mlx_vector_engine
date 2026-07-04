#!/usr/bin/env python3
# [@GHOST]{[@file<GuiEmbedder.py>][@domain<gui_engine>][@role<embedder>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<semantic_embedder>][@return<tuple3>][@orch<GuiIngester>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{Embeds GUI widgets/styles/signals into vectors, finds semantic patterns SQL cannot see}
# [@CLASS]{[@name<GuiEmbedder>][@domain<gui_engine>][@authority<single>]}

import json
import sqlite3
import numpy as np
from pathlib import Path
from typing import Any, Dict, List, Tuple

DB_PATH = Path(__file__).parent / "gui_engine.db"
MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384


class GuiEmbedder:
    """Embed GUI widgets into vectors and find semantic patterns.

    Turns each widget into a text description, embeds it with BGE,
    then uses cosine similarity to find:
    - Similar widgets across files (the play_btn in 5 files)
    - Widget clusters (groups of widgets doing the same thing)
    - Style patterns (widgets with similar styling)
    - Orphan clusters (widgets that look like they belong together)
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {"db_path": str(DB_PATH), "model": MODEL_NAME},
            "catalog": [],
            "results": [],
            "memunit": mem,
            "db_manager": db,
        }
        self.conn = sqlite3.connect(str(DB_PATH))
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.model = None
        self.vectors = None
        self.widget_ids = []
        self.widget_texts = []

    def Run(self, command, params=None):
        if command == "embed_all":
            return self._embed_all()
        elif command == "find_similar":
            return self._find_similar(params.get("widget_var"), params.get("top_k", 10))
        elif command == "cluster_widgets":
            return self._cluster_widgets(params.get("n_clusters", 8))
        elif command == "find_duplicates":
            return self._find_duplicates(params.get("threshold", 0.85))
        elif command == "search":
            return self._search(params.get("query"), params.get("top_k", 10))
        elif command == "Say":
            return self._say(params.get("topic", "patterns"))
        elif command == "read_state":
            return self.read_state()
        return (0, None, ("unknown_command", command, 0))

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def _load_model(self):
        if self.model is not None:
            return (1, True, None)
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(MODEL_NAME)
            return (1, True, None)
        except Exception as e:
            return (0, None, ("model_load_error", str(e), 0))

    def _widget_to_text(self, row):
        parts = []
        parts.append("Widget: {} {}".format(row["widget_var"], row["widget_type"]))
        if row["widget_text"]:
            parts.append("Text: {}".format(row["widget_text"]))
        if row["class_name"]:
            parts.append("Class: {}".format(row["class_name"]))
        if row["context"]:
            parts.append("Method: {}".format(row["context"]))
        fname = row["file_path"].split("/")[-1] if row["file_path"] else ""
        parts.append("File: {}".format(fname))
        return " | ".join(parts)

    def _embed_all(self):
        ok, _, err = self._load_model()
        if not ok:
            return (0, None, err)
        self.cursor.execute("""
            SELECT id, widget_var, widget_type, widget_text, class_name,
                   file_path, context, line_num
            FROM gui_widgets ORDER BY id
        """)
        rows = self.cursor.fetchall()
        if not rows:
            return (0, None, ("no_widgets", "No widgets in DB", 0))
        self.widget_ids = []
        self.widget_texts = []
        for r in rows:
            self.widget_ids.append(r["id"])
            self.widget_texts.append(self._widget_to_text(r))
        embeddings = self.model.encode(self.widget_texts, show_progress_bar=False)
        self.vectors = np.array(embeddings, dtype=np.float32)
        self.state["catalog"] = [{"id": wid, "text": txt} for wid, txt in zip(self.widget_ids, self.widget_texts)]
        return (1, {"embedded": len(self.widget_ids), "dim": self.vectors.shape[1]}, None)

    def _cosine_sim(self, vec_a, vec_b):
        dot = np.dot(vec_a, vec_b)
        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))

    def _find_similar(self, widget_var, top_k=10):
        if self.vectors is None:
            ok, _, err = self._embed_all()
            if not ok:
                return (0, None, err)
        self.cursor.execute("""
            SELECT id FROM gui_widgets WHERE widget_var = ? LIMIT 1
        """, (widget_var,))
        row = self.cursor.fetchone()
        if not row:
            return (0, None, ("widget_not_found", widget_var, 0))
        target_idx = self.widget_ids.index(row["id"])
        target_vec = self.vectors[target_idx]
        sims = []
        for i, wid in enumerate(self.widget_ids):
            if i == target_idx:
                continue
            sim = self._cosine_sim(target_vec, self.vectors[i])
            sims.append((sim, wid, i))
        sims.sort(reverse=True)
        results = []
        for sim, wid, idx in sims[:top_k]:
            self.cursor.execute("SELECT * FROM gui_widgets WHERE id = ?", (wid,))
            w = dict(self.cursor.fetchone())
            w["similarity"] = round(sim, 4)
            results.append(w)
        return (1, results, None)

    def _find_duplicates(self, threshold=0.85):
        if self.vectors is None:
            ok, _, err = self._embed_all()
            if not ok:
                return (0, None, err)
        groups = []
        used = set()
        for i in range(len(self.widget_ids)):
            if i in used:
                continue
            cluster = [i]
            used.add(i)
            for j in range(i + 1, len(self.widget_ids)):
                if j in used:
                    continue
                sim = self._cosine_sim(self.vectors[i], self.vectors[j])
                if sim >= threshold:
                    cluster.append(j)
                    used.add(j)
            if len(cluster) > 1:
                members = []
                for idx in cluster:
                    self.cursor.execute("SELECT * FROM gui_widgets WHERE id = ?", (self.widget_ids[idx],))
                    w = dict(self.cursor.fetchone())
                    w["similarity"] = round(self._cosine_sim(self.vectors[cluster[0]], self.vectors[idx]), 4)
                    members.append(w)
                groups.append(members)
        groups.sort(key=lambda g: len(g), reverse=True)
        return (1, {"duplicate_groups": len(groups), "total_duplicates": sum(len(g) for g in groups), "groups": groups[:20]}, None)

    def _cluster_widgets(self, n_clusters=8):
        if self.vectors is None:
            ok, _, err = self._embed_all()
            if not ok:
                return (0, None, err)
        try:
            from sklearn.cluster import KMeans
        except ImportError:
            return self._simple_cluster(n_clusters)
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(self.vectors)
        clusters = {}
        for i, label in enumerate(labels):
            label = int(label)
            if label not in clusters:
                clusters[label] = []
            self.cursor.execute("SELECT * FROM gui_widgets WHERE id = ?", (self.widget_ids[i],))
            w = dict(self.cursor.fetchone())
            clusters[label].append(w)
        result = []
        for label in sorted(clusters.keys(), key=lambda l: len(clusters[l]), reverse=True):
            members = clusters[label]
            types = list(set(w["widget_type"] for w in members))
            files = list(set(w["file_path"].split("/")[-1] for w in members))
            classes = list(set(w["class_name"] for w in members if w["class_name"]))
            result.append({
                "cluster": label,
                "size": len(members),
                "widget_types": types[:5],
                "files": files[:5],
                "classes": classes[:5],
                "sample_widgets": [w["widget_var"] for w in members[:5]],
            })
        return (1, result, None)

    def _simple_cluster(self, n_clusters):
        if self.vectors is None:
            return (0, None, ("no_vectors", "Embed first", 0))
        n = len(self.widget_ids)
        if n == 0:
            return (0, None, ("no_widgets", "No widgets", 0))
        step = max(1, n // n_clusters)
        centroids = [self.vectors[i] for i in range(0, n, step)][:n_clusters]
        clusters = {i: [] for i in range(len(centroids))}
        for i in range(n):
            best_c = 0
            best_sim = -1
            for c, centroid in enumerate(centroids):
                sim = self._cosine_sim(self.vectors[i], centroid)
                if sim > best_sim:
                    best_sim = sim
                    best_c = c
            clusters[best_c].append(i)
        result = []
        for c in sorted(clusters.keys(), key=lambda k: len(clusters[k]), reverse=True):
            members = clusters[c]
            widget_rows = []
            for idx in members[:5]:
                self.cursor.execute("SELECT * FROM gui_widgets WHERE id = ?", (self.widget_ids[idx],))
                widget_rows.append(dict(self.cursor.fetchone()))
            types = list(set(w["widget_type"] for w in widget_rows))
            result.append({
                "cluster": c,
                "size": len(members),
                "widget_types": types,
                "sample_widgets": [w["widget_var"] for w in widget_rows],
            })
        return (1, result, None)

    def _search(self, query, top_k=10):
        if self.vectors is None:
            ok, _, err = self._embed_all()
            if not ok:
                return (0, None, err)
        query_vec = self.model.encode([query], show_progress_bar=False)[0]
        sims = []
        for i in range(len(self.widget_ids)):
            sim = self._cosine_sim(query_vec, self.vectors[i])
            sims.append((sim, i))
        sims.sort(reverse=True)
        results = []
        for sim, idx in sims[:top_k]:
            self.cursor.execute("SELECT * FROM gui_widgets WHERE id = ?", (self.widget_ids[idx],))
            w = dict(self.cursor.fetchone())
            w["similarity"] = round(sim, 4)
            results.append(w)
        return (1, results, None)

    def _say(self, topic):
        if topic == "patterns":
            return self._say_patterns()
        elif topic == "duplicates":
            return self._say_duplicates()
        elif topic == "clusters":
            return self._say_clusters()
        return (0, None, ("unknown_topic", topic, 0))

    def _say_patterns(self):
        ok, data, err = self._find_duplicates(0.82)
        if not ok:
            return (0, None, err)
        lines = []
        lines.append("SEMANTIC DUPLICATES — widgets that mean the same thing across files:")
        lines.append("")
        lines.append("Found {} duplicate groups, {} total duplicate widgets".format(
            data["duplicate_groups"], data["total_duplicates"]))
        lines.append("")
        for i, group in enumerate(data["groups"][:10]):
            files = set()
            for w in group:
                if w["file_path"]:
                    files.add(w["file_path"].split("/")[-1])
            lines.append("Group {} ({} widgets, similarity {}):".format(
                i + 1, len(group), group[0]["similarity"]))
            lines.append("  Types: {}".format(", ".join(set(w["widget_type"] for w in group))))
            lines.append("  Files: {}".format(", ".join(list(files)[:5])))
            lines.append("  Widgets: {}".format(", ".join(w["widget_var"] for w in group[:5])))
            lines.append("")
        lines.append("These are your VB-style template candidates.")
        lines.append("Each group is one button created many times. Button once, property many.")
        return (1, "\n".join(lines), None)

    def _say_duplicates(self):
        return self._say_patterns()

    def _say_clusters(self):
        ok, clusters, err = self._cluster_widgets(8)
        if not ok:
            return (0, None, err)
        lines = []
        lines.append("WIDGET CLUSTERS — 8 semantic groups found by embedding:")
        lines.append("")
        for c in clusters:
            lines.append("Cluster {} ({} widgets):".format(c["cluster"], c["size"]))
            lines.append("  Types: {}".format(", ".join(c["widget_types"])))
            lines.append("  Files: {}".format(", ".join(c["files"])))
            lines.append("  Sample: {}".format(", ".join(c["sample_widgets"])))
            lines.append("")
        return (1, "\n".join(lines), None)

    def read_state(self):
        return (1, {
            "config": self.state["config"],
            "embedded": len(self.widget_ids) if self.vectors is not None else 0,
            "vector_shape": list(self.vectors.shape) if self.vectors is not None else None,
        }, None)

    def close(self):
        self.conn.close()


if __name__ == "__main__":
    embedder = GuiEmbedder()
    print("Embedding all widgets...")
    ok, data, err = embedder.Run("embed_all")
    if ok:
        print("Embedded {} widgets ({} dim)".format(data["embedded"], data["dim"]))
    else:
        print("Error:", err)
        embedder.close()
        exit(1)

    print()
    print("=== SEMANTIC DUPLICATES ===")
    ok, text, err = embedder.Run("Say", {"topic": "patterns"})
    if ok:
        print(text)

    print()
    print("=== WIDGET CLUSTERS ===")
    ok, text, err = embedder.Run("Say", {"topic": "clusters"})
    if ok:
        print(text)

    print()
    print("=== SEARCH: 'play button' ===")
    ok, results, err = embedder.Run("search", {"query": "play button for animation", "top_k": 5})
    if ok:
        for r in results:
            print("  {} ({}) sim={} in {}".format(
                r["widget_var"], r["widget_type"], r["similarity"],
                r["file_path"].split("/")[-1] if r["file_path"] else "?"))

    print()
    print("=== SEARCH: 'status display label' ===")
    ok, results, err = embedder.Run("search", {"query": "status display label showing connection info", "top_k": 5})
    if ok:
        for r in results:
            print("  {} ({}) sim={} in {}".format(
                r["widget_var"], r["widget_type"], r["similarity"],
                r["file_path"].split("/")[-1] if r["file_path"] else "?"))

    embedder.close()
