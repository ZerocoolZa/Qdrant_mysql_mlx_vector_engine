<!-- [@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<Binding spec for MemUnit event-sourcing schema. In-RAM SQLite is working projection, event-log file is durable truth. Defines replay algorithm, rollback contract, BCL binding. No VBStyle violations (spec doc).>][@todos<none>]} -->
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/MEMUNIT_EVENT_SOURCING_SPEC.md"
# date="2026-06-27" author="Devin" session_id="memunit-eventsourcing-spec"
# context="Binding specification for MemUnit event-sourcing schema. In-RAM SQLite is the working projection; the persisted event-log file is the durable truth. Enables exact reconstruction of any BCL-stamped codebase at any point in time, including full AST + execution state rollback. Full reasoning at class AND method level."}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="spec doc"}
# [@FILEID]{id="MEMUNIT_EVENT_SOURCING_SPEC.md" domain="memunit" authority="spec"}
# [@SUMMARY]{summary="Event-sourcing schema for deterministic AST + reasoning reconstruction. In-RAM SQLite (:memory:) is the live derived projection, rebuilt on every startup from the durable event-log file. Append-only event log is sole truth. AST nodes, versioned content, BCL stamps, trace steps, dependency edges, execution state, and materialized snapshots. Replay algorithm rebuilds any past state. Rollback is append-only (never deletes)."}

# MemUnit Event-Sourcing Schema — Binding Specification

> **Core thesis:** The persisted event-log file is the only source of truth.
> The in-RAM SQLite database is a **working projection** — rebuilt on every
> startup by replaying the event log into `:memory:`. Every AST node, every
> BCL stamp, every reasoning trace, and every execution state is a derived
> projection of the event log. Nothing is mutated in place. Reconstruct any
> past state by replaying events up to a bound.
>
> **Storage model:**
> - **Durable truth:** `memunit_events.log` (append-only file on disk) + `memunit_snapshots/` (checkpoint files)
> - **Working state:** `:memory:` SQLite database, rebuilt on startup, lost on exit, never the source of truth
> - **Why in-RAM SQLite:** zero network latency, microsecond reads, full SQL for queries, atomic transactions via BEGIN/COMMIT, and it can be discarded and rebuilt at any time from the event log
>
> **Scope:** This spec defines the in-RAM SQLite schema for MemUnit, the
> event-log file format, the replay algorithm, and the binding contract for
> how BCL attaches to AST and how state is rebuilt. Full reasoning at class
> AND method level.
>
> **Non-goal:** This is not a new language. BCL is a given primitive. This is
> the binding contract for how BCL attaches to AST and how state is rebuilt.

---

## 1. Design Principles (inviolable)

| # | Principle | Consequence |
|---|---|---|
| P1 | **Append-only event log file is sole truth** | The `.log` file is only ever appended to; corrections are new events |
| P2 | **In-RAM SQLite is derived, rebuildable, disposable** | The `:memory:` DB can be dropped at any time and rebuilt from the event log |
| P3 | **AST nodes are identity, versions are content** | A node's `node_id` is immutable; its content changes via new version rows |
| P4 | **BCL stamps bind to (node_id, version_id)** | Reasoning is per-version, not per-node — old reasoning is preserved |
| P5 | **Reasoning exists at class AND method level** | Class-level stamps describe class-wide intent; method stamps describe per-method logic. Both are first-class. |
| P6 | **Rollback is append-only** | Rollback = a new `EVENT_ROLLBACK` event that re-points `is_current`; never deletes history |
| P7 | **No orphan nodes** | An AST node with no BCL stamp at its current version → pre-execution gate rejects |
| P8 | **Trace chains are continuous** | A gap in `mu_trace_steps.step_no` for a `trace_id` → gate rejects |
| P9 | **Deterministic replay** | Same event-log prefix → identical in-RAM state, row-for-row |
| P10 | **Snapshots are cache, not truth** | Snapshot files may be deleted and rebuilt from the event log at any time |
| P11 | **Single connection, single writer** | `:memory:` SQLite has one connection; no concurrent writers, no lock contention |

---

## 2. Storage Architecture

```
DISK (durable truth)                          RAM (working projection)
┌──────────────────────────────┐             ┌──────────────────────────────┐
│ memunit_events.log           │  replay     │ :memory: SQLite              │
│   (append-only JSON lines)   │ ─────────>  │   mu_events                  │
│                              │             │   mu_ast_nodes               │
│ memunit_snapshots/           │  hydrate    │   mu_ast_versions            │
│   snap_000001.json           │ ─────────>  │   mu_bcl_stamps              │
│   snap_001000.json           │             │   mu_trace_steps             │
│   snap_002000.json           │             │   mu_dependency_edges        │
│                              │             │   mu_node_state              │
│ memunit_blobs/               │  load       │   mu_edge_state              │
│   <content_hash>.lz4         │ ─────────>  │   mu_semantic_tags           │
│   (content-addressed AST)    │             │   mu_execution_state         │
└──────────────────────────────┘             └──────────────────────────────┘
        ▲                                              │
        │ checkpoint (every N events                   │
        │   or session end)                            │
        └──────────────────────────────────────────────┘
```

**Lifecycle:**
1. **Startup:** open `:memory:` SQLite → create schema → load latest snapshot → replay events forward from snapshot's last event id → in-RAM DB is live
2. **Runtime:** all reads/writes go through the in-RAM DB; every write also appends to `memunit_events.log` (write-ahead to disk before committing in RAM — durability)
3. **Checkpoint:** every N events (default 1000) or on session end, dump a snapshot to `memunit_snapshots/snap_XXXXXX.json` and flush the event log
4. **Shutdown:** final checkpoint, close `:memory:` (RAM freed), disk files persist
5. **Crash recovery:** on next startup, replay from last good snapshot + remaining event log; the write-ahead-to-disk-before-RAM-commit rule guarantees no lost events

