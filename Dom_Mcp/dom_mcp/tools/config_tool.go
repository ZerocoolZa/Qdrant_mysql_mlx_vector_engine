package tools

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"

	"github.com/BurntSushi/toml"
)

// ConfigModule provides tools for reading and updating the dom_mcp config
// at runtime, so the AI can self-heal configuration errors (e.g. set
// pinecone host when search fails, set gmail env hints, etc.).
type ConfigModule struct {
	mu         sync.Mutex
	configPath string
}

// NewConfigModule creates a config management module.
// configPath is the path to the dom_mcp.toml file.
func NewConfigModule(configPath string) *ConfigModule {
	return &ConfigModule{configPath: configPath}
}

func (m *ConfigModule) Name() string { return "config" }

func (m *ConfigModule) Tools() []Tool {
	return []Tool{
		&configGetTool{m: m},
		&configSetTool{m: m},
		&configListTool{m: m},
		&configReloadTool{m: m},
	}
}

// loadConfigMap reads the TOML file into a nested map for generic access.
func (m *ConfigModule) loadConfigMap() (map[string]any, error) {
	data, err := os.ReadFile(m.configPath)
	if err != nil {
		return nil, fmt.Errorf("read config %s: %w", m.configPath, err)
	}
	var cfg map[string]any
	if _, err := toml.Decode(string(data), &cfg); err != nil {
		return nil, fmt.Errorf("decode toml: %w", err)
	}
	return cfg, nil
}

// saveConfigMap writes a nested map back to the TOML file.
// We use a simple encoder that handles nested tables and key-value pairs.
func (m *ConfigModule) saveConfigMap(cfg map[string]any) error {
	var sb strings.Builder
	if err := writeTomlTable(&sb, "", cfg); err != nil {
		return err
	}
	// Write atomically: write to temp then rename.
	tmp := m.configPath + ".tmp"
	if err := os.WriteFile(tmp, []byte(sb.String()), 0644); err != nil {
		return fmt.Errorf("write temp config: %w", err)
	}
	if err := os.Rename(tmp, m.configPath); err != nil {
		return fmt.Errorf("rename config: %w", err)
	}
	return nil
}

// writeTomlTable recursively writes a TOML table. prefix is the dotted path
// (e.g. "tools.pinecone"). Top-level call uses prefix="".
func writeTomlTable(sb *strings.Builder, prefix string, m map[string]any) error {
	// First pass: write scalar values at this level.
	for k, v := range m {
		if isScalarValue(v) {
			writeTomlKeyValue(sb, k, v)
		}
	}
	// Second pass: write nested tables.
	for k, v := range m {
		nested, ok := v.(map[string]any)
		if !ok {
			continue
		}
		var fullKey string
		if prefix == "" {
			fullKey = k
		} else {
			fullKey = prefix + "." + k
		}
		sb.WriteString("\n[")
		sb.WriteString(fullKey)
		sb.WriteString("]\n")
		if err := writeTomlTable(sb, fullKey, nested); err != nil {
			return err
		}
	}
	return nil
}

func isScalarValue(v any) bool {
	switch v.(type) {
	case map[string]any:
		return false
	case []any:
		return false
	default:
		return true
	}
}

func writeTomlKeyValue(sb *strings.Builder, key string, val any) {
	sb.WriteString(key)
	sb.WriteString(" = ")
	switch v := val.(type) {
	case string:
		// Quote strings, escaping backslashes and double quotes.
		escaped := strings.ReplaceAll(v, "\\", "\\\\")
		escaped = strings.ReplaceAll(escaped, "\"", "\\\"")
		sb.WriteString("\"")
		sb.WriteString(escaped)
		sb.WriteString("\"")
	case bool:
		if v {
			sb.WriteString("true")
		} else {
			sb.WriteString("false")
		}
	case int:
		sb.WriteString(fmt.Sprintf("%d", v))
	case int64:
		sb.WriteString(fmt.Sprintf("%d", v))
	case float64:
		sb.WriteString(fmt.Sprintf("%g", v))
	case []any:
		// Write as TOML array
		sb.WriteString("[")
		for i, item := range v {
			if i > 0 {
				sb.WriteString(", ")
			}
			if s, ok := item.(string); ok {
				sb.WriteString("\"")
				sb.WriteString(s)
				sb.WriteString("\"")
			} else {
				sb.WriteString(fmt.Sprintf("%v", item))
			}
		}
		sb.WriteString("]")
	default:
		sb.WriteString(fmt.Sprintf("%v", v))
	}
	sb.WriteString("\n")
}

// resolveSection navigates to a nested table by dotted path (e.g. "tools.pinecone").
// Returns the map at that path, or nil if not found.
func resolveSection(cfg map[string]any, section string) map[string]any {
	if section == "" {
		return cfg
	}
	parts := strings.Split(section, ".")
	current := cfg
	for _, p := range parts {
		next, ok := current[p]
		if !ok {
			return nil
		}
		current, ok = next.(map[string]any)
		if !ok {
			return nil
		}
	}
	return current
}

// --- config_get ---

type configGetTool struct{ m *ConfigModule }

