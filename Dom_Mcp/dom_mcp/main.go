package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"dom_mcp/tools"
)

// version is the dom_mcp binary version (overridable via -ldflags).
var version = "1.0.0"

func main() {
	var (
		configPath string
		showVer    bool
		listTools  bool
	)
	flag.StringVar(&configPath, "config", DefaultConfigPath(), "Path to the TOML config file")
	flag.BoolVar(&showVer, "version", false, "Print version and exit")
	flag.BoolVar(&listTools, "list-tools", false, "List enabled tools and exit")
	flag.Parse()

	if showVer {
		fmt.Printf("dom_mcp version %s\n", version)
		os.Exit(0)
	}

	cfg, err := LoadConfig(configPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "dom_mcp: failed to load config: %v\n", err)
		os.Exit(1)
	}

	registry, closers, err := buildRegistry(cfg, configPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "dom_mcp: failed to build tools: %v\n", err)
		os.Exit(1)
	}
	defer func() {
		for _, c := range closers {
			c()
		}
	}()

	if listTools {
		for _, t := range registry.List() {
			fmt.Println(t.Name())
		}
		os.Exit(0)
	}

	if err := runServer(cfg, registry); err != nil {
		fmt.Fprintf(os.Stderr, "dom_mcp: %v\n", err)
		os.Exit(1)
	}
}

// buildRegistry constructs the tool registry from the config, enabling only
// the modules listed in [tools] enabled.
func buildRegistry(cfg *Config, configPath string) (*tools.Registry, []func(), error) {
	registry := tools.NewRegistry()
	var closers []func()
	enabled := make(map[string]bool)
	for _, name := range cfg.Tools.Enabled {
		enabled[name] = true
	}

	// Filesystem (native, no cleanup needed).
	if enabled["filesystem"] {
		registry.Register(tools.NewFilesystemModule(cfg.Tools.Filesystem.AllowedDirs))
	}

	// Gdrive (Google Drive for Desktop mount, native).
	if enabled["gdrive"] {
		registry.Register(tools.NewGdriveModule(cfg.Tools.Gdrive.RootPath))
	}

	// SQLite (native, needs close).
	if enabled["sqlite"] {
		mod, err := tools.NewSqliteModule(cfg.Tools.Sqlite.DBPath)
		if err != nil {
			return nil, closers, fmt.Errorf("sqlite module: %w", err)
		}
		closers = append(closers, func() { mod.Close() })
		registry.Register(mod)
	}

	// MySQL (native, needs close).
	if enabled["mysql"] {
		mod, err := tools.NewMysqlModule(
			cfg.Tools.Mysql.Host,
			cfg.Tools.Mysql.Port,
			cfg.Tools.Mysql.User,
			cfg.Tools.Mysql.Password,
			cfg.Tools.Mysql.Database,
		)
		if err != nil {
			return nil, closers, fmt.Errorf("mysql module: %w", err)
		}
		closers = append(closers, func() { mod.Close() })
		registry.Register(mod)
	}

	// Memory (JSON file store).
	if enabled["memory"] {
		mod, err := tools.NewMemoryModule(cfg.Tools.Memory.MemoryFile)
		if err != nil {
			return nil, closers, fmt.Errorf("memory module: %w", err)
		}
		registry.Register(mod)
	}

	// Msearch (subprocess wrapper).
	if enabled["msearch"] {
		registry.Register(tools.NewMsearchModule(cfg.Tools.Msearch.Binary, cfg.Tools.Msearch.TimeoutMs))
	}

	// ContextRAM (subprocess wrapper).
	if enabled["contextram"] {
		registry.Register(tools.NewContextRAMModule(cfg.Tools.ContextRAM.CtxBinary, cfg.Tools.ContextRAM.TimeoutMs))
	}

	// Pinecone (HTTP client).
	if enabled["pinecone"] {
		mod, err := tools.NewPineconeModule(
			cfg.Tools.Pinecone.APIKeyEnv,
			cfg.Tools.Pinecone.APIKey,
			cfg.Tools.Pinecone.Index,
			cfg.Tools.Pinecone.Host,
			cfg.Tools.Pinecone.TimeoutMs,
		)
		if err != nil {
			return nil, closers, fmt.Errorf("pinecone module: %w", err)
		}
		registry.Register(mod)
	}

	// Graph (DomGraphEngine Python subprocess bridge).
	if enabled["graph"] {
		registry.Register(tools.NewGraphModule(
			cfg.Tools.Graph.PythonBinary,
			cfg.Tools.Graph.BridgePath,
			cfg.Tools.Graph.TimeoutMs,
		))
	}

	// Gmail (gmail-go-mcp subprocess wrapper).
	if enabled["gmail"] {
		mod, err := tools.NewGmailModule(cfg.Tools.Gmail.Binary, cfg.Tools.Gmail.TimeoutMs)
		if err != nil {
			return nil, closers, fmt.Errorf("gmail module: %w", err)
		}
		registry.Register(mod)
	}

	// Taskplanner (native .tasks/ markdown board).
	if enabled["taskplanner"] {
		mod, err := tools.NewTaskplannerModule(cfg.Tools.Taskplanner.TasksDir)
		if err != nil {
			return nil, closers, fmt.Errorf("taskplanner module: %w", err)
		}
		registry.Register(mod)
	}

	// PbReader (pb_reader.py Python subprocess bridge — decrypt/search Windsurf .pb chat files).
	if enabled["pbreader"] {
		registry.Register(tools.NewPbReaderModule(
			cfg.Tools.PbReader.PythonBinary,
			cfg.Tools.PbReader.ScriptPath,
			cfg.Tools.PbReader.TimeoutMs,
		))
	}

	// BclCompressor (bcl_chat_compressor.py Python subprocess bridge — BCL Stage 1 chat compression).
	if enabled["bclcompressor"] {
		registry.Register(tools.NewBclCompressorModule(
			cfg.Tools.BclCompressor.PythonBinary,
			cfg.Tools.BclCompressor.ScriptPath,
			cfg.Tools.BclCompressor.TimeoutMs,
		))
	}

	// Config (self-healing config management — always enabled).
	registry.Register(tools.NewConfigModule(configPath))

	// SuperSearch (multi-word proximity search across chats, rules, problems, answers).
	registry.Register(tools.NewSuperSearchModule(
		"/Library/Frameworks/Python.framework/Versions/3.13/bin/python3",
		"/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Mcp/dom_mcp/tools/super_search.py",
		30000,
	))

	// ToolsMd (auto-generate tools.md — always enabled, needs registry reference).
	// Registered last so it can introspect all other tools.
	toolsMdPath := filepath.Join(homeDir(), ".config", "devin", "rules", "tools.md")
	registry.Register(tools.NewToolsMdModule(registry, toolsMdPath))

	return registry, closers, nil
}

