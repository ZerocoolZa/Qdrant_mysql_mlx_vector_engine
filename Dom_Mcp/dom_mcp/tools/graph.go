package tools

// [@GHOST]{file_path="Dom_Mcp/dom_mcp/tools/graph.go"
// date="2026-06-28" author="Devin" session_id="domgraph-phase5"
// context="MCP exposure for DomGraphEngine — graph_* tools via Python subprocess bridge"}
// [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase Tuple3 Run dispatch"}
// [@FILEID]{id="graph.go" domain="mcp_tools" authority="GraphModule"}
// [@SUMMARY]{summary="MCP module that wraps dom_graph_bridge.py as subprocess. Exposes DomGraphEngine commands as graph_* tools for MCP clients."}
// [@CLASS]{class="GraphModule" domain="mcp_tools" authority="single"}
// [@METHOD]{method="Name" type="interface"}
// [@METHOD]{method="Tools" type="interface"}
// [@METHOD]{method="run" type="helper"}

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"os/exec"
	"strings"
	"time"
)

// GraphModule wraps the dom_graph_bridge.py Python script as a subprocess.
// It exposes DomGraphEngine commands as MCP graph_* tools.
type GraphModule struct {
	binary    string // path to python3
	bridge    string // path to dom_graph_bridge.py
	timeoutMs int
}

// NewGraphModule creates a GraphModule from config.
func NewGraphModule(pythonBinary, bridgePath string, timeoutMs int) *GraphModule {
	if pythonBinary == "" {
		pythonBinary = "python3"
	}
	if timeoutMs <= 0 {
		timeoutMs = 30000
	}
	return &GraphModule{binary: pythonBinary, bridge: bridgePath, timeoutMs: timeoutMs}
}

func (m *GraphModule) Name() string { return "graph" }

