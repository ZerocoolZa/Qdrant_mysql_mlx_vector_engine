// Taskplanner MCP Server — native Go replacement for the Node.js taskplanner.
// Speaks MCP over stdio, manages .tasks/ markdown files.
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

type StateDef struct {
	Name     string `json:"name"`
	FileName string `json:"fileName"`
	Order    int    `json:"order"`
}

type Config struct {
	Version        int        `json:"version"`
	IdPrefix       string     `json:"idPrefix"`
	NextId         int        `json:"nextId"`
	States         []StateDef `json:"states"`
	Priorities     []string   `json:"priorities"`
	Tags           []string   `json:"tags"`
	InsertPosition string     `json:"insertPosition"`
	AiPlanRequired bool       `json:"aiPlanRequired"`
	SortBy         string     `json:"sortBy"`
}

func loadConfig(dir string) (*Config, error) {
	data, err := os.ReadFile(filepath.Join(dir, "config.json"))
	if err != nil {
		return nil, fmt.Errorf("read config.json: %w", err)
	}
	var c Config
	if err := json.Unmarshal(data, &c); err != nil {
		return nil, fmt.Errorf("parse config.json: %w", err)
	}
	return &c, nil
}

func saveConfig(dir string, c *Config) error {
	data, err := json.MarshalIndent(c, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(dir, "config.json"), data, 0644)
}

// stateFileName maps a lowercase state key (backlog, next, in_progress, ...)
// to the configured file name.
func (c *Config) stateFileName(key string) (string, bool) {
	canonical := canonicalState(key)
	for _, s := range c.States {
		if canonicalState(s.Name) == canonical {
			return s.FileName, true
		}
	}
	return "", false
}

// canonicalState normalises a state name or key to a single lowercase form.
func canonicalState(s string) string {
	s = strings.ToLower(strings.TrimSpace(s))
	s = strings.ReplaceAll(s, " ", "_")
	switch s {
	case "in_progress", "in-progress", "inprogress":
		return "in_progress"
	case "backlog":
		return "backlog"
	case "next":
		return "next"
	case "done":
		return "done"
	case "rejected":
		return "rejected"
	}
	return s
}

// ---------------------------------------------------------------------------
// Task model + markdown parsing
// ---------------------------------------------------------------------------

type Task struct {
	ID        string `json:"id"`
	Title     string `json:"title"`
	Priority  string `json:"priority"`
	Tags      string `json:"tags"`
	Updated   string `json:"updated"`
	State     string `json:"state"`
	FileName  string `json:"fileName"`
	RawBody   string `json:"rawBody"`   // full markdown body (after heading, before ---)
	Plan      string `json:"plan"`      // content of ### Plan section
	FullBlock string `json:"fullBlock"` // entire task block including heading + trailing ---
}

var taskHeadingRe = regexp.MustCompile(`^## (TASK-\d+):\s*(.*)$`)
var priorityRe = regexp.MustCompile(`\*\*Priority:\*\*\s*(\S+)`)
var tagsRe = regexp.MustCompile(`\*\*Tags:\*\*\s*(.*)`)
var updatedRe = regexp.MustCompile(`\*\*Updated:\*\*\s*(.*)`)
var planHeadingRe = regexp.MustCompile(`^### Plan\s*$`)

