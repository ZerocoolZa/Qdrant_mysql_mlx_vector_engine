package main

import (
	"context"
	"fmt"
	"os"

	"dom_mcp/tools"
)

func main() {
	registry := tools.NewRegistry()

	// Register a few modules to test
	registry.Register(tools.NewFilesystemModule([]string{"/Users/wws"}))
	registry.Register(tools.NewPbReaderModule("/usr/bin/python3", "/Users/wws/Qdrant_mysql_mlx_vector_engine/chat_mover/pb_reader.py", 120000))

	// Register tools_md module
	tm := tools.NewToolsMdModule(registry, "/tmp/tools_test.md")
	registry.Register(tm)

	// Find the tools_md tool and call it in preview mode
	for _, t := range registry.List() {
		if t.Name() == "tools_md" {
			result := t.Execute(context.Background(), map[string]any{"preview": true})
			fmt.Println(result.Content[0][:5000])
			fmt.Println("\n\n... [truncated for display] ...")

			// Also write to disk
			result2 := t.Execute(context.Background(), map[string]any{})
			fmt.Println("\n\nWrite result:", result2.Content[0])

			// Verify file exists
			if _, err := os.Stat("/tmp/tools_test.md"); err == nil {
				fmt.Println("File written successfully!")
			}
			return
		}
	}
	fmt.Println("tools_md tool not found!")
}