func (m *GraphModule) Tools() []Tool {
	return []Tool{
		&graphTool{name: "graph_decide", desc: "Run the full 8-step decision pipeline (get_candidates → filter → when_rules → resolve_conflicts → score → decide). Returns chosen fix with score and reason trace.", m: m, required: []string{"query"}},
		&graphTool{name: "graph_get_candidates", desc: "Get candidate nodes matching a query from the unified graph DB.", m: m, required: []string{"query"}},
		&graphTool{name: "graph_query_nodes", desc: "Query nodes by domain, type, and name pattern.", m: m, required: nil},
		&graphTool{name: "graph_get_node", desc: "Get a single node by ID.", m: m, required: []string{"node_id"}},
		&graphTool{name: "graph_get_edges", desc: "Get edges connected to a node.", m: m, required: []string{"node_id"}},
		&graphTool{name: "graph_get_rules", desc: "Get rules filtered by domain, type, or target node.", m: m, required: nil},
		&graphTool{name: "graph_query_decisions", desc: "Query past decisions by domain and type.", m: m, required: nil},
		&graphTool{name: "graph_get_decision", desc: "Get a single decision by ID.", m: m, required: []string{"decision_id"}},
		&graphTool{name: "graph_rank_fixes", desc: "Rank fixes by success rate and confidence.", m: m, required: nil},
		&graphTool{name: "graph_analyze_risk", desc: "Analyze risk of modifying a method (complexity, dependencies, depth).", m: m, required: []string{"method_id"}},
		&graphTool{name: "graph_simulate", desc: "Simulate applying a fix in an in-memory sandbox.", m: m, required: []string{"fix_id"}},
		&graphTool{name: "graph_validate", desc: "Validate a fix by simulating and checking compilation.", m: m, required: []string{"fix_id"}},
		&graphTool{name: "graph_analyze_cost", desc: "Analyze the cost of modifying a method (lines, complexity, affected methods).", m: m, required: []string{"method_id"}},
		&graphTool{name: "graph_analyze_benefit", desc: "Analyze the benefit of fixing a problem (fixes resolved, violations addressed).", m: m, required: []string{"problem"}},
		&graphTool{name: "graph_overall_confidence", desc: "Get overall confidence score (parse, match, graph, repair, runtime).", m: m, required: nil},
		&graphTool{name: "graph_graph_confidence", desc: "Get graph coverage and edge confidence distribution.", m: m, required: nil},
		&graphTool{name: "graph_repair_confidence", desc: "Get repair confidence based on fix success rates.", m: m, required: nil},
		&graphTool{name: "graph_runtime_confidence", desc: "Get runtime confidence based on observation and method readiness.", m: m, required: nil},
		&graphTool{name: "graph_stats", desc: "Get unified DB statistics (node/edge/decision counts per domain).", m: m, required: nil},
		&graphTool{name: "graph_gc", desc: "Garbage collect: drop and recreate all tables (clean rebuild). Use instead of rm.", m: m, required: nil},
		&graphTool{name: "graph_migrate_codefix", desc: "Migrate codefix data from dom_graph_work.db to unified DB.", m: m, required: nil},
		&graphTool{name: "graph_migrate_session", desc: "Migrate session data from MySQL to unified DB.", m: m, required: nil},
		&graphTool{name: "graph_to_context_assembly", desc: "Run decide pipeline and convert result to ContextRAM ContextAssembly shape (for ContextRAM integration).", m: m, required: []string{"query"}},
		&graphTool{name: "graph_trace", desc: "Get the reason trace from the last decide call.", m: m, required: nil},
		&graphTool{name: "graph_add_node", desc: "Add a node to the unified graph DB.", m: m, required: []string{"node_type", "name"}},
		&graphTool{name: "graph_add_edge", desc: "Add an edge between two nodes.", m: m, required: []string{"src_node_id", "dst_node_id", "edge_type"}},
		&graphTool{name: "graph_delete_node", desc: "Delete a node by ID (also removes connected edges).", m: m, required: []string{"node_id"}},
		&graphTool{name: "graph_delete_edge", desc: "Delete an edge by ID.", m: m, required: []string{"edge_id"}},
		&graphTool{name: "graph_update_node", desc: "Update node properties (name, description, properties).", m: m, required: []string{"node_id"}},
		&graphTool{name: "graph_get_neighbors", desc: "Get neighbor nodes of a node, optionally filtered by edge type.", m: m, required: []string{"node_id"}},
		&graphTool{name: "graph_get_paths", desc: "Find paths between two nodes using DFS traversal.", m: m, required: []string{"src_node_id", "dst_node_id"}},
		&graphTool{name: "graph_export", desc: "Export graph data to JSON or CSV format.", m: m, required: nil},
		&graphTool{name: "graph_add_rule", desc: "Add a rule to the unified graph DB.", m: m, required: []string{"rule_type"}},
		&graphTool{name: "graph_add_snapshot", desc: "Add a snapshot to the unified graph DB.", m: m, required: []string{"snapshot_type", "content"}},
		&graphTool{name: "graph_get_snapshot", desc: "Get a snapshot by ID.", m: m, required: []string{"snapshot_id"}},
	}
}

// run executes dom_graph_bridge.py with given args and returns stdout.
func (m *GraphModule) run(ctx context.Context, args ...string) (string, error) {
	if m.bridge == "" {
		return "", fmt.Errorf("graph bridge path not configured")
	}
	timeout := time.Duration(m.timeoutMs) * time.Millisecond
	cctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	cmdArgs := append([]string{m.bridge}, args...)
	cmd := exec.CommandContext(cctx, m.binary, cmdArgs...)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		stderrStr := strings.TrimSpace(stderr.String())
		if cctx.Err() == context.DeadlineExceeded {
			return "", fmt.Errorf("graph bridge timed out after %dms", m.timeoutMs)
		}
		if stderrStr != "" {
			return "", fmt.Errorf("graph bridge: %s: %v", stderrStr, err)
		}
		return "", fmt.Errorf("graph bridge: %v", err)
	}
	return stdout.String(), nil
}

// graphTool is a generic tool that maps to a dom_graph_bridge.py command.
type graphTool struct {
	name     string
	desc     string
	m        *GraphModule
	required []string
}

func (t *graphTool) Name() string        { return t.name }
func (t *graphTool) Description() string { return t.desc }

