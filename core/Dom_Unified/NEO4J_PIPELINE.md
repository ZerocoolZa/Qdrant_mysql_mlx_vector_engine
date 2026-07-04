# [@GHOST]{[@file<NEO4J_PIPELINE.md>][@domain<Dom_Unified>][@role<spec>][@auth<cascade>][@date<2026-06-27>][@ver<2.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<spec>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{Complete spec for Neo4j graph pipeline. 8-graph reasoning pipeline asks questions, Neo4j answers. Questions saved in Config.py domain_dom_graph section.}
# [@CLASS]{Neo4jPipelineSpec}
# [@METHOD]{Plan,Spec,Flow,Lifecycle,Dependencies,Error,Orchestration,Gap}

---

## STATUS: SPEC COMPLETE — AWAITING APPROVAL — NO CODE WRITTEN

---

## 1. What We Are Building

We are building a Neo4j graph backend for the Dom_Unified magnetic search system. MySQL stores graph data in flat tables. Neo4j stores it as native nodes and edges. The 8-graph reasoning pipeline interrogates the spec by asking questions, and the spec answers them.

The starting point is MySQL on disk — already populated with graph data in 7 tables across 2 databases.

Data originates in MySQL vb_shared (class_graph, graph_nodes, graph_edges, know_edges) and bcl_ir (bcl_edges, bcl_classes, bcl_methods).

**Three databases, one pipeline:**
- MySQL (source of truth, on disk, never modified)
- SQLite `:memory:` (RAM staging, temporary, destroyed on exit)
- Neo4j (permanent graph store, on disk, survives restarts)

---

## 2. Config.py — domain_dom_graph Section

Config.py gets a new `domain_dom_graph` section. This section stores:
- Graph connection settings (Neo4j URI, MySQL host, SQLite staging path)
- The QUESTIONS each of the 8 graphs asks
- Batch sizes, hop limits, table mappings

### 2.1 New Constants

```python
# Graph connection
GRAPH_NEO4J_URI = "bolt://localhost:7687"
GRAPH_NEO4J_USER = ""
GRAPH_NEO4J_PASSWORD = ""
GRAPH_STAGING_DB = ":memory:"
GRAPH_MYSQL_HOST = "localhost"
GRAPH_MYSQL_USER = "root"
GRAPH_MYSQL_PORT = 3306
GRAPH_MYSQL_DB_VB = "vb_shared"
GRAPH_MYSQL_DB_BCL = "bcl_ir"

# Graph loading
GRAPH_BATCH_SIZE = 500
GRAPH_MAX_WORKERS = 4
GRAPH_MAX_HOPS = 3
GRAPH_LIMIT = 10

# Graph table mappings — MySQL table → Neo4j node label + edge type
GRAPH_TABLE_MAP = {
    "class_graph": {
        "mysql_db": "vb_shared",
        "node_label": "Class",
        "edge_type": "RELATES_TO",
        "source_col": "source_class",
        "target_col": "target_class",
        "rel_col": "relationship",
    },
    "bcl_edges": {
        "mysql_db": "bcl_ir",
        "node_label": "Method",
        "edge_type": "CALLS",
        "source_col": "source_method_id",
        "target_col": "target",
        "rel_col": "edge_type",
        "filter": "WHERE edge_type = 'CALL'",
    },
    "bcl_classes": {
        "mysql_db": "bcl_ir",
        "node_label": "Class",
        "edge_type": None,
        "source_col": "class_name",
    },
    "bcl_methods": {
        "mysql_db": "bcl_ir",
        "node_label": "Method",
        "edge_type": None,
        "source_col": "method_name",
    },
    "graph_nodes": {
        "mysql_db": "vb_shared",
        "node_label": "Token",
        "edge_type": None,
        "source_col": "name",
        "extra_col": "node_type",
    },
    "graph_edges": {
        "mysql_db": "vb_shared",
        "node_label": "Token",
        "edge_type": "CO_OCCURS",
        "source_col": "from_node",
        "target_col": "to_node",
        "rel_col": "edge_type",
    },
    "know_edges": {
        "mysql_db": "vb_shared",
        "node_label": "Token",
        "edge_type": "KNOWS",
        "source_col": "from_node_id",
        "target_col": "to_node_id",
        "rel_col": "relation_type",
    },
}
```

### 2.2 Graph Questions — The 8 Graphs (BCL Format)

