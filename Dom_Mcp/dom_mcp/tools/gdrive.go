package tools

import (
	"context"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

// GdriveModule provides tools for working with Google Drive files via the
// Google Drive for Desktop local mount.
type GdriveModule struct {
	rootPath string
}

// NewGdriveModule creates a gdrive module from the mounted drive root path.
func NewGdriveModule(rootPath string) *GdriveModule {
	return &GdriveModule{rootPath: rootPath}
}

func (m *GdriveModule) Name() string { return "gdrive" }

func (m *GdriveModule) Tools() []Tool {
	return []Tool{
		&gdriveListTool{m: m},
		&gdriveSearchTool{m: m},
		&gdriveReadTool{m: m},
		&gdriveWriteTool{m: m},
		&gdriveMoveTool{m: m},
		&gdriveDeleteTool{m: m},
		&gdriveInfoTool{m: m},
		&gdriveCreateFolderTool{m: m},
	}
}

// resolve joins a relative path with the root mount path. If path is empty,
// the root path itself is returned.
func (m *GdriveModule) resolve(path string) string {
	if path == "" {
		return m.rootPath
	}
	if filepath.IsAbs(path) {
		return path
	}
	return filepath.Join(m.rootPath, path)
}

// ensureRoot checks that the root path is configured and exists.
func (m *GdriveModule) ensureRoot() error {
	if m.rootPath == "" {
		return fmt.Errorf("no root_path configured for gdrive module")
	}
	if _, err := os.Stat(m.rootPath); err != nil {
		return fmt.Errorf("gdrive root path not accessible: %v", err)
	}
	return nil
}

// --- gdrive_list ---

type gdriveListTool struct{ m *GdriveModule }

func (t *gdriveListTool) Name() string { return "gdrive_list" }
func (t *gdriveListTool) Description() string {
	return "List files and folders in a Google Drive directory. Defaults to the root of the mounted drive."
}
func (t *gdriveListTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"path": Prop("string", "Relative path within the mounted Google Drive (default: root)."),
	}, nil)
}
func (t *gdriveListTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	if err := t.m.ensureRoot(); err != nil {
		return NewErrorResult(err.Error())
	}
	path := t.m.resolve(ArgString(args, "path"))
	entries, err := os.ReadDir(path)
	if err != nil {
		return NewErrorResult(fmt.Sprintf("list dir: %v", err))
	}
	var lines []string
	for _, e := range entries {
		typ := "FILE"
		if e.IsDir() {
			typ = "DIR"
		}
		lines = append(lines, fmt.Sprintf("[%s] %s", typ, e.Name()))
	}
	sort.Strings(lines)
	return NewTextResult(strings.Join(lines, "\n"))
}

// --- gdrive_search ---

type gdriveSearchTool struct{ m *GdriveModule }

func (t *gdriveSearchTool) Name() string { return "gdrive_search" }
func (t *gdriveSearchTool) Description() string {
	return "Search for files by name in the mounted Google Drive. Matches filenames against a glob pattern."
}
func (t *gdriveSearchTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"pattern": Prop("string", "Glob pattern to match filenames (e.g. *.pdf)."),
		"path":    Prop("string", "Relative path within the mounted drive to search from (default: root)."),
	}, []string{"pattern"})
}
func (t *gdriveSearchTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	if err := t.m.ensureRoot(); err != nil {
		return NewErrorResult(err.Error())
	}
	pattern := ArgString(args, "pattern")
	if pattern == "" {
		return NewErrorResult("pattern is required")
	}
	path := t.m.resolve(ArgString(args, "path"))
	var matches []string
	err := filepath.WalkDir(path, func(p string, d fs.DirEntry, err error) error {
		if err != nil {
			return nil
		}
		matched, _ := filepath.Match(pattern, d.Name())
		if matched {
			rel, rerr := filepath.Rel(t.m.rootPath, p)
			if rerr != nil {
				rel = p
			}
			matches = append(matches, rel)
		}
		return nil
	})
	if err != nil {
		return NewErrorResult(fmt.Sprintf("search: %v", err))
	}
	if len(matches) == 0 {
		return NewTextResult("No matches found.")
	}
	sort.Strings(matches)
	return NewTextResult(strings.Join(matches, "\n"))
}

// --- gdrive_read ---

type gdriveReadTool struct{ m *GdriveModule }

func (t *gdriveReadTool) Name() string { return "gdrive_read" }
func (t *gdriveReadTool) Description() string {
	return "Read the complete contents of a file from Google Drive."
}
func (t *gdriveReadTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"path": Prop("string", "Relative path within the mounted Google Drive to the file."),
	}, []string{"path"})
}
func (t *gdriveReadTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	if err := t.m.ensureRoot(); err != nil {
		return NewErrorResult(err.Error())
	}
	path := ArgString(args, "path")
	if path == "" {
		return NewErrorResult("path is required")
	}
	full := t.m.resolve(path)
	data, err := os.ReadFile(full)
	if err != nil {
		return NewErrorResult(fmt.Sprintf("read file: %v", err))
	}
	return NewTextResult(string(data))
}

// --- gdrive_write ---

type gdriveWriteTool struct{ m *GdriveModule }