// parseFile reads a markdown state file and returns all tasks in it.
func parseFile(path, stateKey, fileName string) ([]Task, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	content := string(data)
	lines := strings.Split(content, "\n")

	var tasks []Task
	i := 0
	for i < len(lines) {
		m := taskHeadingRe.FindStringSubmatch(lines[i])
		if m == nil {
			i++
			continue
		}
		taskID := m[1]
		title := strings.TrimSpace(m[2])
		start := i
		i++

		// Collect body lines until next ## heading or EOF.
		var bodyLines []string
		for i < len(lines) {
			if taskHeadingRe.MatchString(lines[i]) {
				break
			}
			bodyLines = append(bodyLines, lines[i])
			i++
		}
		body := strings.Join(bodyLines, "\n")
		// Trim trailing separator line (---) from body.
		bodyTrimmed := strings.TrimRight(body, "\n")
		bodyLines2 := strings.Split(bodyTrimmed, "\n")
		// Remove trailing --- separator.
		for len(bodyLines2) > 0 {
			last := strings.TrimSpace(bodyLines2[len(bodyLines2)-1])
			if last == "---" {
				bodyLines2 = bodyLines2[:len(bodyLines2)-1]
			} else {
				break
			}
		}
		cleanBody := strings.TrimRight(strings.Join(bodyLines2, "\n"), "\n")

		task := Task{
			ID:       taskID,
			Title:    title,
			State:    stateKey,
			FileName: fileName,
			RawBody:  cleanBody,
		}
		if m := priorityRe.FindStringSubmatch(cleanBody); m != nil {
			task.Priority = strings.TrimSpace(m[1])
		}
		if m := tagsRe.FindStringSubmatch(cleanBody); m != nil {
			task.Tags = strings.TrimSpace(m[1])
		}
		if m := updatedRe.FindStringSubmatch(cleanBody); m != nil {
			task.Updated = strings.TrimSpace(m[1])
		}
		task.Plan = extractPlan(cleanBody)
		task.FullBlock = strings.Join(lines[start:i], "\n")

		tasks = append(tasks, task)
	}
	return tasks, nil
}

// extractPlan returns the text under the ### Plan heading.
func extractPlan(body string) string {
	lines := strings.Split(body, "\n")
	var planLines []string
	inPlan := false
	for _, ln := range lines {
		if planHeadingRe.MatchString(ln) {
			inPlan = true
			continue
		}
		if inPlan {
			// Stop if we hit another ### or ## heading.
			if strings.HasPrefix(strings.TrimSpace(ln), "## ") || strings.HasPrefix(strings.TrimSpace(ln), "### ") {
				if strings.TrimSpace(ln) != "" {
					break
				}
			}
			planLines = append(planLines, ln)
		}
	}
	return strings.TrimSpace(strings.Join(planLines, "\n"))
}

// allTasks reads every state file and returns all tasks.
func allTasks(dir string, cfg *Config) ([]Task, error) {
	var tasks []Task
	for _, s := range cfg.States {
		fp := filepath.Join(dir, s.FileName)
		st, err := parseFile(fp, canonicalState(s.Name), s.FileName)
		if err != nil {
			return nil, fmt.Errorf("parse %s: %w", s.FileName, err)
		}
		tasks = append(tasks, st...)
	}
	return tasks, nil
}

// findTask searches all state files for a task by ID.
func findTask(dir string, cfg *Config, id string) (*Task, error) {
	tasks, err := allTasks(dir, cfg)
	if err != nil {
		return nil, err
	}
	for i := range tasks {
		if tasks[i].ID == id {
			return &tasks[i], nil
		}
	}
	return nil, nil
}

// ---------------------------------------------------------------------------
// File manipulation helpers
// ---------------------------------------------------------------------------

// readFileLines reads a file and returns its lines. Returns empty if missing.
func readFileLines(path string) ([]string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	return strings.Split(string(data), "\n"), nil
}

// removeTaskBlock removes the task block (heading through line before next ## or EOF)
// from a list of lines, returns the new lines.
func removeTaskBlock(lines []string, taskID string) []string {
	out := make([]string, 0, len(lines))
	i := 0
	for i < len(lines) {
		m := taskHeadingRe.FindStringSubmatch(lines[i])
		if m != nil && m[1] == taskID {
			// Skip this task block.
			i++
			for i < len(lines) && !taskHeadingRe.MatchString(lines[i]) {
				i++
			}
			// Also skip a trailing --- separator that belongs to the removed task.
			// (The separator line is the last non-empty line before the next heading.)
			// Actually the --- is part of the body we already skipped, so nothing extra.
		} else {
			out = append(out, lines[i])
			i++
		}
	}
	return out
}

