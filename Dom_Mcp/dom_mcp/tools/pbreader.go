		
				package tools

// [@GHOST]{file_path="Dom_Mcp/dom_mcp/tools/pbreader.go"
// date="2026-07-04" author="Devin" session_id="bnd-laws"
// context="MCP exposure for PbReader — cascade_chat_* tools via Python subprocess bridge"}
// [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase Tuple3 Run dispatch"}
// [@FILEID]{id="pbreader.go" domain="mcp_tools" authority="PbReaderModule"}
// [@SUMMARY]{summary="MCP module that wraps pb_reader.py as subprocess. Exposes Windsurf Cascade .pb chat decryption, search, read, export-to-MySQL, verify, and clean as cascade_chat_* tools for MCP clients."}
// [@CLASS]{class="PbReaderModule" domain="mcp_tools" authority="single"}
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

// PbReaderModule wraps the pb_reader.py Python script as a subprocess.
// It exposes Windsurf Cascade .pb chat file operations as MCP cascade_chat_* tools.
type PbReaderModule struct {
	binary    string // path to python3
	script    string // path to pb_reader.py
	timeoutMs int
}

// NewPbReaderModule creates a PbReaderModule from config.
func NewPbReaderModule(pythonBinary, scriptPath string, timeoutMs int) *PbReaderModule {
	if pythonBinary == "" {
		pythonBinary = "python3"
	}
	if timeoutMs <= 0 {
		timeoutMs = 30000
	}
	return &PbReaderModule{binary: pythonBinary, script: scriptPath, timeoutMs: timeoutMs}
}

func (m *PbReaderModule) Name() string { return "cascade_chat" }

func (m *PbReaderModule) Tools() []Tool {
	return []Tool{
		&pbTool{name: "cascade_chat_scan", desc: "Scan ~/.codeium/windsurf/ for encrypted .pb Cascade chat files. Returns list of files with paths, categories (cascade/implicit/memories), and sizes.", m: m, required: nil},
		&pbTool{name: "cascade_chat_list", desc: "List all trajectories currently loaded in the in-RAM SQLite database.", m: m, required: nil},
		&pbTool{name: "cascade_chat_index", desc: "Build chat index mapping funny_name (UUID.pb filename) to decrypted_name (title from first user message) plus ALL details from checkpoints (conversation_title, user_intent, session_summary, code_change_summary, memory_summary, edited_files). Auto-loads all .pb files if RAM is empty. Optional query filters by title/file/trajectory_id.", m: m, required: nil, extraProps: map[string]map[string]any{
			"query": Prop("string", "Filter by title, file_name, or trajectory_id (LIKE match)."),
			"limit": Prop("integer", "Max results to return (0 = all)."),
		}},
		&pbTool{name: "cascade_chat_load", desc: "Decrypt and load one .pb Cascade chat file into RAM. Returns trajectory ID and step count.", m: m, required: []string{"file"}},
		&pbTool{name: "cascade_chat_load_all", desc: "Decrypt and load all .pb Cascade chat files found via scan into RAM.", m: m, required: nil},
		&pbTool{name: "cascade_chat_read", desc: "Read a .pb Cascade chat file as a conversation (user messages, assistant responses, commands, checkpoints). Auto-loads if not already in RAM.", m: m, required: []string{"file"}},
		&pbTool{name: "cascade_chat_search", desc: "Search loaded Cascade chat content by keyword. Searches user messages, assistant messages, and command output. Auto-loads all if nothing loaded.", m: m, required: []string{"query"}},
		&pbTool{name: "cascade_chat_search_sessions", desc: "Search MySQL cascade_chats for which chat sessions match keyword(s). Returns ranked sessions with weighted scores (first_prompt=5pts, round=4pts, user=3pts, assistant=2pts, command=1pt). Multi-word query = multiple keywords. No RAM load needed — queries MySQL directly.", m: m, required: []string{"query"}, extraProps: map[string]map[string]any{
			"limit":   Prop("integer", "Max sessions to return (default 20)."),
			"detail":  Prop("boolean", "Include snippet previews of top matches."),
		}},
		&pbTool{name: "cascade_chat_session_detail", desc: "Get full detail of a chat session by trajectory_id from MySQL. Returns trajectory info, all rounds with prompts, user messages, key assistant responses, commands run, files referenced, checkpoints. Everything the model needs to understand what a session was about.", m: m, required: []string{"trajectory_id"}, extraProps: map[string]map[string]any{
			"max_messages": Prop("integer", "Max messages per type (default 50)."),
		}},
		&pbTool{name: "cascade_chat_search_files", desc: "Search which chat sessions mentioned or created specific files. Searches command outputs, file_context messages, and assistant messages for file paths matching the query. Returns sessions ranked by mention count. No RAM load needed.", m: m, required: []string{"query"}, extraProps: map[string]map[string]any{
			"limit": Prop("integer", "Max sessions to return (default 20)."),
		}},
		&pbTool{name: "cascade_chat_export", desc: "Export a .pb Cascade chat file to markdown files in an output directory. One file per conversation round plus an index.", m: m, required: []string{"file", "outdir"}},
		&pbTool{name: "cascade_chat_stats", desc: "Show in-RAM SQLite database statistics (trajectory count, step count, message counts).", m: m, required: nil},
		&pbTool{name: "cascade_chat_export_db", desc: "Transfer all loaded Cascade chats from RAM SQLite to MySQL cascade_chats database. Uses prepared statements. Skips trajectories already in MySQL (dedup by trajectory_id). Run cascade_chat_load_all first.", m: m, required: nil},
		&pbTool{name: "cascade_chat_verify_db", desc: "Verify that all scanned .pb Cascade chat files are present in MySQL cascade_chats database. Returns verified count, missing count, and all_verified boolean.", m: m, required: nil},
		&pbTool{name: "cascade_chat_clean", desc: "Delete .pb Cascade chat files from disk AFTER verifying all are in MySQL. SAFETY: If ANY file is missing from DB, aborts. Requires confirm=true to actually delete. Without confirm, returns verification report and pending_confirmation status.", m: m, required: nil},
		&pbTool{name: "bcl_chat_compress", desc: "Compress a chat markdown file to BCL tokens (Stage 1). Extracts [@USER_SAYS] [@AI_SAYS] [@ERROR] [@FILE] [@COMMAND_RAN] [@FRUSTRATION_SIGNAL] [@QUESTION] [@TOPIC] tokens. Writes compressed .md file.", m: m, required: []string{"input"}, extraProps: map[string]map[string]any{
			"output": Prop("string", "Output BCL .md file path (default: <input>_BCL_stage1.md)."),
		}},
		&pbTool{name: "bcl_chat_dry_run", desc: "Extract BCL tokens from a chat markdown file without writing output. Returns token count, line count, and compression ratio preview.", m: m, required: []string{"input"}},
	}
}