---

## 3. Event Log File Format (`memunit_events.log`)

Append-only JSON Lines (one JSON object per line). Human-readable, greppable, and trivially replayable.

```jsonl
{"id":1,"type":"EVENT_AST_NODE_CREATED","ts":"2026-06-27T12:00:01","ast_node_id":1,"ast_version_after":1,"trace_id":"trace_memunit_v1","session_id":"sess_001","parent_event_id":null,"cause":"initial ingest","before":null,"after":{"node_type":"CLASS","symbolic_name":"MemUnit","parent_node_id":null,"file_path":"Dom_Graph/MemUnit.py","hash_base":"a1b2c3..."}}
{"id":2,"type":"EVENT_AST_VERSION_ADDED","ts":"2026-06-27T12:00:02","ast_node_id":1,"ast_version_before":null,"ast_version_after":2,"trace_id":"trace_memunit_v1","session_id":"sess_001","parent_event_id":1,"cause":"method body parsed","before":null,"after":{"version_no":1,"content_hash":"d4e5f6...","content_format":"SOURCE","blob_uri":"memunit_blobs/d4e5f6.lz4"}}
{"id":3,"type":"EVENT_BCL_STAMP_ATTACHED","ts":"2026-06-27T12:00:03","ast_node_id":1,"ast_version_after":2,"trace_id":"trace_memunit_v1","session_id":"sess_001","parent_event_id":2,"cause":"class reasoning bound","before":null,"after":{"stamp_id":1,"scope_binding":"FULL","intent_vector":{"primary_goal":"Reasoning state store"},"dependency_set":{"graph_edges":[4,5,6]},"event_refs":[1]}}
```

