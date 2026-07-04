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

// FilesystemModule provides native filesystem tools using os and path/filepath.
type FilesystemModule struct {
	allowedDirs []string
}

// NewFilesystemModule creates a filesystem module from config.
func NewFilesystemModule(allowedDirs []string) *FilesystemModule {
	return &FilesystemModule{allowedDirs: allowedDirs}
}

func (m *FilesystemModule) Name() string { return "filesystem" }

func (m *FilesystemModule) Tools() []Tool {
	return []Tool{
		&readFileTool{m: m},
		&readMultipleFilesTool{m: m},
		&writeFileTool{m: m},
		&modifyFileTool{m: m},
		&listDirectoryTool{m: m},
		&searchFilesTool{m: m},
		&searchWithinFilesTool{m: m},
		&createDirectoryTool{m: m},
		&moveFileTool{m: m},
		&copyFileTool{m: m},
		&deleteFileTool{m: m},
		&getFileInfoTool{m: m},
		&listAllowedDirsTool{m: m},
		&treeTool{m: m},
	}
}

// isAllowed checks that the resolved path is inside one of the allowed dirs.
func (m *FilesystemModule) isAllowed(path string) bool {
	abs, err := filepath.Abs(path)
	if err != nil {
		return false
	}
	for _, dir := range m.allowedDirs {
		ad, err := filepath.Abs(dir)
		if err != nil {
			continue
		}
		if strings.HasPrefix(abs+string(filepath.Separator), ad+string(filepath.Separator)) || abs == ad {
			return true
		}
	}
	return false
}

func (m *FilesystemModule) ensureAllowed(path string) error {
	if len(m.allowedDirs) == 0 {
		return fmt.Errorf("no allowed_dirs configured")
	}
	if !m.isAllowed(path) {
		return fmt.Errorf("path %s is outside allowed directories", path)
	}
	return nil
}

// --- read_file ---

type readFileTool struct{ m *FilesystemModule }

func (t *readFileTool) Name() string { return "read_file" }
func (t *readFileTool) Description() string {
	return "Read the complete contents of a file. Returns the file content as text."
}
func (t *readFileTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"path": Prop("string", "Absolute or relative path to the file to read."),
	}, []string{"path"})
}
func (t *readFileTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	path := ArgString(args, "path")
	if path == "" {
		return NewErrorResult("path is required")
	}
	if err := t.m.ensureAllowed(path); err != nil {
		return NewErrorResult(err.Error())
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return NewErrorResult(fmt.Sprintf("read file: %v", err))
	}
	return NewTextResult(string(data))
}

// --- write_file ---

type writeFileTool struct{ m *FilesystemModule }

func (t *writeFileTool) Name() string { return "write_file" }
func (t *writeFileTool) Description() string {
	return "Create a new file or completely overwrite an existing file with the given content."
}
func (t *writeFileTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"path":    Prop("string", "Path to the file to write."),
		"content": Prop("string", "The complete content to write to the file."),
	}, []string{"path", "content"})
}
func (t *writeFileTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	path := ArgString(args, "path")
	content := ArgString(args, "content")
	if path == "" {
		return NewErrorResult("path is required")
	}
	if err := t.m.ensureAllowed(path); err != nil {
		return NewErrorResult(err.Error())
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return NewErrorResult(fmt.Sprintf("mkdir: %v", err))
	}
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		return NewErrorResult(fmt.Sprintf("write file: %v", err))
	}
	return NewTextResult(fmt.Sprintf("Successfully wrote %d bytes to %s", len(content), path))
}

// --- list_directory ---

type listDirectoryTool struct{ m *FilesystemModule }