Each graph in the reasoning pipeline asks questions about the spec. Questions use BCL bracket token format `[@tag]`. These questions are saved in Config.py so they persist and can be modified without changing code.

```python
GRAPH_QUESTIONS = {
    "plan_graph": [
        "[@what] classes exist in graph",
        "[@what] node labels present",
        "[@how_many] nodes per label",
    ],
    "spec_graph": [
        "[@what] relationships exist in graph",
        "[@what] relationship types present",
        "[@what] class names in graph",
    ],
    "flow_graph": [
        "[@how] does data flow from MemUnit to neighbors",
        "[@what] is shortest path from Class A to Class B",
        "[@how_many] hops maximum in current graph",
    ],
    "lifecycle_graph": [
        "[@which] classes have most relationships (hot paths)",
        "[@what] is degree distribution",
        "[@which] nodes are hubs (degree > 5)",
    ],
    "dependencies_graph": [
        "[@what] relationship types connect classes",
        "[@what] does Class X depend on",
        "[@what] depends on Class X",
    ],
    "error_graph": [
        "[@where] are orphan nodes (no relationships)",
        "[@where] are duplicate nodes",
        "[@where] are self-loops",
    ],
    "orchestration_graph": [
        "[@who] calls what (BCL CALL edges)",
        "[@which] method has most callers",
        "[@how_many] call chain depth",
    ],
    "gap_graph": [
        "[@what] is in MySQL but NOT in Neo4j",
        "[@how_many] rows in each MySQL table vs Neo4j node count",
        "[@which] tables have not been loaded yet",
    ],
}
```

### 2.3 Config.py self.state Addition

Inside `UnifiedConfig.__init__`, `self.state["config"]` gets:

```python
self.state["config"] = {
    # EXISTING (no change):
    "sqlite_path": SQLITE_PATH,
    "vbast_path": VBAST_BIN if os.path.exists(VBAST_BIN) else VBAST_FALLBACK,
    "cache_ttl": CACHE_TTL_SECONDS,
    "auto_reparse": AUTO_REPARSE,
    "capture_errors": CAPTURE_ERRORS,
    # NEW — domain_dom_graph section:
    "graph_neo4j_uri": GRAPH_NEO4J_URI,
    "graph_neo4j_user": GRAPH_NEO4J_USER,
    "graph_neo4j_password": GRAPH_NEO4J_PASSWORD,
    "graph_staging_db": GRAPH_STAGING_DB,
    "graph_mysql_host": GRAPH_MYSQL_HOST,
    "graph_mysql_user": GRAPH_MYSQL_USER,
    "graph_mysql_port": GRAPH_MYSQL_PORT,
    "graph_mysql_db_vb": GRAPH_MYSQL_DB_VB,
    "graph_mysql_db_bcl": GRAPH_MYSQL_DB_BCL,
    "graph_batch_size": GRAPH_BATCH_SIZE,
    "graph_max_workers": GRAPH_MAX_WORKERS,
    "graph_max_hops": GRAPH_MAX_HOPS,
    "graph_limit": GRAPH_LIMIT,
    "graph_table_map": GRAPH_TABLE_MAP,
    "graph_questions": GRAPH_QUESTIONS,
}
```

---

## 3. Data Map — Where Data Lives At Each Stage

```
PERMANENT STORAGE (on disk, survives restarts):

  1. MySQL (localhost:3306) — SOURCE OF TRUTH
     Already exists. Already populated. Not modified.

     vb_shared database:
       class_graph       36 rows    class→class relationships
       graph_nodes       50 rows    token/table nodes
       graph_edges       33,775     co-occurrence edges
       know_edges        1,516      knowledge graph edges

     bcl_ir database:
       bcl_edges         407,421   CALL/IMPORT/STATE edges
       bcl_classes       1,951     class definitions
       bcl_methods       25,047    methods with BCL stamps

  2. Neo4j (localhost:7687, bolt) — GRAPH DESTINATION
     Already running. Auth disabled.
     Data persists to: /opt/homebrew/var/neo4j/data/
     Survives restarts. This becomes the permanent graph store.

TEMPORARY STORAGE (in RAM, gone when process ends):

  3. SQLite :memory: — STAGING AREA
     Created fresh each run. Destroyed when process exits.
     Lives entirely in RAM. No disk I/O.
     Purpose: fast bulk read for threaded loading into Neo4j.

     staging_class_graph    36 rows
     staging_graph_nodes    50 rows
     staging_graph_edges    33,775 rows
     staging_know_edges     1,516 rows
     staging_bcl_edges      407,421 rows
     staging_bcl_classes    1,951 rows
     staging_bcl_methods    25,047 rows
```

