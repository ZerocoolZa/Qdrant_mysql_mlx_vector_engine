package tools

// [@GHOST]{file_path="Dom_Mcp/dom_mcp/tools/toolsmd.go"
// date="2026-07-04" author="Devin" session_id="mcp-tools-md"
// context="Auto-generate tools.md from registry — helps model decide which tool to use when"}
// [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase Module dispatch"}
// [@FILEID]{id="toolsmd.go" domain="mcp_tools" authority="ToolsMdModule"}
// [@SUMMARY]{summary="ToolsMdModule — introspects the tool registry and generates a markdown document listing every MCP tool with when-to-use, fallbacks, and related tools. Writes to .devin/rules/tools.md so it's auto-loaded as a rule."}
// [@CLASS]{class="ToolsMdModule" domain="mcp_tools" authority="single"}
// [@METHOD]{method="Name" type="interface"}
// [@METHOD]{method="Tools" type="interface"}
// [@METHOD]{method="generateMarkdown" type="helper"}
// [@METHOD]{method="toolMetadata" type="helper"}

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

// ToolMeta holds rich metadata for a tool that the Tool interface doesn't carry.
// This is maintained in one place (here) so the Tool interface stays clean.
type ToolMeta struct {
	WhenToUse string   // When should the model use this tool?
	Fallback  string   // What to use if this tool fails or is unavailable
	Related   []string // Other tools that do similar/complementary things
	Category  string   // Grouping: search, storage, chat, email, config, etc.
}

