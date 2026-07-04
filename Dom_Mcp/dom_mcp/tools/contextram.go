package tools

import (
	"bytes"
	"context"
	"fmt"
	"os/exec"
	"strings"
	"time"
)

// ContextRAMModule wraps the Swift ctx binary as a subprocess.
type ContextRAMModule struct {
	binary    string
	timeoutMs int
}

// NewContextRAMModule creates a contextram module from config.
func NewContextRAMModule(binary string, timeoutMs int) *ContextRAMModule {
	if timeoutMs <= 0 {
		timeoutMs = 10000
	}
	return &ContextRAMModule{binary: binary, timeoutMs: timeoutMs}
}

func (m *ContextRAMModule) Name() string { return "contextram" }

func (m *ContextRAMModule) Tools() []Tool {
	return []Tool{
		&ctxTool{name: "ctx_put", desc: "Store a context node with a type and content.", m: m, required: []string{"type", "content"}},
		&ctxTool{name: "ctx_get", desc: "Retrieve a context node by its ID.", m: m, required: []string{"id"}},
		&ctxTool{name: "ctx_update", desc: "Update an existing context node.", m: m, required: []string{"id"}},
		&ctxTool{name: "ctx_delete", desc: "Delete a context node by ID.", m: m, required: []string{"id"}},
		&ctxTool{name: "ctx_list", desc: "List context nodes, optionally filtered by type and status.", m: m, required: nil},
		&ctxTool{name: "ctx_query", desc: "Full-text query of context nodes.", m: m, required: []string{"query"}},
		&ctxTool{name: "ctx_link", desc: "Create a link between two context nodes.", m: m, required: []string{"from", "to"}},
		&ctxTool{name: "ctx_promote", desc: "Promote a context node to a higher status.", m: m, required: []string{"id"}},
		&ctxTool{name: "ctx_demote", desc: "Demote a context node to a lower status.", m: m, required: []string{"id"}},
		&ctxTool{name: "ctx_lock", desc: "Lock a context node from modification.", m: m, required: []string{"id"}},
		&ctxTool{name: "ctx_unlock", desc: "Unlock a locked context node.", m: m, required: []string{"id"}},
		&ctxTool{name: "ctx_stats", desc: "Get statistics about the context store.", m: m, required: nil},
		&ctxTool{name: "ctx_events", desc: "Get events for context nodes.", m: m, required: nil},
		&ctxTool{name: "ctx_assemble", desc: "Assemble context for a query into a compact output.", m: m, required: []string{"query"}},
		&ctxTool{name: "ctx_snapshot", desc: "Create a snapshot of the context store.", m: m, required: nil},
		&ctxTool{name: "ctx_restore", desc: "Restore context store from a snapshot.", m: m, required: []string{"snapshot"}},
		&ctxTool{name: "ctx_recent", desc: "Get recent context nodes.", m: m, required: nil},
		&ctxTool{name: "ctx_clear_expired", desc: "Clear expired context nodes.", m: m, required: nil},
		&ctxTool{name: "ctx_path", desc: "Get the path of a context node in the hierarchy.", m: m, required: []string{"id"}},
		&ctxTool{name: "ctx_ingest", desc: "Ingest a file into the context store.", m: m, required: []string{"file"}},
		&ctxTool{name: "ctx_ingest_chat", desc: "Ingest chat data into the context store.", m: m, required: []string{"file"}},
		&ctxTool{name: "ctx_semantic", desc: "Semantic search of context nodes.", m: m, required: []string{"query"}},
		&ctxTool{name: "ctx_embed", desc: "Generate embeddings for context nodes.", m: m, required: []string{"id"}},
		&ctxTool{name: "ctx_embed_stats", desc: "Get embedding statistics.", m: m, required: nil},
		&ctxTool{name: "ctx_auto", desc: "Automatic context management.", m: m, required: nil},
		&ctxTool{name: "ctx_suggest", desc: "Get context suggestions.", m: m, required: nil},
		&ctxTool{name: "ctx_config", desc: "Get or set context store configuration.", m: m, required: nil},
	}
}

// run executes the ctx binary with given args and returns stdout.
func (m *ContextRAMModule) run(ctx context.Context, args ...string) (string, error) {
	if m.binary == "" {
		return "", fmt.Errorf("ctx binary path not configured")
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
			return "", fmt.Errorf("ctx timed out after %dms", m.timeoutMs)
		}
		if stderrStr != "" {
			return "", fmt.Errorf("ctx: %s: %v", stderrStr, err)
		}
		return "", fmt.Errorf("ctx: %v", err)
	}
	return stdout.String(), nil
}

// ctxTool is a generic tool that maps to a ctx subcommand.
type ctxTool struct {
	name     string
	desc     string
	m        *ContextRAMModule
	required []string
}

func (t *ctxTool) Name() string        { return t.name }
func (t *ctxTool) Description() string { return t.desc }

