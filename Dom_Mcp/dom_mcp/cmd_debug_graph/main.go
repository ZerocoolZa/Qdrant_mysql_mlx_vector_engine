package main

import (
	"context"
	"fmt"
	"os"
	"sort"
	"strings"

	"dom_mcp/tools"
)

func main() {
	// Build registry with all modules that don't need external connections
	registry := tools.NewRegistry()

	// Filesystem
	registry.Register(tools.NewFilesystemModule([]string{"/Users/wws"}))

	// PbReader
	registry.Register(tools.NewPbReaderModule(
		"/usr/bin/python3",
		"/Users/wws/Qdrant_mysql_mlx_vector_engine/chat_mover/pb_reader.py",
		120000,
	))

	// BclCompressor
	registry.Register(tools.NewBclCompressorModule(
		"/usr/bin/python3",
		"/Users/wws/Qdrant_mysql_mlx_vector_engine/chat_mover/bcl_chat_compressor.py",
		120000,
	))

	// SuperSearch
	registry.Register(tools.NewSuperSearchModule(
		"/usr/bin/python3",
		"/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Mcp/dom_mcp/tools/super_search.py",
		30000,
	))

	// Config
	registry.Register(tools.NewConfigModule("/Users/wws/.config/devin/dom_mcp.toml"))

	// ToolsMd — registered last
	tm := tools.NewToolsMdModule(registry, "/tmp/tools_debug.md")
	registry.Register(tm)

	allTools := registry.List()
	fmt.Printf("=== DEBUG: tools_md generator ===\n")
	fmt.Printf("Total tools registered: %d\n\n", len(allTools))

	// Sort tools by name
	sort.Slice(allTools, func(i, j int) bool {
		return allTools[i].Name() < allTools[j].Name()
	})

	// Print each tool with its schema
	for _, t := range allTools {
		schema := t.InputSchema()
		reqCount := 0
		if r, ok := schema["required"].([]string); ok {
			reqCount = len(r)
		}
		propsCount := 0
		if props, ok := schema["properties"].(map[string]any); ok {
			propsCount = len(props)
		}
		fmt.Printf("  %-40s props=%d required=%d\n", t.Name(), propsCount, reqCount)
	}

	// Call tools_md in preview mode
	fmt.Printf("\n=== Calling tools_md (preview=true) ===\n\n")
	for _, t := range allTools {
		if t.Name() == "tools_md" {
			result := t.Execute(context.Background(), map[string]any{"preview": true})
			if result.IsError {
				fmt.Printf("ERROR: %s\n", result.Content[0])
				os.Exit(1)
			}
			md := result.Content[0]
			fmt.Printf("Generated markdown: %d bytes, %d lines\n", len(md), strings.Count(md, "\n"))

			// Show first 2000 chars
			preview := md
			if len(preview) > 2000 {
				preview = preview[:2000] + "\n... [truncated] ..."
			}
			fmt.Printf("\n--- PREVIEW (first 2000 chars) ---\n%s\n", preview)

			// Now write to disk
			fmt.Printf("\n=== Writing to /tmp/tools_debug.md ===\n")
			result2 := t.Execute(context.Background(), map[string]any{})
			fmt.Printf("Write result: %s\n", result2.Content[0])

			// Verify file
			info, _ := os.Stat("/tmp/tools_debug.md")
			if info != nil {
				fmt.Printf("File size: %d bytes\n", info.Size())
			}
			break
		}
	}

	// Generate Mermaid graph of tool relationships
	fmt.Printf("\n=== MERMAID GRAPH: Tool Relationship Graph ===\n\n")
	generateMermaidGraph(allTools)
}