// toolMetadataMap is the curated metadata for every tool.
// When a new tool is added, add its metadata here.
func toolMetadataMap() map[string]ToolMeta {
	return map[string]ToolMeta{
		// ── Cascade Chat Search ──────────────────────────────
		"cascade_chat_search_sessions": {
			Category:  "chat-search",
			WhenToUse:  "Use FIRST when searching for which chat sessions discussed a topic. Multi-word queries split into keywords and score sessions. No RAM load needed — queries MySQL directly. Always start here for 'which session built X' or 'find the chat where we discussed Y'.",
			Fallback:   "If no results, try cascade_chat_search (searches loaded RAM content) or cascade_chat_search_files (if looking for file references).",
			Related:    []string{"cascade_chat_search", "cascade_chat_search_files", "cascade_chat_session_detail"},
		},
		"cascade_chat_session_detail": {
			Category:  "chat-search",
			WhenToUse:  "Use AFTER search-sessions or search-files to get full detail of a specific session. Returns all rounds, user messages, assistant responses, commands, files, checkpoints. Pass the trajectory_id from search results.",
			Fallback:   "If the session is not in MySQL, use cascade_chat_read with the .pb file path instead.",
			Related:    []string{"cascade_chat_search_sessions", "cascade_chat_search_files", "cascade_chat_read"},
		},
		"cascade_chat_search_files": {
			Category:  "chat-search",
			WhenToUse:  "Use when you want to know which sessions mentioned, created, or modified a specific file. Searches command outputs, file_context messages, and assistant content for file paths. Ranked by mention count.",
			Fallback:   "If no results in MySQL, use cascade_chat_search with the filename as query (searches RAM-loaded content).",
			Related:    []string{"cascade_chat_search_sessions", "cascade_chat_session_detail", "cascade_chat_search"},
		},
		"cascade_chat_search": {
			Category:  "chat-search",
			WhenToUse:  "Use for keyword search across loaded .pb chat content in RAM. Searches user messages, assistant messages, and command output. Auto-loads all .pb files if nothing loaded. Slower than search-sessions (must decrypt+load first).",
			Fallback:   "If RAM loading is too slow, use cascade_chat_search_sessions (queries MySQL directly, no load needed).",
			Related:    []string{"cascade_chat_search_sessions", "cascade_chat_search_files"},
		},
		"cascade_chat_scan": {
			Category:  "chat-ops",
			WhenToUse:  "Use to discover what .pb Cascade chat files exist on disk. Returns paths, categories (cascade/implicit/memories), and sizes. Run before load or load-all to see what's available.",
			Fallback:   "None — this is the discovery tool.",
			Related:    []string{"cascade_chat_load", "cascade_chat_load_all"},
		},
		"cascade_chat_list": {
			Category:  "chat-ops",
			WhenToUse:  "Use to see what's currently loaded in RAM SQLite. Shows trajectory IDs, step counts, message counts.",
			Fallback:   "If empty, run cascade_chat_load_all first.",
			Related:    []string{"cascade_chat_stats", "cascade_chat_load_all"},
		},
		"cascade_chat_load": {
			Category:  "chat-ops",
			WhenToUse:  "Use to decrypt and load a single .pb file into RAM. Required before read or search (RAM-based).",
			Fallback:   "If file not found, run cascade_chat_scan to get valid paths.",
			Related:    []string{"cascade_chat_load_all", "cascade_chat_scan", "cascade_chat_read"},
		},
		"cascade_chat_load_all": {
			Category:  "chat-ops",
			WhenToUse:  "Use to load ALL .pb files into RAM at once. Required before RAM-based search across all sessions.",
			Fallback:   "If too slow, use cascade_chat_search_sessions (MySQL direct, no load needed).",
			Related:    []string{"cascade_chat_load", "cascade_chat_search", "cascade_chat_stats"},
		},
		"cascade_chat_read": {
			Category:  "chat-ops",
			WhenToUse:  "Use to read a single .pb file as a conversation (user messages, assistant responses, commands). Auto-loads if not in RAM.",
			Fallback:   "If you only need search results, use cascade_chat_search instead.",
			Related:    []string{"cascade_chat_load", "cascade_chat_export"},
		},
		"cascade_chat_export": {
			Category:  "chat-ops",
			WhenToUse:  "Use to export a .pb chat to markdown files (one per round + index). Good for archiving or sharing.",
			Fallback:   "None.",
			Related:    []string{"cascade_chat_read", "cascade_chat_export_db"},
		},
		"cascade_chat_stats": {
			Category:  "chat-ops",
			WhenToUse:  "Use to check how many trajectories/steps/messages are loaded in RAM.",
			Fallback:   "None.",
			Related:    []string{"cascade_chat_list"},
		},
		"cascade_chat_export_db": {
			Category:  "chat-mysql",
			WhenToUse:  "Use to transfer loaded RAM chats to MySQL cascade_chats database. Run after load-all to populate MySQL for search-sessions.",
			Fallback:   "If MySQL connection fails, check config [tools.mysql].",
			Related:    []string{"cascade_chat_load_all", "cascade_chat_verify_db", "cascade_chat_search_sessions"},
		},
		"cascade_chat_verify_db": {
			Category:  "chat-mysql",
			WhenToUse:  "Use to verify all .pb files on disk are present in MySQL. Run before clean.",
			Fallback:   "None.",
			Related:    []string{"cascade_chat_export_db", "cascade_chat_clean"},
		},
		"cascade_chat_clean": {
			Category:  "chat-mysql",
			WhenToUse:  "Use to delete .pb files from disk AFTER verifying all are in MySQL. SAFETY: requires confirm=true. Aborts if any file is missing from DB.",
			Fallback:   "None — this is destructive. Always run verify_db first.",
			Related:    []string{"cascade_chat_verify_db", "cascade_chat_export_db"},
		},

		// ── BCL Chat Compression ─────────────────────────────
		"bcl_chat_compress": {
			Category:  "bcl",
			WhenToUse:  "Use to compress a chat markdown file to BCL tokens (Stage 1). Extracts [@USER_SAYS] [@AI_SAYS] [@ERROR] [@FILE] [@COMMAND_RAN] tokens.",
			Fallback:   "If compression fails, use bcl_chat_dry_run to preview without writing.",
			Related:    []string{"bcl_chat_dry_run"},
		},
		"bcl_chat_dry_run": {
			Category:  "bcl",
			WhenToUse:  "Use to preview BCL token extraction without writing output. Returns token count, line count, compression ratio.",
			Fallback:   "None.",
			Related:    []string{"bcl_chat_compress"},
		},

		// ── Filesystem ───────────────────────────────────────
		"read_file": {
			Category:  "filesystem",
			WhenToUse:  "Use to read file contents from allowed directories.",
			Fallback:   "If path not allowed, check [tools.filesystem] allowed_dirs in config.",
			Related:    []string{"write_file", "list_dir"},
		},
		"write_file": {
			Category:  "filesystem",
			WhenToUse:  "Use to write content to a file in allowed directories.",
			Fallback:   "If path not allowed, check config.",
			Related:    []string{"read_file", "list_dir"},
		},
		"list_dir": {
			Category:  "filesystem",
			WhenToUse:  "Use to list directory contents.",
			Fallback:   "None.",
			Related:    []string{"read_file", "write_file"},
		},

		// ── MySQL ────────────────────────────────────────────
		"mysql_query": {
			Category:  "database",
			WhenToUse:  "Use to run SQL queries against MySQL databases (vb_shared, vb_code_test, cascade_chats, CODEBASE, devin, diagnostic_kb).",
			Fallback:   "If connection fails, check [tools.mysql] config (host, port, user, password).",
			Related:    []string{"sqlite_query"},
		},

		// ── SQLite ───────────────────────────────────────────
		"sqlite_query": {
			Category:  "database",
			WhenToUse:  "Use to run SQL queries against the local SQLite database (go_mcp_store.db).",
			Fallback:   "For MySQL databases, use mysql_query.",
			Related:    []string{"mysql_query"},
		},

		// ── Memory ───────────────────────────────────────────
		"create_entities": {
			Category:  "memory",
			WhenToUse:  "Use to create entities in the knowledge graph memory store.",
			Fallback:   "None.",
			Related:    []string{"create_relations", "add_observations", "read_memory"},
		},
		"create_relations": {
			Category:  "memory",
			WhenToUse:  "Use to create relationships between entities in the knowledge graph.",
			Fallback:   "None.",
			Related:    []string{"create_entities", "add_observations"},
		},
		"add_observations": {
			Category:  "memory",
			WhenToUse:  "Use to add observations to existing entities in the knowledge graph.",
			Fallback:   "None.",
			Related:    []string{"create_entities", "create_relations"},
		},
		"read_memory": {
			Category:  "memory",
			WhenToUse:  "Use to read the full memory graph or search for specific entities.",
			Fallback:   "None.",
			Related:    []string{"create_entities", "add_observations"},
		},

		// ── MSearch ──────────────────────────────────────────
		"msearch": {
			Category:  "search",
			WhenToUse:  "Use to search MySQL knowledge base (vb_shared: learned_rules, know_problems, know_solutions) via native C binary. Fast full-text search across 10K+ rules.",
			Fallback:   "If msearch binary not found, use mysql_query with LIKE queries directly.",
			Related:    []string{"mysql_query", "cascade_chat_search_sessions"},
		},

		// ── ContextRAM ───────────────────────────────────────
		"contextram_query": {
			Category:  "search",
			WhenToUse:  "Use to query ContextRAM store for context-augmented retrieval.",
			Fallback:   "If ctx binary not found, check [tools.contextram] config.",
			Related:    []string{"msearch", "pinecone_query"},
		},

		// ── Pinecone ─────────────────────────────────────────
		"pinecone_query": {
			Category:  "search",
			WhenToUse:  "Use to query Pinecone vector index for semantic similarity search.",
			Fallback:   "If no API key or index, check [tools.pinecone] config.",
			Related:    []string{"contextram_query", "msearch"},
		},

		// ── Graph ────────────────────────────────────────────
		"graph_query": {
			Category:  "graph",
			WhenToUse:  "Use to query the DomGraphEngine (Python bridge) for knowledge graph operations.",
			Fallback:   "If bridge fails, check [tools.graph] bridge_path config.",
			Related:    []string{"mysql_query", "read_memory"},
		},

		// ── Gmail ────────────────────────────────────────────
		"gmail_send": {
			Category:  "email",
			WhenToUse:  "Use to send email via Gmail MCP.",
			Fallback:   "If gmail-go-mcp binary not found, check [tools.gmail] config.",
			Related:    []string{"gmail_search"},
		},
		"gmail_search": {
			Category:  "email",
			WhenToUse:  "Use to search Gmail messages.",
			Fallback:   "If binary not found, check config.",
			Related:    []string{"gmail_send"},
		},

		// ── TaskPlanner ──────────────────────────────────────
		"taskplanner_board": {
			Category:  "tasks",
			WhenToUse:  "Use to view the task board (Backlog, Next, In Progress, Done).",
			Fallback:   "If no tasks, check [tools.taskplanner] tasks_dir config.",
			Related:    []string{"taskplanner_list", "taskplanner_create", "taskplanner_move"},
		},
		"taskplanner_list": {
			Category:  "tasks",
			WhenToUse:  "Use to list tasks in a specific column.",
			Fallback:   "Use taskplanner_board for full overview.",
			Related:    []string{"taskplanner_board", "taskplanner_get"},
		},
		"taskplanner_get": {
			Category:  "tasks",
			WhenToUse:  "Use to get details of a specific task by ID.",
			Fallback:   "Use taskplanner_list to find the ID first.",
			Related:    []string{"taskplanner_list", "taskplanner_update"},
		},
		"taskplanner_create": {
			Category:  "tasks",
			WhenToUse:  "Use to create a new task in the backlog.",
			Fallback:   "None.",
			Related:    []string{"taskplanner_move", "taskplanner_update"},
		},
		"taskplanner_move": {
			Category:  "tasks",
			WhenToUse:  "Use to move a task between columns (Backlog → Next → In Progress → Done).",
			Fallback:   "None.",
			Related:    []string{"taskplanner_create", "taskplanner_update"},
		},
		"taskplanner_update": {
			Category:  "tasks",
			WhenToUse:  "Use to update task content or metadata.",
			Fallback:   "None.",
			Related:    []string{"taskplanner_get", "taskplanner_move"},
		},

		// ── Config ───────────────────────────────────────────
		"config_reload": {
			Category:  "config",
			WhenToUse:  "Use to reload the MCP server config after editing dom_mcp.toml.",
			Fallback:   "None.",
			Related:    []string{"config_get", "config_set"},
		},
		"config_get": {
			Category:  "config",
			WhenToUse:  "Use to read a config value.",
			Fallback:   "None.",
			Related:    []string{"config_reload", "config_set"},
		},
		"config_set": {
			Category:  "config",
			WhenToUse:  "Use to set a config value and save.",
			Fallback:   "None.",
			Related:    []string{"config_reload", "config_get"},
		},

		// ── ToolsMd (self) ───────────────────────────────────
		"tools_md": {
			Category:  "meta",
			WhenToUse:  "Use to regenerate the tools.md documentation file. Call this after adding new tools or when the model needs a reference of all available tools, when to use each, and fallbacks.",
			Fallback:   "None — this IS the documentation tool.",
			Related:    []string{"config_get"},
		},
	}
}