// run executes pb_reader.py with given CLI args and returns stdout.
func (m *PbReaderModule) run(ctx context.Context, args ...string) (string, error) {
	if m.script == "" {
		return "", fmt.Errorf("pb_reader.py path not configured")
	}
	timeout := time.Duration(m.timeoutMs) * time.Millisecond
	cctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	cmdArgs := append([]string{m.script}, args...)
	cmd := exec.CommandContext(cctx, m.binary, cmdArgs...)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		stderrStr := strings.TrimSpace(stderr.String())
		if cctx.Err() == context.DeadlineExceeded {
			return "", fmt.Errorf("cascade_chat timed out after %dms", m.timeoutMs)
		}
		if stderrStr != "" {
			return "", fmt.Errorf("cascade_chat: %s: %v", stderrStr, err)
		}
		return "", fmt.Errorf("cascade_chat: %v", err)
	}
	return stdout.String(), nil
}

// pbTool is a generic tool that maps to a pb_reader.py CLI command.
type pbTool struct {
	name       string
	desc       string
	m          *PbReaderModule
	required   []string
	extraProps map[string]map[string]any
}

func (t *pbTool) Name() string        { return t.name }
func (t *pbTool) Description() string { return t.desc }

func (t *pbTool) InputSchema() map[string]any {
	props := map[string]map[string]any{
		"file":    Prop("string", "Path to a .pb Cascade chat file to load/read/export."),
		"query":   Prop("string", "Search query text."),
		"scope":   PropEnum("Search scope: all, user, assistant, or commands.", "all", "user", "assistant", "commands"),
		"outdir":  Prop("string", "Output directory for markdown export."),
		"step":    Prop("integer", "Show only a specific step index when reading."),
		"root":    Prop("string", "Custom Windsurf root directory (default: ~/.codeium/windsurf)."),
		"confirm": Prop("boolean", "Must be true to actually delete .pb files during clean. If false or omitted, returns verification report only."),
		"trajectory_id": Prop("string", "Trajectory ID (UUID) from search-sessions or search-files results."),
		"limit":   Prop("integer", "Max results to return (default 20)."),
		"detail":  Prop("boolean", "Include snippet previews of top matches."),
		"max_messages": Prop("integer", "Max messages per type (default 50)."),
	}
	for k, v := range t.extraProps {
		props[k] = v
	}
	return Schema(props, t.required)
}