func generateMermaidGraph(allTools []tools.Tool) {
	// Tool metadata for relationships (same as toolsmd.go)
	// We'll extract related tools from the metadata
	relationships := map[string][]string{
		"cascade_chat_search_sessions": {"cascade_chat_search", "cascade_chat_search_files", "cascade_chat_session_detail"},
		"cascade_chat_session_detail":  {"cascade_chat_search_sessions", "cascade_chat_search_files", "cascade_chat_read"},
		"cascade_chat_search_files":    {"cascade_chat_search_sessions", "cascade_chat_session_detail", "cascade_chat_search"},
		"cascade_chat_search":          {"cascade_chat_search_sessions", "cascade_chat_search_files"},
		"cascade_chat_scan":            {"cascade_chat_load", "cascade_chat_load_all"},
		"cascade_chat_list":            {"cascade_chat_stats", "cascade_chat_load_all"},
		"cascade_chat_load":            {"cascade_chat_load_all", "cascade_chat_scan", "cascade_chat_read"},
		"cascade_chat_load_all":        {"cascade_chat_load", "cascade_chat_search", "cascade_chat_stats"},
		"cascade_chat_read":            {"cascade_chat_load", "cascade_chat_export"},
		"cascade_chat_export":          {"cascade_chat_read", "cascade_chat_export_db"},
		"cascade_chat_stats":           {"cascade_chat_list"},
		"cascade_chat_export_db":       {"cascade_chat_load_all", "cascade_chat_verify_db", "cascade_chat_search_sessions"},
		"cascade_chat_verify_db":       {"cascade_chat_export_db", "cascade_chat_clean"},
		"cascade_chat_clean":           {"cascade_chat_verify_db", "cascade_chat_export_db"},
		"bcl_chat_compress":            {"bcl_chat_dry_run"},
		"bcl_chat_dry_run":             {"bcl_chat_compress"},
		"read_file":                    {"write_file", "list_directory"},
		"write_file":                   {"read_file", "list_directory"},
		"list_directory":               {"read_file", "write_file"},
		"mysql_read_query":             {"sqlite_query", "msearch"},
		"sqlite_query":                 {"mysql_read_query"},
		"msearch":                      {"mysql_read_query", "cascade_chat_search_sessions"},
		"tools_md":                     {"config_get"},
	}

	// Categories for subgraph grouping
	categories := map[string]string{
		"cascade_chat_search_sessions": "chat-search",
		"cascade_chat_session_detail":  "chat-search",
		"cascade_chat_search_files":    "chat-search",
		"cascade_chat_search":          "chat-search",
		"cascade_chat_scan":            "chat-ops",
		"cascade_chat_list":            "chat-ops",
		"cascade_chat_load":            "chat-ops",
		"cascade_chat_load_all":        "chat-ops",
		"cascade_chat_read":            "chat-ops",
		"cascade_chat_export":          "chat-ops",
		"cascade_chat_stats":           "chat-ops",
		"cascade_chat_export_db":       "chat-mysql",
		"cascade_chat_verify_db":       "chat-mysql",
		"cascade_chat_clean":           "chat-mysql",
		"bcl_chat_compress":            "bcl",
		"bcl_chat_dry_run":             "bcl",
		"read_file":                    "filesystem",
		"write_file":                   "filesystem",
		"list_directory":               "filesystem",
		"mysql_read_query":             "database",
		"sqlite_query":                 "database",
		"msearch":                      "search",
		"tools_md":                     "meta",
	}

	// Category colors
	catColors := map[string]string{
		"chat-search": "#ff6b6b",
		"chat-ops":    "#4ecdc4",
		"chat-mysql":  "#45b7d1",
		"bcl":         "#f9ca24",
		"filesystem":  "#6c5ce7",
		"database":    "#a29bfe",
		"search":      "#fd79a8",
		"meta":        "#00cec9",
	}

	// Build mermaid
	fmt.Println("```mermaid")
	fmt.Println("graph LR")

	// Group nodes by category
	catNodes := make(map[string][]string)
	for _, t := range allTools {
		cat := categories[t.Name()]
		if cat == "" {
			cat = "other"
		}
		catNodes[cat] = append(catNodes[cat], t.Name())
	}

	// Print subgraphs
	catOrder := []string{"chat-search", "chat-ops", "chat-mysql", "bcl", "filesystem", "database", "search", "meta", "other"}
	for _, cat := range catOrder {
		nodes := catNodes[cat]
		if len(nodes) == 0 {
			continue
		}
		fmt.Printf("    subgraph %s [%s]\n", cat, cat)
		for _, n := range nodes {
			color := catColors[cat]
			if color == "" {
				color = "#b2bec3"
			}
			fmt.Printf("        %s[\"%s\"]:::%sStyle\n", n, n, cat)
		}
		fmt.Println("    end")
	}

	// Print edges (related → tool, dashed for fallback)
	printed := make(map[string]bool)
	for _, t := range allTools {
		rels := relationships[t.Name()]
		for _, r := range rels {
			// Check if related tool exists
			found := false
			for _, tt := range allTools {
				if tt.Name() == r {
					found = true
					break
				}
			}
			if found {
				key := r + "->" + t.Name()
				if !printed[key] {
					fmt.Printf("    %s -.-> %s\n", r, t.Name())
					printed[key] = true
				}
			}
		}
	}

	// Class definitions for colors
	for cat, color := range catColors {
		fmt.Printf("    classDef %sStyle fill:%s,stroke:#333,stroke-width:2px,color:#fff\n", cat, color)
	}

	fmt.Println("```")
	fmt.Println()
	fmt.Println("### Graph Legend")
	fmt.Println()
	fmt.Println("| Category | Color | Tools |")
	fmt.Println("|----------|-------|-------|")
	for _, cat := range catOrder {
		nodes := catNodes[cat]
		if len(nodes) == 0 {
			continue
		}
		color := catColors[cat]
		if color == "" {
			color = "#b2bec3"
		}
		fmt.Printf("| %s | `%s` | %d |%s|\n", cat, color, len(nodes), strings.Join(nodes, "`, `"))
	}
}