// ToolsMdModule generates tools.md from the registry.
type ToolsMdModule struct {
	registry *Registry
	outPath  string
}

// NewToolsMdModule creates the module. outPath is where tools.md gets written.
func NewToolsMdModule(reg *Registry, outPath string) *ToolsMdModule {
	if outPath == "" {
		home, _ := os.UserHomeDir()
		outPath = filepath.Join(home, ".config", "devin", "rules", "tools.md")
	}
	return &ToolsMdModule{registry: reg, outPath: outPath}
}

func (m *ToolsMdModule) Name() string { return "tools_md" }

func (m *ToolsMdModule) Tools() []Tool {
	return []Tool{
		&toolsMdTool{name: "tools_md", desc: "Auto-generate tools.md — a markdown document listing every MCP tool with when-to-use, fallbacks, and related tools. Writes to .devin/rules/tools.md so it's auto-loaded as a rule. Call this after adding new tools or when you need a tool reference.", m: m, required: nil},
	}
}

// toolsMdTool is the MCP tool for generating tools.md.
type toolsMdTool struct {
	name     string
	desc     string
	m        *ToolsMdModule
	required []string
}

func (t *toolsMdTool) Name() string        { return t.name }
func (t *toolsMdTool) Description() string { return t.desc }

func (t *toolsMdTool) InputSchema() map[string]any {
	props := map[string]map[string]any{
		"output_path": Prop("string", "Custom output path for tools.md (default: ~/.config/devin/rules/tools.md)."),
		"preview":     Prop("boolean", "If true, return the markdown content without writing to disk."),
	}
	return Schema(props, t.required)
}