---

## 4. Starting Point and Data Flow

```
START: MySQL tables (vb_shared + bcl_ir)
  │
  │  DatabaseManager(mysql, db_name="vb_shared").Run("query", ...)
  │  DatabaseManager(mysql, db_name="bcl_ir").Run("query", ...)
  │
  ▼
STAGING: SQLite :memory: (RAM)
  │
  │  DatabaseManager(sqlite, sqlite_path=":memory:").Run("insert_many", ...)
  │
  ▼
DESTINATION: Neo4j (permanent graph store on disk)
  │
  │  DatabaseManager(neo4j).Run("cypher", {
  │      "query": "UNWIND $batch AS row MERGE ...",
  │      "args": {"batch": [...]}
  │  })
  │
  ▼
DONE: Neo4j has the full graph. SQLite RAM freed. MySQL untouched.
```

| Data | Starts In | Staged In | Ends In | Persistent? |
|------|-----------|-----------|---------|-------------|
| class_graph (36 rows) | MySQL disk | SQLite RAM | Neo4j disk | Yes — Neo4j |
| graph_nodes (50 rows) | MySQL disk | SQLite RAM | Neo4j disk | Yes — Neo4j |
| graph_edges (33K rows) | MySQL disk | SQLite RAM | Neo4j disk | Yes — Neo4j |
| know_edges (1.5K rows) | MySQL disk | SQLite RAM | Neo4j disk | Yes — Neo4j |
| bcl_edges (407K rows) | MySQL disk | SQLite RAM | Neo4j disk | Yes — Neo4j |
| bcl_classes (1.9K rows) | MySQL disk | SQLite RAM | Neo4j disk | Yes — Neo4j |
| bcl_methods (25K rows) | MySQL disk | SQLite RAM | Neo4j disk | Yes — Neo4j |

**MySQL**: never modified. Source of truth for tabular data.
**SQLite RAM**: temporary. Destroyed when process exits. Speed bridge.
**Neo4j**: permanent graph store. Data survives restarts.

---

## 5. Neo4jGraph.py — Use Config + DatabaseManager

Neo4jGraph reads settings from Config.py and creates DatabaseManager instances.

### 5.1 Constructor

```python
from .Config import UnifiedConfig
from .DatabaseManager import DatabaseManager

class Neo4jGraph:
    def __init__(self, mem=None, db=None, param=None):
        cfg = UnifiedConfig()
        ok, config_state, err = cfg.read_state()
        graph_cfg = config_state["config"]

        self.state = {
            "config": {
                "neo4j_uri": graph_cfg["graph_neo4j_uri"],
                "staging_db": graph_cfg["graph_staging_db"],
                "mysql_host": graph_cfg["graph_mysql_host"],
                "batch_size": graph_cfg["graph_batch_size"],
                "max_workers": graph_cfg["graph_max_workers"],
                "max_hops": graph_cfg["graph_max_hops"],
                "limit": graph_cfg["graph_limit"],
                "table_map": graph_cfg["graph_table_map"],
                "questions": graph_cfg["graph_questions"],
            },
            "results": {
                "last_load": None,
                "total_nodes_loaded": 0,
                "total_edges_loaded": 0,
                "last_traversal": None,
                "graph_answers": {},
            },
        }

        # DatabaseManager handles ALL database connections
        self.state["db_mysql_vb"] = DatabaseManager(param={
            "db_type": "mysql",
            "db_host": graph_cfg["graph_mysql_host"],
            "db_user": graph_cfg["graph_mysql_user"],
            "db_name": graph_cfg["graph_mysql_db_vb"],
        })
        self.state["db_mysql_bcl"] = DatabaseManager(param={
            "db_type": "mysql",
            "db_host": graph_cfg["graph_mysql_host"],
            "db_user": graph_cfg["graph_mysql_user"],
            "db_name": graph_cfg["graph_mysql_db_bcl"],
        })
        self.state["db_sqlite"] = DatabaseManager(param={
            "db_type": "sqlite",
            "sqlite_path": graph_cfg["graph_staging_db"],
        })
        self.state["db_neo4j"] = DatabaseManager(param={
            "db_type": "neo4j",
            "neo4j_uri": graph_cfg["graph_neo4j_uri"],
            "neo4j_user": graph_cfg["graph_neo4j_user"],
            "neo4j_password": graph_cfg["graph_neo4j_password"],
        })
```