func (t *graphTool) InputSchema() map[string]any {
	props := map[string]map[string]any{
		"query":          Prop("string", "Search query text."),
		"domain":         Prop("string", "Domain filter (codefix, gui, session)."),
		"node_type":      Prop("string", "Node type (method, class, file, knowledge, observation, attempt)."),
		"node_id":        Prop("integer", "Node ID."),
		"edge_id":        Prop("integer", "Edge ID."),
		"edge_type":      Prop("string", "Edge type (calls, imports, inherits, conflicts_with)."),
		"src_node_id":    Prop("integer", "Source node ID for edge."),
		"dst_node_id":    Prop("integer", "Destination node ID for edge."),
		"max_depth":      Prop("integer", "Maximum traversal depth for path finding."),
		"rule_type":      Prop("string", "Rule type (when, when_not, conflict_resolution, scoring, learning, principle)."),
		"snapshot_type":  Prop("string", "Snapshot type."),
		"snapshot_id":    Prop("integer", "Snapshot ID."),
		"content":        Prop("string", "Content text."),
		"name":           Prop("string", "Node or entity name."),
		"description":    Prop("string", "Description text."),
		"confidence":     Prop("number", "Confidence score (0-100)."),
		"limit":          Prop("integer", "Maximum results to return."),
		"method_id":      Prop("integer", "Method node ID for risk/cost analysis."),
		"fix_id":         Prop("integer", "Fix node ID for simulate/validate."),
		"problem":        Prop("string", "Problem description for benefit analysis."),
		"decision_id":    Prop("integer", "Decision ID."),
		"decision_type":  Prop("string", "Decision type filter."),
		"error_type":     Prop("string", "Error type for confidence matching."),
		"file_path":      Prop("string", "File path for parse confidence."),
		"file":           Prop("string", "File path (alias for file_path)."),
		"target_node_id": Prop("integer", "Target node ID for rules."),
		"properties":     Prop("string", "JSON string of node properties."),
		"persist":        Prop("boolean", "Whether to persist the decision to DB."),
		"source_db":      Prop("string", "Source database path for migration."),
		"pattern":        Prop("string", "Pattern for match confidence."),
		"target":         Prop("string", "Target for match confidence."),
		"format":         Prop("string", "Export format (json or csv)."),
	}
	return Schema(props, t.required)
}