func (t *toolsMdTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	outPath := ArgString(args, "output_path")
	if outPath == "" {
		outPath = t.m.outPath
	}
	preview := ArgBool(args, "preview")

	md := t.m.generateMarkdown()

	if preview {
		return NewTextResult(md)
	}

	// Ensure directory exists
	dir := filepath.Dir(outPath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return NewErrorResult(fmt.Sprintf("tools_md: cannot create dir %s: %v", dir, err))
	}

	if err := os.WriteFile(outPath, []byte(md), 0644); err != nil {
		return NewErrorResult(fmt.Sprintf("tools_md: cannot write %s: %v", outPath, err))
	}

	toolCount := len(t.m.registry.List())
	return NewTextResult(fmt.Sprintf("tools.md generated at %s\n%d tools documented.\nCategories: %s", outPath, toolCount, strings.Join(t.m.categories(), ", ")))
}

// generateMarkdown builds the full tools.md document from the registry.
func (m *ToolsMdModule) generateMarkdown() string {
	allTools := m.registry.List()
	meta := toolMetadataMap()

	// Group by category
	categories := make(map[string][]Tool)
	for _, t := range allTools {
		cat := "other"
		if tm, ok := meta[t.Name()]; ok {
			cat = tm.Category
		}
		categories[cat] = append(categories[cat], t)
	}

	// Sort category names
	catNames := make([]string, 0, len(categories))
	for k := range categories {
		catNames = append(catNames, k)
	}
	sort.Strings(catNames)

	var b strings.Builder
	b.WriteString("# MCP Tools Reference — dom_mcp\n\n")
	b.WriteString(fmt.Sprintf("<!-- Auto-generated by tools_md on %s. Do not edit manually. -->\n", time.Now().Format("2006-01-02 15:04:05")))
	b.WriteString(fmt.Sprintf("<!-- %d tools across %d categories. -->\n\n", len(allTools), len(catNames)))
	b.WriteString("This document lists every MCP tool available on the dom_mcp server.\n")
	b.WriteString("Use it to decide which tool to use for a given task, what fallback to try if a tool fails, and which tools are related.\n\n")

	// Quick reference table
	b.WriteString("## Quick Reference\n\n")
	b.WriteString("| Tool | Category | When To Use |\n")
	b.WriteString("|------|----------|-------------|\n")
	for _, cat := range catNames {
		tools := categories[cat]
		sort.Slice(tools, func(i, j int) bool { return tools[i].Name() < tools[j].Name() })
		for _, t := range tools {
			tm := meta[t.Name()]
			whenShort := tm.WhenToUse
			if len(whenShort) > 100 {
				whenShort = whenShort[:97] + "..."
			}
			b.WriteString(fmt.Sprintf("| `%s` | %s | %s |\n", t.Name(), cat, escapeMD(whenShort)))
		}
	}
	b.WriteString("\n")

	// Decision tree
	b.WriteString("## Decision Tree — Which Tool Should I Use?\n\n")
	b.WriteString("```\n")
	b.WriteString("Do I want to search chat history?\n")
	b.WriteString("  ├─ Which sessions discussed a topic?     → cascade_chat_search_sessions\n")
	b.WriteString("  ├─ Which sessions touched a file?        → cascade_chat_search_files\n")
	b.WriteString("  ├─ Get full detail of one session?       → cascade_chat_session_detail\n")
	b.WriteString("  └─ Keyword search across loaded chats?   → cascade_chat_search\n")
	b.WriteString("\n")
	b.WriteString("Do I want to search knowledge base?\n")
	b.WriteString("  ├─ Full-text search learned_rules etc?   → msearch\n")
	b.WriteString("  ├─ Semantic/vector search?               → pinecone_query\n")
	b.WriteString("  └─ Raw SQL query?                        → mysql_query\n")
	b.WriteString("\n")
	b.WriteString("Do I want to manage tasks?\n")
	b.WriteString("  ├─ View board?                           → taskplanner_board\n")
	b.WriteString("  ├─ Create task?                          → taskplanner_create\n")
	b.WriteString("  ├─ Move task?                            → taskplanner_move\n")
	b.WriteString("  └─ Update task?                          → taskplanner_update\n")
	b.WriteString("\n")
	b.WriteString("Do I want to manage memory/knowledge graph?\n")
	b.WriteString("  ├─ Create entity?                        → create_entities\n")
	b.WriteString("  ├─ Create relationship?                  → create_relations\n")
	b.WriteString("  ├─ Add observation?                      → add_observations\n")
	b.WriteString("  └─ Read memory?                          → read_memory\n")
	b.WriteString("\n")
	b.WriteString("Do I want to work with files?\n")
	b.WriteString("  ├─ Read file?                            → read_file\n")
	b.WriteString("  ├─ Write file?                           → write_file\n")
	b.WriteString("  └─ List directory?                       → list_dir\n")
	b.WriteString("\n")
	b.WriteString("Do I want to compress chats to BCL?\n")
	b.WriteString("  ├─ Compress to BCL tokens?               → bcl_chat_compress\n")
	b.WriteString("  └─ Preview without writing?              → bcl_chat_dry_run\n")
	b.WriteString("\n")
	b.WriteString("Do I want email?\n")
	b.WriteString("  ├─ Send email?                           → gmail_send\n")
	b.WriteString("  └─ Search email?                         → gmail_search\n")
	b.WriteString("\n")
	b.WriteString("Do I want to document all tools?           → tools_md\n")
	b.WriteString("```\n\n")

	// Detailed sections per category
	for _, cat := range catNames {
		tools := categories[cat]
		sort.Slice(tools, func(i, j int) bool { return tools[i].Name() < tools[j].Name() })
		b.WriteString(fmt.Sprintf("## %s\n\n", categoryTitle(cat)))
		for _, t := range tools {
			tm := meta[t.Name()]
			b.WriteString(fmt.Sprintf("### `%s`\n\n", t.Name()))
			b.WriteString(fmt.Sprintf("**Description:** %s\n\n", t.Description()))
			if tm.WhenToUse != "" {
				b.WriteString(fmt.Sprintf("**When to use:** %s\n\n", tm.WhenToUse))
			}
			if tm.Fallback != "" {
				b.WriteString(fmt.Sprintf("**Fallback:** %s\n\n", tm.Fallback))
			}
			if len(tm.Related) > 0 {
				rel := make([]string, len(tm.Related))
				for i, r := range tm.Related {
					rel[i] = fmt.Sprintf("`%s`", r)
				}
				b.WriteString(fmt.Sprintf("**Related:** %s\n\n", strings.Join(rel, ", ")))
			}
			// Parameters
			schema := t.InputSchema()
			if props, ok := schema["properties"].(map[string]any); ok && len(props) > 0 {
				b.WriteString("**Parameters:**\n\n")
				b.WriteString("| Param | Type | Description | Required |\n")
				b.WriteString("|-------|------|-------------|----------|\n")
				required := []string{}
				if r, ok := schema["required"].([]string); ok {
					required = r
				}
				reqSet := make(map[string]bool)
				for _, r := range required {
					reqSet[r] = true
				}
				propNames := make([]string, 0, len(props))
				for k := range props {
					propNames = append(propNames, k)
				}
				sort.Strings(propNames)
				for _, pname := range propNames {
					pdef := props[pname].(map[string]any)
					ptype := fmt.Sprintf("%v", pdef["type"])
					pdesc := fmt.Sprintf("%v", pdef["description"])
					req := "no"
					if reqSet[pname] {
						req = "yes"
					}
					b.WriteString(fmt.Sprintf("| `%s` | %s | %s | %s |\n", pname, ptype, escapeMD(pdesc), req))
				}
				b.WriteString("\n")
			}
			b.WriteString("---\n\n")
		}
	}

	b.WriteString("## Fallback Chain Summary\n\n")
	b.WriteString("| Tool | Fallback |\n")
	b.WriteString("|------|----------|\n")
	for _, cat := range catNames {
		tools := categories[cat]
		sort.Slice(tools, func(i, j int) bool { return tools[i].Name() < tools[j].Name() })
		for _, t := range tools {
			tm := meta[t.Name()]
			if tm.Fallback != "" {
				fbShort := tm.Fallback
				if len(fbShort) > 80 {
					fbShort = fbShort[:77] + "..."
				}
				b.WriteString(fmt.Sprintf("| `%s` | %s |\n", t.Name(), escapeMD(fbShort)))
			}
		}
	}
	b.WriteString("\n")

	return b.String()
}