func (t *pbTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	// Map tool name to CLI command (strip cascade_chat_ prefix, convert _ to -)
	command := strings.TrimPrefix(t.name, "cascade_chat_")
	command = strings.ReplaceAll(command, "_", "-")

	cmdArgs := []string{command}

	// Per-tool arg mapping
	switch t.name {
	case "cascade_chat_load":
		if v := ArgString(args, "file"); v != "" {
			cmdArgs = append(cmdArgs, v)
		} else {
			return NewErrorResult("cascade_chat_load requires 'file' parameter")
		}

	case "cascade_chat_read":
		if v := ArgString(args, "file"); v != "" {
			cmdArgs = append(cmdArgs, v)
		} else {
			return NewErrorResult("cascade_chat_read requires 'file' parameter")
		}
		if v := ArgInt(args, "step", -1); v >= 0 {
			cmdArgs = append(cmdArgs, "--step", fmt.Sprintf("%d", v))
		}

	case "cascade_chat_index":
		if v := ArgString(args, "query"); v != "" {
			cmdArgs = append(cmdArgs, v)
		}
		if v := ArgInt(args, "limit", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--limit", fmt.Sprintf("%d", v))
		}

	case "cascade_chat_search":
		if v := ArgString(args, "query"); v != "" {
			cmdArgs = append(cmdArgs, v)
		} else {
			return NewErrorResult("cascade_chat_search requires 'query' parameter")
		}
		if v := ArgString(args, "scope"); v != "" {
			cmdArgs = append(cmdArgs, "--scope", v)
		}

	case "cascade_chat_search_sessions":
		if v := ArgString(args, "query"); v != "" {
			cmdArgs = append(cmdArgs, v)
		} else {
			return NewErrorResult("cascade_chat_search_sessions requires 'query' parameter")
		}
		if v := ArgInt(args, "limit", 20); v != 20 {
			cmdArgs = append(cmdArgs, "--limit", fmt.Sprintf("%d", v))
		}
		if ArgBool(args, "detail") {
			cmdArgs = append(cmdArgs, "--detail")
		}

	case "cascade_chat_session_detail":
		if v := ArgString(args, "trajectory_id"); v != "" {
			cmdArgs = append(cmdArgs, v)
		} else {
			return NewErrorResult("cascade_chat_session_detail requires 'trajectory_id' parameter")
		}
		if v := ArgInt(args, "max_messages", 50); v != 50 {
			cmdArgs = append(cmdArgs, "--max-messages", fmt.Sprintf("%d", v))
		}

	case "cascade_chat_search_files":
		if v := ArgString(args, "query"); v != "" {
			cmdArgs = append(cmdArgs, v)
		} else {
			return NewErrorResult("cascade_chat_search_files requires 'query' parameter")
		}
		if v := ArgInt(args, "limit", 20); v != 20 {
			cmdArgs = append(cmdArgs, "--limit", fmt.Sprintf("%d", v))
		}

	case "cascade_chat_export":
		if v := ArgString(args, "file"); v != "" {
			cmdArgs = append(cmdArgs, v)
		} else {
			return NewErrorResult("cascade_chat_export requires 'file' parameter")
		}
		if v := ArgString(args, "outdir"); v != "" {
			cmdArgs = append(cmdArgs, v)
		} else {
			return NewErrorResult("cascade_chat_export requires 'outdir' parameter")
		}

	case "cascade_chat_clean":
		if ArgBool(args, "confirm") {
			cmdArgs = append(cmdArgs, "--confirm")
		}

	case "bcl_chat_compress":
		if v := ArgString(args, "input"); v != "" {
			cmdArgs = append(cmdArgs, v)
		} else {
			return NewErrorResult("bcl_chat_compress requires 'input' parameter")
		}
		if v := ArgString(args, "output"); v != "" {
			cmdArgs = append(cmdArgs, v)
		}

	case "bcl_chat_dry_run":
		if v := ArgString(args, "input"); v != "" {
			cmdArgs = append(cmdArgs, v)
		} else {
			return NewErrorResult("bcl_chat_dry_run requires 'input' parameter")
		}
	}

	out, err := t.m.run(ctx, cmdArgs...)
	if err != nil {
		return NewErrorResult(fmt.Sprintf("cascade_chat error: %v", err))
	}

	// For scan and list, try to parse stdout as JSON (file paths or trajectory data)
	// pb_reader.py outputs paths to stdout, logs to stderr
	if t.name == "cascade_chat_scan" || t.name == "cascade_chat_list" || t.name == "cascade_chat_stats" || t.name == "cascade_chat_index" {
		lines := strings.TrimSpace(out)
		if lines == "" {
			return NewTextResult("No output. Check stderr for details.")
		}
		// Try to parse as JSON array
		var arr []any
		if err := json.Unmarshal([]byte(lines), &arr); err == nil {
			return JSONResult(arr)
		}
		return NewTextResult(lines)
	}

	// For export_db, verify_db, clean, search-sessions, session-detail, search-files — output is JSON to stdout
	if t.name == "cascade_chat_export_db" || t.name == "cascade_chat_verify_db" || t.name == "cascade_chat_clean" ||
		t.name == "cascade_chat_search_sessions" || t.name == "cascade_chat_session_detail" || t.name == "cascade_chat_search_files" {
		lines := strings.TrimSpace(out)
		if lines == "" {
			return NewTextResult("No output. Check stderr for details.")
		}
		// Try to parse as JSON object
		var obj map[string]any
		if err := json.Unmarshal([]byte(lines), &obj); err == nil {
			return JSONResult(obj)
		}
		return NewTextResult(lines)
	}

	// For read, search, export — return the text output
	return NewTextResult(strings.TrimSpace(out))
}
