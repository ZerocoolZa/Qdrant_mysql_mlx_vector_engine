package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/BurntSushi/toml"
)

// ServerConfig holds MCP server identity.
type ServerConfig struct {
	Name    string `toml:"name"`
	Version string `toml:"version"`
}

// ToolsConfig holds the enabled tool list and per-tool config maps.
type ToolsConfig struct {
	Enabled     []string                  `toml:"enabled"`
	Msearch     MsearchConfig             `toml:"msearch"`
	ContextRAM  ContextRAMConfig          `toml:"contextram"`
	Filesystem  FilesystemConfig          `toml:"filesystem"`
	Gdrive      GdriveConfig              `toml:"gdrive"`
	Sqlite      SqliteConfig              `toml:"sqlite"`
	Mysql       MysqlConfig               `toml:"mysql"`
	Memory      MemoryConfig              `toml:"memory"`
	Pinecone    PineconeConfig            `toml:"pinecone"`
	Graph       GraphConfig               `toml:"graph"`
	Gmail       GmailConfig               `toml:"gmail"`
	Taskplanner TaskplannerConfig         `toml:"taskplanner"`
	PbReader    PbReaderConfig            `toml:"pbreader"`
	BclCompressor BclCompressorConfig      `toml:"bclcompressor"`
	Raw         map[string]toml.Primitive `toml:"-"`
}

// GraphConfig for the DomGraphEngine Python subprocess bridge.
type GraphConfig struct {
	PythonBinary string `toml:"python_binary"`
	BridgePath   string `toml:"bridge_path"`
	TimeoutMs    int    `toml:"timeout_ms"`
}

// MsearchConfig for the C msearch subprocess wrapper.
type MsearchConfig struct {
	Binary    string `toml:"binary"`
	TimeoutMs int    `toml:"timeout_ms"`
}

// ContextRAMConfig for the Swift ctx subprocess wrapper.
type ContextRAMConfig struct {
	CtxBinary string `toml:"ctx_binary"`
	StorePath string `toml:"store_path"`
	TimeoutMs int    `toml:"timeout_ms"`
}

// FilesystemConfig for native filesystem operations.
type FilesystemConfig struct {
	AllowedDirs []string `toml:"allowed_dirs"`
}

// GdriveConfig for the Google Drive for Desktop mount.
type GdriveConfig struct {
	RootPath string `toml:"root_path"`
}

// SqliteConfig for the pure-Go SQLite driver.
type SqliteConfig struct {
	DBPath string `toml:"db_path"`
}

// MysqlConfig for the go-sql-driver/mysql driver.
type MysqlConfig struct {
	Host     string `toml:"host"`
	Port     int    `toml:"port"`
	User     string `toml:"user"`
	Password string `toml:"password"`
	Database string `toml:"database"`
}

// MemoryConfig for the JSON file memory store.
type MemoryConfig struct {
	MemoryFile string `toml:"memory_file"`
}

// PineconeConfig for the Pinecone HTTP API client.
type PineconeConfig struct {
	APIKeyEnv string `toml:"api_key_env"`
	APIKey    string `toml:"api_key"`
	Index     string `toml:"index"`
	Host      string `toml:"host"`
	TimeoutMs int    `toml:"timeout_ms"`
}

// GmailConfig for the gmail-go-mcp subprocess wrapper.
// Account credentials are read from environment variables by the binary:
// ACCOUNT_{name}_EMAIL, ACCOUNT_{name}_PASSWORD, DEFAULT_ACCOUNT_ID.
type GmailConfig struct {
	Binary    string `toml:"binary"`
	TimeoutMs int    `toml:"timeout_ms"`
}

// TaskplannerConfig for the native taskplanner module.
type TaskplannerConfig struct {
	TasksDir string `toml:"tasks_dir"`
}

// PbReaderConfig for the pb_reader.py Python subprocess bridge.
type PbReaderConfig struct {
	PythonBinary string `toml:"python_binary"`
	ScriptPath   string `toml:"script_path"`
	TimeoutMs    int    `toml:"timeout_ms"`
}

