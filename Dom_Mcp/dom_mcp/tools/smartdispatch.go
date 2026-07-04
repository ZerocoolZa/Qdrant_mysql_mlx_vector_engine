package tools

// [@GHOST]{file_path="Dom_Mcp/dom_mcp/tools/smartdispatch.go"
// date="2026-07-04" author="Devin" session_id="mcp-smart-dispatch"
// context="Natural language dispatcher — AI says 'search for kokoro' and MCP picks the right tool"}
// [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase Module dispatch"}
// [@FILEID]{id="smartdispatch.go" domain="mcp_tools" authority="SmartDispatchModule"}
// [@SUMMARY]{summary="SmartDispatchModule — one tool 'ask' that takes natural language and routes to the best tool(s). Extracts parameters from the query, runs the tool, returns the result. The AI never needs to memorize tool names."}
// [@CLASS]{class="SmartDispatchModule" domain="mcp_tools" authority="single"}
// [@METHOD]{method="Name" type="interface"}
// [@METHOD]{method="Tools" type="interface"}
// [@METHOD]{method="Execute" type="dispatch"}
// [@METHOD]{method="route" type="helper"}
// [@METHOD]{method="extractParams" type="helper"}

import (
	"context"
	"fmt"
	"regexp"
	"sort"
	"strings"
)

// ── Intent patterns ──────────────────────────────────────────
// Each pattern maps a natural language intent to a tool + param extractor.
// The router scores each pattern by keyword overlap with the query
// and picks the highest-scoring match.

type intentRule struct {
	Keywords     []string          // words/phrases that trigger this intent (lowercased)
	Tool         string            // tool to call
	ParamExtract func(query string, args map[string]any) map[string]any
	// extracts tool params from the NL query
	MinScore     int              // minimum keyword hits to consider this a match
	Description  string           // human-readable explanation of this intent
}