func (t *listDirectoryTool) Name() string { return "list_directory" }
func (t *listDirectoryTool) Description() string {
	return "Get a detailed listing of all files and directories in a specified path."
}
func (t *listDirectoryTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"path": Prop("string", "Path to the directory to list."),
	}, []string{"path"})
}
func (t *listDirectoryTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	path := ArgString(args, "path")
	if path == "" {
		return NewErrorResult("path is required")
	}
	if err := t.m.ensureAllowed(path); err != nil {
		return NewErrorResult(err.Error())
	}
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

// --- search_files ---

type searchFilesTool struct{ m *FilesystemModule }

func (t *searchFilesTool) Name() string { return "search_files" }
func (t *searchFilesTool) Description() string {
	return "Recursively find files matching a pattern. Returns matching file paths."
}
func (t *searchFilesTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"path":    Prop("string", "Starting directory for the search."),
		"pattern": Prop("string", "Glob pattern to match filenames (e.g. *.go)."),
	}, []string{"path", "pattern"})
}
func (t *searchFilesTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	path := ArgString(args, "path")
	pattern := ArgString(args, "pattern")
	if path == "" || pattern == "" {
		return NewErrorResult("path and pattern are required")
	}
	if err := t.m.ensureAllowed(path); err != nil {
		return NewErrorResult(err.Error())
	}
	var matches []string
	err := filepath.WalkDir(path, func(p string, d fs.DirEntry, err error) error {
		if err != nil {
			return nil
		}
		matched, _ := filepath.Match(pattern, d.Name())
		if matched {
			matches = append(matches, p)
		}
		return nil
	})
	if err != nil {
		return NewErrorResult(fmt.Sprintf("search: %v", err))
	}
	if len(matches) == 0 {
		return NewTextResult("No matches found.")
	}
	return NewTextResult(strings.Join(matches, "\n"))
}

// --- create_directory ---

type createDirectoryTool struct{ m *FilesystemModule }

func (t *createDirectoryTool) Name() string { return "create_directory" }
func (t *createDirectoryTool) Description() string {
	return "Create a new directory or ensure a directory path exists (like mkdir -p)."
}
func (t *createDirectoryTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"path": Prop("string", "Path to the directory to create."),
	}, []string{"path"})
}
func (t *createDirectoryTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	path := ArgString(args, "path")
	if path == "" {
		return NewErrorResult("path is required")
	}
	if err := t.m.ensureAllowed(path); err != nil {
		return NewErrorResult(err.Error())
	}
	if err := os.MkdirAll(path, 0o755); err != nil {
		return NewErrorResult(fmt.Sprintf("mkdir: %v", err))
	}
	return NewTextResult(fmt.Sprintf("Successfully created directory %s", path))
}

// --- move_file ---

type moveFileTool struct{ m *FilesystemModule }

func (t *moveFileTool) Name() string { return "move_file" }
func (t *moveFileTool) Description() string {
	return "Move or rename a file or directory. The source must exist; the destination must not."
}
func (t *moveFileTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"src": Prop("string", "Source path."),
		"dst": Prop("string", "Destination path."),
	}, []string{"src", "dst"})
}
func (t *moveFileTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	src := ArgString(args, "src")
	dst := ArgString(args, "dst")
	if src == "" || dst == "" {
		return NewErrorResult("src and dst are required")
	}
	if err := t.m.ensureAllowed(src); err != nil {
		return NewErrorResult(err.Error())
	}
	if err := t.m.ensureAllowed(dst); err != nil {
		return NewErrorResult(err.Error())
	}
	if err := os.Rename(src, dst); err != nil {
		return NewErrorResult(fmt.Sprintf("move: %v", err))
	}
	return NewTextResult(fmt.Sprintf("Successfully moved %s to %s", src, dst))
}

// --- get_file_info ---

type getFileInfoTool struct{ m *FilesystemModule }

func (t *getFileInfoTool) Name() string { return "get_file_info" }
func (t *getFileInfoTool) Description() string {
	return "Retrieve detailed metadata about a file or directory."
}
func (t *getFileInfoTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"path": Prop("string", "Path to the file or directory."),
	}, []string{"path"})
}
func (t *getFileInfoTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	path := ArgString(args, "path")
	if path == "" {
		return NewErrorResult("path is required")
	}
	if err := t.m.ensureAllowed(path); err != nil {
		return NewErrorResult(err.Error())
	}
	info, err := os.Stat(path)
	if err != nil {
		return NewErrorResult(fmt.Sprintf("stat: %v", err))
	}
	typ := "file"
	if info.IsDir() {
		typ = "directory"
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

// --- read_multiple_files ---

type readMultipleFilesTool struct{ m *FilesystemModule }

func (t *readMultipleFilesTool) Name() string { return "read_multiple_files" }
func (t *readMultipleFilesTool) Description() string {
	return "Read the contents of multiple files simultaneously. Returns each file's content."
}
func (t *readMultipleFilesTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"paths": PropArray("string", "List of file paths to read."),
	}, []string{"paths"})
}
func (t *readMultipleFilesTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	paths := ArgArray(args, "paths")
	if len(paths) == 0 {
		return NewErrorResult("paths is required")
	}
	var sb strings.Builder
	for _, p := range paths {
		path, ok := p.(string)
		if !ok {
			continue
		}
		if err := t.m.ensureAllowed(path); err != nil {
			sb.WriteString(fmt.Sprintf("--- %s ---\nERROR: %v\n\n", path, err))
			continue
		}
		data, err := os.ReadFile(path)
		if err != nil {
			sb.WriteString(fmt.Sprintf("--- %s ---\nERROR: %v\n\n", path, err))
			continue
		}
		sb.WriteString(fmt.Sprintf("--- %s ---\n%s\n\n", path, string(data)))
	}
	return NewTextResult(sb.String())
}

