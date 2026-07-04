// Command contextram-go-mcp is a thin Go MCP shim that wraps the Swift `ctx`
// binary. It exposes the same 27 tools as the Node.js ContextRAM MCP wrapper
// (mcp-server/index.js) but spawns the Swift binary per call instead of
// keeping a Node.js process resident, dropping idle RAM from ~50 MB to ~5 MB.
//
// This file is a pure protocol adapter: it maps MCP tool names + arguments to
// `ctx` subcommand argv, runs the binary via os/exec, and returns stdout as
// the tool result. No ContextRAM logic is reimplemented here.
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"os"
	"os/exec"
	"strings"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

// defaultCtxBinary is the default path to the Swift ctx binary.
// The release build is preferred; the Node.js wrapper historically used debug.
const defaultCtxBinary = "/Users/wws/contestsystem/ContextRAMSwift/.build/release/ctx"

// toolDef describes one MCP tool: its name, description, JSON schema, and the
// function that converts MCP arguments into a `ctx` argv.
type toolDef struct {
	name        string
	description string
	// schema is the raw JSON Schema object, matching the Node.js wrapper exactly.
	schema string
	// toArgs maps the decoded arguments map to a `ctx` subcommand argv.
	toArgs func(args map[string]any) []string
}

// str returns args[key] as a string, or "" if absent/not a string.
func str(args map[string]any, key string) string {
	v, ok := args[key]
	if !ok {
		return ""
	}
	s, _ := v.(string)
	return s
}

// num returns args[key] as a float64, ok=false if absent/not a number.
func num(args map[string]any, key string) (float64, bool) {
	v, ok := args[key]
	if !ok {
		return 0, false
	}
	f, ok := v.(float64)
	return f, ok
}

// numStr returns args[key] formatted as a string if present, else "".
func numStr(args map[string]any, key string) string {
	f, ok := num(args, key)
	if !ok {
		return ""
	}
	return fmt.Sprintf("%v", f)
}

// boolFlag returns true if args[key] is truthy.
func boolFlag(args map[string]any, key string) bool {
	v, ok := args[key]
	if !ok {
		return false
	}
	b, _ := v.(bool)
	return b
}

// pushIf appends "--flag value" only when value is non-empty.
func pushIf(out []string, flag, value string) []string {
	if value != "" {
		return append(out, flag, value)
	}
	return out
}

