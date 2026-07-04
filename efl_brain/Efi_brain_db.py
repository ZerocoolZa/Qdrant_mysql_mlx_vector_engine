#!/usr/bin/env python3
# ============================================================================
# GHOST HEADER
# ----------------------------------------------------------------------------
# File:     Efi_brain_db.py
# Domain:   efl_brain
# Authority: Database-mediated communication layer — the dinner table
# DB:       efl_brain.db (SQLite)
#
# VBSTYLE HEADER
# ----------------------------------------------------------------------------
# This is the communication layer between all brothers in the efl_brain house.
# No brother imports another brother. They all import this class.
# Each brother writes his results to the database. The next brother reads them.
#
# Brothers:
#   Efi_core.py          — writes methods, classes, edges
#   Efi_agent_graph.py   — writes prediction links, world model, emotional state
#   Efi_solution_engine  — writes violations, reads prediction links for fragility
#   Efi_graph_viewer.py  — reads graph state for visualization
#   Efi_ram_ai.py        — writes vectors
#
# The database is the dinner table. They don't talk directly.
# They leave notes on the table. When the next brother comes home, he reads them.
# ============================================================================

"""
Brain Database — the dinner table for all brothers.

This class wraps efl_brain.db and provides read/write methods for each brother.
No brother needs to import another brother. They all talk through this class.

Tables managed:
  agent_prediction_links — learned prediction links from the agent graph
  agent_world_model      — compressed world model state
  agent_emotional_state  — emotional state snapshots
  agent_violations       — violations from the solution engine
  agent_blast_radius     — blast radius data from the agent graph
"""

import os
import json
import sqlite3
import time
from collections import defaultdict

import Config_efl_brain as Config

DB_PATH = Config.DB_PATH