// categories returns all category names sorted.
func (m *ToolsMdModule) categories() []string {
	allTools := m.registry.List()
	meta := toolMetadataMap()
	catSet := make(map[string]bool)
	for _, t := range allTools {
		cat := "other"
		if tm, ok := meta[t.Name()]; ok {
			cat = tm.Category
		}
		catSet[cat] = true
	}
	cats := make([]string, 0, len(catSet))
	for k := range catSet {
		cats = append(cats, k)
	}
	sort.Strings(cats)
	return cats
}

// categoryTitle converts a category slug to a title.
func categoryTitle(cat string) string {
	titles := map[string]string{
		"chat-search": "Cascade Chat Search",
		"chat-ops":    "Cascade Chat Operations",
		"chat-mysql":  "Cascade Chat MySQL",
		"bcl":         "BCL Chat Compression",
		"filesystem":  "Filesystem",
		"database":    "Database",
		"memory":      "Memory / Knowledge Graph",
		"search":      "Search",
		"graph":       "Graph",
		"email":       "Email",
		"tasks":       "Task Planner",
		"config":      "Config",
		"meta":        "Meta",
		"other":       "Other",
	}
	if t, ok := titles[cat]; ok {
		return t
	}
	return strings.Title(cat)
}

// escapeMD escapes pipe characters for markdown table cells.
func escapeMD(s string) string {
	return strings.ReplaceAll(s, "|", "\\|")
}