// insertTaskBlock inserts a task block into a file's lines at the top or bottom.
func insertTaskBlock(lines []string, block string, position string) []string {
	blockLines := strings.Split(block, "\n")
	if position == "bottom" {
		// Ensure there's a separator before the new block if file is non-empty.
		result := append([]string{}, lines...)
		// Trim trailing empty lines.
		for len(result) > 0 && strings.TrimSpace(result[len(result)-1]) == "" {
			result = result[:len(result)-1]
		}
		if len(result) > 0 {
			result = append(result, "", "---", "")
		}
		result = append(result, blockLines...)
		return result
	}
	// Default: top. Skip the leading "# Title" header line, insert after it.
	result := make([]string, 0, len(lines)+len(blockLines)+4)
	if len(lines) > 0 && strings.HasPrefix(lines[0], "# ") {
		result = append(result, lines[0])
		// Insert block after header + blank line.
		result = append(result, "")
		result = append(result, blockLines...)
		result = append(result, "", "---")
		// Append rest of original (skip header, skip leading blank lines after header).
		rest := lines[1:]
		for len(rest) > 0 && strings.TrimSpace(rest[0]) == "" {
			rest = rest[1:]
		}
		for len(rest) > 0 && strings.TrimSpace(rest[0]) == "---" {
			rest = rest[1:]
			for len(rest) > 0 && strings.TrimSpace(rest[0]) == "" {
				rest = rest[1:]
			}
		}
		result = append(result, "")
		result = append(result, rest...)
	} else {
		result = append(result, blockLines...)
		result = append(result, "", "---")
		result = append(result, lines...)
	}
	return result
}

// buildTaskBlock constructs a markdown task block from fields.
func buildTaskBlock(id, title, priority, tags, plan string) string {
	now := time.Now().Format("2006-01-02 15:04")
	var sb strings.Builder
	fmt.Fprintf(&sb, "## %s: %s\n", id, title)
	fmt.Fprintf(&sb, "**Priority:** %s | **Tags:** %s\n", priority, tags)
	fmt.Fprintf(&sb, "**Updated:** %s\n", now)
	sb.WriteString("\n")
	if plan != "" {
		sb.WriteString("### Plan\n\n")
		sb.WriteString(plan)
		sb.WriteString("\n")
	}
	// Trim trailing newline so the block is clean.
	return strings.TrimRight(sb.String(), "\n")
}

// writeLines writes lines to a file, ensuring a trailing newline.
func writeLines(path string, lines []string) error {
	content := strings.Join(lines, "\n")
	content = strings.TrimRight(content, "\n") + "\n"
	return os.WriteFile(path, []byte(content), 0644)
}

// ---------------------------------------------------------------------------
// MCP tool input types
// ---------------------------------------------------------------------------

type BoardInput struct{}

type BoardDataInput struct{}

type BoardVisualInput struct{}

type ListInput struct {
	State string `json:"state" jsonschema:"the state to list: backlog, next, in_progress, done, rejected"`
}

type GetInput struct {
	Id string `json:"id" jsonschema:"task ID, e.g. TASK-088"`
}

type CreateInput struct {
	Title    string `json:"title" jsonschema:"task title"`
	Priority string `json:"priority,omitempty" jsonschema:"priority P0-P4, default P2"`
	Tags     string `json:"tags,omitempty" jsonschema:"comma-separated tags"`
	Plan     string `json:"plan,omitempty" jsonschema:"plan text for the ### Plan section"`
}

type MoveInput struct {
	Id       string `json:"id" jsonschema:"task ID to move"`
	ToState  string `json:"toState" jsonschema:"target state: backlog, next, in_progress, done, rejected"`
}

type UpdateInput struct {
	Id       string `json:"id" jsonschema:"task ID to update"`
	Title    string `json:"title,omitempty" jsonschema:"new title"`
	Priority string `json:"priority,omitempty" jsonschema:"new priority P0-P4"`
	Tags     string `json:"tags,omitempty" jsonschema:"new comma-separated tags"`
	Plan     string `json:"plan,omitempty" jsonschema:"new plan text"`
	Description string `json:"description,omitempty" jsonschema:"new description text (replaces body before ### Plan)"`
}

type DeleteInput struct {
	Id string `json:"id" jsonschema:"task ID to delete"`
}

// ---------------------------------------------------------------------------
// Server context
// ---------------------------------------------------------------------------

type ServerCtx struct {
	Dir string
}