// homeDir returns the user's home directory or "." on error.
func homeDir() string {
	h, err := os.UserHomeDir()
	if err != nil {
		return "."
	}
	return h
}

// runServer creates the MCP server, registers all tools, and runs over stdio.
func runServer(cfg *Config, registry *tools.Registry) error {
	logger := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{
		Level: slog.LevelInfo,
	}))

	server := mcp.NewServer(
		&mcp.Implementation{Name: cfg.Server.Name, Version: cfg.Server.Version},
		&mcp.ServerOptions{
			Logger: logger,
		},
	)

	// Register every tool from the registry onto the MCP server.
	for _, t := range registry.List() {
		tool := t // capture for closure
		server.AddTool(&mcp.Tool{
			Name:        tool.Name(),
			Description: tool.Description(),
			InputSchema: tool.InputSchema(),
		}, func(ctx context.Context, req *mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			var args map[string]any
			if len(req.Params.Arguments) > 0 {
				if err := json.Unmarshal(req.Params.Arguments, &args); err != nil {
					return &mcp.CallToolResult{
						Content: []mcp.Content{&mcp.TextContent{Text: fmt.Sprintf("invalid arguments: %v", err)}},
						IsError: true,
					}, nil
				}
			}
			result := tool.Execute(ctx, args)
			content := make([]mcp.Content, 0, len(result.Content))
			for _, text := range result.Content {
				content = append(content, &mcp.TextContent{Text: text})
			}
			res := &mcp.CallToolResult{
				Content: content,
				IsError: result.IsError,
			}
			if result.Structured != nil {
				res.StructuredContent = result.Structured
			}
			return res, nil
		})
	}

	// Set up signal handling for graceful shutdown.
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sigCh
		cancel()
	}()

	logger.Info("dom_mcp starting", "server", cfg.Server.Name, "version", cfg.Server.Version, "tools", len(registry.List()))

	// Run over stdio transport.
	return server.Run(ctx, &mcp.StdioTransport{})
}