**Rules:**
- `id` is monotonic, gapless, never reused
- Every line is self-contained (no external references needed to apply it)
- `before`/`after` are JSON snapshots of the affected row (small) or URIs to blob files (large)
- File is append-only; corruption recovery = truncate at last valid line + replay
- `event_hash` (SHA-256 of the line excluding the hash field itself) is stored in-RAM only for tamper detection during replay; not written to the file (the file's own line ordering is the integrity guarantee)

---

## 4. In-RAM SQLite Schema

All tables live in `:memory:`. SQLite dialect: `AUTOINCREMENT` not `AUTO_INCREMENT`, `CHECK` constraints not `ENUM`, `TEXT` for JSON (validated in Python), no `ENGINE=` clause.

### 4.1 `mu_events` — Event log mirror (in-RAM copy of the file)

```sql
CREATE TABLE mu_events (
  id                   INTEGER PRIMARY KEY AUTOINCREMENT,
  type                 TEXT    NOT NULL CHECK (type IN (
    'EVENT_NODE_CREATED','EVENT_NODE_UPDATED','EVENT_STATE_CHANGED',
    'EVENT_EDGE_CREATED','EVENT_TAG_ADDED','EVENT_TASK_STARTED',
    'EVENT_TASK_COMPLETED','EVENT_ERROR_RAISED','EVENT_CODE_GRAPH_CHANGED',
    'EVENT_AST_NODE_CREATED','EVENT_AST_VERSION_ADDED','EVENT_AST_NODE_DESTROYED',
    'EVENT_BCL_STAMP_ATTACHED','EVENT_BCL_STAMP_SUPERSEDED',
    'EVENT_TRACE_STEP_APPENDED','EVENT_DEPENDENCY_EDGE_ADDED',
    'EVENT_ROLLBACK','EVENT_CHECKPOINT'
  )),
  ts                   TEXT    NOT NULL,  -- ISO 8601
  target_node          INTEGER,
  target_edge          INTEGER,
  ast_node_id          INTEGER,
  ast_version_before   INTEGER,
  ast_version_after    INTEGER,
  trace_id             TEXT,
  session_id           TEXT,
  parent_event_id      INTEGER,
  cause                TEXT,
  before_state         TEXT,  -- JSON
  after_state          TEXT,  -- JSON
  event_hash           TEXT   -- SHA-256, computed on load
);
CREATE INDEX idx_events_type   ON mu_events(type);
CREATE INDEX idx_events_node   ON mu_events(ast_node_id);
CREATE INDEX idx_events_trace  ON mu_events(trace_id);
CREATE INDEX idx_events_session ON mu_events(session_id);
CREATE INDEX idx_events_parent ON mu_events(parent_event_id);
CREATE INDEX idx_events_ts     ON mu_events(ts);
```

### 4.2 `mu_ast_nodes` — Identity registry (immutable identity)

```sql
CREATE TABLE mu_ast_nodes (
  node_id            INTEGER PRIMARY KEY AUTOINCREMENT,
  node_type          TEXT    NOT NULL CHECK (node_type IN ('FILE','CLASS','METHOD','BLOCK')),
  symbolic_name      TEXT    NOT NULL,
  parent_node_id     INTEGER,
  file_path          TEXT,
  line_range         TEXT,   -- e.g. "291-329"
  hash_base          TEXT    NOT NULL,  -- SHA-256(type||name||parent||path)
  created_event_id   INTEGER NOT NULL,
  destroyed_event_id INTEGER,           -- NULL = live
  created_at         TEXT    NOT NULL,
  FOREIGN KEY (parent_node_id) REFERENCES mu_ast_nodes(node_id),
  FOREIGN KEY (created_event_id) REFERENCES mu_events(id),
  FOREIGN KEY (destroyed_event_id) REFERENCES mu_events(id)
);
CREATE INDEX idx_nodes_type     ON mu_ast_nodes(node_type);
CREATE INDEX idx_nodes_parent   ON mu_ast_nodes(parent_node_id);
CREATE INDEX idx_nodes_symbolic ON mu_ast_nodes(symbolic_name);
CREATE INDEX idx_nodes_file     ON mu_ast_nodes(file_path);
CREATE INDEX idx_nodes_live     ON mu_ast_nodes(destroyed_event_id);
```

**Identity rule:** `hash_base = SHA256(node_type || symbolic_name || parent_node_id || file_path)`.
Two nodes with the same `hash_base` are the *same logical node* across rebuilds.
This is what makes replay deterministic across re-ingestions.

### 4.3 `mu_ast_versions` — Content-addressed versions

```sql
CREATE TABLE mu_ast_versions (
  version_id          INTEGER PRIMARY KEY AUTOINCREMENT,
  node_id             INTEGER NOT NULL,
  version_no          INTEGER NOT NULL,
  content_hash        TEXT    NOT NULL,  -- SHA-256 of decompressed content
  content_blob        TEXT,              -- inline if small; NULL if blob_uri used
  content_format      TEXT    NOT NULL CHECK (content_format IN ('SOURCE','AST_JSON')),
  blob_uri            TEXT,              -- path to memunit_blobs/<hash>.lz4 if content_blob is NULL
  created_event_id    INTEGER NOT NULL,
  superseded_event_id INTEGER,           -- event id that created the next version
  is_current          INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0,1)),
  created_at          TEXT    NOT NULL,
  UNIQUE (node_id, version_no),
  FOREIGN KEY (node_id) REFERENCES mu_ast_nodes(node_id),
  FOREIGN KEY (created_event_id) REFERENCES mu_events(id)
);
CREATE INDEX idx_versions_node    ON mu_ast_versions(node_id);
CREATE INDEX idx_versions_hash    ON mu_ast_versions(content_hash);
CREATE INDEX idx_versions_current ON mu_ast_versions(node_id, is_current);
```

**Rules:**
- Only one `is_current=1` per `node_id` at any point in the event log.
- `content_blob` holds inline content if < 4KB (compressed); larger content lives in `memunit_blobs/<content_hash>.lz4` and `content_blob` is NULL with `blob_uri` set.
- `version_no` is monotonic per node; never reused.
- Content-addressed: two version rows with the same `content_hash` share the same blob file (dedup).

### 4.4 `mu_bcl_stamps` — Reasoning layer (class AND method level)

```sql
CREATE TABLE mu_bcl_stamps (
  stamp_id          INTEGER PRIMARY KEY AUTOINCREMENT,
  node_id           INTEGER NOT NULL,    -- AST node (FILE/CLASS/METHOD/BLOCK)
  ast_version_id    INTEGER NOT NULL,    -- which content version this binds to
  trace_id          TEXT    NOT NULL,    -- global reasoning chain id
  scope_binding     TEXT    NOT NULL CHECK (scope_binding IN ('FULL','PARTIAL','DELTA')),
  coverage_detail   TEXT,                -- for PARTIAL: which sub-nodes (JSON)
  intent_vector     TEXT    NOT NULL,    -- JSON: {primary_goal, secondary_goals[], optimization_targets[], constraints[], rejected_strategies[]}
  dependency_set    TEXT    NOT NULL,    -- JSON: {reads[], writes[], calls[], imports[], graph_edges[]}
  event_refs        TEXT    NOT NULL,    -- JSON: [event_id, ...] ordered causality chain
  state_status      TEXT    NOT NULL CHECK (state_status IN ('ACTIVE','STALE','BROKEN','DERIVED')) DEFAULT 'ACTIVE',
  confidence_score  REAL    NOT NULL DEFAULT 1.0,
  validation_state  TEXT    NOT NULL CHECK (validation_state IN ('UNVERIFIED','VERIFIED','FAILED')) DEFAULT 'UNVERIFIED',
  created_event_id  INTEGER NOT NULL,
  superseded_by     INTEGER,             -- stamp_id of replacement (append-only)
  created_at        TEXT    NOT NULL,
  FOREIGN KEY (node_id) REFERENCES mu_ast_nodes(node_id),
  FOREIGN KEY (ast_version_id) REFERENCES mu_ast_versions(version_id),
  FOREIGN KEY (created_event_id) REFERENCES mu_events(id),
  FOREIGN KEY (superseded_by) REFERENCES mu_bcl_stamps(stamp_id)
);
CREATE INDEX idx_stamps_node     ON mu_bcl_stamps(node_id);
CREATE INDEX idx_stamps_version  ON mu_bcl_stamps(ast_version_id);
CREATE INDEX idx_stamps_trace    ON mu_bcl_stamps(trace_id);
CREATE INDEX idx_stamps_status   ON mu_bcl_stamps(state_status);
CREATE INDEX idx_stamps_scope    ON mu_bcl_stamps(scope_binding);
CREATE INDEX idx_stamps_active   ON mu_bcl_stamps(superseded_by);
```

**Class-level vs method-level reasoning (P5):**
- A `CLASS` node has a stamp with `scope_binding=FULL` describing class-wide intent (the `intent_vector.primary_goal` of the whole class).
- Each `METHOD` node under that class has its own stamp with `scope_binding=FULL` or `PARTIAL` describing that method's logic.
- The class stamp's `dependency_set.graph_edges` lists the method node_ids it contains.
- A method stamp's `event_refs` MUST include the class stamp's `created_event_id` as the first entry (causality: method reasoning descends from class reasoning).

**No-orphan rule (P7):** For every `mu_ast_nodes` row where `destroyed_event_id IS NULL`, there MUST be at least one `mu_bcl_stamps` row with `node_id = X AND ast_version_id = (current version of X) AND state_status = 'ACTIVE' AND superseded_by IS NULL`. The pre-execution gate enforces this.

### 4.5 `mu_trace_steps` — Deterministic replay chain

```sql
CREATE TABLE mu_trace_steps (
  step_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  trace_id       TEXT    NOT NULL,
  step_no        INTEGER NOT NULL,
  decision       TEXT    NOT NULL,   -- structured atom, not prose
  input_nodes    TEXT    NOT NULL,   -- JSON: [node_id, ...]
  transformation TEXT    NOT NULL,   -- structured op name
  output_nodes   TEXT    NOT NULL,   -- JSON: [node_id, ...]
  event_id       INTEGER NOT NULL,
  created_at     TEXT    NOT NULL,
  UNIQUE (trace_id, step_no),
  FOREIGN KEY (event_id) REFERENCES mu_events(id)
);
CREATE INDEX idx_trace_steps_trace ON mu_trace_steps(trace_id);
CREATE INDEX idx_trace_steps_step  ON mu_trace_steps(trace_id, step_no);
```

**Continuity rule (P8):** For a given `trace_id`, `step_no` MUST be a contiguous sequence starting at 1. Any gap = broken trace = gate rejects.

### 4.6 `mu_dependency_edges` — Versioned graph binding

```sql
CREATE TABLE mu_dependency_edges (
  edge_id           INTEGER PRIMARY KEY AUTOINCREMENT,
  from_node_id      INTEGER NOT NULL,
  to_node_id        INTEGER NOT NULL,
  from_version_id   INTEGER NOT NULL,
  to_version_id     INTEGER,           -- NULL = "any version" (e.g. imports)
  edge_type         TEXT    NOT NULL CHECK (edge_type IN ('READS','WRITES','CALLS','IMPORTS','INHERITS','GRAPH')),
  evidence_event_id INTEGER NOT NULL,
  validity_state    TEXT    NOT NULL CHECK (validity_state IN ('VALID','SUPERSEDED','BROKEN')) DEFAULT 'VALID',
  created_at        TEXT    NOT NULL,
  FOREIGN KEY (from_node_id) REFERENCES mu_ast_nodes(node_id),
  FOREIGN KEY (to_node_id) REFERENCES mu_ast_nodes(node_id),
  FOREIGN KEY (evidence_event_id) REFERENCES mu_events(id)
);
CREATE INDEX idx_edges_from     ON mu_dependency_edges(from_node_id);
CREATE INDEX idx_edges_to       ON mu_dependency_edges(to_node_id);
CREATE INDEX idx_edges_from_ver ON mu_dependency_edges(from_version_id);
CREATE INDEX idx_edges_type     ON mu_dependency_edges(edge_type);
CREATE INDEX idx_edges_validity ON mu_dependency_edges(validity_state);
```

**Rule:** Every `from_node_id` and `to_node_id` MUST exist in `mu_ast_nodes`. No raw strings at runtime level (matches BCL grammar spec §6).

### 4.7 `mu_node_state` — Reasoning-node state (existing, kept)

```sql
CREATE TABLE mu_node_state (
  node_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  node_type      TEXT    NOT NULL,
  semantic_tag   TEXT,
  current_state  TEXT    NOT NULL DEFAULT 'OPEN',
  version        INTEGER NOT NULL DEFAULT 1,
  title          TEXT,
  content        TEXT,
  uncertainty    TEXT,
  parent_id      INTEGER,
  root_id        INTEGER,
  bcl_method_id  INTEGER,
  bcl_class_id   INTEGER,
  confidence     REAL    NOT NULL DEFAULT 1.0,
  last_touch     TEXT    NOT NULL
);
CREATE INDEX idx_node_state_state   ON mu_node_state(current_state);
CREATE INDEX idx_node_state_semantic ON mu_node_state(semantic_tag);
CREATE INDEX idx_node_state_root    ON mu_node_state(root_id);
CREATE INDEX idx_node_state_bcl     ON mu_node_state(bcl_method_id);
```

### 4.8 `mu_edge_state` — Reasoning-edge state (existing, kept)

```sql
CREATE TABLE mu_edge_state (
  edge_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  from_node      INTEGER NOT NULL,
  to_node        INTEGER NOT NULL,
  edge_type      TEXT    NOT NULL,
  strength       REAL    NOT NULL DEFAULT 1.0,
  validity_state TEXT    NOT NULL DEFAULT 'VALID',
  evidence       TEXT,
  certainty      TEXT    NOT NULL DEFAULT 'PROBABLE',
  last_touch     TEXT    NOT NULL
);
CREATE INDEX idx_edge_state_from ON mu_edge_state(from_node);
CREATE INDEX idx_edge_state_to   ON mu_edge_state(to_node);
CREATE INDEX idx_edge_state_type ON mu_edge_state(edge_type);
```

### 4.9 `mu_semantic_tags` (existing, kept)

```sql
CREATE TABLE mu_semantic_tags (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  node_id         INTEGER NOT NULL,
  tag             TEXT    NOT NULL,
  confidence_score REAL   NOT NULL DEFAULT 0.5,
  source          TEXT    NOT NULL DEFAULT 'manual'
);
CREATE INDEX idx_tags_node ON mu_semantic_tags(node_id);
CREATE INDEX idx_tags_tag  ON mu_semantic_tags(tag);
```

### 4.10 `mu_execution_state` — Live execution context (extended)

```sql
CREATE TABLE mu_execution_state (
  id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id               INTEGER NOT NULL,
  active_node           INTEGER,
  execution_path        TEXT,    -- JSON
  open_loops            TEXT,    -- JSON
  blocked_by            TEXT,    -- JSON
  last_error            TEXT,
  active_ast_versions   TEXT,    -- JSON: {node_id: version_id, ...}
  rollback_point_event  INTEGER,
  last_rollback_at      TEXT,
  last_touch            TEXT    NOT NULL
);
CREATE INDEX idx_exec_task     ON mu_execution_state(task_id);
CREATE INDEX idx_exec_rollback ON mu_execution_state(rollback_point_event);
```

### 4.11 `mu_snapshots` — Rebuild checkpoints (in-RAM index of snapshot files)

```sql
CREATE TABLE mu_snapshots (
  snapshot_id         INTEGER PRIMARY KEY AUTOINCREMENT,
  taken_at_event_id   INTEGER NOT NULL,
  taken_at_ts         TEXT    NOT NULL,
  snapshot_file       TEXT    NOT NULL,  -- path to memunit_snapshots/snap_XXXXXX.json
  ast_node_versions   TEXT    NOT NULL,  -- JSON: {node_id: version_id, ...}
  active_stamps       TEXT    NOT NULL,  -- JSON: [stamp_id, ...]
  trace_ids           TEXT    NOT NULL,  -- JSON: [trace_id, ...]
  dependency_edge_ids TEXT    NOT NULL,  -- JSON: [edge_id, ...]
  content_hash        TEXT    NOT NULL,  -- hash of all the above (tamper check)
  created_at          TEXT    NOT NULL
);
CREATE INDEX idx_snapshots_event ON mu_snapshots(taken_at_event_id);
```

**Cache rule (P10):** Any snapshot file may be deleted and rebuilt from the event log. Snapshots are an optimization to avoid replaying from epoch on every rebuild. The replay algorithm (§5) uses the latest snapshot before the target bound, then replays forward.

---

## 5. Replay Algorithm

Rebuild the in-RAM SQLite state as of a bound `B`, where `B` is either a timestamp or an event id.

```
FUNCTION RebuildAt(bound B):
    # 1. Find the latest snapshot at or before B
    S = SELECT * FROM mu_snapshots
        WHERE taken_at_event_id <= B.event_id
        ORDER BY taken_at_event_id DESC LIMIT 1

    IF S exists:
        state = hydrate(S.ast_node_versions, S.active_stamps,
                        S.trace_ids, S.dependency_edge_ids)
        start_event = S.taken_at_event_id + 1
    ELSE:
        state = empty
        start_event = 1

    # 2. Replay events forward from start_event to B
    events = SELECT * FROM mu_events
             WHERE id >= start_event AND id <= B.event_id
             ORDER BY id ASC

    FOR each event E in events:
        APPLY(E, state)

    # 3. Verify integrity
    IF NOT VerifyContinuity(state):
        RAISE BrokenTraceError

    RETURN state


FUNCTION APPLY(event E, state):
    SWITCH E.type:
        CASE 'EVENT_AST_NODE_CREATED':
            INSERT INTO mu_ast_nodes (node_id, node_type, symbolic_name,
                parent_node_id, file_path, line_range, hash_base,
                created_event_id, created_at)
            VALUES (E.ast_node_id, E.after.node_type, E.after.symbolic_name,
                E.after.parent_node_id, E.after.file_path, E.after.line_range,
                E.after.hash_base, E.id, E.ts)

        CASE 'EVENT_AST_VERSION_ADDED':
            # flip is_current on prior version
            UPDATE mu_ast_versions SET is_current=0
              WHERE node_id=E.ast_node_id AND is_current=1
            INSERT INTO mu_ast_versions (version_id, node_id, version_no,
                content_hash, content_blob, content_format, blob_uri,
                created_event_id, is_current, created_at)
            VALUES (E.ast_version_after, E.ast_node_id, E.after.version_no,
                E.after.content_hash, E.after.content_blob,
                E.after.content_format, E.after.blob_uri, E.id, 1, E.ts)

        CASE 'EVENT_AST_NODE_DESTROYED':
            UPDATE mu_ast_nodes SET destroyed_event_id=E.id
              WHERE node_id=E.ast_node_id

        CASE 'EVENT_BCL_STAMP_ATTACHED':
            INSERT INTO mu_bcl_stamps (stamp_id, node_id, ast_version_id,
                trace_id, scope_binding, coverage_detail, intent_vector,
                dependency_set, event_refs, state_status, confidence_score,
                validation_state, created_event_id, created_at)
            VALUES (E.after.stamp_id, E.ast_node_id, E.ast_version_after,
                E.trace_id, E.after.scope_binding, E.after.coverage_detail,
                E.after.intent_vector, E.after.dependency_set,
                E.after.event_refs, 'ACTIVE', E.after.confidence_score,
                'UNVERIFIED', E.id, E.ts)

        CASE 'EVENT_BCL_STAMP_SUPERSEDED':
            UPDATE mu_bcl_stamps SET superseded_by=E.after.new_stamp_id
              WHERE stamp_id=E.after.old_stamp_id
            INSERT new stamp row (same as EVENT_BCL_STAMP_ATTACHED)

        CASE 'EVENT_TRACE_STEP_APPENDED':
            INSERT INTO mu_trace_steps (step_id, trace_id, step_no, decision,
                input_nodes, transformation, output_nodes, event_id, created_at)
            VALUES (E.after.step_id, E.trace_id, E.after.step_no,
                E.after.decision, E.after.input_nodes,
                E.after.transformation, E.after.output_nodes, E.id, E.ts)

        CASE 'EVENT_DEPENDENCY_EDGE_ADDED':
            INSERT INTO mu_dependency_edges (edge_id, from_node_id, to_node_id,
                from_version_id, to_version_id, edge_type, evidence_event_id,
                validity_state, created_at)
            VALUES (E.after.edge_id, E.after.from_node_id, E.after.to_node_id,
                E.after.from_version_id, E.after.to_version_id,
                E.after.edge_type, E.id, 'VALID', E.ts)

        CASE 'EVENT_ROLLBACK':
            # Append-only: re-point is_current to the version at B
            target_versions = json_parse(E.after_state)
            FOR node_id, version_id IN target_versions:
                UPDATE mu_ast_versions SET is_current=0
                  WHERE node_id=node_id AND is_current=1
                UPDATE mu_ast_versions SET is_current=1
                  WHERE node_id=node_id AND version_id=version_id
            UPDATE mu_execution_state SET
                rollback_point_event=E.id,
                last_rollback_at=E.ts,
                active_ast_versions=E.after_state
              WHERE task_id=current_task

        CASE existing reasoning events (NODE_CREATED, STATE_CHANGED, etc.):
            # delegate to existing EventSourcedMemUnit logic
            apply_existing(E, state)

        DEFAULT:
            RAISE UnknownEventError


FUNCTION VerifyContinuity(state):
    # P7: no orphan nodes
    orphans = SELECT n.node_id FROM mu_ast_nodes n
              LEFT JOIN mu_bcl_stamps s
                ON s.node_id=n.node_id AND s.state_status='ACTIVE'
                   AND s.superseded_by IS NULL
                   AND s.ast_version_id = (
                     SELECT version_id FROM mu_ast_versions
                     WHERE node_id=n.node_id AND is_current=1)
              WHERE n.destroyed_event_id IS NULL AND s.stamp_id IS NULL
    IF orphans: RETURN False

    # P8: trace continuity
    broken = SELECT trace_id FROM mu_trace_steps
             GROUP BY trace_id
             HAVING MIN(step_no) != 1
                OR (MAX(step_no) - MIN(step_no) + 1) != COUNT(*)
    IF broken: RETURN False

    # P9: dependency edges reference live versions
    stale = SELECT e.edge_id FROM mu_dependency_edges e
            JOIN mu_ast_versions v ON v.version_id=e.from_version_id
            WHERE e.validity_state='VALID' AND v.is_current=0
    IF stale: RETURN False

    RETURN True
```

**Complexity:** Without snapshots, O(N) where N = events up to B. With snapshots
every K events, O(K) per rebuild. Recommended K = 1000 or per-session-boundary.
In-RAM SQLite makes this fast — no network, no disk seeks during replay.

---

## 6. Rollback Protocol (append-only, P6)

Rollback NEVER deletes. It appends an `EVENT_ROLLBACK` that re-points
`is_current` to a prior version. The history of what was rolled back is
preserved forever — both in the event log file and in the in-RAM DB.

```
FUNCTION RollbackTo(target_event_id T):
    # 1. Rebuild state at T (read-only, into a temp in-RAM DB)
    past = RebuildAt(T)

    # 2. Capture the target version map
    target_versions = SELECT node_id, current_version FROM past

    # 3. Append to event log file FIRST (durability: disk before RAM)
    append_to_log({
        type: 'EVENT_ROLLBACK',
        ts: now_iso(),
        after_state: json(target_versions),
        cause: 'rollback to ' + T,
        parent_event_id: current_max_event_id
    })

    # 4. Load the new event into the in-RAM DB
    rollback_event = load_last_event_from_log()

    # 5. Apply the rollback event to live in-RAM state
    APPLY(rollback_event, live_state)

    # 6. Log a trace step (the rollback itself is a reasoning act)
    append_to_log({
        type: 'EVENT_TRACE_STEP_APPENDED',
        trace_id: current_trace,
        after: {
            step_no: next_step,
            decision: 'ROLLBACK',
            input_nodes: [],
            transformation: 'revert_to_version',
            output_nodes: list(target_versions.keys())
        }
    })
```

**Why append-only rollback matters:** You can always ask "what did the system
look like before the rollback?" by rebuilding at `T-1`. You can audit *why* a
rollback happened (the `cause` + `parent_event_id` chain). You can replay a
rollback forward to see if a different fix would have worked. None of this is
possible if rollback deletes.

**Durability rule:** The event is appended to the disk file *before* the in-RAM
DB is mutated. If the process crashes between the two, the next startup replays
the event log (which has the rollback) and the in-RAM DB converges to the same
state. No lost rollbacks.

---

## 7. Pre-Execution Gate Integration

Extends `PreExecutionGate.py`. The gate now checks the full binding contract,
not just stamp existence. All checks run against the in-RAM SQLite DB (fast).

```
FUNCTION ValidateMethod(method_name):
    # existing checks (stamp exists, fresh, event_refs valid, source stamped)
    ...existing logic...

    # NEW: AST binding checks
    node = SELECT * FROM mu_ast_nodes
           WHERE symbolic_name = method_name AND destroyed_event_id IS NULL
    IF NOT node:
        REJECT("NO_AST_NODE", "method has no live AST node")

    version = SELECT * FROM mu_ast_versions
              WHERE node_id = node.node_id AND is_current = 1
    IF NOT version:
        REJECT("NO_CURRENT_VERSION", "method's AST node has no current version")

    stamp = SELECT * FROM mu_bcl_stamps
            WHERE node_id = node.node_id AND ast_version_id = version.version_id
              AND state_status = 'ACTIVE' AND superseded_by IS NULL
    IF NOT stamp:
        REJECT("NO_STAMP_FOR_VERSION",
               "no active BCL stamp for the current version of this method")

    # NEW: trace continuity (P8)
    steps = SELECT step_no FROM mu_trace_steps
            WHERE trace_id = stamp.trace_id ORDER BY step_no
    IF steps != range(1, len(steps)+1):
        REJECT("BROKEN_TRACE", "trace chain has gaps")

    # NEW: dependency edges reference valid versions (P9)
    edges = SELECT * FROM mu_dependency_edges
            WHERE from_node_id = node.node_id
              AND from_version_id = version.version_id
              AND validity_state = 'VALID'
    FOR edge IN edges:
        IF edge.to_version_id IS NOT NULL:
            target = SELECT is_current FROM mu_ast_versions
                     WHERE version_id = edge.to_version_id
            IF NOT target.is_current:
                REJECT("STALE_DEPENDENCY",
                       "edge points to a superseded version")

    # NEW: class-level reasoning exists (P5)
    class_node = SELECT * FROM mu_ast_nodes WHERE node_id = node.parent_node_id
    IF class_node AND class_node.node_type = 'CLASS':
        class_stamp = SELECT * FROM mu_bcl_stamps
                      WHERE node_id = class_node.node_id
                        AND state_status = 'ACTIVE'
                        AND superseded_by IS NULL
        IF NOT class_stamp:
            REJECT("NO_CLASS_REASONING",
                   "parent class has no active BCL stamp — method reasoning is orphaned")

    APPROVE
```

---

## 8. Class + Method Reasoning Binding (P5 detail)

The user's requirement: **full reasoning at class AND method level.**

```
FILE: MemUnit.py
  └─ CLASS: MemUnit
       ├─ BCL_STAMP (class-level, scope=FULL)
       │    intent_vector.primary_goal = "Reasoning state store for LLM cognitive architecture"
       │    dependency_set.graph_edges = [method_node_ids...]
       │    event_refs = [class_creation_event]
       │
       ├─ METHOD: CreateNode
       │    └─ BCL_STAMP (method-level, scope=FULL)
       │         intent_vector.primary_goal = "Insert a reasoning node + log creation event"
       │         dependency_set.writes = [mu_nodes, mu_events]
       │         event_refs = [class_stamp.created_event_id, method_creation_event]
       │         trace_id = "trace_memunit_createnode_v1"
       │
       ├─ METHOD: TransitionState
       │    └─ BCL_STAMP (method-level, scope=FULL)
       │         intent_vector.primary_goal = "Enforce state machine + log transition"
       │         constraints = ["VALID_TRANSITIONS whitelist"]
       │         event_refs = [class_stamp.created_event_id, ...]
       │
       └─ METHOD: QueryChain
            └─ BCL_STAMP (method-level, scope=FULL)
                 intent_vector.primary_goal = "Reconstruct reasoning chain by root_id"
                 dependency_set.reads = [mu_nodes, mu_edges]
```

**Binding rules:**
1. A method stamp's `event_refs[0]` MUST be its class stamp's `created_event_id`.
2. A class stamp's `dependency_set.graph_edges` MUST list all live method node_ids under it.
3. If a method is added/removed, the class stamp is superseded (new class stamp with updated `graph_edges`).
4. A method's `intent_vector.constraints` may refine the class's `intent_vector.constraints` but never contradict them.

---

## 9. Migration Path (from existing MySQL schema)

The existing `EventSourcedMemUnit.py` uses MySQL. Migration to in-RAM SQLite is a cutover, not an in-place alter.

```
Phase 1 (build new system, parallel):
  - Implement the in-RAM SQLite MemUnit (this spec)
  - Implement the event-log file writer + reader
  - Implement the replay engine
  - New writes go to BOTH MySQL (legacy) and the new event log (dual-write)

Phase 2 (backfill):
  - For each existing bcl_methods/bcl_classes/bcl_files row in MySQL:
    emit EVENT_AST_NODE_CREATED + EVENT_AST_VERSION_ADDED +
    EVENT_BCL_STAMP_ATTACHED into the new event log
  - For each existing mu_events row in MySQL: copy into the new event log
  - Take first snapshot at current max event id

Phase 3 (cutover):
  - PreExecutionGate switches to reading from in-RAM SQLite
  - Stop dual-writing to MySQL (MySQL becomes read-only legacy)
  - New code only uses the in-RAM SQLite path

Phase 4 (decommission):
  - After verification period, archive MySQL tables (read-only backup)
  - Event log file + snapshots are the sole durable truth
```

---

## 10. Conflict Resolution (when traces diverge)

If two agents reason about the same node concurrently and produce divergent
trace chains:

```
RULE: Last-writer-wins on ast_version_id, but BOTH traces are preserved.

  Agent A: EVENT_AST_VERSION_ADDED (version 5, trace_id=TA)
  Agent B: EVENT_AST_VERSION_ADDED (version 5, trace_id=TB)  -- conflict

RESOLUTION:
  1. Both events are kept (append-only).
  2. The event with the higher id wins is_current (deterministic).
  3. The losing trace's stamp is marked state_status='DERIVED' (not BROKEN).
  4. A new EVENT_BCL_STAMP_SUPERSEDED links the losing stamp to the winning one.
  5. The losing trace is still replayable (you can rebuild at the losing event
     to see what that agent produced).
```

This preserves both reasoning paths for audit without blocking either agent.

**Single-writer note (P11):** In-RAM SQLite has one connection, so concurrent
agents serialize through the single writer. If true parallelism is needed,
each agent gets its own `:memory:` DB (its own projection) and reconciles via
the shared event log file (file lock + append). The reconciliation is
deterministic by event id ordering.

---

## 11. Compression Rules (avoid file bloat)

| Blob type | Strategy |
|---|---|
| `mu_ast_versions.content_blob` (inline, < 4KB) | LZ4 frame compression, stored as TEXT (base64) |
| `mu_ast_versions.content_blob` (>= 4KB) | LZ4 to `memunit_blobs/<content_hash>.lz4`, `content_blob`=NULL, `blob_uri`=path |
| `mu_bcl_stamps.intent_vector` (JSON) | Stored as TEXT; Python validates on read |
| `mu_events.before_state`/`after_state` | Inline JSON if < 4KB; blob URI if larger |
| `mu_snapshots.*_ids` (JSON) | Stored as TEXT in-RAM; snapshot files on disk are LZ4-compressed JSON |
| Snapshot files older than 30 days + superseded by a newer snapshot | Droppable (rebuildable from event log) |

**Dedup rule:** Two `mu_ast_versions` rows with the same `content_hash` share
the same blob file (content-addressed storage). Only the metadata row is
duplicated. This means a revert that produces identical content to a prior
version stores zero new blob bytes.

---

## 12. Verification Checklist (for this spec)

- [ ] Every AST node has at most one `is_current=1` version at any event bound
- [ ] Every live AST node has exactly one ACTIVE, non-superseded BCL stamp at its current version
- [ ] Every method stamp's `event_refs[0]` equals its class stamp's `created_event_id`
- [ ] Every `trace_id` has contiguous `step_no` starting at 1
- [ ] Every `mu_dependency_edges.from_version_id` matches `is_current` at the bound
- [ ] `RebuildAt(B)` is deterministic: same B → same in-RAM state, row-for-row
- [ ] Rollback appends an event to the file; never deletes
- [ ] Event log file is appended to BEFORE in-RAM DB is mutated (durability)
- [ ] Snapshots can be dropped and rebuilt from the event log
- [ ] Pre-execution gate rejects on any broken invariant above
- [ ] In-RAM SQLite DB can be discarded and fully rebuilt from event log + snapshots

---

## 13. File Plan (implementation, one class per file)

Per VBStyle one-class-per-file rule. All in `Dom_Graph/`.

| File | Class | Domain | Role |
|---|---|---|---|
| `EventLogStore.py` | EventLogStore | event_log | Append-only writer + reader for `memunit_events.log` (disk durability) |
| `InRamDb.py` | InRamDb | ram_db | Open `:memory:` SQLite, create schema (§4), single connection, BEGIN/COMMIT |
| `AstNodeRegistry.py` | AstNodeRegistry | ast_identity | CRUD for `mu_ast_nodes` (in-RAM) |
| `AstVersionStore.py` | AstVersionStore | ast_content | CRUD + LZ4 compression for `mu_ast_versions` (in-RAM + blob files) |
| `BclStampStore.py` | BclStampStore | bcl_reasoning | CRUD for `mu_bcl_stamps` (class + method level) |
| `TraceChainStore.py` | TraceChainStore | trace_replay | Append + verify continuity for `mu_trace_steps` |
| `DependencyEdgeStore.py` | DependencyEdgeStore | dep_graph | CRUD for `mu_dependency_edges` |
| `SnapshotStore.py` | SnapshotStore | rebuild_cache | Take + hydrate `mu_snapshots` (in-RAM index + disk files) |
| `ReplayEngine.py` | ReplayEngine | replay | `RebuildAt(B)` + `Apply(E, state)` + `VerifyContinuity` |
| `RollbackEngine.py` | RollbackEngine | rollback | Append-only `RollbackTo(T)` (disk-first, then RAM) |
| `PreExecutionGate.py` | (existing, extend) | bcl_stamp | Add §7 checks (read from in-RAM SQLite) |
| `MemUnitMigrator.py` | MemUnitMigrator | migration | §9 phased migration from MySQL to in-RAM SQLite |
| `Config.py` | (existing, extend) | config | Event log path, snapshot dir, blob dir, snapshot interval, compression threshold |

Each class: `__init__(self, mem=None, db=None, param=None)`, `self.state` dict,
`Run(self, command, params=None)` dispatch, `_p()` helper, `read_state()`,
`set_config()`, all methods return Tuple3 `(1, data, None)` or
`(0, None, (code, desc, 0))`. No print, no decorators, no `self._`, no hardcode.

**Wiring:** `InRamDb` is the shared `db` injected into all stores. `EventLogStore`
is the shared `mem` injected into all stores (durability layer). Each store
writes to `EventLogStore` first (disk), then to `InRamDb` (RAM), in that order.

---

## 14. Final Model

```
LLM OUTPUT (structured reasoning + code)
   |
   v
BCL COMPILER (BCL_COMPILER_PLAN.md — deterministic, type x verb x noun)
   |
   v
AST BINDING LAYER (AstNodeRegistry + AstVersionStore — in-RAM SQLite)
   |
   v
REASONING BINDING (BclStampStore + TraceChainStore — class + method level)
   |
   v
DEPENDENCY BINDING (DependencyEdgeStore — versioned graph edges)
   |
   v
EVENT LOG FILE (memunit_events.log — append-only, durable truth on disk)
   |
   v
IN-RAM SQLITE (:memory: — working projection, rebuilt on every startup)
   |
   v
FILE INJECTION (BCL stamped source — [@BCL_STAMP] header in code)
   |
   v
PRE-EXECUTION GATE (PreExecutionGate — §7 full binding contract check)
   |
   v
EXECUTION
   |
   v
(on any mutation) -> append event to disk file -> apply to in-RAM DB
                                                              |
                                                              v
                                              SnapshotStore (checkpoint every N events)
                                                              |
                                                              v
                                    ReplayEngine.RebuildAt(B) — any past state, deterministic
                                                              |
                                                              v
                                    RollbackEngine.RollbackTo(T) — append-only, never deletes
```

**This is a deterministic, replayable reasoning-to-code compiler with full
causal trace binding at AST level — class AND method — backed by an in-RAM
SQLite working projection over a durable append-only event log file.**