class BrainDb:
    """The dinner table — all brothers read and write here."""

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self.conn = None

    def Connect(self):
        """Connect to the database and create tables if needed."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._CreateTables()
        return True

    def Disconnect(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def _CreateTables(self):
        """Create the agent tables if they don't exist."""
        c = self.conn.cursor()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS agent_prediction_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_node TEXT NOT NULL,
                target_node TEXT NOT NULL,
                expected_reward REAL DEFAULT 0.5,
                expected_pain REAL DEFAULT 0.0,
                confidence REAL DEFAULT 0.5,
                update_count INTEGER DEFAULT 0,
                writer TEXT DEFAULT 'agent_graph',
                written_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_node, target_node)
            );

            CREATE TABLE IF NOT EXISTS agent_world_model (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                explored_fraction REAL DEFAULT 0.0,
                avg_reward REAL DEFAULT 0.0,
                avg_pain REAL DEFAULT 0.0,
                avg_confidence REAL DEFAULT 0.0,
                high_value_count INTEGER DEFAULT 0,
                dangerous_count INTEGER DEFAULT 0,
                node_types_seen TEXT,
                writer TEXT DEFAULT 'agent_graph',
                written_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS agent_emotional_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mood REAL DEFAULT 0.5,
                arousal REAL DEFAULT 0.5,
                frustration REAL DEFAULT 0.0,
                trend TEXT DEFAULT 'stable',
                exploration_bias REAL DEFAULT 0.5,
                writer TEXT DEFAULT 'agent_graph',
                written_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS agent_violations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                rule TEXT NOT NULL,
                severity TEXT DEFAULT 'medium',
                fix_action TEXT,
                blast_radius INTEGER,
                writer TEXT DEFAULT 'solution_engine',
                written_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(file_path, rule)
            );

            CREATE TABLE IF NOT EXISTS agent_blast_radius (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_node TEXT NOT NULL,
                affected_node TEXT NOT NULL,
                writer TEXT DEFAULT 'agent_graph',
                written_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_node, affected_node)
            );

            CREATE INDEX IF NOT EXISTS idx_pred_links_src ON agent_prediction_links(source_node);
            CREATE INDEX IF NOT EXISTS idx_pred_links_dst ON agent_prediction_links(target_node);
            CREATE INDEX IF NOT EXISTS idx_violations_file ON agent_violations(file_path);
            CREATE INDEX IF NOT EXISTS idx_blast_src ON agent_blast_radius(source_node);
        """)
        self.conn.commit()

    # ------------------------------------------------------------------
    # WRITER: AgentGraph — prediction links, world model, emotion, blast
    # ------------------------------------------------------------------

    def WritePredictionLinks(self, links, writer="agent_graph"):
        """Write prediction links. links = list of dicts with source_node, target_node, etc."""
        c = self.conn.cursor()
        for link in links:
            c.execute("""
                INSERT OR REPLACE INTO agent_prediction_links
                    (source_node, target_node, expected_reward, expected_pain,
                     confidence, update_count, writer, written_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                link["source_node"], link["target_node"],
                link.get("expected_reward", 0.5),
                link.get("expected_pain", 0.0),
                link.get("confidence", 0.5),
                link.get("update_count", 0),
                writer,
            ))
        self.conn.commit()
        return len(links)

    def ReadPredictionLinks(self, for_node=None):
        """Read prediction links. If for_node given, returns links from that node."""
        c = self.conn.cursor()
        if for_node:
            c.execute("SELECT * FROM agent_prediction_links WHERE source_node = ?", (for_node,))
        else:
            c.execute("SELECT * FROM agent_prediction_links")
        return [dict(r) for r in c.fetchall()]

    def WriteWorldModel(self, wm, writer="agent_graph"):
        """Write world model state."""
        c = self.conn.cursor()
        c.execute("""
            INSERT INTO agent_world_model
                (explored_fraction, avg_reward, avg_pain, avg_confidence,
                 high_value_count, dangerous_count, node_types_seen, writer, written_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            wm.get("explored_fraction", 0.0),
            wm.get("avg_reward", 0.0),
            wm.get("avg_pain", 0.0),
            wm.get("avg_confidence", 0.0),
            wm.get("high_value_count", 0),
            wm.get("dangerous_count", 0),
            json.dumps(wm.get("node_types_seen", {})),
            writer,
        ))
        self.conn.commit()

    def ReadWorldModel(self):
        """Read the latest world model."""
        c = self.conn.cursor()
        c.execute("SELECT * FROM agent_world_model ORDER BY written_at DESC LIMIT 1")
        row = c.fetchone()
        if row:
            d = dict(row)
            d["node_types_seen"] = json.loads(d.get("node_types_seen") or "{}")
            return d
        return None

    def WriteEmotionalState(self, em, writer="agent_graph"):
        """Write emotional state snapshot."""
        c = self.conn.cursor()
        c.execute("""
            INSERT INTO agent_emotional_state
                (mood, arousal, frustration, trend, exploration_bias, writer, written_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            em.get("mood", 0.5),
            em.get("arousal", 0.5),
            em.get("frustration", 0.0),
            em.get("trend", "stable"),
            em.get("exploration_bias", 0.5),
            writer,
        ))
        self.conn.commit()

    def ReadEmotionalState(self):
        """Read the latest emotional state."""
        c = self.conn.cursor()
        c.execute("SELECT * FROM agent_emotional_state ORDER BY written_at DESC LIMIT 1")
        row = c.fetchone()
        return dict(row) if row else None

    def WriteBlastRadius(self, source_node, affected_nodes, writer="agent_graph"):
        """Write blast radius data for a node."""
        c = self.conn.cursor()
        # Clear old entries for this source
        c.execute("DELETE FROM agent_blast_radius WHERE source_node = ?", (source_node,))
        for affected in affected_nodes:
            c.execute("""
                INSERT OR IGNORE INTO agent_blast_radius
                    (source_node, affected_node, writer, written_at)
                VALUES (?, ?, ?, datetime('now'))
            """, (source_node, affected, writer))
        self.conn.commit()
        return len(affected_nodes)

    def ReadBlastRadius(self, for_node=None):
        """Read blast radius data. If for_node given, returns affected nodes for that node."""
        c = self.conn.cursor()
        if for_node:
            c.execute("SELECT affected_node FROM agent_blast_radius WHERE source_node = ?", (for_node,))
            return [r["affected_node"] for r in c.fetchall()]
        else:
            c.execute("SELECT source_node, COUNT(*) as count FROM agent_blast_radius GROUP BY source_node")
            return {r["source_node"]: r["count"] for r in c.fetchall()}

    # ------------------------------------------------------------------
    # WRITER: SolutionEngine — violations
    # ------------------------------------------------------------------

    def WriteViolations(self, violations, writer="solution_engine"):
        """Write violations. violations = list of dicts with file_path, rule, etc."""
        c = self.conn.cursor()
        for v in violations:
            c.execute("""
                INSERT OR REPLACE INTO agent_violations
                    (file_path, rule, severity, fix_action, blast_radius, writer, written_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                v["file_path"],
                v["rule"],
                v.get("severity", "medium"),
                v.get("fix_action"),
                v.get("blast_radius"),
                writer,
            ))
        self.conn.commit()
        return len(violations)

    def ReadViolations(self, for_file=None):
        """Read violations. If for_file given, returns violations for that file."""
        c = self.conn.cursor()
        if for_file:
            c.execute("SELECT * FROM agent_violations WHERE file_path = ?", (for_file,))
        else:
            c.execute("SELECT * FROM agent_violations")
        return [dict(r) for r in c.fetchall()]

    def UpdateViolationBlastRadius(self, file_path, blast_radius):
        """Update the blast radius for a violation (solution engine reads from agent graph)."""
        c = self.conn.cursor()
        c.execute("""
            UPDATE agent_violations SET blast_radius = ? WHERE file_path = ?
        """, (blast_radius, file_path))
        self.conn.commit()

    # ------------------------------------------------------------------
    # READER: GraphViewer — read everything for visualization
    # ------------------------------------------------------------------

    def ReadAllForVisualization(self):
        """Read all agent data for the graph viewer."""
        return {
            "prediction_links": self.ReadPredictionLinks(),
            "world_model": self.ReadWorldModel(),
            "emotional_state": self.ReadEmotionalState(),
            "blast_radius": self.ReadBlastRadius(),
            "violations": self.ReadViolations(),
        }

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def Stats(self):
        """Return table row counts for quick health check."""
        c = self.conn.cursor()
        tables = [
            "agent_prediction_links", "agent_world_model",
            "agent_emotional_state", "agent_violations", "agent_blast_radius",
        ]
        stats = {}
        for t in tables:
            c.execute(f"SELECT COUNT(*) as n FROM {t}")
            stats[t] = c.fetchone()["n"]
        return stats


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    db = BrainDb()
    db.Connect()
    stats = db.Stats()
    print("=" * 60)
    print("  BRAIN DB — The Dinner Table")
    print("=" * 60)
    print(f"\n  Database: {db.db_path}")
    print(f"\n  Tables:")
    for table, count in stats.items():
        print(f"    {table:30s} {count:6d} rows")
    db.Disconnect()
    print("\n  OK — dinner table is ready.")
    print("=" * 60)