func (t *gdriveWriteTool) Name() string { return "gdrive_write" }
func (t *gdriveWriteTool) Description() string {
	return "Create or overwrite a file in Google Drive with the given content."
}
func (t *gdriveWriteTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"path":    Prop("string", "Relative path within the mounted Google Drive for the file."),
		"content": Prop("string", "The complete content to write to the file."),
	}, []string{"path", "content"})
}
func (t *gdriveWriteTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	if err := t.m.ensureRoot(); err != nil {
		return NewErrorResult(err.Error())
	}
	path := ArgString(args, "path")
	content := ArgString(args, "content")
	if path == "" {
		return NewErrorResult("path is required")
	}
	full := t.m.resolve(path)
	if err := os.MkdirAll(filepath.Dir(full), 0o755); err != nil {
		return NewErrorResult(fmt.Sprintf("mkdir: %v", err))
	}
	if err := os.WriteFile(full, []byte(content), 0o644); err != nil {
		return NewErrorResult(fmt.Sprintf("write file: %v", err))
	}
	return NewTextResult(fmt.Sprintf("Successfully wrote %d bytes to %s", len(content), path))
}

// --- gdrive_move ---

type gdriveMoveTool struct{ m *GdriveModule }

func (t *gdriveMoveTool) Name() string { return "gdrive_move" }
func (t *gdriveMoveTool) Description() string {
	return "Move or rename a file or folder in Google Drive."
}
func (t *gdriveMoveTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"src": Prop("string", "Source relative path within the mounted Google Drive."),
		"dst": Prop("string", "Destination relative path within the mounted Google Drive."),
	}, []string{"src", "dst"})
}
func (t *gdriveMoveTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	if err := t.m.ensureRoot(); err != nil {
		return NewErrorResult(err.Error())
	}
	src := ArgString(args, "src")
	dst := ArgString(args, "dst")
	if src == "" || dst == "" {
		return NewErrorResult("src and dst are required")
	}
	fullSrc := t.m.resolve(src)
	fullDst := t.m.resolve(dst)
	if err := os.MkdirAll(filepath.Dir(fullDst), 0o755); err != nil {
		return NewErrorResult(fmt.Sprintf("mkdir: %v", err))
	}
	if err := os.Rename(fullSrc, fullDst); err != nil {
		return NewErrorResult(fmt.Sprintf("move: %v", err))
	}
	return NewTextResult(fmt.Sprintf("Successfully moved %s to %s", src, dst))
}

// --- gdrive_delete ---

type gdriveDeleteTool struct{ m *GdriveModule }

func (t *gdriveDeleteTool) Name() string { return "gdrive_delete" }
func (t *gdriveDeleteTool) Description() string {
	return "Delete a file or folder from Google Drive. Folders must be empty."
}
func (t *gdriveDeleteTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"path": Prop("string", "Relative path within the mounted Google Drive to delete."),
	}, []string{"path"})
}
func (t *gdriveDeleteTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	if err := t.m.ensureRoot(); err != nil {
		return NewErrorResult(err.Error())
	}
	path := ArgString(args, "path")
	if path == "" {
		return NewErrorResult("path is required")
	}
	full := t.m.resolve(path)
	if err := os.Remove(full); err != nil {
		return NewErrorResult(fmt.Sprintf("delete: %v", err))
	}
	return NewTextResult(fmt.Sprintf("Successfully deleted %s", path))
}

// --- gdrive_info ---

type gdriveInfoTool struct{ m *GdriveModule }

func (t *gdriveInfoTool) Name() string { return "gdrive_info" }
func (t *gdriveInfoTool) Description() string {
	return "Get metadata for a Google Drive file or folder: size, modified date, type."
}
func (t *gdriveInfoTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"path": Prop("string", "Relative path within the mounted Google Drive."),
	}, []string{"path"})
}
func (t *gdriveInfoTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	if err := t.m.ensureRoot(); err != nil {
		return NewErrorResult(err.Error())
	}
	path := ArgString(args, "path")
	if path == "" {
		return NewErrorResult("path is required")
	}
	full := t.m.resolve(path)
	info, err := os.Stat(full)
	if err != nil {
		return NewErrorResult(fmt.Sprintf("stat: %v", err))
	}
	typ := "file"
	if info.IsDir() {
		typ = "folder"
	}
	return JSONResult(map[string]any{
		"path":    path,
		"type":    typ,
		"size":    info.Size(),
		"mode":    info.Mode().String(),
		"modTime": info.ModTime().Format(time.RFC3339),
		"isDir":   info.IsDir(),
	})
}

// --- gdrive_create_folder ---

type gdriveCreateFolderTool struct{ m *GdriveModule }

func (t *gdriveCreateFolderTool) Name() string { return "gdrive_create_folder" }
func (t *gdriveCreateFolderTool) Description() string {
	return "Create a new folder in Google Drive (like mkdir -p)."
}
func (t *gdriveCreateFolderTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"path": Prop("string", "Relative path within the mounted Google Drive for the new folder."),
	}, []string{"path"})
}
func (t *gdriveCreateFolderTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	if err := t.m.ensureRoot(); err != nil {
		return NewErrorResult(err.Error())
	}
	path := ArgString(args, "path")
	if path == "" {
		return NewErrorResult("path is required")
	}
	full := t.m.resolve(path)
	if err := os.MkdirAll(full, 0o755); err != nil {
		return NewErrorResult(fmt.Sprintf("mkdir: %v", err))
	}
	return NewTextResult(fmt.Sprintf("Successfully created folder %s", path))
}