// smartDispatchRules defines the routing table.
// Order matters only for tie-breaking — highest score wins regardless.
func smartDispatchRules() []intentRule {
	return []intentRule{
		// ── Chat Search ──────────────────────────────────
		{
			Keywords: []string{"search", "find", "session", "sessions", "chat", "chats",
				"discussed", "topic", "conversation", "conversations", "which", "where"},
			Tool: "cascade_chat_search_sessions",
			ParamExtract: func(query string, args map[string]any) map[string]any {
				q := extractAfterKeyword(query, []string{"search for", "find", "search",
					"which sessions", "which chats", "find sessions", "find chats",
					"search sessions", "search chats", "look for", "find chat"})
				if q == "" {
					q = stripStopWords(query)
				}
				out := map[string]any{"query": q}
				if v, ok := args["limit"]; ok {
					out["limit"] = v
				}
				return out
			},
			MinScore:    2,
			Description: "Search chat sessions by keyword (MySQL direct, no load needed)",
		},
		{
			Keywords: []string{"file", "files", "mentioned", "touched", "created",
				"modified", "edited", "which file", "what file", "filename"},
			Tool: "cascade_chat_search_files",
			ParamExtract: func(query string, args map[string]any) map[string]any {
				q := extractFilePath(query)
				if q == "" {
					q = extractAfterKeyword(query, []string{"file", "files",
						"mentioned", "touched", "created", "modified"})
				}
				return map[string]any{"query": q}
			},
			MinScore:    2,
			Description: "Find which sessions mentioned/created/modified a file",
		},
		{
			Keywords: []string{"detail", "details", "full", "session detail",
				"show session", "get session", "trajectory", "tell me about",
				"what happened in", "show me"},
			Tool: "cascade_chat_session_detail",
			ParamExtract: func(query string, args map[string]any) map[string]any {
				tid := extractUUID(query)
				if tid == "" {
					tid = extractAfterKeyword(query, []string{"detail", "details",
						"show session", "get session", "tell me about",
						"what happened in", "show me"})
				}
				return map[string]any{"trajectory_id": tid}
			},
			MinScore:    2,
			Description: "Get full detail of a specific session by trajectory_id",
		},

		// ── Chat Ops ─────────────────────────────────────
		{
			Keywords: []string{"load", "all", "load all", "load everything",
				"decrypt", "load chats", "load pb", "load files"},
			Tool: "cascade_chat_load_all",
			ParamExtract: func(query string, args map[string]any) map[string]any {
				return map[string]any{}
			},
			MinScore:    2,
			Description: "Load all .pb chat files into RAM",
		},
		{
			Keywords: []string{"scan", "discover", "list files", "what files",
				"what pb", "available", "how many pb", "how many chats"},
			Tool: "cascade_chat_scan",
			ParamExtract: func(query string, args map[string]any) map[string]any {
				return map[string]any{}
			},
			MinScore:    1,
			Description: "Scan disk for .pb chat files",
		},
		{
			Keywords: []string{"stats", "statistics", "how many loaded",
				"count", "summary", "overview"},
			Tool: "cascade_chat_stats",
			ParamExtract: func(query string, args map[string]any) map[string]any {
				return map[string]any{}
			},
			MinScore:    1,
			Description: "Show RAM DB statistics (loaded trajectories, messages)",
		},
		{
			Keywords: []string{"list loaded", "what loaded", "loaded chats",
				"loaded trajectories", "show loaded"},
			Tool: "cascade_chat_list",
			ParamExtract: func(query string, args map[string]any) map[string]any {
				return map[string]any{}
			},
			MinScore:    2,
			Description: "List currently loaded trajectories in RAM",
		},
		{
			Keywords: []string{"read chat", "read pb", "read file", "show chat",
				"show conversation", "read conversation", "open chat"},
			Tool: "cascade_chat_read",
			ParamExtract: func(query string, args map[string]any) map[string]any {
				fp := extractFilePath(query)
				return map[string]any{"file": fp}
			},
			MinScore:    2,
			Description: "Read a single .pb chat as a conversation",
		},
		{
			Keywords: []string{"export", "markdown", "md", "export chat",
				"export to md", "archive", "save as markdown"},
			Tool: "cascade_chat_export",
			ParamExtract: func(query string, args map[string]any) map[string]any {
				fp := extractFilePath(query)
				return map[string]any{"file": fp, "outdir": "/tmp/chat_export"}
			},
			MinScore:    2,
			Description: "Export a .pb chat to markdown files",
		},

		// ── Chat MySQL ───────────────────────────────────
		{
			Keywords: []string{"export db", "export mysql", "to mysql",
				"populate mysql", "sync mysql", "transfer to mysql",
				"export to database", "export to db"},
			Tool: "cascade_chat_export_db",
			ParamExtract: func(query string, args map[string]any) map[string]any {
				return map[string]any{}
			},
			MinScore:    2,
			Description: "Export loaded RAM chats to MySQL cascade_chats",
		},
		{
			Keywords: []string{"verify", "verify db", "check mysql",
				"all in mysql", "missing from db", "verify all"},
			Tool: "cascade_chat_verify_db",
			ParamExtract: func(query string, args map[string]any) map[string]any {
				return map[string]any{}
			},
			MinScore:    2,
			Description: "Verify all .pb files are in MySQL",
		},

		// ── BCL ──────────────────────────────────────────
		{
			Keywords: []string{"compress", "bcl", "tokens", "tokenize",
				"compress chat", "bcl compress", "extract tokens"},
			Tool: "bcl_chat_compress",
			ParamExtract: func(query string, args map[string]any) map[string]any {
				fp := extractFilePath(query)
				return map[string]any{"input": fp}
			},
			MinScore:    2,
			Description: "Compress a chat markdown file to BCL tokens",
		},
		{
			Keywords: []string{"dry run", "preview", "preview bcl",
				"dry run bcl", "estimate tokens", "preview compression"},
			Tool: "bcl_chat_dry_run",
			ParamExtract: func(query string, args map[string]any) map[string]any {
				fp := extractFilePath(query)
				return map[string]any{"input": fp}
			},
			MinScore:    2,
			Description: "Preview BCL token extraction without writing",
		},

		// ── Filesystem ───────────────────────────────────
		{
			Keywords: []string{"read file", "cat file", "show file",
				"contents of", "what's in file", "read the file"},
			Tool: "read_file",
			ParamExtract: func(query string, args map[string]any) map[string]any {
				fp := extractFilePath(query)
				return map[string]any{"path": fp}
			},
			MinScore:    2,
			Description: "Read file contents",
		},
		{
			Keywords: []string{"write file", "save file", "create file",
				"write to", "save to file"},
			Tool: "write_file",
			ParamExtract: func(query string, args map[string]any) map[string]any {
				fp := extractFilePath(query)
				return map[string]any{"path": fp, "content": ""}
			},
			MinScore:    2,
			Description: "Write content to a file",
		},
		{
			Keywords: []string{"list dir", "list directory", "ls",
				"what's in directory", "show directory", "folder contents"},
			Tool: "list_directory",
			ParamExtract: func(query string, args map[string]any) map[string]any {
				fp := extractFilePath(query)
				return map[string]any{"path": fp}
			},
			MinScore:    2,
			Description: "List directory contents",
		},

		// ── Meta ─────────────────────────────────────────
		{
			Keywords: []string{"tools", "help", "what tools", "tool list",
				"available tools", "document tools", "tools.md", "generate docs"},
			Tool: "tools_md",
			ParamExtract: func(query string, args map[string]any) map[string]any {
				return map[string]any{"preview": true}
			},
			MinScore:    2,
			Description: "Generate/list available tools documentation",
		},
	}
}