// --- modify_file ---

type modifyFileTool struct{ m *FilesystemModule }

func (t *modifyFileTool) Name() string { return "modify_file" }
func (t *modifyFileTool) Description() string {
	return "Modify a file by replacing old_string with new_string. If replace_all is true, replaces all occurrences."
}
func (t *modifyFileTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"path":        Prop("string", "Path to the file to modify."),
		"old_string":  Prop("string", "Text to find in the file."),
		"new_string":  Prop("string", "Replacement text."),
		"replace_all": Prop("boolean", "Replace all occurrences (default false)."),
	}, []string{"path", "old_string", "new_string"})
}
func (t *modifyFileTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	path := ArgString(args, "path")
	oldStr := ArgString(args, "old_string")
	newStr := ArgString(args, "new_string")
	if path == "" || oldStr == "" {
		return NewErrorResult("path and old_string are required")
	}
	if err := t.m.ensureAllowed(path); err != nil {
		return NewErrorResult(err.Error())
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return NewErrorResult(fmt.Sprintf("read: %v", err))
	}
	content := string(data)
	replaceAll := false
	if v, ok := args["replace_all"]; ok {
		if b, ok := v.(bool); ok {
			replaceAll = b
		}
	}
	if replaceAll {
		content = strings.ReplaceAll(content, oldStr, newStr)
	} else {
		content = strings.Replace(content, oldStr, newStr, 1)
	}
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		return NewErrorResult(fmt.Sprintf("write: %v", err))
	}
	return NewTextResult(fmt.Sprintf("Successfully modified %s", path))
}

// --- search_within_files ---

type searchWithinFilesTool struct{ m *FilesystemModule }

func (t *searchWithinFilesTool) Name() string { return "search_within_files" }
func (t *searchWithinFilesTool) Description() string {
	return "Search for text within files in a directory. Returns matching lines with file paths and line numbers."
}
func (t *searchWithinFilesTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"path":    Prop("string", "Directory to search in."),
		"pattern": Prop("string", "Text pattern to search for within file contents."),
	}, []string{"path", "pattern"})
}
func (t *searchWithinFilesTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	path := ArgString(args, "path")
	pattern := ArgString(args, "pattern")
	if path == "" || pattern == "" {
		return NewErrorResult("path and pattern are required")
	}
	if err := t.m.ensureAllowed(path); err != nil {
		return NewErrorResult(err.Error())
	}
	var results []string
	filepath.WalkDir(path, func(p string, d fs.DirEntry, err error) error {
		if err != nil || d.IsDir() {
			return nil
		}
		data, err := os.ReadFile(p)
		if err != nil {
			return nil
		}
		lines := strings.Split(string(data), "\n")
		for i, line := range lines {
			if strings.Contains(line, pattern) {
				results = append(results, fmt.Sprintf("%s:%d: %s", p, i+1, strings.TrimSpace(line)))
			}
		}
		return nil
	})
	if len(results) == 0 {
		return NewTextResult("No matches found.")
	}
	return NewTextResult(strings.Join(results, "\n"))
}

// --- copy_file ---

type copyFileTool struct{ m *FilesystemModule }