func (t *configGetTool) Name() string { return "config_get" }
func (t *configGetTool) Description() string {
	return "Read a config value from the dom_mcp TOML config. Pass section (e.g. 'tools.pinecone') and key (e.g. 'host'). Returns the current value."
}
func (t *configGetTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"section": Prop("string", "Dotted section path (e.g. 'tools.pinecone', 'tools.contextram', 'server')."),
		"key":     Prop("string", "The config key to read (e.g. 'host', 'index', 'api_key')."),
	}, []string{"section", "key"})
}
func (t *configGetTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	section := ArgString(args, "section")
	key := ArgString(args, "key")
	if key == "" {
		return NewErrorResult("key is required")
	}
	cfg, err := t.m.loadConfigMap()
	if err != nil {
		return NewErrorResult(err.Error())
	}
	sec := resolveSection(cfg, section)
	if sec == nil {
		return NewErrorResult(fmt.Sprintf("section '%s' not found in config", section))
	}
	val, ok := sec[key]
	if !ok {
		return NewErrorResult(fmt.Sprintf("key '%s' not found in section '%s'", key, section))
	}
	return NewTextResult(fmt.Sprintf("%v", val))
}

// --- config_set ---

type configSetTool struct{ m *ConfigModule }

func (t *configSetTool) Name() string { return "config_set" }
func (t *configSetTool) Description() string {
	return "Set a config value in the dom_mcp TOML config file. Pass section (e.g. 'tools.pinecone'), key (e.g. 'host'), and value. The file is written atomically. Use this to self-heal config errors (e.g. set pinecone host when search fails). Changes take effect on next server restart."
}
func (t *configSetTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"section": Prop("string", "Dotted section path (e.g. 'tools.pinecone', 'tools.contextram')."),
		"key":     Prop("string", "The config key to set (e.g. 'host', 'index', 'api_key')."),
		"value":   Prop("string", "The value to set (strings, numbers, booleans all passed as string)."),
		"type":    Prop("string", "Value type: 'string' (default), 'int', 'bool'."),
	}, []string{"section", "key", "value"})
}
func (t *configSetTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	t.m.mu.Lock()
	defer t.m.mu.Unlock()

	section := ArgString(args, "section")
	key := ArgString(args, "key")
	valueStr := ArgString(args, "value")
	valType := ArgString(args, "type")
	if valType == "" {
		valType = "string"
	}

	if key == "" || valueStr == "" {
		return NewErrorResult("key and value are required")
	}

	cfg, err := t.m.loadConfigMap()
	if err != nil {
		return NewErrorResult(err.Error())
	}

	// Navigate to or create the section.
	parts := []string{}
	if section != "" {
		parts = strings.Split(section, ".")
	}
	current := cfg
	for _, p := range parts {
		next, ok := current[p]
		if !ok {
			// Create the section if it doesn't exist.
			newSec := make(map[string]any)
			current[p] = newSec
			current = newSec
		} else {
			current, ok = next.(map[string]any)
			if !ok {
				return NewErrorResult(fmt.Sprintf("section '%s' is not a table", p))
			}
		}
	}

	// Convert value based on type.
	var val any
	switch valType {
	case "int":
		var n int
		if _, err := fmt.Sscanf(valueStr, "%d", &n); err != nil {
			return NewErrorResult(fmt.Sprintf("cannot parse '%s' as int: %v", valueStr, err))
		}
		val = n
	case "bool":
		lower := strings.ToLower(valueStr)
		if lower == "true" || lower == "1" || lower == "yes" {
			val = true
		} else if lower == "false" || lower == "0" || lower == "no" {
			val = false
		} else {
			return NewErrorResult(fmt.Sprintf("cannot parse '%s' as bool (use true/false)", valueStr))
		}
	default:
		val = valueStr
	}

	current[key] = val

	if err := t.m.saveConfigMap(cfg); err != nil {
		return NewErrorResult(err.Error())
	}

	return NewTextResult(fmt.Sprintf("Config updated: [%s] %s = %v\nChanges take effect on next server restart.", section, key, val))
}

// --- config_list ---

type configListTool struct{ m *ConfigModule }

func (t *configListTool) Name() string { return "config_list" }
func (t *configListTool) Description() string {
	return "List all keys in a config section (e.g. 'tools.pinecone'). Pass section='tools' to list all tool sections. Omit section to list top-level config."
}
func (t *configListTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"section": Prop("string", "Dotted section path to list (e.g. 'tools.pinecone'). Omit to list entire config."),
	}, nil)
}
func (t *configListTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	section := ArgString(args, "section")
	cfg, err := t.m.loadConfigMap()
	if err != nil {
		return NewErrorResult(err.Error())
	}
	sec := resolveSection(cfg, section)
	if sec == nil {
		return NewErrorResult(fmt.Sprintf("section '%s' not found", section))
	}
	var sb strings.Builder
	for k, v := range sec {
		if isScalarValue(v) {
			sb.WriteString(fmt.Sprintf("  %s = %v\n", k, v))
		} else {
			sb.WriteString(fmt.Sprintf("  %s = (table)\n", k))
		}
	}
	return NewTextResult(strings.TrimRight(sb.String(), "\n"))
}

// --- config_reload ---

type configReloadTool struct{ m *ConfigModule }

func (t *configReloadTool) Name() string { return "config_reload" }
func (t *configReloadTool) Description() string {
	return "Reload and display the full current config file. Use after config_set to verify changes were saved."
}
func (t *configReloadTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{}, nil)
}
func (t *configReloadTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	data, err := os.ReadFile(t.m.configPath)
	if err != nil {
		return NewErrorResult(fmt.Sprintf("read config: %v", err))
	}
	return NewTextResult(string(data))
}

// expandTildeForConfig expands ~ in a config path (used by main.go).
func expandTildeForConfig(p string) string {
	if p == "" {
		return p
	}
	if strings.HasPrefix(p, "~") {
		home, err := os.UserHomeDir()
		if err == nil {
			if p == "~" {
				return home
			}
			if strings.HasPrefix(p, "~/") {
				return filepath.Join(home, p[2:])
			}
		}
	}
	return p
}
