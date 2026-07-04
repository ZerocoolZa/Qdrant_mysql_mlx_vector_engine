package tools

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
)

// ToolResult is the structured result returned by a Tool's Execute method.
// It is converted to MCP CallToolResult content by the registry.
type ToolResult struct {
	// Content is a list of text blocks to return to the client.
	Content []string
	// IsError marks this as a tool-level error (not a protocol error).
	IsError bool
	// Structured is optional structured JSON output.
	Structured any
}

// NewTextResult is a convenience constructor for a single text content block.
func NewTextResult(text string) *ToolResult {
	return &ToolResult{Content: []string{text}}
}

// NewErrorResult returns an error tool result.
func NewErrorResult(msg string) *ToolResult {
	return &ToolResult{Content: []string{msg}, IsError: true}
}

// Tool is the interface every tool module implements.
// Adding a new tool = implementing this interface and registering it.
type Tool interface {
	// Name is the unique MCP tool name (e.g. "read_file").
	Name() string
	// Description is the human-readable tool description.
	Description() string
	// InputSchema returns the JSON Schema (as map[string]any) for the tool input.
	InputSchema() map[string]any
	// Execute runs the tool with the given JSON-decoded arguments.
	Execute(ctx context.Context, args map[string]any) *ToolResult
}

// Module is a set of tools provided by one source file (e.g. filesystem.go).
// A module is constructed from its config and returns its tool list.
type Module interface {
	// Name is the module identifier (matches the [tools.X] config key).
	Name() string
	// Tools returns all tools this module provides.
	Tools() []Tool
}

// Registry maps tool names to Tool implementations.
type Registry struct {
	mu    sync.RWMutex
	tools map[string]Tool
}

// NewRegistry creates an empty tool registry.
func NewRegistry() *Registry {
	return &Registry{tools: make(map[string]Tool)}
}

// Register adds a module's tools to the registry.
func (r *Registry) Register(m Module) {
	r.mu.Lock()
	defer r.mu.Unlock()
	for _, t := range m.Tools() {
		r.tools[t.Name()] = t
	}
}

// Get returns a tool by name, or nil if not found.
func (r *Registry) Get(name string) Tool {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return r.tools[name]
}

// List returns all registered tools.
func (r *Registry) List() []Tool {
	r.mu.RLock()
	defer r.mu.RUnlock()
	out := make([]Tool, 0, len(r.tools))
	for _, t := range r.tools {
		out = append(out, t)
	}
	return out
}

// --- Helpers for building JSON schemas ---

// Schema builds a JSON Schema object map for an object type.
func Schema(props map[string]map[string]any, required []string) map[string]any {
	properties := make(map[string]any, len(props))
	for k, v := range props {
		properties[k] = v
	}
	s := map[string]any{
		"type":       "object",
		"properties": properties,
	}
	if len(required) > 0 {
		s["required"] = required
	}
	return s
}

// Prop builds a property descriptor for a JSON Schema.
func Prop(typ string, desc string) map[string]any {
	return map[string]any{"type": typ, "description": desc}
}

// PropEnum builds a string property with an enum constraint.
func PropEnum(desc string, values ...string) map[string]any {
	enums := make([]any, len(values))
	for i, v := range values {
		enums[i] = v
	}
	return map[string]any{"type": "string", "description": desc, "enum": enums}
}

// PropArray builds an array property.
func PropArray(itemType string, desc string) map[string]any {
	return map[string]any{
		"type":        "array",
		"description": desc,
		"items":       map[string]any{"type": itemType},
	}
}

// ArgString extracts a string argument, returning "" if missing or wrong type.
func ArgString(args map[string]any, key string) string {
	v, ok := args[key]
	if !ok {
		return ""
	}
	s, _ := v.(string)
	return s
}

// ArgInt extracts an int argument with a default.
func ArgInt(args map[string]any, key string, def int) int {
	v, ok := args[key]
	if !ok {
		return def
	}
	switch n := v.(type) {
	case float64:
		return int(n)
	case int:
		return n
	case int64:
		return int(n)
	}
	return def
}

// ArgArray extracts a []any argument.
func ArgArray(args map[string]any, key string) []any {
	v, ok := args[key]
	if !ok {
		return nil
	}
	a, _ := v.([]any)
	return a
}

// ArgBool extracts a bool argument (default false).
func ArgBool(args map[string]any, key string) bool {
	v, ok := args[key]
	if !ok {
		return false
	}
	b, _ := v.(bool)
	return b
}

// ArgFloat extracts a float64 argument with a default.
func ArgFloat(args map[string]any, key string) float64 {
	v, ok := args[key]
	if !ok {
		return 0
	}
	switch n := v.(type) {
	case float64:
		return n
	case int:
		return float64(n)
	case int64:
		return float64(n)
	}
	return 0
}

// ArgStringArray extracts a []string argument.
func ArgStringArray(args map[string]any, key string) []string {
	a := ArgArray(args, key)
	out := make([]string, 0, len(a))
	for _, v := range a {
		if s, ok := v.(string); ok {
			out = append(out, s)
		}
	}
	return out
}

// JSONString marshals a value to indented JSON, returning a text result.
func JSONResult(v any) *ToolResult {
	data, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return NewErrorResult(fmt.Sprintf("marshal error: %v", err))
	}
	return NewTextResult(string(data))
}