// ---------------------------------------------------------------------------
// Tool handlers
// ---------------------------------------------------------------------------

func handleBoard(sctx *ServerCtx, cfg *Config) func(context.Context, *mcp.CallToolRequest, BoardInput) (*mcp.CallToolResult, any, error) {
	return func(ctx context.Context, req *mcp.CallToolRequest, in BoardInput) (*mcp.CallToolResult, any, error) {
		tasks, err := allTasks(sctx.Dir, cfg)
		if err != nil {
			return nil, nil, err
		}
		sortTasks(tasks, cfg)
		return textResult(tasksToText(tasks)), nil, nil
	}
}

func handleBoardData(sctx *ServerCtx, cfg *Config) func(context.Context, *mcp.CallToolRequest, BoardDataInput) (*mcp.CallToolResult, any, error) {
	return func(ctx context.Context, req *mcp.CallToolRequest, in BoardDataInput) (*mcp.CallToolResult, any, error) {
		tasks, err := allTasks(sctx.Dir, cfg)
		if err != nil {
			return nil, nil, err
		}
		sortTasks(tasks, cfg)
		type taskJSON struct {
			Id       string `json:"id"`
			Title    string `json:"title"`
			State    string `json:"state"`
			Priority string `json:"priority"`
			Tags     string `json:"tags"`
		}
		out := make([]taskJSON, 0, len(tasks))
		for _, t := range tasks {
			out = append(out, taskJSON{Id: t.ID, Title: t.Title, State: t.State, Priority: t.Priority, Tags: t.Tags})
		}
		data, err := json.MarshalIndent(out, "", "  ")
		if err != nil {
			return nil, nil, err
		}
		return textResult(string(data)), nil, nil
	}
}

func handleBoardVisual(sctx *ServerCtx, cfg *Config) func(context.Context, *mcp.CallToolRequest, BoardVisualInput) (*mcp.CallToolResult, any, error) {
	return func(ctx context.Context, req *mcp.CallToolRequest, in BoardVisualInput) (*mcp.CallToolResult, any, error) {
		tasks, err := allTasks(sctx.Dir, cfg)
		if err != nil {
			return nil, nil, err
		}
		sortTasks(tasks, cfg)
		byState := make(map[string][]Task)
		for _, t := range tasks {
			byState[t.State] = append(byState[t.State], t)
		}
		var sb strings.Builder
		sb.WriteString("# Task Board (Visual)\n\n")
		states := []string{"Backlog", "Next", "In Progress", "Done", "Rejected"}
		for _, state := range states {
			stasks := byState[state]
			sb.WriteString(fmt.Sprintf("## %s (%d)\n", state, len(stasks)))
			for _, t := range stasks {
				marker := " "
				if t.Priority == "P0" || t.Priority == "P1" {
					marker = "*"
				}
				sb.WriteString(fmt.Sprintf("  %s %s: %s [%s]\n", marker, t.ID, t.Title, t.Priority))
			}
			sb.WriteString("\n")
		}
		return textResult(sb.String()), nil, nil
	}
}

func handleList(sctx *ServerCtx, cfg *Config) func(context.Context, *mcp.CallToolRequest, ListInput) (*mcp.CallToolResult, any, error) {
	return func(ctx context.Context, req *mcp.CallToolRequest, in ListInput) (*mcp.CallToolResult, any, error) {
		key := canonicalState(in.State)
		fileName, ok := cfg.stateFileName(key)
		if !ok {
			return nil, nil, fmt.Errorf("unknown state: %s", in.State)
		}
		tasks, err := parseFile(filepath.Join(sctx.Dir, fileName), key, fileName)
		if err != nil {
			return nil, nil, err
		}
		sortTasks(tasks, cfg)
		return textResult(tasksToText(tasks)), nil, nil
	}
}

func handleGet(sctx *ServerCtx, cfg *Config) func(context.Context, *mcp.CallToolRequest, GetInput) (*mcp.CallToolResult, any, error) {
	return func(ctx context.Context, req *mcp.CallToolRequest, in GetInput) (*mcp.CallToolResult, any, error) {
		task, err := findTask(sctx.Dir, cfg, in.Id)
		if err != nil {
			return nil, nil, err
		}
		if task == nil {
			return textResult(fmt.Sprintf("Task %s not found.", in.Id)), nil, nil
		}
		return textResult(taskToFullText(task)), nil, nil
	}
}