// allTools returns the 27 tool definitions matching the Node.js wrapper.
func allTools() []toolDef {
	return []toolDef{
		{
			name:        "ctx_put",
			description: "Create a new context node (goal, task, fact, memory, etc.)",
			schema: `{"type":"object","properties":{
"type":{"type":"string","enum":["goal","task","problem","question","fact","rule","memory","event","observation","hypothesis","decision","file","code","error","test","result","conversation","plan","dependency","resource"],"description":"Node type"},
"value":{"type":"string","description":"Node content/value"},
"status":{"type":"string","enum":["active","pending","resolved","failed","archived","locked","expired","superseded","unknown"],"description":"Optional status"},
"authority":{"type":"string","enum":["system","truthDB","human","model","externalSource","consensus"],"description":"Optional authority level"},
"score":{"type":"number","description":"Optional relevance score (default 1)"},
"tags":{"type":"string","description":"Comma-separated tags"},
"source":{"type":"string","description":"Optional source label"}
},"required":["type","value"]}`,
			toArgs: func(a map[string]any) []string {
				out := []string{"put", "--type", str(a, "type"), "--value", str(a, "value")}
				out = pushIf(out, "--status", str(a, "status"))
				out = pushIf(out, "--authority", str(a, "authority"))
				if s := numStr(a, "score"); s != "" {
					out = append(out, "--score", s)
				}
				out = pushIf(out, "--tags", str(a, "tags"))
				out = pushIf(out, "--source", str(a, "source"))
				return out
			},
		},
		{
			name:        "ctx_config",
			description: "Show or update ContextRAM config, including CoreML embedding and SQLite/MySQL source metadata",
			schema: `{"type":"object","properties":{
"init":{"type":"boolean","description":"Reset/write default config"},
"set":{"type":"string","description":"Config key to set"},
"value":{"type":"string","description":"Value for --set"},
"store_path":{"type":"string","description":"JSON context store path"},
"embedding_provider":{"type":"string","enum":["local","coreml"],"description":"Embedding provider"},
"coreml_model":{"type":"string","description":"CoreML model path"},
"coreml_dir":{"type":"string","description":"Directory to discover CoreML models"},
"sqlite_path":{"type":"string","description":"SQLite source path metadata"},
"sqlite_table":{"type":"string","description":"SQLite table name"},
"mysql_database":{"type":"string","description":"MySQL database name metadata"},
"mysql_host":{"type":"string","description":"MySQL host"},
"mysql_user":{"type":"string","description":"MySQL user"},
"mysql_table":{"type":"string","description":"MySQL table name"},
"mysql_text_column":{"type":"string","description":"MySQL text/content column"},
"mysql_password_env":{"type":"string","description":"Environment variable containing MySQL password"}
}}`,
			toArgs: func(a map[string]any) []string {
				out := []string{"config"}
				if boolFlag(a, "init") {
					out = append(out, "--init")
				}
				out = pushIf(out, "--set", str(a, "set"))
				out = pushIf(out, "--value", str(a, "value"))
				out = pushIf(out, "--store-path", str(a, "store_path"))
				out = pushIf(out, "--embedding-provider", str(a, "embedding_provider"))
				out = pushIf(out, "--coreml-model", str(a, "coreml_model"))
				out = pushIf(out, "--coreml-dir", str(a, "coreml_dir"))
				out = pushIf(out, "--sqlite-path", str(a, "sqlite_path"))
				out = pushIf(out, "--sqlite-table", str(a, "sqlite_table"))
				out = pushIf(out, "--mysql-database", str(a, "mysql_database"))
				out = pushIf(out, "--mysql-host", str(a, "mysql_host"))
				out = pushIf(out, "--mysql-user", str(a, "mysql_user"))
				out = pushIf(out, "--mysql-table", str(a, "mysql_table"))
				out = pushIf(out, "--mysql-text-column", str(a, "mysql_text_column"))
				out = pushIf(out, "--mysql-password-env", str(a, "mysql_password_env"))
				return out
			},
		},
		{
			name:        "ctx_get",
			description: "Retrieve a context node by its ID",
			schema:      `{"type":"object","properties":{"id":{"type":"string","description":"Node ID"}},"required":["id"]}`,
			toArgs: func(a map[string]any) []string {
				return []string{"get", str(a, "id")}
			},
		},
		{
			name:        "ctx_update",
			description: "Update an existing context node",
			schema: `{"type":"object","properties":{
"id":{"type":"string","description":"Node ID"},
"value":{"type":"string","description":"New value/content"},
"status":{"type":"string","enum":["active","pending","resolved","failed","archived","locked","expired","superseded","unknown"],"description":"New status"},
"authority":{"type":"string","enum":["system","truthDB","human","model","externalSource","consensus"],"description":"New authority"},
"score":{"type":"number","description":"New score"},
"tags":{"type":"string","description":"Comma-separated tags"},
"source":{"type":"string","description":"New source label"}
},"required":["id"]}`,
			toArgs: func(a map[string]any) []string {
				out := []string{"update", str(a, "id")}
				out = pushIf(out, "--value", str(a, "value"))
				out = pushIf(out, "--status", str(a, "status"))
				out = pushIf(out, "--authority", str(a, "authority"))
				if s := numStr(a, "score"); s != "" {
					out = append(out, "--score", s)
				}
				out = pushIf(out, "--tags", str(a, "tags"))
				out = pushIf(out, "--source", str(a, "source"))
				return out
			},
		},
		{
			name:        "ctx_delete",
			description: "Delete a context node by ID",
			schema:      `{"type":"object","properties":{"id":{"type":"string","description":"Node ID"}},"required":["id"]}`,
			toArgs: func(a map[string]any) []string {
				return []string{"delete", str(a, "id")}
			},
		},
		{
			name:        "ctx_list",
			description: "List context nodes with optional filters",
			schema:      `{"type":"object","properties":{"type":{"type":"string","description":"Filter by node type"},"status":{"type":"string","description":"Filter by status"},"tag":{"type":"string","description":"Filter by tag"}}}`,
			toArgs: func(a map[string]any) []string {
				out := []string{"list"}
				out = pushIf(out, "--type", str(a, "type"))
				out = pushIf(out, "--status", str(a, "status"))
				out = pushIf(out, "--tag", str(a, "tag"))
				return out
			},
		},
		{
			name:        "ctx_query",
			description: "Search context nodes by text",
			schema:      `{"type":"object","properties":{"text":{"type":"string","description":"Search text"},"limit":{"type":"number","description":"Max results (default 10)"}},"required":["text"]}`,
			toArgs: func(a map[string]any) []string {
				out := []string{"query", str(a, "text")}
				out = pushIf(out, "--limit", numStr(a, "limit"))
				return out
			},
		},
		{
			name:        "ctx_link",
			description: "Link two context nodes with a relationship",
			schema: `{"type":"object","properties":{
"id":{"type":"string","description":"Source node ID"},
"relationship":{"type":"string","enum":["dependsOn","supports","contradicts","createdBy","references","resolves","causedBy","partOf","relatedTo"],"description":"Relationship type"},
"target_id":{"type":"string","description":"Target node ID"}
},"required":["id","relationship","target_id"]}`,
			toArgs: func(a map[string]any) []string {
				return []string{"link", str(a, "id"), str(a, "relationship"), str(a, "target_id")}
			},
		},
		{
			name:        "ctx_promote",
			description: "Promote a node (increase score/importance)",
			schema:      `{"type":"object","properties":{"id":{"type":"string","description":"Node ID"}},"required":["id"]}`,
			toArgs: func(a map[string]any) []string {
				return []string{"promote", str(a, "id")}
			},
		},
		{
			name:        "ctx_demote",
			description: "Demote a node (decrease score/importance)",
			schema:      `{"type":"object","properties":{"id":{"type":"string","description":"Node ID"}},"required":["id"]}`,
			toArgs: func(a map[string]any) []string {
				return []string{"demote", str(a, "id")}
			},
		},
		{
			name:        "ctx_lock",
			description: "Lock a node to prevent changes",
			schema:      `{"type":"object","properties":{"id":{"type":"string","description":"Node ID"}},"required":["id"]}`,
			toArgs: func(a map[string]any) []string {
				return []string{"lock", str(a, "id")}
			},
		},
		{
			name:        "ctx_unlock",
			description: "Unlock a previously locked node",
			schema:      `{"type":"object","properties":{"id":{"type":"string","description":"Node ID"}},"required":["id"]}`,
			toArgs: func(a map[string]any) []string {
				return []string{"unlock", str(a, "id")}
			},
		},
		{
			name:        "ctx_stats",
			description: "Get context store statistics as JSON",
			schema:      `{"type":"object","properties":{}}`,
			toArgs: func(a map[string]any) []string {
				return []string{"stats"}
			},
		},
		{
			name:        "ctx_events",
			description: "Get recent event history",
			schema:      `{"type":"object","properties":{"limit":{"type":"number","description":"Max events (default 20)"}}}`,
			toArgs: func(a map[string]any) []string {
				out := []string{"events"}
				out = pushIf(out, "--limit", numStr(a, "limit"))
				return out
			},
		},
		{
			name:        "ctx_assemble",
			description: "Assemble a context view for a query (returns structured JSON)",
			schema:      `{"type":"object","properties":{"query":{"type":"string","description":"Optional query text"},"limit":{"type":"number","description":"Items per layer (default 5)"}}}`,
			toArgs: func(a map[string]any) []string {
				out := []string{"assemble"}
				out = pushIf(out, "--query", str(a, "query"))
				out = pushIf(out, "--limit", numStr(a, "limit"))
				return out
			},
		},
		{
			name:        "ctx_snapshot",
			description: "Save a snapshot to a file",
			schema:      `{"type":"object","properties":{"path":{"type":"string","description":"Optional snapshot path (default: ~/.contextram/context.json)"}}}`,
			toArgs: func(a map[string]any) []string {
				out := []string{"snapshot"}
				if p := str(a, "path"); p != "" {
					out = append(out, p)
				}
				return out
			},
		},
		{
			name:        "ctx_restore",
			description: "Restore context store from a snapshot file",
			schema:      `{"type":"object","properties":{"path":{"type":"string","description":"Snapshot file path"}},"required":["path"]}`,
			toArgs: func(a map[string]any) []string {
				return []string{"restore", str(a, "path")}
			},
		},
		{
			name:        "ctx_recent",
			description: "List most recently updated context nodes",
			schema:      `{"type":"object","properties":{"limit":{"type":"number","description":"Max results (default 10)"}}}`,
			toArgs: func(a map[string]any) []string {
				out := []string{"recent"}
				out = pushIf(out, "--limit", numStr(a, "limit"))
				return out
			},
		},
		{
			name:        "ctx_clear_expired",
			description: "Clear expired context nodes (mark them as expired)",
			schema:      `{"type":"object","properties":{}}`,
			toArgs: func(a map[string]any) []string {
				return []string{"clear-expired"}
			},
		},
		{
			name:        "ctx_path",
			description: "Get the current context store file path",
			schema:      `{"type":"object","properties":{}}`,
			toArgs: func(a map[string]any) []string {
				return []string{"path"}
			},
		},
		{
			name:        "ctx_ingest",
			description: "Ingest a folder into ContextRAM as searchable file chunks",
			schema: `{"type":"object","properties":{
"path":{"type":"string","description":"Folder path to ingest"},
"tags":{"type":"string","description":"Comma-separated tags to apply"},
"extensions":{"type":"string","description":"Comma-separated extensions to ingest, e.g. swift,md,py"},
"chunk_size":{"type":"number","description":"Chunk size in characters (default 800)"},
"chunk_overlap":{"type":"number","description":"Chunk overlap in characters (default 100)"},
"max_file_size":{"type":"number","description":"Maximum file size in bytes (default 2000000)"}
},"required":["path"]}`,
			toArgs: func(a map[string]any) []string {
				out := []string{"ingest", str(a, "path")}
				out = pushIf(out, "--tags", str(a, "tags"))
				out = pushIf(out, "--extensions", str(a, "extensions"))
				out = pushIf(out, "--chunk-size", numStr(a, "chunk_size"))
				out = pushIf(out, "--chunk-overlap", numStr(a, "chunk_overlap"))
				out = pushIf(out, "--max-file-size", numStr(a, "max_file_size"))
				return out
			},
		},
		{
			name:        "ctx_ingest_chat",
			description: "Parse a markdown chat log and auto-classify messages into ContextRAM nodes",
			schema: `{"type":"object","properties":{
"path":{"type":"string","description":"Markdown chat file path"},
"tags":{"type":"string","description":"Comma-separated tags to apply"},
"min_chars":{"type":"number","description":"Minimum message length to ingest (default 3)"},
"dry_run":{"type":"boolean","description":"Preview classifications without writing nodes"}
},"required":["path"]}`,
			toArgs: func(a map[string]any) []string {
				out := []string{"ingest-chat", str(a, "path")}
				out = pushIf(out, "--tags", str(a, "tags"))
				out = pushIf(out, "--min-chars", numStr(a, "min_chars"))
				if boolFlag(a, "dry_run") {
					out = append(out, "--dry-run")
				}
				return out
			},
		},
		{
			name:        "ctx_semantic",
			description: "Semantic-style TF-IDF search over ContextRAM nodes",
			schema: `{"type":"object","properties":{
"text":{"type":"string","description":"Search text"},
"limit":{"type":"number","description":"Max results (default 10)"},
"tag":{"type":"string","description":"Optional tag filter"}
},"required":["text"]}`,
			toArgs: func(a map[string]any) []string {
				out := []string{"semantic", str(a, "text")}
				out = pushIf(out, "--limit", numStr(a, "limit"))
				out = pushIf(out, "--tag", str(a, "tag"))
				return out
			},
		},
		{
			name:        "ctx_embed",
			description: "Pure Swift in-memory dense hashed embedding search over ContextRAM nodes",
			schema: `{"type":"object","properties":{
"text":{"type":"string","description":"Search text"},
"limit":{"type":"number","description":"Max results (default 10)"},
"tag":{"type":"string","description":"Optional tag filter"},
"type":{"type":"string","description":"Optional node type filter"},
"dimensions":{"type":"number","description":"Embedding dimensions, clamped 32-4096 (default 384)"},
"min_token_length":{"type":"number","description":"Minimum token length (default 3)"},
"no_ngrams":{"type":"boolean","description":"Disable character n-gram features"},
"json":{"type":"boolean","description":"Return JSON result payload"}
},"required":["text"]}`,
			toArgs: func(a map[string]any) []string {
				out := []string{"embed", "--text", str(a, "text")}
				out = pushIf(out, "--limit", numStr(a, "limit"))
				out = pushIf(out, "--tag", str(a, "tag"))
				out = pushIf(out, "--type", str(a, "type"))
				out = pushIf(out, "--dimensions", numStr(a, "dimensions"))
				out = pushIf(out, "--min-token-length", numStr(a, "min_token_length"))
				if boolFlag(a, "no_ngrams") {
					out = append(out, "--no-ngrams")
				}
				if boolFlag(a, "json") {
					out = append(out, "--json")
				}
				return out
			},
		},
		{
			name:        "ctx_embed_stats",
			description: "Build the pure Swift in-memory embedding index and return RAM/dimension stats",
			schema: `{"type":"object","properties":{
"tag":{"type":"string","description":"Optional tag filter"},
"type":{"type":"string","description":"Optional node type filter"},
"dimensions":{"type":"number","description":"Embedding dimensions, clamped 32-4096 (default 384)"},
"min_token_length":{"type":"number","description":"Minimum token length (default 3)"},
"no_ngrams":{"type":"boolean","description":"Disable character n-gram features"}
}}`,
			toArgs: func(a map[string]any) []string {
				out := []string{"embed-stats"}
				out = pushIf(out, "--tag", str(a, "tag"))
				out = pushIf(out, "--type", str(a, "type"))
				out = pushIf(out, "--dimensions", numStr(a, "dimensions"))
				out = pushIf(out, "--min-token-length", numStr(a, "min_token_length"))
				if boolFlag(a, "no_ngrams") {
					out = append(out, "--no-ngrams")
				}
				return out
			},
		},
		{
			name:        "ctx_auto",
			description: "Auto-assemble context for a task with proactive loading",
			schema: `{"type":"object","properties":{
"task":{"type":"string","description":"Task description"},
"file":{"type":"string","description":"Current file being edited"},
"limit":{"type":"number","description":"Items per layer (default 5)"}
}}`,
			toArgs: func(a map[string]any) []string {
				out := []string{"auto"}
				out = pushIf(out, "--task", str(a, "task"))
				out = pushIf(out, "--file", str(a, "file"))
				out = pushIf(out, "--limit", numStr(a, "limit"))
				return out
			},
		},
		{
			name:        "ctx_suggest",
			description: "Get proactive context suggestions based on current work",
			schema: `{"type":"object","properties":{
"task":{"type":"string","description":"Current task description"},
"file":{"type":"string","description":"Current file being edited"}
}}`,
			toArgs: func(a map[string]any) []string {
				out := []string{"suggest"}
				out = pushIf(out, "--task", str(a, "task"))
				out = pushIf(out, "--file", str(a, "file"))
				return out
			},
		},
	}
}