func (t *graphTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	// Map tool name to bridge command (strip graph_ prefix)
	command := strings.TrimPrefix(t.name, "graph_")

	cmdArgs := []string{command}

	// Per-tool arg mapping
	switch t.name {
	case "graph_decide":
		if v := ArgString(args, "query"); v != "" {
			cmdArgs = append(cmdArgs, "--query", v)
		}
		if v := ArgString(args, "domain"); v != "" {
			cmdArgs = append(cmdArgs, "--domain", v)
		}
		if v := ArgInt(args, "limit", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--limit", fmt.Sprintf("%d", v))
		}
		if v := ArgString(args, "file"); v != "" {
			cmdArgs = append(cmdArgs, "--file", v)
		}
		if ArgBool(args, "persist") {
			cmdArgs = append(cmdArgs, "--persist")
		}

	case "graph_get_candidates", "graph_query_nodes":
		if v := ArgString(args, "query"); v != "" {
			cmdArgs = append(cmdArgs, "--query", v)
		}
		if v := ArgString(args, "domain"); v != "" {
			cmdArgs = append(cmdArgs, "--domain", v)
		}
		if v := ArgString(args, "node_type"); v != "" {
			cmdArgs = append(cmdArgs, "--node_type", v)
		}
		if v := ArgInt(args, "limit", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--limit", fmt.Sprintf("%d", v))
		}

	case "graph_get_node", "graph_get_edges":
		if v := ArgInt(args, "node_id", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--node_id", fmt.Sprintf("%d", v))
		}
		if v := ArgString(args, "domain"); v != "" {
			cmdArgs = append(cmdArgs, "--domain", v)
		}

	case "graph_get_rules":
		if v := ArgString(args, "domain"); v != "" {
			cmdArgs = append(cmdArgs, "--domain", v)
		}
		if v := ArgString(args, "rule_type"); v != "" {
			cmdArgs = append(cmdArgs, "--rule_type", v)
		}
		if v := ArgInt(args, "target_node_id", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--target_node_id", fmt.Sprintf("%d", v))
		}

	case "graph_query_decisions":
		if v := ArgString(args, "domain"); v != "" {
			cmdArgs = append(cmdArgs, "--domain", v)
		}
		if v := ArgString(args, "decision_type"); v != "" {
			cmdArgs = append(cmdArgs, "--decision_type", v)
		}
		if v := ArgInt(args, "limit", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--limit", fmt.Sprintf("%d", v))
		}

	case "graph_get_decision":
		if v := ArgInt(args, "decision_id", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--decision_id", fmt.Sprintf("%d", v))
		}

	case "graph_rank_fixes":
		if v := ArgString(args, "domain"); v != "" {
			cmdArgs = append(cmdArgs, "--domain", v)
		}
		if v := ArgString(args, "query"); v != "" {
			cmdArgs = append(cmdArgs, "--query", v)
		}
		if v := ArgInt(args, "limit", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--limit", fmt.Sprintf("%d", v))
		}

	case "graph_analyze_risk", "graph_analyze_cost":
		if v := ArgInt(args, "method_id", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--method_id", fmt.Sprintf("%d", v))
		}

	case "graph_simulate", "graph_validate":
		if v := ArgInt(args, "fix_id", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--fix_id", fmt.Sprintf("%d", v))
		}
		if v := ArgString(args, "domain"); v != "" {
			cmdArgs = append(cmdArgs, "--domain", v)
		}

	case "graph_analyze_benefit":
		if v := ArgString(args, "problem"); v != "" {
			cmdArgs = append(cmdArgs, "--problem", v)
		}

	case "graph_overall_confidence":
		if v := ArgString(args, "file_path"); v != "" {
			cmdArgs = append(cmdArgs, "--file_path", v)
		}
		if v := ArgString(args, "file"); v != "" {
			cmdArgs = append(cmdArgs, "--file_path", v)
		}
		if v := ArgString(args, "error_type"); v != "" {
			cmdArgs = append(cmdArgs, "--error_type", v)
		}
		if v := ArgString(args, "pattern"); v != "" {
			cmdArgs = append(cmdArgs, "--pattern", v)
		}

	case "graph_to_context_assembly":
		if v := ArgString(args, "query"); v != "" {
			cmdArgs = append(cmdArgs, "--query", v)
		}
		if v := ArgString(args, "domain"); v != "" {
			cmdArgs = append(cmdArgs, "--domain", v)
		}
		if v := ArgInt(args, "limit", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--limit", fmt.Sprintf("%d", v))
		}
		if v := ArgString(args, "file"); v != "" {
			cmdArgs = append(cmdArgs, "--file", v)
		}

	case "graph_add_node":
		if v := ArgString(args, "node_type"); v != "" {
			cmdArgs = append(cmdArgs, "--node_type", v)
		}
		if v := ArgString(args, "name"); v != "" {
			cmdArgs = append(cmdArgs, "--name", v)
		}
		if v := ArgString(args, "domain"); v != "" {
			cmdArgs = append(cmdArgs, "--domain", v)
		}
		if v := ArgString(args, "description"); v != "" {
			cmdArgs = append(cmdArgs, "--description", v)
		}
		if v := ArgFloat(args, "confidence"); v > 0 {
			cmdArgs = append(cmdArgs, "--confidence", fmt.Sprintf("%f", v))
		}
		if v := ArgString(args, "properties"); v != "" {
			cmdArgs = append(cmdArgs, "--properties", v)
		}

	case "graph_add_edge":
		if v := ArgInt(args, "src_node_id", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--src_node_id", fmt.Sprintf("%d", v))
		}
		if v := ArgInt(args, "dst_node_id", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--dst_node_id", fmt.Sprintf("%d", v))
		}
		if v := ArgString(args, "edge_type"); v != "" {
			cmdArgs = append(cmdArgs, "--edge_type", v)
		}
		if v := ArgString(args, "domain"); v != "" {
			cmdArgs = append(cmdArgs, "--domain", v)
		}

	case "graph_delete_node":
		if v := ArgInt(args, "node_id", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--node_id", fmt.Sprintf("%d", v))
		}

	case "graph_delete_edge":
		if v := ArgInt(args, "edge_id", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--edge_id", fmt.Sprintf("%d", v))
		}

	case "graph_update_node":
		if v := ArgInt(args, "node_id", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--node_id", fmt.Sprintf("%d", v))
		}
		if v := ArgString(args, "name"); v != "" {
			cmdArgs = append(cmdArgs, "--name", v)
		}
		if v := ArgString(args, "description"); v != "" {
			cmdArgs = append(cmdArgs, "--description", v)
		}
		if v := ArgString(args, "properties"); v != "" {
			cmdArgs = append(cmdArgs, "--properties", v)
		}

	case "graph_get_neighbors":
		if v := ArgInt(args, "node_id", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--node_id", fmt.Sprintf("%d", v))
		}
		if v := ArgString(args, "edge_type"); v != "" {
			cmdArgs = append(cmdArgs, "--edge_type", v)
		}
		if v := ArgString(args, "domain"); v != "" {
			cmdArgs = append(cmdArgs, "--domain", v)
		}
		if v := ArgInt(args, "limit", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--limit", fmt.Sprintf("%d", v))
		}

	case "graph_get_paths":
		if v := ArgInt(args, "src_node_id", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--src_node_id", fmt.Sprintf("%d", v))
		}
		if v := ArgInt(args, "dst_node_id", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--dst_node_id", fmt.Sprintf("%d", v))
		}
		if v := ArgInt(args, "max_depth", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--max_depth", fmt.Sprintf("%d", v))
		}
		if v := ArgString(args, "domain"); v != "" {
			cmdArgs = append(cmdArgs, "--domain", v)
		}

	case "graph_export":
		if v := ArgString(args, "format"); v != "" {
			cmdArgs = append(cmdArgs, "--format", v)
		}
		if v := ArgString(args, "domain"); v != "" {
			cmdArgs = append(cmdArgs, "--domain", v)
		}
		if v := ArgInt(args, "limit", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--limit", fmt.Sprintf("%d", v))
		}

	case "graph_add_rule":
		if v := ArgString(args, "rule_type"); v != "" {
			cmdArgs = append(cmdArgs, "--rule_type", v)
		}
		if v := ArgString(args, "domain"); v != "" {
			cmdArgs = append(cmdArgs, "--domain", v)
		}
		if v := ArgInt(args, "target_node_id", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--target_node_id", fmt.Sprintf("%d", v))
		}

	case "graph_add_snapshot":
		if v := ArgString(args, "snapshot_type"); v != "" {
			cmdArgs = append(cmdArgs, "--snapshot_type", v)
		}
		if v := ArgString(args, "content"); v != "" {
			cmdArgs = append(cmdArgs, "--content", v)
		}
		if v := ArgString(args, "domain"); v != "" {
			cmdArgs = append(cmdArgs, "--domain", v)
		}

	case "graph_get_snapshot":
		if v := ArgInt(args, "snapshot_id", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--snapshot_id", fmt.Sprintf("%d", v))
		}

	case "graph_migrate_codefix":
		if v := ArgString(args, "source_db"); v != "" {
			cmdArgs = append(cmdArgs, "--source_db", v)
		}

	case "graph_migrate_session":
		// session migration has no special args

	case "graph_stats", "graph_gc", "graph_trace":
		// no args needed

	default:
		// Generic: pass all args as --key value
		for k, v := range args {
			cmdArgs = append(cmdArgs, "--"+k, fmt.Sprintf("%v", v))
		}
	}

	out, err := t.m.run(ctx, cmdArgs...)
	if err != nil {
		return &ToolResult{Content: []string{fmt.Sprintf("graph error: %v", err)}, IsError: true}
	}

	// Validate JSON output
	var parsed map[string]any
	if jerr := json.Unmarshal([]byte(out), &parsed); jerr != nil {
		// Return raw output if not JSON
		return &ToolResult{Content: []string{out}}
	}

	// Check if the bridge returned an error
	if okVal, exists := parsed["ok"]; exists {
		if okNum, ok := okVal.(float64); ok && okNum == 0 {
			errMsg := "graph bridge returned error"
			if e, ok := parsed["error"].(map[string]any); ok {
				if desc, ok := e["desc"].(string); ok {
					errMsg = desc
				}
			}
			return &ToolResult{Content: []string{errMsg}, IsError: true}
		}
	}

	return &ToolResult{Content: []string{out}}
}