func (t *ctxTool) InputSchema() map[string]any {
	props := map[string]map[string]any{
		"type":       Prop("string", "Node type (e.g. note, task, reference, fact)."),
		"content":    Prop("string", "Node content text (mapped to --value)."),
		"authority":  Prop("string", "Authority source (e.g. human, model, cli)."),
		"tags":       Prop("string", "Comma-separated tags."),
		"id":         Prop("string", "Node ID (UUID)."),
		"value":      Prop("string", "New value for update."),
		"query":      Prop("string", "Search query text."),
		"from":       Prop("string", "Source node ID for linking."),
		"to":         Prop("string", "Target node ID for linking."),
		"rel":        Prop("string", "Relationship type for linking (e.g. supports, refutes)."),
		"status":     Prop("string", "Filter by node status (e.g. active, resolved)."),
		"tag":        Prop("string", "Filter by single tag."),
		"limit":      Prop("integer", "Maximum results to return."),
		"file":       Prop("string", "File or folder path to ingest."),
		"snapshot":   Prop("string", "Snapshot path to restore."),
		"task":       Prop("string", "Task description for auto/suggest."),
		"extensions": Prop("string", "Comma-separated file extensions for ingest."),
		"dry_run":    Prop("boolean", "Dry run for ingest-chat."),
	}
	return Schema(props, t.required)
}