// runCtx spawns the ctx binary with the given args and returns trimmed stdout.
// On non-zero exit it returns stderr (or a code message) as an error.
func runCtx(ctx context.Context, binary string, args []string) (string, error) {
	cmd := exec.CommandContext(ctx, binary, args...)
	cmd.Dir = dirOf(binary)
	out, err := cmd.Output()
	if err != nil {
		if ee, ok := err.(*exec.ExitError); ok && len(ee.Stderr) > 0 {
			return "", fmt.Errorf("%s", strings.TrimSpace(string(ee.Stderr)))
		}
		return "", err
	}
	return strings.TrimSpace(string(out)), nil
}

// dirOf returns the directory part of a path, or "." if none.
func dirOf(p string) string {
	for i := len(p) - 1; i >= 0; i-- {
		if p[i] == '/' {
			return p[:i]
		}
	}
	return "."
}

func main() {
	ctxBinary := flag.String("ctx-binary", "", "path to the Swift ctx binary (env: CTX_BINARY)")
	flag.Parse()

	path := *ctxBinary
	if path == "" {
		path = os.Getenv("CTX_BINARY")
	}
	if path == "" {
		path = defaultCtxBinary
	}

	// If the configured binary does not exist, fall back to the debug build so
	// the server still functions in dev environments without a release build.
	if _, err := os.Stat(path); err != nil {
		debugPath := "/Users/wws/contestsystem/ContextRAMSwift/.build/debug/ctx"
		if _, err2 := os.Stat(debugPath); err2 == nil {
			path = debugPath
		}
	}

	defs := allTools()
	byName := make(map[string]toolDef, len(defs))
	for _, d := range defs {
		byName[d.name] = d
	}

	server := mcp.NewServer(&mcp.Implementation{Name: "contextram-mcp", Version: "1.0.0"}, nil)

	for _, d := range defs {
		d := d // capture for closure
		server.AddTool(&mcp.Tool{
			Name:        d.name,
			Description: d.description,
			InputSchema: json.RawMessage(d.schema),
		}, func(ctx context.Context, req *mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			var args map[string]any
			if len(req.Params.Arguments) > 0 {
				if err := json.Unmarshal(req.Params.Arguments, &args); err != nil {
					return &mcp.CallToolResult{
						Content: []mcp.Content{&mcp.TextContent{Text: "invalid arguments: " + err.Error()}},
						IsError: true,
					}, nil
				}
			}
			if args == nil {
				args = map[string]any{}
			}
			cmdArgs := d.toArgs(args)
			output, err := runCtx(ctx, path, cmdArgs)
			if err != nil {
				return &mcp.CallToolResult{
					Content: []mcp.Content{&mcp.TextContent{Text: err.Error()}},
					IsError: true,
				}, nil
			}
			return &mcp.CallToolResult{
				Content: []mcp.Content{&mcp.TextContent{Text: output}},
			}, nil
		})
	}

	if err := server.Run(context.Background(), &mcp.StdioTransport{}); err != nil {
		log.Fatalf("server error: %v", err)
	}
}