func (t *copyFileTool) Name() string { return "copy_file" }
func (t *copyFileTool) Description() string {
	return "Copy a file or directory from source to destination."
}
func (t *copyFileTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"src": Prop("string", "Source path."),
		"dst": Prop("string", "Destination path."),
	}, []string{"src", "dst"})
}
func (t *copyFileTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	src := ArgString(args, "src")
	dst := ArgString(args, "dst")
	if src == "" || dst == "" {
		return NewErrorResult("src and dst are required")
	}
	if err := t.m.ensureAllowed(src); err != nil {
		return NewErrorResult(err.Error())
	}
	if err := t.m.ensureAllowed(dst); err != nil {
		return NewErrorResult(err.Error())
	}
	data, err := os.ReadFile(src)
	if err != nil {
		return NewErrorResult(fmt.Sprintf("read src: %v", err))
	}
	if err := os.MkdirAll(filepath.Dir(dst), 0o755); err != nil {
		return NewErrorResult(fmt.Sprintf("mkdir: %v", err))
	}
	if err := os.WriteFile(dst, data, 0o644); err != nil {
		return NewErrorResult(fmt.Sprintf("write dst: %v", err))
	}
	return NewTextResult(fmt.Sprintf("Successfully copied %s to %s", src, dst))
}

// --- delete_file ---

type deleteFileTool struct{ m *FilesystemModule }

func (t *deleteFileTool) Name() string { return "delete_file" }
func (t *deleteFileTool) Description() string {
	return "Delete a file or empty directory."
}
func (t *deleteFileTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"path": Prop("string", "Path to the file or empty directory to delete."),
	}, []string{"path"})
}
func (t *deleteFileTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	path := ArgString(args, "path")
	if path == "" {
		return NewErrorResult("path is required")
	}
	if err := t.m.ensureAllowed(path); err != nil {
		return NewErrorResult(err.Error())
	}
	info, err := os.Stat(path)
	if err != nil {
		return NewErrorResult(fmt.Sprintf("stat: %v", err))
	}
	if info.IsDir() {
		if err := os.Remove(path); err != nil {
			return NewErrorResult(fmt.Sprintf("remove dir: %v", err))
		}
	} else {
		if err := os.Remove(path); err != nil {
			return NewErrorResult(fmt.Sprintf("remove file: %v", err))
		}
	}
	return NewTextResult(fmt.Sprintf("Successfully deleted %s", path))
}

// --- list_allowed_directories ---

type listAllowedDirsTool struct{ m *FilesystemModule }

func (t *listAllowedDirsTool) Name() string { return "list_allowed_directories" }
func (t *listAllowedDirsTool) Description() string {
	return "List the directories that the filesystem tool is allowed to access."
}
func (t *listAllowedDirsTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{}, nil)
}
func (t *listAllowedDirsTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	return NewTextResult(strings.Join(t.m.allowedDirs, "\n"))
}

// --- tree ---

type treeTool struct{ m *FilesystemModule }

func (t *treeTool) Name() string { return "tree" }
func (t *treeTool) Description() string {
	return "Get a recursive tree view of files and directories starting from a path."
}
func (t *treeTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"path":  Prop("string", "Root directory for the tree."),
		"depth": Prop("integer", "Maximum depth to traverse (default 3)."),
	}, []string{"path"})
}
func (t *treeTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	path := ArgString(args, "path")
	if path == "" {
		return NewErrorResult("path is required")
	}
	if err := t.m.ensureAllowed(path); err != nil {
		return NewErrorResult(err.Error())
	}
	maxDepth := ArgInt(args, "depth", 3)
	var sb strings.Builder
	var walk func(p string, depth int, prefix string)
	walk = func(p string, depth int, prefix string) {
		if depth > maxDepth {
			return
		}
		entries, err := os.ReadDir(p)
		if err != nil {
			return
		}
		sort.Slice(entries, func(i, j int) bool {
			if entries[i].IsDir() != entries[j].IsDir() {
				return entries[i].IsDir()
			}
			return entries[i].Name() < entries[j].Name()
		})
		for i, e := range entries {
			isLast := i == len(entries)-1
			connector := "├── "
			if isLast {
				connector = "└── "
			}
			typ := ""
			if e.IsDir() {
				typ = "/"
			}
			sb.WriteString(fmt.Sprintf("%s%s%s%s\n", prefix, connector, e.Name(), typ))
			if e.IsDir() {
				newPrefix := prefix + "│   "
				if isLast {
					newPrefix = prefix + "    "
				}
				walk(filepath.Join(p, e.Name()), depth+1, newPrefix)
			}
		}
	}
	sb.WriteString(path + "\n")
	walk(path, 1, "")
	return NewTextResult(sb.String())
}