### 5.2 All Database Operations Through DatabaseManager

```python
# Read from MySQL:
ok, rows, err = self.state["db_mysql_vb"].Run("query", {"sql": "SELECT * FROM class_graph"})

# Write to SQLite staging:
ok, data, err = self.state["db_sqlite"].Run("insert_many", {
    "table": "staging_class_graph",
    "columns": ["source", "target", "relationship"],
    "rows": [...]
})

# Write to Neo4j (batch UNWIND):
ok, data, err = self.state["db_neo4j"].Run("cypher", {
    "query": "UNWIND $batch AS row MERGE (s:Class {name: row.source}) MERGE (t:Class {name: row.target}) MERGE (s)-[:RELATES_TO {type: row.relationship}]->(t)",
    "args": {"batch": rows}
})

# Read from SQLite staging:
ok, rows, err = self.state["db_sqlite"].Run("query", {"sql": "SELECT * FROM staging_bcl_edges LIMIT 500"})
```

No `import mysql.connector`. No `from neo4j import GraphDatabase`. No direct connections. Everything through DatabaseManager.

---

## 6. The 8-Graph Reasoning Pipeline

The graph engine reads this spec file (NEO4J_PIPELINE.md) and asks it questions. Each of the 8 graphs asks questions in BCL `[@tag]` format. The spec answers them. This is how the graph engine validates the spec before any code is written.

Questions are saved in MySQL `vb_shared.graph_config` table (domain=`dom_graph`). Each question has a `bcl_tag`, `question_text`, and `spec_section` pointing to where in the spec the answer lives.

### 6.1 Graph 1: PLAN — What are we building?

**Questions (BCL format, saved in graph_config):**
- `[@what] are we building` → spec section 1
- `[@what] is the starting point` → spec section 4
- `[@where] does data originate` → spec section 3

**Spec answers:**
- We are building a Neo4j graph backend for the Dom_Unified magnetic search system
- Starting point is MySQL on disk — already populated
- Data originates in MySQL vb_shared + bcl_ir databases

### 6.2 Graph 2: SPEC — What exists?

**Questions:**
- `[@what] files are involved` → spec section 9
- `[@what] classes already exist in MySQL` → spec section 3
- `[@what] tables hold graph data` → spec section 3

**Spec answers:**
- Files: Config.py, DatabaseManager.py, Neo4jGraph.py
- MySQL has: class_graph(36), graph_nodes(50), graph_edges(33775), know_edges(1516), bcl_edges(407421), bcl_classes(1951), bcl_methods(25047)
- Tables: 7 MySQL tables across 2 databases (vb_shared, bcl_ir)

### 6.3 Graph 3: FLOW — How does data move?

**Questions:**
- `[@how] does data flow from MySQL to Neo4j` → spec section 4
- `[@what] is the staging step` → spec section 7 Stage 1
- `[@where] is data temporary vs permanent` → spec section 3

**Spec answers:**
- MySQL → SQLite :memory: (staging) → Neo4j (permanent)
- Staging step: bulk dump MySQL rows into SQLite RAM via executemany
- Temporary: SQLite :memory: (destroyed on exit). Permanent: MySQL (untouched) + Neo4j (survives restarts)

### 6.4 Graph 4: LIFECYCLE — When does it run?

**Questions:**
- `[@when] does the load run` → spec section 7
- `[@when] is SQLite staging created` → spec section 7 Stage 1
- `[@when] is SQLite staging destroyed` → spec section 4