func handleCreate(sctx *ServerCtx, cfg *Config) func(context.Context, *mcp.CallToolRequest, CreateInput) (*mcp.CallToolResult, any, error) {
	return func(ctx context.Context, req *mcp.CallToolRequest, in CreateInput) (*mcp.CallToolResult, any, error) {
		priority := in.Priority
		if priority == "" {
			priority = "P2"
		}
		tags := in.Tags
		if tags == "" {
			tags = "untagged"
		}
		id := fmt.Sprintf("%s-%03d", cfg.IdPrefix, cfg.NextId)
		block := buildTaskBlock(id, in.Title, priority, tags, in.Plan)

		fileName, ok := cfg.stateFileName("backlog")
		if !ok {
			fileName = "BACKLOG.md"
		}
		fp := filepath.Join(sctx.Dir, fileName)
		lines, err := readFileLines(fp)
		if err != nil {
			return nil, nil, err
		}
		// Ensure file has a header.
		if len(lines) == 0 {
			lines = []string{"# Backlog", ""}
		}
		newLines := insertTaskBlock(lines, block, cfg.InsertPosition)
		if err := writeLines(fp, newLines); err != nil {
			return nil, nil, err
		}
		// Increment nextId and save config.
		cfg.NextId++
		if err := saveConfig(sctx.Dir, cfg); err != nil {
			return nil, nil, fmt.Errorf("created task but failed to save config: %w", err)
		}
		return textResult(fmt.Sprintf("Created %s: %s in %s\nPriority: %s | Tags: %s", id, in.Title, fileName, priority, tags)), nil, nil
	}
}

func handleMove(sctx *ServerCtx, cfg *Config) func(context.Context, *mcp.CallToolRequest, MoveInput) (*mcp.CallToolResult, any, error) {
	return func(ctx context.Context, req *mcp.CallToolRequest, in MoveInput) (*mcp.CallToolResult, any, error) {
		task, err := findTask(sctx.Dir, cfg, in.Id)
		if err != nil {
			return nil, nil, err
		}
		if task == nil {
			return textResult(fmt.Sprintf("Task %s not found.", in.Id)), nil, nil
		}
		toKey := canonicalState(in.ToState)
		toFile, ok := cfg.stateFileName(toKey)
		if !ok {
			return nil, nil, fmt.Errorf("unknown target state: %s", in.ToState)
		}
		if canonicalState(task.State) == toKey {
			return textResult(fmt.Sprintf("Task %s is already in %s.", in.Id, toKey)), nil, nil
		}

		// Remove from source file.
		srcPath := filepath.Join(sctx.Dir, task.FileName)
		srcLines, err := readFileLines(srcPath)
		if err != nil {
			return nil, nil, err
		}
		srcLines = removeTaskBlock(srcLines, in.Id)
		if err := writeLines(srcPath, srcLines); err != nil {
			return nil, nil, err
		}

		// Rebuild block with updated timestamp.
		block := buildTaskBlock(task.ID, task.Title, task.Priority, task.Tags, task.Plan)

		// Insert into target file.
		dstPath := filepath.Join(sctx.Dir, toFile)
		dstLines, err := readFileLines(dstPath)
		if err != nil {
			return nil, nil, err
		}
		if len(dstLines) == 0 {
			header := "#" + strings.Title(strings.ReplaceAll(toKey, "_", " "))
			dstLines = []string{header, ""}
		}
		newDst := insertTaskBlock(dstLines, block, cfg.InsertPosition)
		if err := writeLines(dstPath, newDst); err != nil {
			return nil, nil, err
		}
		return textResult(fmt.Sprintf("Moved %s from %s to %s.", in.Id, task.State, toKey)), nil, nil
	}
}

