package tools

// [@GHOST]{file_path="Dom_Mcp/dom_mcp/tools/supersearch.go"
// date="2026-07-04" author="Devin" session_id="bnd-laws"
// context="MCP exposure for super_search.py — multi-word semantic proximity search via Python subprocess bridge"}
// [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase Tuple3 Run dispatch"}
// [@FILEID]{id="supersearch.go" domain="mcp_tools" authority="SuperSearchModule"}
// [@SUMMARY]{summary="MCP module that wraps super_search.py as subprocess. Exposes msearch_super tool for multi-word semantic proximity search across chat messages, knowledge base, learned rules, and code. Scores by coverage, proximity, and TF-IDF. Returns ranked results with snippets."}
// [@CLASS]{class="SuperSearchModule" domain="mcp_tools" authority="single"}
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

// SuperSearchModule wraps the super_search.py Python script as a subprocess.
// It exposes the msearch_super tool for multi-word semantic proximity search.
type SuperSearchModule struct {
	binary    string // path to python3
	script    string // path to super_search.py
	timeoutMs int
}

// NewSuperSearchModule creates a SuperSearchModule from config.
func NewSuperSearchModule(pythonPath, scriptPath string, timeoutMs int) *SuperSearchModule {
	if pythonPath == "" {
		pythonPath = "python3"
	}
	if timeoutMs <= 0 {
		timeoutMs = 30000
	}
	return &SuperSearchModule{binary: pythonPath, script: scriptPath, timeoutMs: timeoutMs}
}

func (m *SuperSearchModule) Name() string { return "supersearch" }

func (m *SuperSearchModule) Tools() []Tool {
	return []Tool{
		&superSearchTool{m: m},
	}
}

// run executes super_search.py with a JSON payload on stdin and returns stdout.
func (m *SuperSearchModule) run(ctx context.Context, payload map[string]any) (string, error) {
	if m.script == "" {
		return "", fmt.Errorf("super_search.py path not configured")
	}
	timeout := time.Duration(m.timeoutMs) * time.Millisecond
	cctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	cmd := exec.CommandContext(cctx, m.binary, m.script)

	// Build JSON stdin payload
	stdinBytes, err := json.Marshal(payload)
	if err != nil {
		return "", fmt.Errorf("msearch_super: failed to marshal stdin payload: %v", err)
	}
	cmd.Stdin = bytes.NewReader(stdinBytes)

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		stderrStr := strings.TrimSpace(stderr.String())
		if cctx.Err() == context.DeadlineExceeded {
			return "", fmt.Errorf("msearch_super timed out after %dms", m.timeoutMs)
		}
		if stderrStr != "" {
			return "", fmt.Errorf("msearch_super: %s: %v", stderrStr, err)
		}
		return "", fmt.Errorf("msearch_super: %v", err)
	}
	return stdout.String(), nil
}

// superSearchTool implements the msearch_super tool.
type superSearchTool struct {
	m *SuperSearchModule
}

func (t *superSearchTool) Name() string { return "msearch_super" }

func (t *superSearchTool) Description() string {
	return "Multi-word semantic proximity search. Accepts comma-separated words (e.g. 'kokoro,voice,pipeline'). Searches across chat messages, knowledge base, learned rules, and code. Scores by coverage (how many words match), proximity (how close words are), and TF-IDF (how rare the words are). Returns ranked results with snippets."
}

func (t *superSearchTool) InputSchema() map[string]any {
	props := map[string]map[string]any{
		"query":            Prop("string", "Comma-separated search words, e.g. 'kokoro,voice,pipeline'."),
		"limit":            Prop("integer", "Max results to return (default 20)."),
		"scope":            PropEnum("Search scope.", "all", "chats", "rules", "problems", "answers", "code"),
		"min_coverage":     Prop("number", "Minimum fraction of query words that must match (0.0-1.0, default 0.3)."),
		"proximity_window": Prop("integer", "Max distance in characters between matched words for proximity bonus (default 200)."),
	}
	return Schema(props, []string{"query"})
}

func (t *superSearchTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	query := ArgString(args, "query")
	if query == "" {
		return NewErrorResult("msearch_super requires 'query' parameter")
	}

	limit := ArgInt(args, "limit", 20)
	scope := ArgString(args, "scope")
	if scope == "" {
		scope = "all"
	}
	minCoverage := ArgFloat(args, "min_coverage")
	if minCoverage == 0 {
		minCoverage = 0.3
	}
	proximityWindow := ArgInt(args, "proximity_window", 200)

	payload := map[string]any{
		"query":            query,
		"limit":            limit,
		"scope":            scope,
		"min_coverage":     minCoverage,
		"proximity_window": proximityWindow,
	}

	out, err := t.m.run(ctx, payload)
	if err != nil {
		return NewErrorResult(fmt.Sprintf("msearch_super error: %v", err))
	}

	lines := strings.TrimSpace(out)
	if lines == "" {
		return NewTextResult("No output. Check stderr for details.")
	}

	// Try to parse stdout as JSON (object or array)
	var obj map[string]any
	if err := json.Unmarshal([]byte(lines), &obj); err == nil {
		return JSONResult(obj)
	}
	var arr []any
	if err := json.Unmarshal([]byte(lines), &arr); err == nil {
		return JSONResult(arr)
	}

	// Fallback: return raw text
	return NewTextResult(lines)
}