// BclCompressorConfig for the bcl_chat_compressor.py Python subprocess bridge.
type BclCompressorConfig struct {
	PythonBinary string `toml:"python_binary"`
	ScriptPath   string `toml:"script_path"`
	TimeoutMs    int    `toml:"timeout_ms"`
}

// Config is the top-level dom_mcp configuration.
type Config struct {
	Server ServerConfig `toml:"server"`
	Tools  ToolsConfig  `toml:"tools"`
}

// LoadConfig reads and parses the TOML config file, expanding ~ in paths.
func LoadConfig(path string) (*Config, error) {
	path, err := expandPath(path)
	if err != nil {
		return nil, err
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read config %s: %w", path, err)
	}
	return ParseConfig(data)
}

// ParseConfig parses TOML bytes into a Config.
func ParseConfig(data []byte) (*Config, error) {
	var cfg Config
	if _, err := toml.Decode(string(data), &cfg); err != nil {
		return nil, fmt.Errorf("decode toml: %w", err)
	}
	if cfg.Server.Name == "" {
		cfg.Server.Name = "dom_mcp"
	}
	if cfg.Server.Version == "" {
		cfg.Server.Version = "1.0.0"
	}
	// Expand ~ in all path fields.
	cfg.Tools.Filesystem.AllowedDirs = expandPaths(cfg.Tools.Filesystem.AllowedDirs)
	cfg.Tools.Gdrive.RootPath = expandTilde(cfg.Tools.Gdrive.RootPath)
	cfg.Tools.Msearch.Binary = expandTilde(cfg.Tools.Msearch.Binary)
	cfg.Tools.ContextRAM.CtxBinary = expandTilde(cfg.Tools.ContextRAM.CtxBinary)
	cfg.Tools.ContextRAM.StorePath = expandTilde(cfg.Tools.ContextRAM.StorePath)
	cfg.Tools.Sqlite.DBPath = expandTilde(cfg.Tools.Sqlite.DBPath)
	cfg.Tools.Memory.MemoryFile = expandTilde(cfg.Tools.Memory.MemoryFile)
	cfg.Tools.Graph.PythonBinary = expandTilde(cfg.Tools.Graph.PythonBinary)
	cfg.Tools.Graph.BridgePath = expandTilde(cfg.Tools.Graph.BridgePath)
	cfg.Tools.Gmail.Binary = expandTilde(cfg.Tools.Gmail.Binary)
	cfg.Tools.Taskplanner.TasksDir = expandTilde(cfg.Tools.Taskplanner.TasksDir)
	cfg.Tools.PbReader.PythonBinary = expandTilde(cfg.Tools.PbReader.PythonBinary)
	cfg.Tools.PbReader.ScriptPath = expandTilde(cfg.Tools.PbReader.ScriptPath)
	cfg.Tools.BclCompressor.PythonBinary = expandTilde(cfg.Tools.BclCompressor.PythonBinary)
	cfg.Tools.BclCompressor.ScriptPath = expandTilde(cfg.Tools.BclCompressor.ScriptPath)
	return &cfg, nil
}

func expandTilde(p string) string {
	ep, err := expandPath(p)
	if err != nil {
		return p
	}
	return ep
}

func expandPaths(ps []string) []string {
	out := make([]string, 0, len(ps))
	for _, p := range ps {
		out = append(out, expandTilde(p))
	}
	return out
}

func expandPath(p string) (string, error) {
	if p == "" {
		return "", nil
	}
	if strings.HasPrefix(p, "~") {
		home, err := os.UserHomeDir()
		if err != nil {
			return "", err
		}
		if p == "~" {
			return home, nil
		}
		if strings.HasPrefix(p, "~/") {
			return filepath.Join(home, p[2:]), nil
		}
	}
	return p, nil
}

// DefaultConfigPath returns the default config file location.
func DefaultConfigPath() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return "dom_mcp.toml"
	}
	return filepath.Join(home, ".config", "devin", "dom_mcp.toml")
}