// ── SmartDispatchModule ──────────────────────────────────────

type SmartDispatchModule struct {
	registry *Registry
}

func NewSmartDispatchModule(registry *Registry) *SmartDispatchModule {
	return &SmartDispatchModule{registry: registry}
}

func (m *SmartDispatchModule) Name() string { return "smart_dispatch" }

func (m *SmartDispatchModule) Tools() []Tool {
	return []Tool{&smartAskTool{registry: m.registry}}
}

// ── smartAskTool ─────────────────────────────────────────────

type smartAskTool struct {
	registry *Registry
}

func (t *smartAskTool) Name() string { return "ask" }

func (t *smartAskTool) Description() string {
	return "Natural language tool dispatcher. " +
		"Instead of picking a specific tool, just describe what you want in plain English. " +
		"Examples: 'search for kokoro voice pipeline', 'load all chats', " +
		"'which sessions mentioned model_gui.py', 'show me session 8fe75f98-5aff-47d7-9695-cc3acf2c6963', " +
		"'export to mysql', 'what tools are available', 'stats'. " +
		"The dispatcher matches your query against tool intents and runs the best match. " +
		"If multiple tools could match, it explains what it picked and why. " +
		"Pass extra params (limit, file, outdir) as regular arguments alongside 'query'."
}

func (t *smartAskTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"query": {
			"type": "string",
			"description": "Natural language request. E.g. 'search for kokoro', 'load all chats', 'stats', 'which sessions touched model_gui.py'",
		},
		"limit": {
			"type": "integer",
			"description": "Optional: max results (for search tools). Default 20.",
		},
		"file": {
			"type": "string",
			"description": "Optional: explicit file path (overrides extraction from query).",
		},
		"outdir": {
			"type": "string",
			"description": "Optional: output directory (for export tools).",
		},
		"dry_run": {
			"type": "boolean",
			"description": "If true, show what tool WOULD be called without executing it. Useful for debugging the dispatcher.",
		},
	}, []string{"query"})
}

