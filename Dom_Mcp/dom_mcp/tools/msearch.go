package tools

import (
	"bytes"
	"context"
	"fmt"
	"os/exec"
	"strings"
	"time"
)

// MsearchModule wraps the C msearch binary as a subprocess.
type MsearchModule struct {
	binary    string
	timeoutMs int
}

// NewMsearchModule creates a msearch module from config.
func NewMsearchModule(binary string, timeoutMs int) *MsearchModule {
	if timeoutMs <= 0 {
		timeoutMs = 30000
	}
	return &MsearchModule{binary: binary, timeoutMs: timeoutMs}
}

func (m *MsearchModule) Name() string { return "msearch" }

func (m *MsearchModule) Tools() []Tool {
	return []Tool{
		&msearchTool{m: m},
	}
}

// run executes the msearch binary with given args and returns stdout.
func (m *MsearchModule) run(ctx context.Context, args ...string) (string, error) {
	if m.binary == "" {
		return "", fmt.Errorf("msearch binary path not configured")
	}
	timeout := time.Duration(m.timeoutMs) * time.Millisecond
	cctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	cmd := exec.CommandContext(cctx, m.binary, args...)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		stderrStr := strings.TrimSpace(stderr.String())
		if cctx.Err() == context.DeadlineExceeded {
			return "", fmt.Errorf("msearch timed out after %dms", m.timeoutMs)
		}
		if stderrStr != "" {
			return "", fmt.Errorf("msearch: %s: %v", stderrStr, err)
		}
		return "", fmt.Errorf("msearch: %v", err)
	}
	return stdout.String(), nil
}

// --- msearch ---

type msearchTool struct{ m *MsearchModule }

func (t *msearchTool) Name() string { return "msearch" }
func (t *msearchTool) Description() string {
	return "Search the local knowledge base (MySQL + SQLite, 215K+ messages). Returns matching messages with surrounding context. Supports --json, --limit, --table, --db, --type, --mode, --smart, --context-reconstruct flags."
}
func (t *msearchTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"query":   Prop("string", "Search query — what to look for in the knowledge base."),
		"limit":   Prop("integer", "Max rows per table (default 50)."),
		"table":   Prop("string", "Filter tables by name substring (--table)."),
		"db":      Prop("string", "Database name (default: vb_shared)."),
		"type":    Prop("string", "Semantic type filter: token_table, code_table, data_table, meta_table."),
		"mode":    Prop("string", "Match mode: magnetic (default), exact, prefix, regex."),
		"json":    Prop("boolean", "Output as JSON for programmatic parsing."),
		"smart":   Prop("boolean", "Consolidated 10-section semantic object (1 query, all info)."),
		"status":  Prop("string", "Filter by status."),
		"context": Prop("string", "Context text for relevance ranking."),
	}, []string{"query"})
}
func (t *msearchTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	query := ArgString(args, "query")
	if query == "" {
		return NewErrorResult("query is required")
	}

	// msearch takes: <keyword> [options] — NO subcommand
	cmdArgs := []string{query}

	if v := ArgInt(args, "limit", 0); v > 0 {
		cmdArgs = append(cmdArgs, "--limit", fmt.Sprintf("%d", v))
	}
	if v := ArgString(args, "table"); v != "" {
		cmdArgs = append(cmdArgs, "--table", v)
	}
	if v := ArgString(args, "db"); v != "" {
		cmdArgs = append(cmdArgs, "--db", v)
	}
	if v := ArgString(args, "type"); v != "" {
		cmdArgs = append(cmdArgs, "--type", v)
	}
	if v := ArgString(args, "mode"); v != "" {
		cmdArgs = append(cmdArgs, "--mode", v)
	}
	if v, ok := args["json"].(bool); ok && v {
		cmdArgs = append(cmdArgs, "--json")
	}
	if v, ok := args["smart"].(bool); ok && v {
		cmdArgs = append(cmdArgs, "--smart")
	}
	if v := ArgString(args, "status"); v != "" {
		cmdArgs = append(cmdArgs, "--status", v)
	}
	if v := ArgString(args, "context"); v != "" {
		cmdArgs = append(cmdArgs, "--context", v)
	}

	out, err := t.m.run(ctx, cmdArgs...)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(out)
}