func (t *ctxTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	// Map tool name to ctx subcommand (handle underscore→hyphen conversion).
	sub := strings.TrimPrefix(t.name, "ctx_")
	switch sub {
	case "clear_expired":
		sub = "clear-expired"
	case "embed_stats":
		sub = "embed-stats"
	case "ingest_chat":
		sub = "ingest-chat"
	}

	cmdArgs := []string{sub}

	// Per-tool arg mapping: some tools need positional args, some need flags.
	switch t.name {
	case "ctx_get", "ctx_delete", "ctx_promote", "ctx_demote", "ctx_lock", "ctx_unlock":
		// These take a positional NODE_ID
		if id := ArgString(args, "id"); id != "" {
			cmdArgs = append(cmdArgs, id)
		}

	case "ctx_put":
		// ctx put --type X --value Y --authority Z --tags T
		if v := ArgString(args, "type"); v != "" {
			cmdArgs = append(cmdArgs, "--type", v)
		}
		if v := ArgString(args, "content"); v != "" {
			cmdArgs = append(cmdArgs, "--value", v) // content → --value
		}
		if v := ArgString(args, "authority"); v != "" {
			cmdArgs = append(cmdArgs, "--authority", v)
		}
		if v := ArgString(args, "tags"); v != "" {
			cmdArgs = append(cmdArgs, "--tags", v)
		}

	case "ctx_update":
		// ctx update NODE_ID --value X --status Y
		if id := ArgString(args, "id"); id != "" {
			cmdArgs = append(cmdArgs, id)
		}
		if v := ArgString(args, "value"); v != "" {
			cmdArgs = append(cmdArgs, "--value", v)
		}
		if v := ArgString(args, "content"); v != "" {
			cmdArgs = append(cmdArgs, "--value", v) // also accept content
		}
		if v := ArgString(args, "status"); v != "" {
			cmdArgs = append(cmdArgs, "--status", v)
		}

	case "ctx_list":
		// ctx list [--type X] [--status Y] [--tag Z]
		if v := ArgString(args, "type"); v != "" {
			cmdArgs = append(cmdArgs, "--type", v)
		}
		if v := ArgString(args, "status"); v != "" {
			cmdArgs = append(cmdArgs, "--status", v)
		}
		if v := ArgString(args, "tag"); v != "" {
			cmdArgs = append(cmdArgs, "--tag", v)
		}
		if v := ArgInt(args, "limit", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--limit", fmt.Sprintf("%d", v))
		}

	case "ctx_query":
		// ctx query "search text" [--limit N]
		if v := ArgString(args, "query"); v != "" {
			cmdArgs = append(cmdArgs, v) // positional
		}
		if v := ArgInt(args, "limit", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--limit", fmt.Sprintf("%d", v))
		}

	case "ctx_recent":
		if v := ArgInt(args, "limit", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--limit", fmt.Sprintf("%d", v))
		}

	case "ctx_link":
		// ctx link NODE_ID REL TARGET_ID (all positional)
		if v := ArgString(args, "from"); v != "" {
			cmdArgs = append(cmdArgs, v)
		}
		if v := ArgString(args, "rel"); v != "" {
			cmdArgs = append(cmdArgs, v)
		} else {
			cmdArgs = append(cmdArgs, "supports") // default relationship
		}
		if v := ArgString(args, "to"); v != "" {
			cmdArgs = append(cmdArgs, v)
		}

	case "ctx_assemble":
		if v := ArgString(args, "query"); v != "" {
			cmdArgs = append(cmdArgs, "--query", v)
		}
		if v := ArgInt(args, "limit", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--limit", fmt.Sprintf("%d", v))
		}

	case "ctx_events":
		if v := ArgInt(args, "limit", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--limit", fmt.Sprintf("%d", v))
		}

	case "ctx_snapshot":
		// ctx snapshot [path] — optional positional
		if v := ArgString(args, "snapshot"); v != "" {
			cmdArgs = append(cmdArgs, v)
		}

	case "ctx_restore":
		// ctx restore path — positional
		if v := ArgString(args, "snapshot"); v != "" {
			cmdArgs = append(cmdArgs, v)
		}

	case "ctx_path":
		// ctx path — no args (returns store path)

	case "ctx_ingest":
		// ctx ingest <folder> [--tags T] [--extensions E] ...
		if v := ArgString(args, "file"); v != "" {
			cmdArgs = append(cmdArgs, v) // positional folder
		}
		if v := ArgString(args, "tags"); v != "" {
			cmdArgs = append(cmdArgs, "--tags", v)
		}
		if v := ArgString(args, "extensions"); v != "" {
			cmdArgs = append(cmdArgs, "--extensions", v)
		}

	case "ctx_ingest_chat":
		// ctx ingest-chat <file.md> [--tags T] [--min-chars N] [--dry-run]
		if v := ArgString(args, "file"); v != "" {
			cmdArgs = append(cmdArgs, v) // positional file
		}
		if v := ArgString(args, "tags"); v != "" {
			cmdArgs = append(cmdArgs, "--tags", v)
		}
		if v, ok := args["dry_run"]; ok {
			if b, _ := v.(bool); b {
				cmdArgs = append(cmdArgs, "--dry-run")
			}
		}

	case "ctx_semantic":
		// ctx semantic "query text" [--limit N] [--tag T]
		if v := ArgString(args, "query"); v != "" {
			cmdArgs = append(cmdArgs, v) // positional
		}
		if v := ArgInt(args, "limit", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--limit", fmt.Sprintf("%d", v))
		}
		if v := ArgString(args, "tag"); v != "" {
			cmdArgs = append(cmdArgs, "--tag", v)
		}

	case "ctx_embed":
		// ctx embed "query text" [--limit N] [--tag T] [--type T] [--dimensions D] [--json]
		if v := ArgString(args, "query"); v != "" {
			cmdArgs = append(cmdArgs, v) // positional
		}
		if v := ArgInt(args, "limit", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--limit", fmt.Sprintf("%d", v))
		}
		if v := ArgString(args, "tag"); v != "" {
			cmdArgs = append(cmdArgs, "--tag", v)
		}
		if v := ArgString(args, "type"); v != "" {
			cmdArgs = append(cmdArgs, "--type", v)
		}

	case "ctx_embed_stats":
		// ctx embed-stats [--tag T] [--type T]
		if v := ArgString(args, "tag"); v != "" {
			cmdArgs = append(cmdArgs, "--tag", v)
		}
		if v := ArgString(args, "type"); v != "" {
			cmdArgs = append(cmdArgs, "--type", v)
		}

	case "ctx_auto":
		// ctx auto [--task "desc"] [--file path] [--limit N]
		if v := ArgString(args, "task"); v != "" {
			cmdArgs = append(cmdArgs, "--task", v)
		}
		if v := ArgString(args, "file"); v != "" {
			cmdArgs = append(cmdArgs, "--file", v)
		}
		if v := ArgInt(args, "limit", 0); v > 0 {
			cmdArgs = append(cmdArgs, "--limit", fmt.Sprintf("%d", v))
		}

	case "ctx_suggest":
		// ctx suggest [--task "desc"] [--file path]
		if v := ArgString(args, "task"); v != "" {
			cmdArgs = append(cmdArgs, "--task", v)
		}
		if v := ArgString(args, "file"); v != "" {
			cmdArgs = append(cmdArgs, "--file", v)
		}

	case "ctx_config":
		// ctx config [--init] [--set KEY --value VAL]
		// Pass through any args as flags
		for _, key := range []string{"init", "set", "value", "embedding-provider", "coreml-model", "sqlite-path", "sqlite-table", "mysql-database", "mysql-host", "mysql-user"} {
			if v, ok := args[key]; ok {
				switch val := v.(type) {
				case string:
					if val != "" {
						cmdArgs = append(cmdArgs, "--"+key, val)
					}
				case bool:
					if val {
						cmdArgs = append(cmdArgs, "--"+key)
					}
				}
			}
		}

	default:
		// Generic fallback: send all args as --key value flags
		for _, key := range []string{"type", "content", "id", "query", "from", "to", "rel", "status", "limit", "file", "snapshot"} {
			if v, ok := args[key]; ok {
				switch val := v.(type) {
				case string:
					if val != "" {
						cmdArgs = append(cmdArgs, "--"+key, val)
					}
				case float64:
					cmdArgs = append(cmdArgs, "--"+key, fmt.Sprintf("%d", int(val)))
				}
			}
		}
	}

	out, err := t.m.run(ctx, cmdArgs...)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(out)
}