func (t *smartAskTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	query := ArgString(args, "query")
	if query == "" {
		return NewErrorResult("'query' is required. Describe what you want in plain English.")
	}

	queryLower := strings.ToLower(query)
	rules := smartDispatchRules()

	// Score each rule by keyword overlap
	type scored struct {
		rule  intentRule
		score int
		hits  []string
	}
	var ranked []scored
	for _, rule := range rules {
		hits := []string{}
		for _, kw := range rule.Keywords {
			if strings.Contains(queryLower, kw) {
				hits = append(hits, kw)
			}
		}
		score := len(hits)
		if score >= rule.MinScore {
			ranked = append(ranked, scored{rule: rule, score: score, hits: hits})
		}
	}

	// Sort by score descending
	sort.Slice(ranked, func(i, j int) bool {
		return ranked[i].score > ranked[j].score
	})

	if len(ranked) == 0 {
		// No match — show available intents
		var sb strings.Builder
		sb.WriteString("No tool matched your query. Here are the intents I understand:\n\n")
		for _, rule := range rules {
			sb.WriteString(fmt.Sprintf("  • %s → %s\n    keywords: %s\n",
				rule.Description, rule.Tool, strings.Join(rule.Keywords, ", ")))
		}
		sb.WriteString("\nTry rephrasing your request using these keywords.")
		return NewTextResult(sb.String())
	}

	// Pick the best match
	best := ranked[0]
	tool := t.registry.Get(best.rule.Tool)
	if tool == nil {
		return NewErrorResult(fmt.Sprintf(
			"Dispatcher matched intent '%s' → tool '%s', but that tool is not registered.",
			best.rule.Description, best.rule.Tool))
	}

	// Extract params
	toolArgs := best.rule.ParamExtract(query, args)

	// Dry run mode — show what would happen
	if ArgBool(args, "dry_run") {
		var sb strings.Builder
		sb.WriteString("=== DRY RUN — Smart Dispatch ===\n\n")
		sb.WriteString(fmt.Sprintf("Query: %s\n", query))
		sb.WriteString(fmt.Sprintf("Matched: %s\n", best.rule.Description))
		sb.WriteString(fmt.Sprintf("Tool: %s\n", best.rule.Tool))
		sb.WriteString(fmt.Sprintf("Score: %d (keywords: %s)\n",
			best.score, strings.Join(best.hits, ", ")))
		sb.WriteString(fmt.Sprintf("Extracted params: %v\n", toolArgs))
		if len(ranked) > 1 {
			sb.WriteString("\nOther candidates:\n")
			for i := 1; i < len(ranked) && i < 4; i++ {
				sb.WriteString(fmt.Sprintf("  [%d] %s → %s (score=%d, keywords: %s)\n",
					i, ranked[i].rule.Description, ranked[i].rule.Tool,
					ranked[i].score, strings.Join(ranked[i].hits, ", ")))
			}
		}
		return NewTextResult(sb.String())
	}

	// Execute the tool
	result := tool.Execute(ctx, toolArgs)

	// Prepend dispatch info to the result
	header := fmt.Sprintf("[ask] → %s (score=%d, matched: %s)\n\n",
		best.rule.Tool, best.score, strings.Join(best.hits, ", "))

	if result.IsError {
		return &ToolResult{
			Content:  []string{header + result.Content[0]},
			IsError:  true,
		}
	}

	// Append alternatives if there were close runner-ups
	footer := ""
	if len(ranked) > 1 && ranked[1].score >= best.score-1 {
		footer = "\n\n---\nOther tools that could help:\n"
		for i := 1; i < len(ranked) && i < 3; i++ {
			footer += fmt.Sprintf("  • %s → %s (score=%d)\n",
				ranked[i].rule.Description, ranked[i].rule.Tool, ranked[i].score)
		}
	}

	return &ToolResult{
		Content: []string{header + result.Content[0] + footer},
	}
}

// ── Parameter extraction helpers ─────────────────────────────

// extractAfterKeyword finds the text after the first matching keyword phrase.
func extractAfterKeyword(query string, keywords []string) string {
	queryLower := strings.ToLower(query)
	for _, kw := range keywords {
		idx := strings.Index(queryLower, kw)
		if idx >= 0 {
			rest := query[idx+len(kw):]
			rest = strings.TrimSpace(rest)
			// Strip leading punctuation
			rest = strings.TrimLeft(rest, " :,-\"'for")
			rest = strings.TrimSpace(rest)
			if rest != "" {
				return rest
			}
		}
	}
	return ""
}

// extractFilePath finds a file path in the query.
// Looks for paths starting with / or ~/ or containing .py/.md/.pb etc.
func extractFilePath(query string) string {
	// Match absolute paths, home paths, or relative paths with extensions
	re := regexp.MustCompile(`(?:~/[^ ]+|/[^ ]+\.[a-zA-Z]+|[^ /]+\.(?:py|md|pb|txt|go|js|ts|json|yaml|yml|sql|sh|c|h))`)
	m := re.FindString(query)
	if m != "" {
		return strings.Trim(m, "\"'`,.")
	}
	return ""
}

// extractUUID finds a UUID in the query.
func extractUUID(query string) string {
	re := regexp.MustCompile(`[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}`)
	return re.FindString(query)
}

// stripStopWords removes common command words to get the search query.
func stripStopWords(query string) string {
	stop := []string{"search", "for", "find", "show", "me", "get", "the", "a",
		"which", "what", "where", "when", "how", "about", "of", "to", "in",
		"all", "chats", "sessions", "session", "chat", "please", "can", "you",
		"i", "want", "need", "look", "looking", "tell"}
	words := strings.Fields(query)
	var kept []string
	for _, w := range words {
		if !contains(stop, strings.ToLower(w)) {
			kept = append(kept, w)
		}
	}
	return strings.Join(kept, " ")
}

func contains(slice []string, s string) bool {
	for _, v := range slice {
		if v == s {
			return true
		}
	}
	return false
}