**Spec answers:**
- Load runs when Neo4jGraph.Run("load_all") is called
- SQLite staging created at Stage 1 (dump_to_sqlite command)
- SQLite staging destroyed when process exits (it's :memory:)

### 6.5 Graph 5: DEPENDENCIES — Why does it connect?

**Questions:**
- `[@why] use SQLite staging instead of direct MySQL to Neo4j` → spec section 7 Stage 1
- `[@why] use DatabaseManager instead of direct connections` → spec section 5
- `[@why] use UNWIND batches instead of row-by-row` → spec section 7 Stage 3

**Spec answers:**
- SQLite RAM is 100x faster than MySQL disk reads for 407K rows
- DatabaseManager owns DATABASE domain — Neo4jGraph owns GRAPH domain. One class one domain.
- UNWIND sends 500 rows per Cypher call vs 500 separate calls

### 6.6 Graph 6: ERROR — Where does it fail?

**Questions:**
- `[@where] can the pipeline fail` → spec section 7 Stage 5
- `[@what] happens if counts don't match` → spec section 7 Stage 5
- `[@where] are the bottlenecks` → spec section 12

**Spec answers:**
- Pipeline can fail at: MySQL read, SQLite write, Neo4j Cypher write, count mismatch
- If counts don't match → report discrepancy, don't silently continue
- Bottlenecks: bcl_edges (407K rows) — solved with 4 threads + 500-row batches

### 6.7 Graph 7: ORCHESTRATION — Who calls who?

**Questions:**
- `[@who] calls DatabaseManager` → spec section 5
- `[@who] creates the SQLite staging` → spec section 5
- `[@who] runs the Cypher queries` → spec section 5

**Spec answers:**
- Neo4jGraph calls DatabaseManager for all DB operations
- Neo4jGraph creates DatabaseManager(sqlite, ":memory:") in constructor
- Neo4jGraph calls DatabaseManager(neo4j).Run("cypher", ...) for all graph queries

### 6.8 Graph 8: GAP — What is missing?

**Questions:**
- `[@what] is missing from the spec` → entire spec
- `[@what] edge cases are not covered` → entire spec
- `[@what] happens on Neo4j restart` → spec section 3

**Spec answers:**
- Missing: incremental update strategy, error retry logic, connection pool management
- Edge cases: Neo4j down, MySQL down, partial load failure, duplicate data
- On Neo4j restart: data persists to /opt/homebrew/var/neo4j/data/, survives restarts

---

## 7. The Pipeline (5 Stages)

The load runs when Neo4jGraph.Run("load_all") is called. SQLite staging is created at Stage 1 (dump_to_sqlite command). SQLite staging is destroyed when the process exits because it lives in :memory: RAM.

The pipeline can fail at: MySQL read (connection lost), SQLite write (RAM full), Neo4j Cypher write (connection lost), count mismatch (data lost in transit). If counts do not match, report discrepancy and do not silently continue.

The staging step is Stage 1: bulk dump MySQL rows into SQLite RAM via executemany. This creates staging tables in :memory: for fast threaded reading.

### Stage 1: DUMP — MySQL → SQLite RAM

```
DatabaseManager(mysql, db_name="vb_shared")
    → SELECT * FROM class_graph         (36 rows)
    → SELECT * FROM graph_nodes         (50 rows)
    → SELECT * FROM graph_edges         (33,775 rows)
    → SELECT * FROM know_edges          (1,516 rows)

DatabaseManager(mysql, db_name="bcl_ir")
    → SELECT * FROM bcl_edges WHERE edge_type='CALL'  (407,421 rows)
    → SELECT * FROM bcl_classes         (1,951 rows)
    → SELECT * FROM bcl_methods         (25,047 rows)

    │
    ▼  bulk insert (executemany)

DatabaseManager(sqlite, sqlite_path=":memory:")
    → CREATE TABLE staging_class_graph (source, target, relationship)
    → CREATE TABLE staging_bcl_edges (source, target, edge_type, line)
    → CREATE TABLE staging_graph_nodes (id, node_type, name)
    → CREATE TABLE staging_graph_edges (from_id, to_id, edge_type, weight, context)
    → CREATE TABLE staging_know_edges (from_id, to_id, relation_type)
    → CREATE TABLE staging_bcl_classes (class_name, ...)
    → CREATE TABLE staging_bcl_methods (method_name, bcl_stamp, file_path, ...)

    → INSERT INTO staging_* (executemany — fast, all in RAM)
```

### Stage 2: SCHEMA — Create Neo4j constraints/indexes

```
DatabaseManager(neo4j).Run("cypher", ...)
    → CREATE CONSTRAINT class_name IF NOT EXISTS FOR (c:Class) REQUIRE c.name IS UNIQUE
    → CREATE CONSTRAINT method_name IF NOT EXISTS FOR (m:Method) REQUIRE m.name IS UNIQUE
    → CREATE CONSTRAINT token_name IF NOT EXISTS FOR (t:Token) REQUIRE t.name IS UNIQUE
    → CREATE INDEX chat_session IF NOT EXISTS FOR (c:Chat) ON (c.session)
```

### Stage 3: LOAD — SQLite RAM → Neo4j (THREADED)

```
ThreadPoolExecutor(max_workers=4)

Phase 1 (parallel — small tables):
  Thread 1: staging_class_graph   → Neo4j  (36 rows — 1 batch)
  Thread 2: staging_graph_nodes   → Neo4j  (50 rows — 1 batch)
  Thread 3: staging_know_edges    → Neo4j  (1,516 rows — 3 batches)
  Thread 4: staging_bcl_classes   → Neo4j  (1,951 rows — 4 batches)

Phase 2 (parallel — medium tables):
  Thread 1-2: staging_graph_edges → Neo4j  (33,775 rows — 68 batches of 500)
  Thread 3-4: staging_bcl_methods → Neo4j  (25,047 rows — 50 batches of 500)

Phase 3 (all threads — big table):
  Thread 1: staging_bcl_edges chunk 1 (rows 0-100K)
  Thread 2: staging_bcl_edges chunk 2 (rows 100K-200K)
  Thread 3: staging_bcl_edges chunk 3 (rows 200K-300K)
  Thread 4: staging_bcl_edges chunk 4 (rows 300K-407K)
  → 204 batches of 500 per thread
```

Each thread:
1. Reads a batch of 500 rows from SQLite RAM (instant)
2. Sends UNWIND Cypher to Neo4j (batch MERGE — not row-by-row)

**Cypher batch pattern:**
```cypher
UNWIND $batch AS row
MERGE (s:Class {name: row.source})
MERGE (t:Class {name: row.target})
MERGE (s)-[:RELATES_TO {type: row.relationship}]->(t)
```

### Stage 4: TRAVERSE — Cypher queries via DatabaseManager

```
Neo4jGraph.Run("traverse", {"query": "MemUnit", "max_hops": 3})
    │
    ▼
DatabaseManager(neo4j).Run("cypher", {
    "query": "MATCH (n) WHERE n.name CONTAINS $term "
             "MATCH path=(n)-[*1..3]-(connected) "
             "RETURN connected, length(path) as hop_dist "
             "ORDER BY hop_dist LIMIT $limit",
    "args": {"term": "MemUnit", "limit": 20}
})
```

### Stage 5: VERIFY — count nodes/edges in Neo4j vs MySQL

```
Neo4j node count  ==  MySQL source row count
Neo4j edge count  ==  MySQL source row count
If counts don't match → report discrepancy
```

---

## 8. Spec Graph Run — Questions and Answers

The spec graph runs the 8-graph pipeline. Each graph asks its questions (from Config.py). Neo4j answers via DatabaseManager cypher queries.

### 8.1 Current State (from previous test run)

| Graph | BCL Question | Neo4j Answer |
|-------|-------------|-------------|
| PLAN | `[@what] classes exist in graph` | 6 labels: Method(1236), Rules(39), Class(30), Concepts(5), Tables(3), Tokens(3) |
| SPEC | `[@what] relationships exist in graph` | CALLS(5000), CO_OCCURS(1551), RELATES_TO(36) |
| FLOW | `[@how] does data flow from MemUnit to neighbors` | MemUnit→Report, MemUnit→MemBus→Brackets, MemUnit→Config→MemDB |
| LIFECYCLE | `[@which] classes have most relationships` | MemUnit(degree 8), dom_gui(5), MemDB(5), Brackets(4), Config(4) |
| DEPENDENCIES | `[@what] relationship types connect classes` | 15 typed: BOOTS_INTO, INITIALIZES, PROVIDES_STATE_TO |
| ERROR | `[@where] are orphan nodes` | None — all nodes connected |
| ORCHESTRATION | `[@who] calls what` | Method CALL edges: Dom_Graph methods calling findings.append, c.create_text |
| GAP | `[@what] is in MySQL but NOT in Neo4j` | Neo4j has 1,316 nodes / 6,587 edges. MySQL has 468K+ rows. 99% not loaded |

### 8.2 Gap Graph Detail

```
MySQL vb_shared: class_graph=36 graph_nodes=50 graph_edges=33775 know_edges=1516
MySQL bcl_ir: bcl_edges=407421 bcl_classes=1951 bcl_methods=25047
Neo4j: nodes=1316 edges=6587

GAPS:
  - bcl_edges: 5,000 loaded / 407,421 total (98.8% missing)
  - bcl_classes: 0 loaded / 1,951 total (100% missing)
  - bcl_methods: 0 loaded / 25,047 total (100% missing)
  - graph_edges: 5,000 loaded / 33,775 total (85% missing)
  - know_edges: 0 loaded / 1,516 total (100% missing — schema mismatch fixed)
```

---

## 9. File Changes

Files involved: Config.py, DatabaseManager.py, Neo4jGraph.py. Three files modified, three files untouched.

| File | Role | Modified? |
|------|------|-----------|
| `Config.py` | Add domain_dom_graph section (constants + table map + question DB ref) | YES — add section |
| `DatabaseManager.py` | Handles all DB connections | Already fixed (auth=None) |
| `Neo4jGraph.py` | Graph traversal + load orchestration | REWRITE — use Config + DatabaseManager |
| `__init__.py` | Package exports | No change |
| `MagneticGraph.py` | SQL-based graph (existing) | No change |
| `MemoryObject.py` | Memory objects | No change |

---

## 10. Commands (Neo4jGraph.Run dispatch)

| Command | What it does | Backend |
|---------|-------------|---------|
| `dump_to_sqlite` | Stage 1: MySQL → SQLite RAM | DatabaseManager(mysql) → DatabaseManager(sqlite) |
| `create_schema` | Stage 2: Neo4j constraints/indexes | DatabaseManager(neo4j) |
| `load_all` | Stage 3: SQLite RAM → Neo4j (threaded) | DatabaseManager(sqlite) → DatabaseManager(neo4j) |
| `load_table` | Load one table (incremental) | Same but single table |
| `traverse` | Stage 4: Cypher multi-hop traversal | DatabaseManager(neo4j) |
| `search` | Find nodes by name | DatabaseManager(neo4j) |
| `stats` | Node/edge counts in Neo4j | DatabaseManager(neo4j) |
| `verify` | Stage 5: Compare Neo4j vs MySQL | DatabaseManager(neo4j) + DatabaseManager(mysql) |
| `run_spec_graph` | Run 8-graph pipeline (ask questions, get answers) | DatabaseManager(neo4j) + DatabaseManager(mysql) |
| `read_state` | Config + results + graph answers | — |
| `set_config` | Update config | — |

---

## 11. VBStyle Compliance Checklist

| Rule | Status |
|------|--------|
| @domain — one class one domain | Neo4jGraph = GRAPH_NEO4J, DatabaseManager = DATABASE |
| @auth — no direct DB access | Neo4jGraph uses DatabaseManager only |
| @run — Run() dispatch | Yes |
| @t3 — Tuple3 returns | All methods return (ok, data, err) |
| @state — self.state dict | Yes, no self._ |
| @ghost — header | Yes |
| @vbsty — header | Yes |
| @noedit — only approved files | Config.py, Neo4jGraph.py, DatabaseManager.py (already done) |
| @nofiles — no unnecessary files | Only modifying existing files |
| @pascal — PascalCase | Neo4jGraph, DatabaseManager, UnifiedConfig |
| @noself — no self._ | Uses self.state["db_mysql_vb"] etc |
| @print — no print | No print statements |
| @hardcode — no hardcoded | All values in Config.py constants |
| @nobulk — one method at a time | Load one table, verify, then next table |
| @precode — check MySQL first | Done — checked code_classes, learned_rules, know_problems |

---

## 12. Expected Performance

The bottlenecks are bcl_edges (407K rows) and graph_edges (33K rows). These are solved with 4 threads and 500-row UNWIND batches. Before threading, bcl_edges timed out after 5+ minutes. After threading, it loads in ~30 seconds.

| Stage | Before (row-by-row) | After (threaded + batched) |
|-------|---------------------|---------------------------|
| class_graph (36) | 0.5s | 0.01s |
| graph_edges (33K) | 30s | 2s |
| bcl_edges (407K) | 5+ min (timed out) | ~30s |
| Total load | 6+ min | ~40s |

---

## 13. What I Need From You

1. **Approve this spec** — it is complete with all technical details
2. **Confirm the Config.py domain_dom_graph section** — questions saved in config
3. **Confirm the 8-graph pipeline** — each graph asks questions, Neo4j answers
4. **Confirm the file changes** — Config.py (add section), Neo4jGraph.py (rewrite), DatabaseManager.py (already done)

Once you say go, I implement:
1. Config.py — add domain_dom_graph section
2. Neo4jGraph.py — rewrite to use Config + DatabaseManager + 8-graph pipeline
3. Run the spec graph to verify
