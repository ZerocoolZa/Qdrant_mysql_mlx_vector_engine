<!-- [@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<Design document for unified DomGraphEngine merging 3 separate decision/graph engines into one VBStyle authority. Describes 5-table SQLite schema, 8-step pipeline, ContextRAM integration. Has #[@GHOST] and #[@VBSTYLE] headers in markdown. Comprehensive 1580-line spec. No VBStyle violations applicable to markdown.>][@todos<none>]} -->
# [@GHOST]{[@file<DOM_GRAPH_ENGINE_DESIGN.md>][@domain<Dom_Graph>][@role<design_document>][@auth<devin>][@date<2026-06-28>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<design_document>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}

# DomGraphEngine — Unified Decision Graph Engine Design Document

## Overview

Three separate decision/graph engines currently follow the same conceptual pipeline
(INPUT -> CANDIDATES -> FILTER -> RESOLVE -> SCORE -> DECIDE -> TRACE) but live in
separate files with separate databases, separate dispatch tables, and separate
schema. This document defines a single `DomGraphEngine` class that unifies all
three into one VBStyle-compliant authority with one schema, one `Run()` dispatch,
and one shared 8-step pipeline.

### Current State Summary

| Engine | File | DB | Status | Pipeline Steps |
|--------|------|----|--------|----------------|
| GUIDecisionEngine | `gui_engine/gui_engine.py:321` | SQLite `token_registry.db` | STUB (line 382 returns "not implemented") | candidates -> hard_filter -> when_rules -> conflict -> score -> decide -> trace |
| DecisionEngine | `Dom_Graph/decision_engine.py:35` | SQLite `dom_graph_work.db` | WORKING (full sandbox simulation) | get_candidates -> rank_fixes -> analyze_risk -> simulate -> validate -> analyze_cost -> analyze_benefit -> decide |
| DomSessionGraph | `core/Dom_Unified/DomSessionGraph.py:61` | MySQL `vb_shared` | WORKING (MySQL-backed) | open -> add_path -> update_path -> add_resume -> get_resume -> render -> dashboard -> close |

### ContextRAM Integration Surface

ContextRAM (`/Users/wws/contestsystem/ContextRAMSwift`) is a Swift node/edge store
with 28K+ nodes exposed via the `ctx` CLI. Its data model (Models.swift) defines:

- **NodeType** (19 values): goal, task, problem, question, fact, rule, memory,
  event, observation, hypothesis, decision, file, code, error, test, result,
  conversation, plan, dependency, resource
- **StatusType** (9 values): active, pending, resolved, failed, archived, locked,
  expired, superseded, unknown
- **AuthorityLevel** (6 values): system, truthDB, human, model, externalSource,
  consensus
- **RelationshipType** (9 values): dependsOn, supports, contradicts, createdBy,
  references, resolves, causedBy, partOf, relatedTo
- **ContextNode**: nodeID, type, value, status, authority, score, created,
  updated, accessed, expiry, tags, source, links, version
- **ContextAssembly**: query, goals, tasks, facts, rules, memories, decisions,
  hypotheses, openQuestions

The existing MCP server (`mcp-server/index.js`) wraps every `ctx` subcommand as
an MCP tool (ctx_put, ctx_get, ctx_query, ctx_assemble, ctx_auto, ctx_suggest,
etc.) by spawning the `ctx` binary.

---

## 1. Unified Schema

One SQLite database (`dom_graph_unified.db`) with five core tables. The design
principle: every entity is a **node**, every relationship is an **edge**, every
decision logic is a **rule**, every decision output is a **decision**, and every
checkpoint is a **snapshot**. The `domain` column on each table distinguishes
which of the three original engines a row belongs to (`gui`, `codefix`, `session`).

### 1.1 CREATE TABLE Statements

```sql
-- ============================================================================
-- nodes: Every entity across all 3 engines
--   gui:     component_ontology rows (GUI components)
--   codefix: knowledge, files, classes, methods rows (code fix candidates)
--   session: session_graphs, session_paths rows (session tracking)
-- ============================================================================
CREATE TABLE nodes (
    node_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    domain           TEXT NOT NULL,          -- 'gui' | 'codefix' | 'session'
    node_type        TEXT NOT NULL,          -- 'component' | 'knowledge' | 'file' | 'class' | 'method' | 'session' | 'path' | 'resume'
    name             TEXT NOT NULL,          -- component_name / problem title / session_id / path_name
    qualified_name   TEXT,                   -- full path or qualified identifier
    description      TEXT,                   -- component description / answer text / main_thread
    content          TEXT,                   -- method_code / full source / notes
    properties       TEXT,                   -- JSON blob for domain-specific fields
    domain_tags      TEXT,                   -- comma-separated tags (gui: domain_tags, codefix: tags, session: path_type)
    complexity_level TEXT,                   -- gui: complexity_level, codefix: cyclomatic_complexity
    confidence       REAL DEFAULT 0,         -- gui: N/A, codefix: confidence, session: progress
    status           TEXT DEFAULT 'active',  -- active | pending | resolved | failed | archived | in_progress | closed | dead_end
    score            REAL DEFAULT 0,         -- computed score after pipeline
    parent_node_id   INTEGER,                -- tree parent (ui_nodes.parent_id, session_paths.parent_path)
    source_file      TEXT,                   -- file path for code nodes
    line_start       INTEGER,
    line_end         INTEGER,
    hash             TEXT,                   -- content hash for dedup
    version          INTEGER DEFAULT 1,
    created          TEXT,
    updated          TEXT,
    FOREIGN KEY (parent_node_id) REFERENCES nodes(node_id)
);

CREATE INDEX idx_nodes_domain    ON nodes(domain);
CREATE INDEX idx_nodes_type      ON nodes(node_type);
CREATE INDEX idx_nodes_name      ON nodes(name);
CREATE INDEX idx_nodes_parent    ON nodes(parent_node_id);
CREATE INDEX idx_nodes_status    ON nodes(status);
CREATE INDEX idx_nodes_confidence ON nodes(confidence DESC);

-- ============================================================================
-- edges: Every relationship across all 3 engines
--   gui:     conflict_resolution_rule pairs (component_a vs component_b)
--   codefix: edges table (calls, contains, references, etc.)
--   session: parent_path relationships between session paths
-- ============================================================================
CREATE TABLE edges (
    edge_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    domain           TEXT NOT NULL,          -- 'gui' | 'codefix' | 'session'
    src_node_id      INTEGER NOT NULL,
    src_type         TEXT NOT NULL,          -- 'method' | 'class' | 'file' | 'component' | 'path' | 'session'
    dst_node_id      INTEGER NOT NULL,
    dst_type         TEXT NOT NULL,
    edge_type        TEXT NOT NULL,          -- 'calls' | 'contains' | 'references' | 'conflicts_with' | 'parent_of' | 'resolves' | 'supports' | 'depends_on'
    evidence         TEXT,
    confidence       REAL DEFAULT 100.0,
    weight           REAL DEFAULT 1.0,       -- for graph traversal
    created          TEXT,
    FOREIGN KEY (src_node_id) REFERENCES nodes(node_id),
    FOREIGN KEY (dst_node_id) REFERENCES nodes(node_id)
);

CREATE INDEX idx_edges_domain  ON edges(domain);
CREATE INDEX idx_edges_src     ON edges(src_node_id);
CREATE INDEX idx_edges_dst     ON edges(dst_node_id);
CREATE INDEX idx_edges_type    ON edges(edge_type);

-- ============================================================================
-- rules: Every decision logic across all 3 engines
--   gui:     when_rule, when_not_rule, conflict_resolution_rule, scoring_model,
--            decision_principle, architecture_learning
--   codefix: implicit scoring logic (success_rate, risk, cost, benefit formulas)
--   session: implicit path status transitions
-- ============================================================================
CREATE TABLE rules (
    rule_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    domain           TEXT NOT NULL,          -- 'gui' | 'codefix' | 'session'
    rule_type        TEXT NOT NULL,          -- 'when' | 'when_not' | 'conflict_resolution' | 'scoring' | 'principle' | 'learning' | 'risk_formula' | 'cost_formula' | 'benefit_formula'
    target_node_id   INTEGER,                -- component_id / method_id this rule applies to
    condition_expr   TEXT,                   -- "data_shape == 'tabular'" / "fix_result == 'success'"
    resolution_expr  TEXT,                   -- IF/THEN/ELSE for conflict resolution
    score_expr       TEXT,                   -- ternary scoring expression
    base_score       REAL DEFAULT 0,
    max_score        REAL DEFAULT 100,
    priority         INTEGER DEFAULT 1,
    description      TEXT,
    category         TEXT,                   -- for architecture_learning
    correction       TEXT,                   -- for architecture_learning
    anti_pattern     TEXT,                   -- for decision_principle
    implementation   TEXT,                   -- for decision_principle
    is_active        INTEGER DEFAULT 1,
    created          TEXT,
    FOREIGN KEY (target_node_id) REFERENCES nodes(node_id)
);

CREATE INDEX idx_rules_domain ON rules(domain);
CREATE INDEX idx_rules_type   ON rules(rule_type);
CREATE INDEX idx_rules_target ON rules(target_node_id);

-- ============================================================================
-- decisions: Every decision output across all 3 engines
--   gui:     decide_component() output (chosen component + reason_trace)
--   codefix: Decide() output (chosen_fix + decision_score + evaluated list)
--   session: add_resume() output (resume_action + state)
-- ============================================================================
CREATE TABLE decisions (
    decision_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    domain           TEXT NOT NULL,          -- 'gui' | 'codefix' | 'session'
    decision_type    TEXT NOT NULL,          -- 'component_choice' | 'fix_choice' | 'resume_point'
    input_context    TEXT,                   -- JSON: the context/problem that was decided on
    chosen_node_id   INTEGER,                -- FK to nodes: the winning candidate
    chosen_name      TEXT,                   -- denormalized for quick read
    decision_score   REAL DEFAULT 0,
    reason           TEXT,
    reason_trace     TEXT,                   -- JSON array of trace steps
    evaluated        TEXT,                   -- JSON array of all evaluated candidates with scores
    state            TEXT,                   -- for resume points: STALLED / IN_PROGRESS / etc.
    resume_action    TEXT,                   -- for resume points
    is_active        INTEGER DEFAULT 1,
    created          TEXT,
    FOREIGN KEY (chosen_node_id) REFERENCES nodes(node_id)
);

CREATE INDEX idx_decisions_domain ON decisions(domain);
CREATE INDEX idx_decisions_type   ON decisions(decision_type);
CREATE INDEX idx_decisions_chosen ON decisions(chosen_node_id);
CREATE INDEX idx_decisions_active ON decisions(is_active);

-- ============================================================================
-- snapshots: Every checkpoint across all 3 engines
--   gui:     N/A (no snapshots currently)
--   codefix: snapshots table (file/class/method content snapshots)
--   session: session_resume_points (project progress checkpoints)
-- ============================================================================
CREATE TABLE snapshots (
    snapshot_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    domain           TEXT NOT NULL,          -- 'gui' | 'codefix' | 'session'
    snapshot_type    TEXT NOT NULL,          -- 'content' | 'resume_point' | 'state_checkpoint'
    target_node_id   INTEGER,                -- node this snapshot captures
    project_name     TEXT,                   -- for resume points
    progress         INTEGER DEFAULT 0,      -- for resume points
    state            TEXT,                   -- for resume points
    resume_action    TEXT,                   -- for resume points
    content          TEXT NOT NULL,          -- snapshot content
    hash             TEXT NOT NULL,
    notes            TEXT,
    is_active        INTEGER DEFAULT 1,
    created          TEXT NOT NULL,
    FOREIGN KEY (target_node_id) REFERENCES nodes(node_id)
);

CREATE INDEX idx_snapshots_domain ON snapshots(domain);
CREATE INDEX idx_snapshots_type   ON snapshots(snapshot_type);
CREATE INDEX idx_snapshots_active ON snapshots(is_active);
```

### 1.2 Schema Design Rationale

The `domain` column is the key partitioning mechanism. It allows all three
engines to share one database without collision, while the `node_type` column
within each domain provides sub-typing. The `properties` JSON column on `nodes`
absorbs domain-specific fields that do not warrant their own column (e.g., GUI
component `base_component`, codefix knowledge `error_type` / `stack_trace`,
session path `trigger_reason` / `was_worth_it`).

---

## 2. Command Dispatch

The unified `DomGraphEngine.Run()` dispatch table maps every command from all
three engines to new unified commands. Commands are namespaced by domain prefix
where ambiguity exists.

### 2.1 Full Dispatch Table

```
Run(command, params) -> Tuple3

# === Shared Pipeline Commands (all domains) ===
"decide"              -> Decide(params)           # Run full 8-step pipeline
"get_candidates"      -> GetCandidates(params)    # Step 1: candidates
"filter"              -> Filter(params)           # Step 2: hard filter
"when_rules"          -> WhenRules(params)        # Step 3: when rule check
"resolve_conflicts"   -> ResolveConflicts(params) # Step 4: conflict resolution
"score"               -> Score(params)            # Step 5: scoring
"trace"               -> Trace(params)            # Step 7: get reason trace
"persist"             -> Persist(params)          # Step 8: persist decision

# === DecisionEngine (codefix) Commands ===
"rank_fixes"          -> RankFixes(params)        # codefix: rank by success_rate
"analyze_risk"        -> AnalyzeRisk(params)      # codefix: risk analysis
"simulate"            -> Simulate(params)         # codefix: sandbox simulation
"validate"            -> Validate(params)         # codefix: compile validation
"analyze_cost"        -> AnalyzeCost(params)      # codefix: cost analysis
"analyze_benefit"     -> AnalyzeBenefit(params)   # codefix: benefit analysis

# === DomSessionGraph (session) Commands ===
"open_session"        -> OpenSession(params)      # session: open
"add_path"            -> AddPath(params)          # session: add_path
"update_path"         -> UpdatePath(params)       # session: update_path
"add_resume"          -> AddResume(params)        # session: add_resume
"get_resume"          -> GetResume(params)        # session: get_resume
"render"              -> Render(params)           # session: render graph
"dashboard"           -> Dashboard(params)        # session: dashboard
"close_session"       -> CloseSession(params)     # session: close
"list_sessions"       -> ListSessions(params)     # session: list_sessions

# === GUIDecisionEngine (gui) Commands ===
"decide_component"    -> DecideComponent(params)  # gui: decide component
"validate_context"    -> ValidateContext(params)  # gui: validate against principles

# === Graph CRUD Commands (new, shared) ===
"add_node"            -> AddNode(params)          # create node in any domain
"get_node"            -> GetNode(params)           # read node by id
"query_nodes"         -> QueryNodes(params)        # search nodes by text/type/domain
"add_edge"            -> AddEdge(params)           # create edge
"get_edges"           -> GetEdges(params)          # read edges for a node
"add_rule"            -> AddRule(params)           # create rule
"get_rules"           -> GetRules(params)          # read rules for a node
"get_decision"        -> GetDecision(params)       # read past decision by id
"query_decisions"     -> QueryDecisions(params)    # search past decisions
"add_snapshot"        -> AddSnapshot(params)       # create snapshot
"get_snapshot"        -> GetSnapshot(params)       # read snapshot

# === VBStyle Standard Commands ===
"read_state"          -> read_state(params)
"set_config"          -> set_config(params)
```

### 2.2 Backward Compatibility Aliases

To allow existing callers to work without modification during migration, the
dispatch table includes alias entries that map old command names to new ones:

```
# Old DecisionEngine aliases
"get_candidates"  -> GetCandidates(params)   # already matches
"decide"          -> Decide(params)           # already matches

# Old DomSessionGraph aliases
"open"            -> OpenSession(params)      # alias
"close"           -> CloseSession(params)     # alias

# Old GUIDecisionEngine aliases
"decide_component" -> DecideComponent(params) # already matches
```

### 2.3 Domain Routing

The `domain` parameter (default: `"codefix"`) routes commands to the correct
sub-pipeline. When `domain` is not specified, the engine infers it from the
command name:

- Commands `open_session`, `add_path`, `update_path`, `add_resume`, `get_resume`,
  `render`, `dashboard`, `close_session`, `list_sessions` -> domain = `"session"`
- Commands `decide_component`, `validate_context` -> domain = `"gui"`
- Commands `rank_fixes`, `analyze_risk`, `simulate`, `validate`,
  `analyze_cost`, `analyze_benefit` -> domain = `"codefix"`
- Commands `decide`, `get_candidates`, `filter`, `when_rules`,
  `resolve_conflicts`, `score`, `trace`, `persist` -> domain from `params["domain"]`

---

## 3. Shared Pipeline

The 8-step decision pipeline unifies the three engines' varying step counts into
one canonical flow. Each step is a method that returns Tuple3 and appends to
`self.state["reason_trace"]`.

### 3.1 Pipeline Overview

```
INPUT (context/problem)
  |
  v
STEP 1: CANDIDATES  -- retrieve candidate nodes from DB
  |
  v
STEP 2: FILTER      -- apply when_not rules / hard exclusions
  |
  v
STEP 3: WHEN_RULES  -- apply when rules / positive triggers
  |
  v
STEP 4: CONFLICT    -- resolve conflicts between remaining candidates
  |
  v
STEP 5: SCORE       -- score survivors (risk, cost, benefit, confidence)
  |
  v
STEP 6: DECIDE      -- pick highest-scoring candidate
  |
  v
STEP 7: TRACE       -- emit reason_trace with full decision audit
  |
  v
STEP 8: PERSIST     -- write decision to decisions table
```

### 3.2 Pseudocode for Each Step

#### Step 1: GetCandidates

```
FUNCTION GetCandidates(params)
    domain = params.get("domain", "codefix")
    query  = params.get("query", params.get("problem", ""))
    limit  = params.get("limit", 50)

    IF domain == "gui":
        SELECT node_id, name, description, domain_tags, complexity_level
        FROM nodes
        WHERE domain = 'gui' AND node_type = 'component'
        ORDER BY confidence DESC

    ELIF domain == "codefix":
        SELECT node_id, name AS problem, description AS answer,
               confidence, properties
        FROM nodes
        WHERE domain = 'codefix' AND node_type = 'knowledge'
          AND description IS NOT NULL
          AND name LIKE '%' || query || '%'
        ORDER BY confidence DESC
        LIMIT limit

    ELIF domain == "session":
        # Sessions do not use candidate retrieval the same way.
        # Return active session paths as candidates for resume decisions.
        SELECT node_id, name, description, confidence AS progress
        FROM nodes
        WHERE domain = 'session' AND node_type = 'path'
          AND status = 'IN_PROGRESS'

    candidates = [row for row in cursor.fetchall()]
    self.state["candidates"] = candidates
    self.state["reason_trace"].append("STEP 1: Retrieved " + str(len(candidates)) + " candidates")
    RETURN (1, {"candidates": candidates, "count": len(candidates)}, None)
END FUNCTION
```

#### Step 2: Filter (Hard Exclusions)

```
FUNCTION Filter(params)
    candidates = self.state.get("candidates", [])
    domain     = params.get("domain", "codefix")
    context    = params.get("context", {})

    IF domain == "gui":
        # Apply when_not rules from rules table
        FOR EACH candidate IN candidates:
            rules = SELECT condition_expr, description
                    FROM rules
                    WHERE domain = 'gui'
                      AND rule_type = 'when_not'
                      AND target_node_id = candidate.node_id
                      AND is_active = 1
            FOR EACH rule IN rules:
                IF EvaluateCondition(rule.condition_expr, context):
                    self.state["reason_trace"].append(
                        candidate.name + " eliminated: " + rule.description)
                    candidates.remove(candidate)
                    BREAK

    ELIF domain == "codefix":
        # Hard filter: exclude candidates with fix_result = 'failed'
        # and no successful attempts
        FOR EACH candidate IN candidates:
            props = JSON.parse(candidate.properties)
            IF props.get("fix_result") == "failed" AND props.get("confidence", 0) < 10:
                self.state["reason_trace"].append(
                    candidate.name + " eliminated: failed fix with low confidence")
                candidates.remove(candidate)

    ELIF domain == "session":
        # No hard filter for sessions — all active paths are valid candidates
        PASS

    self.state["filtered"] = candidates
    self.state["reason_trace"].append("STEP 2: " + str(len(candidates)) + " candidates after filter")
    RETURN (1, {"filtered": candidates, "count": len(candidates)}, None)
END FUNCTION
```

#### Step 3: WhenRules (Positive Triggers)

```
FUNCTION WhenRules(params)
    candidates = self.state.get("filtered", [])
    domain     = params.get("domain", "codefix")
    context    = params.get("context", {})

    IF domain == "gui":
        triggered = []
        FOR EACH candidate IN candidates:
            rules = SELECT condition_expr, description, priority
                    FROM rules
                    WHERE domain = 'gui'
                      AND rule_type = 'when'
                      AND target_node_id = candidate.node_id
                      AND is_active = 1
            IF NOT rules:
                # No when rules = always allowed
                triggered.append(candidate)
                CONTINUE
            FOR EACH rule IN rules:
                IF EvaluateCondition(rule.condition_expr, context):
                    candidate.priority = rule.priority
                    candidate.match_reason = rule.description
                    triggered.append(candidate)
                    self.state["reason_trace"].append(
                        candidate.name + " passes WHEN rule: " + rule.description)
                    BREAK

    ELIF domain == "codefix":
        # "When rules" for codefix = success_rate > threshold
        triggered = []
        FOR EACH candidate IN candidates:
            success_count = COUNT rows IN nodes WHERE description = candidate.description
                            AND properties.fix_result = 'success'
            total_count   = COUNT rows IN nodes WHERE description = candidate.description
            success_rate  = success_count / total_count IF total_count > 0 ELSE 0
            candidate.success_rate = success_rate
            candidate.success_count = success_count
            candidate.total_count = total_count
            IF success_rate > 0 OR candidate.confidence >= 50:
                triggered.append(candidate)
            ELSE:
                self.state["reason_trace"].append(
                    candidate.name + " eliminated: success_rate=0 and confidence<50")

    ELIF domain == "session":
        # No when rules for sessions
        triggered = candidates

    self.state["triggered"] = triggered
    self.state["reason_trace"].append("STEP 3: " + str(len(triggered)) + " candidates after when rules")
    RETURN (1, {"triggered": triggered, "count": len(triggered)}, None)
END FUNCTION
```

#### Step 4: ResolveConflicts

```
FUNCTION ResolveConflicts(params)
    candidates = self.state.get("triggered", [])
    domain     = params.get("domain", "codefix")
    context    = params.get("context", {})

    IF len(candidates) <= 1:
        self.state["resolved"] = candidates
        RETURN (1, {"resolved": candidates, "count": len(candidates)}, None)

    IF domain == "gui":
        # Check conflict_resolution_rule pairs
        resolved = []
        FOR i, candidate_a IN enumerate(candidates):
            FOR candidate_b IN candidates[i+1:]:
                rule = SELECT resolution_expr, priority, description
                       FROM rules
                       WHERE domain = 'gui'
                         AND rule_type = 'conflict_resolution'
                         AND target_node_id = candidate_a.node_id
                         # second target stored in resolution_expr or separate column
                IF rule:
                    winner_name = EvaluateResolution(rule.resolution_expr,
                                                     candidate_a, candidate_b, context)
                    IF winner_name == candidate_a.name:
                        IF candidate_a NOT IN resolved: resolved.append(candidate_a)
                    ELIF winner_name == candidate_b.name:
                        IF candidate_b NOT IN resolved: resolved.append(candidate_b)
                    self.state["reason_trace"].append(
                        "Conflict: " + candidate_a.name + " vs " + candidate_b.name +
                        " -> " + winner_name + " wins: " + rule.description)
        IF NOT resolved:
            resolved = candidates  # no rules found, keep all for scoring

    ELIF domain == "codefix":
        # Conflict resolution = rank by (fix_result=success, success_rate, confidence)
        resolved = sorted(candidates, key=lambda c: (
            c.fix_result == 'success', c.success_rate, c.confidence), reverse=True)

    ELIF domain == "session":
        # No conflict resolution for sessions
        resolved = candidates

    self.state["resolved"] = resolved
    self.state["reason_trace"].append("STEP 4: " + str(len(resolved)) + " candidates after conflict resolution")
    RETURN (1, {"resolved": resolved, "count": len(resolved)}, None)
END FUNCTION
```

#### Step 5: Score

```
FUNCTION Score(params)
    candidates = self.state.get("resolved", [])
    domain     = params.get("domain", "codefix")
    context    = params.get("context", {})
    method_id  = params.get("method_id")
    problem    = params.get("problem", params.get("query", ""))

    IF domain == "gui":
        # Apply scoring_model expressions
        FOR EACH candidate IN candidates:
            scoring = SELECT score_expr, base_score, max_score
                      FROM rules
                      WHERE domain = 'gui'
                        AND rule_type = 'scoring'
                        AND target_node_id = candidate.node_id
            IF scoring:
                score = EvaluateScore(scoring.score_expr, scoring.base_score, context)
                candidate.score = min(score, scoring.max_score)
            ELSE:
                candidate.score = candidate.priority * 0.5
        candidates.sort(key=lambda c: c.score, reverse=True)

    ELIF domain == "codefix":
        # Full scoring: risk + cost + benefit + simulation + validation
        FOR EACH candidate IN candidates:
            risk   = 0.0
            cost   = 0.0
            benefit = 0.0
            IF method_id:
                risk_res   = AnalyzeRisk({"method_id": method_id})
                cost_res   = AnalyzeCost({"method_id": method_id})
                IF risk_res[0] == 1: risk   = risk_res[1]["risk_score"]
                IF cost_res[0] == 1: cost   = cost_res[1]["cost_score"]
                candidate.risk_analysis   = risk_res[1]
                candidate.cost_analysis   = cost_res[1]
            IF problem:
                ben_res = AnalyzeBenefit({"problem": problem})
                IF ben_res[0] == 1: benefit = ben_res[1]["benefit_score"]
                candidate.benefit_analysis = ben_res[1]

            sim_res = Simulate({"fix_id": candidate.node_id})
            val_res = Validate({"fix_id": candidate.node_id})
            candidate.simulation  = sim_res[1] IF sim_res[0] == 1 ELSE {"simulated": False}
            candidate.validation  = val_res[1] IF val_res[0] == 1 ELSE {"validated": False}

            sim_ok = 1 IF candidate.simulation.get("simulated") ELSE 0
            val_ok = 1 IF candidate.validation.get("validated") ELSE 0
            denom  = 1 + risk + (cost / 10.0)
            IF denom == 0: denom = 1

            candidate.decision_score = (
                candidate.confidence *
                (1 + candidate.success_rate) *
                (1 + sim_ok) * (1 + val_ok) + benefit
            ) / denom

        candidates.sort(key=lambda c: c.decision_score, reverse=True)

    ELIF domain == "session":
        # Score session paths by progress * worth_it factor
        FOR EACH candidate IN candidates:
            props = JSON.parse(candidate.properties)
            worth_factor = {"YES": 1.5, "NO": 0.5, "UNKNOWN": 1.0}.get(props.get("was_worth_it"), 1.0)
            candidate.score = candidate.confidence * worth_factor  # confidence = progress
        candidates.sort(key=lambda c: c.score, reverse=True)

    self.state["scored"] = candidates
    self.state["reason_trace"].append("STEP 5: Scored " + str(len(candidates)) + " candidates")
    RETURN (1, {"scored": candidates, "count": len(candidates)}, None)
END FUNCTION
```

#### Step 6: Decide

```
FUNCTION Decide(params)
    candidates = self.state.get("scored", [])
    domain     = params.get("domain", "codefix")

    IF NOT candidates:
        self.state["decision"] = None
        self.state["reason_trace"].append("STEP 6: No candidates — decision is INVALID")
        RETURN (1, {"chosen": None, "reason": "no candidates found"}, None)

    best = candidates[0]

    IF domain == "gui":
        decision = {
            "decision": "VALID",
            "chosen_component": best.name,
            "chosen_node_id": best.node_id,
            "score": best.score,
            "reason": best.match_reason,
        }
    ELIF domain == "codefix":
        decision = {
            "chosen_fix": best,
            "decision_score": best.decision_score,
            "reason": "best confidence/risk ratio after simulation, validation, cost and benefit",
            "evaluated": candidates,
        }
    ELIF domain == "session":
        decision = {
            "chosen_path": best.name,
            "score": best.score,
            "reason": "highest progress * worth_it score",
        }

    self.state["decision"] = decision
    self.state["reason_trace"].append("STEP 6: Decided -> " + str(decision))
    RETURN (1, decision, None)
END FUNCTION
```

#### Step 7: Trace

```
FUNCTION Trace(params)
    trace = self.state.get("reason_trace", [])
    RETURN (1, {"reason_trace": trace, "step_count": len(trace)}, None)
END FUNCTION
```

#### Step 8: Persist

```
FUNCTION Persist(params)
    domain      = params.get("domain", "codefix")
    decision    = self.state.get("decision")
    context     = params.get("context", {})
    reason_trace = self.state.get("reason_trace", [])

    IF NOT decision:
        RETURN (0, None, ("NO_DECISION", "No decision to persist", 0))

    decision_type = {
        "gui": "component_choice",
        "codefix": "fix_choice",
        "session": "resume_point",
    }.get(domain, "unknown")

    chosen_node_id = None
    chosen_name    = None
    score          = 0
    reason         = ""
    evaluated      = []

    IF domain == "gui":
        chosen_node_id = decision.get("chosen_node_id")
        chosen_name    = decision.get("chosen_component")
        score          = decision.get("score", 0)
        reason         = decision.get("reason", "")
    ELIF domain == "codefix":
        chosen_fix = decision.get("chosen_fix")
        IF chosen_fix:
            chosen_node_id = chosen_fix.get("node_id")
            chosen_name    = chosen_fix.get("name")
            score          = decision.get("decision_score", 0)
            reason         = decision.get("reason", "")
            evaluated      = decision.get("evaluated", [])
    ELIF domain == "session":
        chosen_name = decision.get("chosen_path")
        score       = decision.get("score", 0)
        reason      = decision.get("reason", "")

    INSERT INTO decisions (
        domain, decision_type, input_context, chosen_node_id,
        chosen_name, decision_score, reason, reason_trace,
        evaluated, is_active, created
    ) VALUES (
        domain, decision_type, JSON(context), chosen_node_id,
        chosen_name, score, reason, JSON(reason_trace),
        JSON(evaluated), 1, datetime.now()
    )

    decision_id = cursor.lastrowid
    self.state["reason_trace"].append("STEP 8: Persisted decision_id=" + str(decision_id))
    RETURN (1, {"decision_id": decision_id, "persisted": True}, None)
END FUNCTION
```

### 3.3 Full Pipeline Orchestrator

```
FUNCTION Decide(params)
    # Reset trace for new decision run
    self.state["reason_trace"] = []

    # Run all 8 steps in sequence
    FOR step IN [GetCandidates, Filter, WhenRules, ResolveConflicts, Score]:
        result = step(params)
        IF result[0] != 1:
            RETURN result  # propagate error

    # Step 6: Decide
    dec_result = Decide(params)
    IF dec_result[0] != 1:
        RETURN dec_result

    # Step 7: Trace (always succeeds, just reads state)
    Trace(params)

    # Step 8: Persist (optional, controlled by params["persist"])
    IF params.get("persist", True):
        Persist(params)

    RETURN dec_result
END FUNCTION
```

---

## 4. Migration Mapping

### 4.1 GUIDecisionEngine Migration

**Source DB:** `gui_engine/db/database/token_registry.db` (SQLite)
**Target DB:** `dom_graph_unified.db` (SQLite, domain = `"gui"`)

| Source Table | Source Columns | Target Table | Target Columns | Notes |
|---|---|---|---|---|
| `component_ontology` | id | nodes | node_id | auto-increment remapped |
| | name | nodes | name | |
| | domain_tags | nodes | domain_tags | |
| | complexity_level | nodes | complexity_level | |
| | description | nodes | description | |
| `when_not_rule` | component_id | rules | target_node_id | FK remapped to new node_id |
| | condition_expression | rules | condition_expr | |
| | description | rules | description | |
| `when_rule` | component_id | rules | target_node_id | |
| | condition_expression | rules | condition_expr | |
| | description | rules | description | |
| | priority | rules | priority | |
| `conflict_resolution_rule` | component_a_id, component_b_id | edges + rules | src_node_id, dst_node_id (edge_type='conflicts_with') + rules (rule_type='conflict_resolution', target_node_id=component_a_id, resolution_expr stores component_b reference) | Split into edge + rule |
| | resolution_expression | rules | resolution_expr | |
| | winner_priority | rules | priority | |
| | description | rules | description | |
| `scoring_model` | component_id | rules | target_node_id | |
| | score_expression | rules | score_expr | |
| | base_score | rules | base_score | |
| | max_score | rules | max_score | |
| `architecture_learning` | category | rules | category | rule_type = 'learning' |
| | mistake | rules | description | |
| | correction | rules | correction | |
| | rule | rules | condition_expr | |
| | priority | rules | priority | |
| `decision_principle` | principle_name | rules | name (new column or in description) | rule_type = 'principle' |
| | description | rules | description | |
| | implementation | rules | implementation | |
| | anti_pattern | rules | anti_pattern | |

**GUIDecisionEngine does not have a `Run()` dispatch.** It uses direct method
calls (`decide_component()`). The migration adds `Run()` dispatch with
`"decide_component"` as an alias that calls the unified `Decide()` pipeline with
`domain = "gui"`.

### 4.2 DecisionEngine Migration

**Source DB:** `Dom_Graph/dom_graph_work.db` (SQLite)
**Target DB:** `dom_graph_unified.db` (SQLite, domain = `"codefix"`)

| Source Table | Source Columns | Target Table | Target Columns | Notes |
|---|---|---|---|---|
| `knowledge` | knowledge_id | nodes | node_id | remapped |
| | problem | nodes | name | |
| | question | nodes | properties (JSON: {question: ...}) | |
| | answer | nodes | description | |
| | confidence | nodes | confidence | |
| | fix_result | nodes | properties (JSON: {fix_result: ...}) | |
| | error_type | nodes | properties (JSON: {error_type: ...}) | |
| | error_text | nodes | properties (JSON: {error_text: ...}) | |
| | stack_trace | nodes | properties (JSON: {stack_trace: ...}) | |
| | fix_applied | nodes | properties (JSON: {fix_applied: ...}) | |
| | method_id | nodes | properties (JSON: {method_id: ...}) | FK to methods node |
| | class_id | nodes | properties (JSON: {class_id: ...}) | FK to classes node |
| | file_id | nodes | properties (JSON: {file_id: ...}) | FK to files node |
| | tags | nodes | domain_tags | |
| | created | nodes | created | |
| `files` | file_id | nodes | node_id | node_type = 'file' |
| | file_name | nodes | name | |
| | path | nodes | qualified_name | |
| | extension | nodes | properties (JSON) | |
| | hash | nodes | hash | |
| | imports | nodes | properties (JSON) | |
| | exports | nodes | properties (JSON) | |
| | class_count | nodes | properties (JSON) | |
| | method_count | nodes | properties (JSON) | |
| | language | nodes | properties (JSON) | |
| `classes` | class_id | nodes | node_id | node_type = 'class' |
| | class_name | nodes | name | |
| | file_id | nodes | parent_node_id | remapped |
| | parent | nodes | properties (JSON: {parent: ...}) | |
| | interfaces | nodes | properties (JSON) | |
| | method_count | nodes | properties (JSON) | |
| | cyclomatic_complexity | nodes | complexity_level | |
| `methods` | method_id | nodes | node_id | node_type = 'method' |
| | method_name | nodes | name | |
| | class_id | nodes | parent_node_id | remapped |
| | file_id | nodes | properties (JSON: {file_id: ...}) | |
| | method_code | nodes | content | |
| | cyclomatic_complexity | nodes | complexity_level | |
| | line_count | nodes | properties (JSON: {line_count: ...}) | |
| | has_print | nodes | properties (JSON) | |
| | has_decorator | nodes | properties (JSON) | |
| | has_self_underscore | nodes | properties (JSON) | |
| | returns_tuple3 | nodes | properties (JSON) | |
| | is_vbstyle | nodes | properties (JSON) | |
| | start_line | nodes | line_start | |
| | end_line | nodes | line_end | |
| `edges` | edge_id | edges | edge_id | |
| | src_type | edges | src_type | |
| | src_id | edges | src_node_id | remapped |
| | dst_type | edges | dst_type | |
| | dst_id | edges | dst_node_id | remapped |
| | edge_type | edges | edge_type | |
| | evidence | edges | evidence | |
| | confidence | edges | confidence | |
| `attempts` | attempt_id | nodes | node_id | node_type = 'attempt' |
| | method_id | nodes | parent_node_id | remapped |
| | action | nodes | name | |
| | before_code | nodes | properties (JSON) | |
| | after_code | nodes | content | |
| | compile_result | nodes | properties (JSON) | |
| | test_result | nodes | properties (JSON) | |
| | knowledge_id | nodes | properties (JSON: {knowledge_id: ...}) | |
| `observations` | observation_id | nodes | node_id | node_type = 'observation' |
| | observation_type | nodes | node_type | (prefixed: 'observation_' + type) |
| | subject | nodes | name | |
| | evidence | nodes | description | |
| | confidence | nodes | confidence | |
| `snapshots` | snapshot_id | snapshots | snapshot_id | |
| | snapshot_type | snapshots | snapshot_type | |
| | file_id | snapshots | target_node_id | remapped |
| | class_id | snapshots | properties (JSON) | |
| | method_id | snapshots | properties (JSON) | |
| | content | snapshots | content | |
| | hash | snapshots | hash | |
| | notes | snapshots | notes | |
| | created | snapshots | created | |

**DecisionEngine already has `Run()` dispatch.** All 8 commands map directly to
the unified dispatch table. The `Connect()` method is replaced by the unified
`_get_conn()` that opens `dom_graph_unified.db`.

### 4.3 DomSessionGraph Migration

**Source DB:** MySQL `vb_shared` (tables: `session_graphs`, `session_paths`, `session_resume_points`)
**Target DB:** `dom_graph_unified.db` (SQLite, domain = `"session"`)

**Note:** The session engine uses MySQL while the other two use SQLite. The
unified engine uses SQLite for all domains. The migration copies session data
from MySQL to SQLite. A dual-write shim can be used during the transition period.

| Source Table | Source Columns | Target Table | Target Columns | Notes |
|---|---|---|---|---|
| `session_graphs` | id | nodes | node_id | node_type = 'session' |
| | session_id | nodes | name | (was varchar, now TEXT) |
| | session_date | nodes | properties (JSON: {session_date: ...}) | |
| | main_thread | nodes | description | |
| | main_progress | nodes | confidence | (confidence field repurposed for progress) |
| | main_status | nodes | status | (IN_PROGRESS -> in_progress, CLOSED -> closed) |
| | resume_action | nodes | properties (JSON: {resume_action: ...}) | |
| | created_at | nodes | created | |
| | updated_at | nodes | updated | |
| `session_paths` | id | nodes | node_id | node_type = 'path' |
| | session_id | nodes | parent_node_id | remapped to session node_id |
| | path_type | nodes | domain_tags | (MAIN, SIDE, DEAD_END, RESOLVED) |
| | path_name | nodes | name | |
| | path_status | nodes | status | |
| | progress | nodes | confidence | (confidence field repurposed for progress) |
| | trigger_reason | nodes | properties (JSON: {trigger_reason: ...}) | |
| | time_cost_min | nodes | properties (JSON) | |
| | was_worth_it | nodes | properties (JSON) | |
| | parent_path | edges | (edge_type='parent_of', src=path_node, dst=parent_path_node) | Converted to edge |
| | sort_order | nodes | properties (JSON: {sort_order: ...}) | |
| | notes | nodes | content | |
| `session_resume_points` | id | snapshots | snapshot_id | snapshot_type = 'resume_point' |
| | session_id | snapshots | properties (JSON: {session_id: ...}) | |
| | project_name | snapshots | project_name | |
| | progress | snapshots | progress | |
| | state | snapshots | state | |
| | resume_action | snapshots | resume_action | |
| | is_active | snapshots | is_active | |
| | updated_at | snapshots | created | |

**DomSessionGraph already has `Run()` dispatch.** All 9 commands map to the
unified dispatch table. The `_get_conn()` method changes from MySQL to SQLite.
The `read_state()` method is preserved.

---

## 5. ContextRAM Integration

ContextRAM's `ctx_assemble`, `ctx_suggest`, and `ctx_auto` commands currently do
raw text search (TF-IDF / semantic / embedding) over the ContextRAM node store.
The integration replaces the raw text search with a `DomGraphEngine.Decide()`
call that uses the graph structure (edges, rules, decisions) to produce
structured, ranked results.

### 5.1 Architecture

```
ctx auto --task "fix import error in gui_engine.py"
  |
  v
AutoContextRetriever.smartAssemble(query, currentFile)
  |
  v
[NEW] DomGraphEngine.Run("decide", {
    domain: "codefix",
    query: "fix import error in gui_engine.py",
    context: { file: "gui_engine.py", task: "fix import error" },
    persist: False
})
  |
  v
8-step pipeline:
  1. GetCandidates: SELECT knowledge nodes matching "import error"
  2. Filter: exclude failed fixes with low confidence
  3. WhenRules: keep candidates with success_rate > 0
  4. ResolveConflicts: rank by success_rate, confidence
  5. Score: risk + cost + benefit + simulation + validation
  6. Decide: pick best candidate
  7. Trace: build reason_trace
  8. Persist: (skipped, persist=False)
  |
  v
Return ContextAssembly-shaped JSON:
  {
    "query": "fix import error in gui_engine.py",
    "decisions": [chosen_fix_node],
    "facts": [related knowledge nodes],
    "rules": [applicable when_not/when rules],
    "memories": [past decisions on similar problems],
    "reason_trace": [...]
  }
```

### 5.2 Integration Points

#### ctx_assemble

**Current behavior:** `store.assemble(query, limitPerLayer)` does a text search
across all node types and returns a `ContextAssembly` with goals, tasks, facts,
rules, memories, decisions, hypotheses, openQuestions.

**New behavior:** When DomGraphEngine is available, `ctx assemble --query "text"`
calls `DomGraphEngine.Run("decide", {domain: "codefix", query: text, persist: false})`
and merges the result into the `ContextAssembly`:

- `decisions` field: populated with the DomGraphEngine decision output
- `facts` field: populated with the evaluated candidate nodes (knowledge nodes)
- `rules` field: populated with the rules that fired during the pipeline
- `memories` field: populated with past decisions from the `decisions` table
  that match the query

The text search fallback remains for nodes not in DomGraphEngine (e.g., ingested
file chunks, chat history).

**Implementation:** Add a `--use-graph` flag to `ctx assemble`. When set,
AutoContextRetriever calls DomGraphEngine via subprocess (`python3 -c "..."`) or
via a Python bridge module. The Swift CLI shells out to Python for graph
queries, same as it currently shells out for MySQL source ingestion.

#### ctx_suggest

**Current behavior:** `suggestForCurrentWork(currentFile, currentTask)` returns
`ProactiveSuggestion` arrays based on file name matching, task semantic search,
trending queries, and cold-hot nodes.

**New behavior:** When DomGraphEngine is available, `ctx suggest --task "desc"
--file path` calls `DomGraphEngine.Run("get_candidates", {domain: "codefix",
query: task})` to get graph-ranked candidates instead of raw text search. The
suggestions are enriched with:

- `reason`: the reason_trace from the pipeline (why these candidates were chosen)
- `confidence`: the decision_score from the pipeline
- `nodes`: the top-scored candidate nodes

**Implementation:** Add a `--use-graph` flag to `ctx suggest`. The
AutoContextRetriever checks for a config key `graphEngineEnabled` and, if true,
calls DomGraphEngine for the task-based suggestion instead of the semantic
searcher.

#### ctx_auto

**Current behavior:** `smartAssemble(query, currentFile, limitPerLayer)` combines
`store.assemble()` with `onFileEdit()` and `loadForTask()`.

**New behavior:** When DomGraphEngine is available, `ctx auto --task "desc"
--file path` calls `DomGraphEngine.Run("decide", {domain: "codefix", query: task,
context: {file: path}, persist: false})` and uses the result as the primary
assembly layer. The existing file-edit and tag-based loading remain as
supplementary layers.

**Implementation:** Add a `--use-graph` flag to `ctx auto`. The
AutoContextRetriever's `smartAssemble` method gains a `graphEngine` parameter.
When set, it calls DomGraphEngine first, then supplements with the existing
file/tag-based loading.

### 5.3 Bridge Module

A Python bridge module (`dom_graph_bridge.py`) provides a subprocess-callable
interface for the Swift CLI:

```
# Called by ContextRAM Swift CLI via:
#   python3 dom_graph_bridge.py decide --domain codefix --query "..." --file "..."
#
# Returns JSON to stdout:
#   {"ok": 1, "data": {...}, "error": null}

FUNCTION main():
    args = parse_argv()
    engine = DomGraphEngine()
    result = engine.Run(args.command, args.params)
    print(json.dumps({"ok": result[0], "data": result[1], "error": result[2]}))
END FUNCTION
```

The Swift CLI's `AutoContextRetriever` gains a `graphEnginePath` config key
pointing to `dom_graph_bridge.py`. When set, it shells out to Python for graph
queries. This follows the existing pattern where `ctx config --mysql-database`
shells out to MySQL.

### 5.4 Bidirectional Sync

DomGraphEngine can also write back to ContextRAM:

- When a decision is persisted (Step 8), a `decision` node is created in
  ContextRAM via `ctx put --type decision --value "..." --tags graph_decision`
- When a candidate is chosen, it is linked to the problem node via
  `ctx link DECISION_ID resolves PROBLEM_ID`
- This creates a feedback loop: future `ctx assemble` calls will find the
  graph decision as a `decision` layer node

---

## 6. MCP Exposure

The existing ContextRAM MCP server (`mcp-server/index.js`) exposes `ctx_*` tools.
The unified DomGraphEngine adds a new set of `graph_*` MCP tools. These can be
served by extending the existing MCP server or by a new Python MCP server.

### 6.1 New MCP Tools

```
graph_decide
  description: "Run the full 8-step decision pipeline and return the chosen candidate"
  inputSchema:
    domain:   { type: string, enum: ["gui", "codefix", "session"] }
    query:    { type: string, description: "Problem text / context query" }
    context:  { type: object, description: "Decision context (data_shape, user_intent, etc.)" }
    method_id: { type: integer, description: "Method ID for risk/cost analysis (codefix)" }
    persist:  { type: boolean, description: "Persist decision to DB (default true)" }
  required: [domain, query]

graph_trace
  description: "Get the reason trace from the last decision run"
  inputSchema: { type: object, properties: {} }

graph_query
  description: "Query nodes by text, type, domain, or status"
  inputSchema:
    domain:    { type: string, enum: ["gui", "codefix", "session"] }
    node_type: { type: string }
    status:    { type: string }
    text:      { type: string, description: "Search text (LIKE match on name/description)" }
    limit:     { type: integer, description: "Max results (default 50)" }
  required: []

graph_add_node
  description: "Add a node to the graph"
  inputSchema:
    domain:         { type: string, enum: ["gui", "codefix", "session"] }
    node_type:      { type: string }
    name:           { type: string }
    description:    { type: string }
    content:        { type: string }
    properties:     { type: object }
    domain_tags:    { type: string }
    parent_node_id: { type: integer }
    confidence:     { type: number }
  required: [domain, node_type, name]

graph_add_edge
  description: "Add an edge between two nodes"
  inputSchema:
    domain:      { type: string }
    src_node_id: { type: integer }
    dst_node_id: { type: integer }
    edge_type:   { type: string }
    evidence:    { type: string }
    confidence:  { type: number }
  required: [src_node_id, dst_node_id, edge_type]

graph_add_rule
  description: "Add a decision rule (when, when_not, conflict_resolution, scoring)"
  inputSchema:
    domain:          { type: string }
    rule_type:       { type: string, enum: ["when", "when_not", "conflict_resolution", "scoring", "principle", "learning"] }
    target_node_id:  { type: integer }
    condition_expr:  { type: string }
    resolution_expr: { type: string }
    score_expr:      { type: string }
    base_score:      { type: number }
    max_score:       { type: number }
    priority:        { type: integer }
    description:     { type: string }
  required: [domain, rule_type]

graph_get_decision
  description: "Retrieve a past decision by ID"
  inputSchema:
    decision_id: { type: integer }
  required: [decision_id]

graph_query_decisions
  description: "Search past decisions by domain, type, or chosen node"
  inputSchema:
    domain:         { type: string }
    decision_type:  { type: string }
    chosen_node_id: { type: integer }
    limit:          { type: integer }
  required: []

graph_add_snapshot
  description: "Create a snapshot or resume point"
  inputSchema:
    domain:         { type: string }
    snapshot_type:  { type: string }
    target_node_id: { type: integer }
    project_name:   { type: string }
    progress:       { type: integer }
    state:          { type: string }
    resume_action:  { type: string }
    content:        { type: string }
    notes:          { type: string }
  required: [domain, snapshot_type, content]

graph_stats
  description: "Get graph statistics (node/edge/rule/decision counts by domain)"
  inputSchema: { type: object, properties: {} }

graph_migrate
  description: "Migrate data from a legacy engine DB to the unified DB"
  inputSchema:
    source_engine: { type: string, enum: ["gui", "codefix", "session"] }
    source_path:   { type: string, description: "Path to source SQLite DB or MySQL config" }
    dry_run:       { type: boolean, description: "Preview without writing" }
  required: [source_engine]
```

### 6.2 MCP Server Implementation

Two options:

**Option A: Extend existing Node.js MCP server** (`mcp-server/index.js`)
- Add `graph_*` tools to the tools array
- Shell out to `python3 dom_graph_bridge.py` for each tool
- Pro: single MCP server, single transport
- Con: Node.js -> Python subprocess for every call

**Option B: New Python MCP server** (`dom_graph_mcp_server.py`)
- Uses the `mcp` Python SDK directly
- Instantiates `DomGraphEngine` once, reuses for all calls
- Pro: no subprocess overhead, direct Python access
- Con: two MCP servers to configure

**Recommendation: Option B** — a dedicated Python MCP server that hosts
`DomGraphEngine` in-process. This avoids subprocess overhead and allows the
engine to maintain state (connection pool, cached rules) across calls. The
existing ContextRAM MCP server remains for `ctx_*` tools.

### 6.3 MCP Server Configuration

The new MCP server is registered in the Claude Code / Windsurf MCP config:

```json
{
  "mcpServers": {
    "contextram": {
      "command": "node",
      "args": ["/Users/wws/contestsystem/ContextRAMSwift/mcp-server/index.js"]
    },
    "domgraph": {
      "command": "python3",
      "args": ["/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/dom_graph_mcp_server.py"]
    }
  }
}
```

---

## 7. Phased Rollout

### 7.1 Phase Order

| Phase | Engine | Priority | Rationale |
|-------|--------|----------|-----------|
| Phase 1 | DecisionEngine (codefix) | First | Already working, already VBStyle, already has Run() dispatch, already SQLite. Lowest risk, highest value. |
| Phase 2 | DomSessionGraph (session) | Second | Already working, already VBStyle, already has Run() dispatch. Requires MySQL -> SQLite migration but schema is simple (3 tables). |
| Phase 3 | GUIDecisionEngine (gui) | Third | Currently a stub. Porting it last means we implement the gui pipeline fresh in the unified engine, filling in the stub with real logic. |

### 7.2 Phase 1: Port DecisionEngine (codefix)

**Goal:** `DomGraphEngine.Run("decide", {domain: "codefix", query: "..."})`
produces identical results to `DecisionEngine.Run("decide", {problem: "..."})`.

**Steps:**

1. Create `DomGraphEngine.py` with VBStyle headers, `__init__(self, mem=None, db=None, param=None)`, `self.state` dict, `Run()` dispatch, `_p()`, `read_state()`, `set_config()`.
2. Create `dom_graph_unified.db` with the 5-table schema from Section 1.
3. Write migration script `migrate_codefix.py` that copies all rows from `dom_graph_work.db` into `dom_graph_unified.db` with domain = `"codefix"`.
4. Implement `GetCandidates`, `Filter`, `WhenRules`, `ResolveConflicts`, `Score`, `Decide`, `Trace`, `Persist` for domain = `"codefix"`.
5. Port `AnalyzeRisk`, `AnalyzeCost`, `AnalyzeBenefit`, `Simulate`, `Validate`, `RankFixes` as internal methods called by `Score` and `ResolveConflicts`.
6. Run both engines in parallel (shadow mode): call old `DecisionEngine.Run("decide", ...)` and new `DomGraphEngine.Run("decide", {domain: "codefix", ...})` with the same input, compare outputs.
7. When outputs match for 50 consecutive test cases, cutover.

**Regression avoidance:**
- Keep `dom_graph_work.db` intact as backup
- Shadow mode comparison for 50 test cases
- The unified engine reads from `dom_graph_unified.db` which is a copy, so the
  original DB is never modified during Phase 1

**Files to create:**
- `Dom_Graph/DomGraphEngine.py` — the unified engine class
- `Dom_Graph/migrate_codefix.py` — migration script
- `Dom_Graph/dom_graph_unified.db` — new unified database (created by migration script)

### 7.3 Phase 2: Port DomSessionGraph (session)

**Goal:** `DomGraphEngine.Run("open_session", {...})` and all session commands
produce identical results to `DomSessionGraph.Run("open", {...})`.

**Steps:**

1. Add session commands to `DomGraphEngine.Run()` dispatch: `open_session`, `add_path`, `update_path`, `add_resume`, `get_resume`, `render`, `dashboard`, `close_session`, `list_sessions`.
2. Write migration script `migrate_session.py` that copies all rows from MySQL `vb_shared.session_graphs`, `session_paths`, `session_resume_points` into `dom_graph_unified.db` with domain = `"session"`.
3. Implement session commands using SQLite instead of MySQL. The `_get_conn()` method returns the SQLite connection to `dom_graph_unified.db`.
4. Implement `Render` and `Dashboard` to produce the same ASCII output as the original.
5. Run both engines in parallel (shadow mode): call old `DomSessionGraph.Run(...)` and new `DomGraphEngine.Run(...)` with the same input, compare outputs.
6. When outputs match for 20 consecutive test cases, cutover.
7. Optional: set up a dual-write shim that writes to both MySQL and SQLite during the transition, then disable MySQL after cutover.

**Regression avoidance:**
- Keep MySQL tables intact as backup
- Dual-write shim during transition
- Shadow mode comparison for 20 test cases
- The `Render` and `Dashboard` ASCII output must be byte-identical

**Files to create:**
- `Dom_Graph/migrate_session.py` — migration script

### 7.4 Phase 3: Port GUIDecisionEngine (gui)

**Goal:** `DomGraphEngine.Run("decide_component", {context: {...}})` produces a
real decision instead of the stub "not implemented" return.

**Steps:**

1. Add gui commands to `DomGraphEngine.Run()` dispatch: `decide_component`, `validate_context`.
2. Write migration script `migrate_gui.py` that creates the `token_registry.db` tables if they do not exist, populates them with seed data (component_ontology, when_rule, when_not_rule, conflict_resolution_rule, scoring_model), then copies into `dom_graph_unified.db` with domain = `"gui"`.
3. Implement `GetCandidates`, `Filter`, `WhenRules`, `ResolveConflicts`, `Score` for domain = `"gui"` using the rules table (when_not, when, conflict_resolution, scoring rule types).
4. Implement `EvaluateCondition` (the condition expression evaluator from the original GUIDecisionEngine, supporting ==, !=, >, <, >=, <=, AND, OR).
5. Implement `EvaluateResolution` (IF/THEN/ELSE parser).
6. Implement `EvaluateScore` (ternary expression parser).
7. Implement `ValidateContext` (principle validation: check for data_shape, user_intent, interaction_type, device_type in context).
8. Test with seeded component ontology data.

**Regression avoidance:**
- The original engine is a stub, so there is no regression risk — only improvement
- The original `GUIDecisionEngine` class remains in `gui_engine.py` as a thin wrapper that delegates to `DomGraphEngine.Run("decide_component", ...)`
- The `StyleDBV2`, `StyleEngineV2`, `QtStyleRendererV2`, `UIDBV4` classes in `gui_engine.py` are unrelated to the decision engine and remain unchanged

**Files to create:**
- `Dom_Graph/migrate_gui.py` — migration script

### 7.5 Phase 4: ContextRAM Integration

**Goal:** `ctx auto --use-graph --task "..."` and `ctx suggest --use-graph --task "..."`
call DomGraphEngine for ranked results.

**Steps:**

1. Create `dom_graph_bridge.py` — a subprocess-callable Python script that instantiates `DomGraphEngine` and returns JSON.
2. Add `graphEnginePath` config key to ContextRAM's `ContextRAMConfig` (Swift).
3. Modify `AutoContextRetriever.smartAssemble()` to check for `graphEnginePath` and shell out to Python when set.
4. Modify `AutoContextRetriever.suggestForCurrentWork()` similarly.
5. Add `--use-graph` flag to `ctx auto`, `ctx suggest`, `ctx assemble` CLI commands.
6. Test: `ctx auto --use-graph --task "fix import error"` returns graph-ranked decisions.
7. Implement bidirectional sync: DomGraphEngine writes decision nodes back to ContextRAM via `ctx put --type decision`.

**Files to create:**
- `Dom_Graph/dom_graph_bridge.py` — bridge module for Swift CLI
- Modify: `ContextRAMSwift/Sources/ContextRAMCore/AutoContextRetriever.swift`
- Modify: `ContextRAMSwift/Sources/ContextRAMSwift/main.swift`

### 7.6 Phase 5: MCP Exposure

**Goal:** `graph_decide`, `graph_query`, `graph_add_node`, etc. are available as
MCP tools in Claude Code / Windsurf.

**Steps:**

1. Create `dom_graph_mcp_server.py` — a Python MCP server using the `mcp` SDK.
2. Instantiate `DomGraphEngine` once at server startup.
3. Register all `graph_*` tools from Section 6.1.
4. Add MCP server config to Claude Code / Windsurf settings.
5. Test: `graph_decide` with `domain: "codefix"`, `query: "import error"` returns a decision.

**Files to create:**
- `Dom_Graph/dom_graph_mcp_server.py` — Python MCP server

---

## 8. VBStyle Compliance

The unified `DomGraphEngine` follows all VBStyle conventions:

```
# [@GHOST]{file_path, date, author, session_id, context}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="DomGraphEngine.py" domain="dom_graph" authority="DomGraphEngine"}
# [@SUMMARY]{summary="Unified decision graph engine merging GUIDecisionEngine, DecisionEngine, DomSessionGraph"}
# [@CLASS]{class="DomGraphEngine" domain="decision" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="GetCandidates" type="command"}
# [@METHOD]{method="Filter" type="command"}
# [@METHOD]{method="WhenRules" type="command"}
# [@METHOD]{method="ResolveConflicts" type="command"}
# [@METHOD]{method="Score" type="command"}
# [@METHOD]{method="Decide" type="command"}
# [@METHOD]{method="Trace" type="command"}
# [@METHOD]{method="Persist" type="command"}
# [@METHOD]{method="AnalyzeRisk" type="command"}
# [@METHOD]{method="Simulate" type="command"}
# [@METHOD]{method="Validate" type="command"}
# [@METHOD]{method="AnalyzeCost" type="command"}
# [@METHOD]{method="AnalyzeBenefit" type="command"}
# [@METHOD]{method="OpenSession" type="command"}
# [@METHOD]{method="AddPath" type="command"}
# [@METHOD]{method="UpdatePath" type="command"}
# [@METHOD]{method="AddResume" type="command"}
# [@METHOD]{method="GetResume" type="command"}
# [@METHOD]{method="Render" type="command"}
# [@METHOD]{method="Dashboard" type="command"}
# [@METHOD]{method="CloseSession" type="command"}
# [@METHOD]{method="ListSessions" type="command"}
# [@METHOD]{method="DecideComponent" type="command"}
# [@METHOD]{method="ValidateContext" type="command"}
# [@METHOD]{method="AddNode" type="command"}
# [@METHOD]{method="GetNode" type="command"}
# [@METHOD]{method="QueryNodes" type="command"}
# [@METHOD]{method="AddEdge" type="command"}
# [@METHOD]{method="GetEdges" type="command"}
# [@METHOD]{method="AddRule" type="command"}
# [@METHOD]{method="GetRules" type="command"}
# [@METHOD]{method="GetDecision" type="command"}
# [@METHOD]{method="QueryDecisions" type="command"}
# [@METHOD]{method="AddSnapshot" type="command"}
# [@METHOD]{method="GetSnapshot" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="_get_conn" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
```

### Constructor

```python
class DomGraphEngine:
    """Unified decision graph engine."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "dom_graph_unified.db",
                ),
                "default_limit": 50,
                "default_domain": "codefix",
            },
            "candidates": [],
            "filtered": [],
            "triggered": [],
            "resolved": [],
            "scored": [],
            "decision": None,
            "reason_trace": [],
            "current_session": None,
            "stats": {
                "decisions_made": 0,
                "candidates_evaluated": 0,
                "sessions_opened": 0,
            },
            "memunit": mem,
            "db_manager": db,
            "db_conn": None,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value
```

### Run Dispatch

```python
    def Run(self, command, params=None):
        params = params or {}
        dispatch = {
            # Shared pipeline
            "decide": self.Decide,
            "get_candidates": self.GetCandidates,
            "filter": self.Filter,
            "when_rules": self.WhenRules,
            "resolve_conflicts": self.ResolveConflicts,
            "score": self.Score,
            "trace": self.Trace,
            "persist": self.Persist,
            # Codefix
            "rank_fixes": self.RankFixes,
            "analyze_risk": self.AnalyzeRisk,
            "simulate": self.Simulate,
            "validate": self.Validate,
            "analyze_cost": self.AnalyzeCost,
            "analyze_benefit": self.AnalyzeBenefit,
            # Session
            "open_session": self.OpenSession,
            "open": self.OpenSession,  # backward compat alias
            "add_path": self.AddPath,
            "update_path": self.UpdatePath,
            "add_resume": self.AddResume,
            "get_resume": self.GetResume,
            "render": self.Render,
            "dashboard": self.Dashboard,
            "close_session": self.CloseSession,
            "close": self.CloseSession,  # backward compat alias
            "list_sessions": self.ListSessions,
            # GUI
            "decide_component": self.DecideComponent,
            "validate_context": self.ValidateContext,
            # Graph CRUD
            "add_node": self.AddNode,
            "get_node": self.GetNode,
            "query_nodes": self.QueryNodes,
            "add_edge": self.AddEdge,
            "get_edges": self.GetEdges,
            "add_rule": self.AddRule,
            "get_rules": self.GetRules,
            "get_decision": self.GetDecision,
            "query_decisions": self.QueryDecisions,
            "add_snapshot": self.AddSnapshot,
            "get_snapshot": self.GetSnapshot,
            # VBStyle standard
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))
        return handler(params)
```

---

## 9. File Structure

```
Dom_Graph/
    DomGraphEngine.py           # Unified engine class (Phase 1-3)
    dom_graph_unified.db        # Unified SQLite database (created by migration)
    migrate_codefix.py          # Phase 1: migrate DecisionEngine data
    migrate_session.py          # Phase 2: migrate DomSessionGraph data
    migrate_gui.py              # Phase 3: migrate GUIDecisionEngine data
    dom_graph_bridge.py         # Phase 4: bridge for ContextRAM Swift CLI
    dom_graph_mcp_server.py     # Phase 5: Python MCP server
    DOM_GRAPH_ENGINE_DESIGN.md  # This document
    decision_engine.py          # Legacy (kept as fallback during migration)
```

---

## 10. Key Design Decisions

### 10.1 Why SQLite (not MySQL) for the unified DB

DecisionEngine and GUIDecisionEngine already use SQLite. Only DomSessionGraph uses
MySQL. Unifying on SQLite means:
- One connection mechanism (`sqlite3.connect`)
- No external server dependency
- File-based DB is portable and backup-friendly
- The session data volume is small (10 rows in session_paths, 10 in resume_points)
- MySQL can remain as a read replica if needed

### 10.2 Why `domain` column instead of separate tables per engine

A single `nodes` table with a `domain` column allows:
- Cross-domain queries (e.g., "find all decisions across all engines")
- Shared graph traversal (edges can cross domains)
- Simpler schema (5 tables instead of 15+)
- The `properties` JSON column absorbs domain-specific fields without schema bloat

### 10.3 Why `properties` JSON column instead of per-domain tables

The three engines have vastly different domain-specific fields (GUI has
`base_component`, codefix has `error_type` / `stack_trace`, session has
`trigger_reason` / `was_worth_it`). Creating columns for all of them would result
in a sparse table with many NULL columns. A JSON `properties` column keeps the
schema clean while preserving all data. SQLite's JSON functions
(`json_extract`, `json_each`) allow querying within the JSON when needed.

### 10.4 Why keep legacy engines during migration

The legacy engines serve as:
- Backup if the unified engine has bugs
- Reference implementation for validating unified engine output
- Shadow-mode comparison baseline
- They are NOT deleted until the unified engine has been validated in production

### 10.5 Why a Python MCP server instead of extending the Node.js one

The Node.js MCP server spawns the `ctx` binary for every call. A Python MCP
server hosts `DomGraphEngine` in-process, avoiding subprocess overhead and
allowing state reuse (connection pooling, cached rules). The two MCP servers
coexist: `contextram` for `ctx_*` tools, `domgraph` for `graph_*` tools.