func handleUpdate(sctx *ServerCtx, cfg *Config) func(context.Context, *mcp.CallToolRequest, UpdateInput) (*mcp.CallToolResult, any, error) {
	return func(ctx context.Context, req *mcp.CallToolRequest, in UpdateInput) (*mcp.CallToolResult, any, error) {
		task, err := findTask(sctx.Dir, cfg, in.Id)
		if err != nil {
			return nil, nil, err
		}
		if task == nil {
			return textResult(fmt.Sprintf("Task %s not found.", in.Id)), nil, nil
		}

		title := task.Title
		if in.Title != "" {
			title = in.Title
		}
		priority := task.Priority
		if in.Priority != "" {
			priority = in.Priority
		}
		tags := task.Tags
		if in.Tags != "" {
			tags = in.Tags
		}
		plan := task.Plan
		if in.Plan != "" {
			plan = in.Plan
		}
		description := ""
		if in.Description != "" {
			description = in.Description
		}

		// Build new block.
		now := time.Now().Format("2006-01-02 15:04")
		var sb strings.Builder
		fmt.Fprintf(&sb, "## %s: %s\n", task.ID, title)
		fmt.Fprintf(&sb, "**Priority:** %s | **Tags:** %s\n", priority, tags)
		fmt.Fprintf(&sb, "**Updated:** %s\n", now)
		sb.WriteString("\n")
		if description != "" {
			sb.WriteString(description)
			sb.WriteString("\n\n")
		}
		if plan != "" {
			sb.WriteString("### Plan\n\n")
			sb.WriteString(plan)
			sb.WriteString("\n")
		}
		newBlock := strings.TrimRight(sb.String(), "\n")

		// Replace in file.
		fp := filepath.Join(sctx.Dir, task.FileName)
		lines, err := readFileLines(fp)
		if err != nil {
			return nil, nil, err
		}
		lines = removeTaskBlock(lines, task.ID)
		lines = insertTaskBlock(lines, newBlock, cfg.InsertPosition)
		if err := writeLines(fp, lines); err != nil {
			return nil, nil, err
		}
		return textResult(fmt.Sprintf("Updated %s.", task.ID)), nil, nil
	}
}

func handleDelete(sctx *ServerCtx, cfg *Config) func(context.Context, *mcp.CallToolRequest, DeleteInput) (*mcp.CallToolResult, any, error) {
	return func(ctx context.Context, req *mcp.CallToolRequest, in DeleteInput) (*mcp.CallToolResult, any, error) {
		task, err := findTask(sctx.Dir, cfg, in.Id)
		if err != nil {
			return nil, nil, err
		}
		if task == nil {
			return textResult(fmt.Sprintf("Task %s not found.", in.Id)), nil, nil
		}
		fp := filepath.Join(sctx.Dir, task.FileName)
		lines, err := readFileLines(fp)
		if err != nil {
			return nil, nil, err
		}
		lines = removeTaskBlock(lines, in.Id)
		if err := writeLines(fp, lines); err != nil {
			return nil, nil, err
		}
		return textResult(fmt.Sprintf("Deleted %s from %s.", in.Id, task.State)), nil, nil
	}
}

// ---------------------------------------------------------------------------
// Output helpers
// ---------------------------------------------------------------------------

func textResult(text string) *mcp.CallToolResult {
	return &mcp.CallToolResult{
		Content: []mcp.Content{&mcp.TextContent{Text: text}},
	}
}

func tasksToText(tasks []Task) string {
	if len(tasks) == 0 {
		return "No tasks found."
	}
	var sb strings.Builder
	for _, t := range tasks {
		fmt.Fprintf(&sb, "%s [%s] %s — %s\n", t.ID, t.Priority, t.State, t.Title)
		if t.Tags != "" {
			fmt.Fprintf(&sb, "  Tags: %s\n", t.Tags)
		}
		if t.Updated != "" {
			fmt.Fprintf(&sb, "  Updated: %s\n", t.Updated)
		}
	}
	return strings.TrimRight(sb.String(), "\n")
}

func taskToFullText(t *Task) string {
	var sb strings.Builder
	fmt.Fprintf(&sb, "ID: %s\n", t.ID)
	fmt.Fprintf(&sb, "Title: %s\n", t.Title)
	fmt.Fprintf(&sb, "State: %s (%s)\n", t.State, t.FileName)
	fmt.Fprintf(&sb, "Priority: %s\n", t.Priority)
	fmt.Fprintf(&sb, "Tags: %s\n", t.Tags)
	fmt.Fprintf(&sb, "Updated: %s\n", t.Updated)
	sb.WriteString("\n--- Body ---\n")
	sb.WriteString(t.RawBody)
	if t.Plan != "" {
		sb.WriteString("\n\n--- Plan ---\n")
		sb.WriteString(t.Plan)
	}
	return sb.String()
}

func sortTasks(tasks []Task, cfg *Config) {
	switch cfg.SortBy {
	case "priority":
		prioRank := map[string]int{}
		for i, p := range cfg.Priorities {
			prioRank[p] = i
		}
		sort.SliceStable(tasks, func(i, j int) bool {
			ri, ok := prioRank[tasks[i].Priority]
			if !ok {
				ri = 99
			}
			rj, ok := prioRank[tasks[j].Priority]
			if !ok {
				rj = 99
			}
			if ri != rj {
				return ri < rj
			}
			return tasks[i].ID < tasks[j].ID
		})
	default:
		sort.SliceStable(tasks, func(i, j int) bool {
			return tasks[i].ID < tasks[j].ID
		})
	}
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------

func main() {
	tasksDir := flag.String("tasks-dir", ".tasks", "path to the .tasks directory")
	flag.Parse()

	absDir, err := filepath.Abs(*tasksDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error resolving tasks dir: %v\n", err)
		os.Exit(1)
	}

	cfg, err := loadConfig(absDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error loading config from %s: %v\n", absDir, err)
		os.Exit(1)
	}

	sctx := &ServerCtx{Dir: absDir}

	server := mcp.NewServer(&mcp.Implementation{
		Name:    "taskplanner-custom",
		Version: "1.0.0",
	}, nil)

	mcp.AddTool(server, &mcp.Tool{
		Name:        "taskplanner_board",
		Description: "List all tasks across all state files (backlog, next, in_progress, done, rejected).",
	}, handleBoard(sctx, cfg))

	mcp.AddTool(server, &mcp.Tool{
		Name:        "taskplanner_board_data",
		Description: "Get a board overview as structured JSON data with task counts per state and all tasks.",
	}, handleBoardData(sctx, cfg))

	mcp.AddTool(server, &mcp.Tool{
		Name:        "taskplanner_board_visual",
		Description: "Get a visual board rendering with task counts per state, showing priority markers.",
	}, handleBoardVisual(sctx, cfg))

	mcp.AddTool(server, &mcp.Tool{
		Name:        "taskplanner_list",
		Description: "List tasks in a specific state. State: backlog, next, in_progress, done, or rejected.",
	}, handleList(sctx, cfg))

	mcp.AddTool(server, &mcp.Tool{
		Name:        "taskplanner_get",
		Description: "Get full details of a specific task by ID (e.g. TASK-088). Searches all state files.",
	}, handleGet(sctx, cfg))

	mcp.AddTool(server, &mcp.Tool{
		Name:        "taskplanner_create",
		Description: "Create a new task in BACKLOG.md. Auto-generates the next TASK-### ID from config.json.",
	}, handleCreate(sctx, cfg))

	mcp.AddTool(server, &mcp.Tool{
		Name:        "taskplanner_move",
		Description: "Move a task from its current state to another state. Cuts from source file, pastes in target file.",
	}, handleMove(sctx, cfg))

	mcp.AddTool(server, &mcp.Tool{
		Name:        "taskplanner_update",
		Description: "Update a task's title, priority, tags, description, or plan.",
	}, handleUpdate(sctx, cfg))

	mcp.AddTool(server, &mcp.Tool{
		Name:        "taskplanner_delete",
		Description: "Delete a task from its state file.",
	}, handleDelete(sctx, cfg))

	if err := server.Run(context.Background(), &mcp.StdioTransport{}); err != nil {
		fmt.Fprintf(os.Stderr, "Server error: %v\n", err)
		os.Exit(1)
	}
}
