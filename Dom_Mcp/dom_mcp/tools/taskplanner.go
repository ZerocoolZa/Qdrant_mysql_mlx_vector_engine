package tools

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"time"
)

// ---------------------------------------------------------------------------
// Taskplanner config model
// ---------------------------------------------------------------------------

// tpStateDef is one column/state in the task board.
type tpStateDef struct {
	Name     string `json:"name"`
	FileName string `json:"fileName"`
	Order    int    `json:"order"`
}

// tpConfig is the config.json inside the .tasks directory.
type tpConfig struct {
	Version        int          `json:"version"`
	IdPrefix       string       `json:"idPrefix"`
	NextId         int          `json:"nextId"`
	States         []tpStateDef `json:"states"`
	Priorities     []string     `json:"priorities"`
	Tags           []string     `json:"tags"`
	InsertPosition string       `json:"insertPosition"`
	AiPlanRequired bool         `json:"aiPlanRequired"`
	SortBy         string       `json:"sortBy"`
}

// tpLoadConfig reads config.json from the tasks directory.
func tpLoadConfig(dir string) (*tpConfig, error) {
	data, err := os.ReadFile(filepath.Join(dir, "config.json"))
	if err != nil {
		return nil, fmt.Errorf("read config.json: %w", err)
	}
	var c tpConfig
	if err := json.Unmarshal(data, &c); err != nil {
		return nil, fmt.Errorf("parse config.json: %w", err)
	}
	return &c, nil
}

// tpSaveConfig writes config.json back to the tasks directory.
func tpSaveConfig(dir string, c *tpConfig) error {
	data, err := json.MarshalIndent(c, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(dir, "config.json"), data, 0o644)
}

// stateFileName maps a lowercase state key to the configured file name.
func (c *tpConfig) stateFileName(key string) (string, bool) {
	canonical := tpCanonicalState(key)
	for _, s := range c.States {
		if tpCanonicalState(s.Name) == canonical {
			return s.FileName, true
		}
	}
	return "", false
}

// tpCanonicalState normalises a state name or key to a single lowercase form.
func tpCanonicalState(s string) string {
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

// tpTask is a single task parsed from a markdown state file.
type tpTask struct {
	ID        string `json:"id"`
	Title     string `json:"title"`
	Priority  string `json:"priority"`
	Tags      string `json:"tags"`
	Updated   string `json:"updated"`
	State     string `json:"state"`
	FileName  string `json:"fileName"`
	RawBody   string `json:"rawBody"`
	Plan      string `json:"plan"`
	FullBlock string `json:"fullBlock"`
}

var (
	tpTaskHeadingRe = regexp.MustCompile(`^## (TASK-\d+):\s*(.*)$`)
	tpPriorityRe    = regexp.MustCompile(`\*\*Priority:\*\*\s*(\S+)`)
	tpTagsRe        = regexp.MustCompile(`\*\*Tags:\*\*\s*(.*)`)
	tpUpdatedRe     = regexp.MustCompile(`\*\*Updated:\*\*\s*(.*)`)
	tpPlanHeadingRe = regexp.MustCompile(`^### Plan\s*$`)
)

// tpParseFile reads a markdown state file and returns all tasks in it.
func tpParseFile(path, stateKey, fileName string) ([]tpTask, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	content := string(data)
	lines := strings.Split(content, "\n")

	var tasks []tpTask
	i := 0
	for i < len(lines) {
		m := tpTaskHeadingRe.FindStringSubmatch(lines[i])
		if m == nil {
			i++
			continue
		}
		taskID := m[1]
		title := strings.TrimSpace(m[2])
		start := i
		i++

		var bodyLines []string
		for i < len(lines) {
			if tpTaskHeadingRe.MatchString(lines[i]) {
				break
			}
			bodyLines = append(bodyLines, lines[i])
			i++
		}
		body := strings.Join(bodyLines, "\n")
		bodyTrimmed := strings.TrimRight(body, "\n")
		bodyLines2 := strings.Split(bodyTrimmed, "\n")
		for len(bodyLines2) > 0 {
			last := strings.TrimSpace(bodyLines2[len(bodyLines2)-1])
			if last == "---" {
				bodyLines2 = bodyLines2[:len(bodyLines2)-1]
			} else {
				break
			}
		}
		cleanBody := strings.TrimRight(strings.Join(bodyLines2, "\n"), "\n")

		task := tpTask{
			ID:       taskID,
			Title:    title,
			State:    stateKey,
			FileName: fileName,
			RawBody:  cleanBody,
		}
		if m := tpPriorityRe.FindStringSubmatch(cleanBody); m != nil {
			task.Priority = strings.TrimSpace(m[1])
		}
		if m := tpTagsRe.FindStringSubmatch(cleanBody); m != nil {
			task.Tags = strings.TrimSpace(m[1])
		}
		if m := tpUpdatedRe.FindStringSubmatch(cleanBody); m != nil {
			task.Updated = strings.TrimSpace(m[1])
		}
		task.Plan = tpExtractPlan(cleanBody)
		task.FullBlock = strings.Join(lines[start:i], "\n")

		tasks = append(tasks, task)
	}
	return tasks, nil
}

// tpExtractPlan returns the text under the ### Plan heading.
func tpExtractPlan(body string) string {
	lines := strings.Split(body, "\n")
	var planLines []string
	inPlan := false
	for _, ln := range lines {
		if tpPlanHeadingRe.MatchString(ln) {
			inPlan = true
			continue
		}
		if inPlan {
			trimmed := strings.TrimSpace(ln)
			if strings.HasPrefix(trimmed, "## ") || strings.HasPrefix(trimmed, "### ") {
				if trimmed != "" {
					break
				}
			}
			planLines = append(planLines, ln)
		}
	}
	return strings.TrimSpace(strings.Join(planLines, "\n"))
}

// tpAllTasks reads every state file and returns all tasks.
func tpAllTasks(dir string, cfg *tpConfig) ([]tpTask, error) {
	var tasks []tpTask
	for _, s := range cfg.States {
		fp := filepath.Join(dir, s.FileName)
		st, err := tpParseFile(fp, tpCanonicalState(s.Name), s.FileName)
		if err != nil {
			return nil, fmt.Errorf("parse %s: %w", s.FileName, err)
		}
		tasks = append(tasks, st...)
	}
	return tasks, nil
}

// tpFindTask searches all state files for a task by ID.
func tpFindTask(dir string, cfg *tpConfig, id string) (*tpTask, error) {
	tasks, err := tpAllTasks(dir, cfg)
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

// tpReadFileLines reads a file and returns its lines. Returns empty if missing.
func tpReadFileLines(path string) ([]string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	return strings.Split(string(data), "\n"), nil
}

// tpRemoveTaskBlock removes the task block from a list of lines.
func tpRemoveTaskBlock(lines []string, taskID string) []string {
	out := make([]string, 0, len(lines))
	i := 0
	for i < len(lines) {
		m := tpTaskHeadingRe.FindStringSubmatch(lines[i])
		if m != nil && m[1] == taskID {
			i++
			for i < len(lines) && !tpTaskHeadingRe.MatchString(lines[i]) {
				i++
			}
		} else {
			out = append(out, lines[i])
			i++
		}
	}
	return out
}

// tpInsertTaskBlock inserts a task block into a file's lines at the top or bottom.
func tpInsertTaskBlock(lines []string, block string, position string) []string {
	blockLines := strings.Split(block, "\n")
	if position == "bottom" {
		result := append([]string{}, lines...)
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
		result = append(result, "")
		result = append(result, blockLines...)
		result = append(result, "", "---")
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

// tpBuildTaskBlock constructs a markdown task block from fields.
func tpBuildTaskBlock(id, title, priority, tags, plan string) string {
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
	return strings.TrimRight(sb.String(), "\n")
}

// tpWriteLines writes lines to a file, ensuring a trailing newline.
func tpWriteLines(path string, lines []string) error {
	content := strings.Join(lines, "\n")
	content = strings.TrimRight(content, "\n") + "\n"
	return os.WriteFile(path, []byte(content), 0o644)
}

// tpTitleCase capitalises the first letter of each word (replaces strings.Title).
func tpTitleCase(s string) string {
	words := strings.Fields(s)
	for i, w := range words {
		if len(w) > 0 {
			words[i] = strings.ToUpper(w[:1]) + w[1:]
		}
	}
	return strings.Join(words, " ")
}

// ---------------------------------------------------------------------------
// Output helpers
// ---------------------------------------------------------------------------

func tpTasksToText(tasks []tpTask) string {
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

func tpTaskToFullText(t *tpTask) string {
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

func tpSortTasks(tasks []tpTask, cfg *tpConfig) {
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
// Module
// ---------------------------------------------------------------------------

// TaskplannerModule manages .tasks/ markdown files for a kanban-style board.
type TaskplannerModule struct {
	dir string
}

// NewTaskplannerModule creates a taskplanner module from a tasks directory path.
func NewTaskplannerModule(tasksDir string) (*TaskplannerModule, error) {
	if tasksDir == "" {
		return nil, fmt.Errorf("tasks_dir is required")
	}
	absDir, err := filepath.Abs(tasksDir)
	if err != nil {
		return nil, fmt.Errorf("resolve tasks_dir: %w", err)
	}
	if _, err := os.Stat(filepath.Join(absDir, "config.json")); err != nil {
		return nil, fmt.Errorf("config.json not found in %s: %w", absDir, err)
	}
	return &TaskplannerModule{dir: absDir}, nil
}

func (m *TaskplannerModule) Name() string { return "taskplanner" }

func (m *TaskplannerModule) Tools() []Tool {
	return []Tool{
		&tpBoardTool{m: m},
		&tpBoardDataTool{m: m},
		&tpBoardVisualTool{m: m},
		&tpListTool{m: m},
		&tpGetTool{m: m},
		&tpCreateTool{m: m},
		&tpMoveTool{m: m},
		&tpUpdateTool{m: m},
		&tpDeleteTool{m: m},
	}
}

// loadConfig is a convenience wrapper that reads config.json from the module dir.
func (m *TaskplannerModule) loadConfig() (*tpConfig, error) {
	return tpLoadConfig(m.dir)
}

// ---------------------------------------------------------------------------
// taskplanner_board
// ---------------------------------------------------------------------------

type tpBoardTool struct{ m *TaskplannerModule }

func (t *tpBoardTool) Name() string { return "taskplanner_board" }
func (t *tpBoardTool) Description() string {
	return "List all tasks across all state files (backlog, next, in_progress, done, rejected)."
}
func (t *tpBoardTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{}, nil)
}
func (t *tpBoardTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	cfg, err := t.m.loadConfig()
	if err != nil {
		return NewErrorResult(err.Error())
	}
	tasks, err := tpAllTasks(t.m.dir, cfg)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	tpSortTasks(tasks, cfg)
	return NewTextResult(tpTasksToText(tasks))
}

// ---------------------------------------------------------------------------
// taskplanner_board_data
// ---------------------------------------------------------------------------

type tpBoardDataTool struct{ m *TaskplannerModule }

func (t *tpBoardDataTool) Name() string { return "taskplanner_board_data" }
func (t *tpBoardDataTool) Description() string {
	return "Get a board overview as structured JSON data with task counts per state and all tasks."
}
func (t *tpBoardDataTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{}, nil)
}
func (t *tpBoardDataTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	cfg, err := t.m.loadConfig()
	if err != nil {
		return NewErrorResult(err.Error())
	}
	tasks, err := tpAllTasks(t.m.dir, cfg)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	tpSortTasks(tasks, cfg)
	type taskJSON struct {
		Id       string `json:"id"`
		Title    string `json:"title"`
		State    string `json:"state"`
		Priority string `json:"priority"`
		Tags     string `json:"tags"`
	}
	out := make([]taskJSON, 0, len(tasks))
	for _, t2 := range tasks {
		out = append(out, taskJSON{
			Id:       t2.ID,
			Title:    t2.Title,
			State:    t2.State,
			Priority: t2.Priority,
			Tags:     t2.Tags,
		})
	}
	return JSONResult(out)
}

// ---------------------------------------------------------------------------
// taskplanner_board_visual
// ---------------------------------------------------------------------------

type tpBoardVisualTool struct{ m *TaskplannerModule }

func (t *tpBoardVisualTool) Name() string { return "taskplanner_board_visual" }
func (t *tpBoardVisualTool) Description() string {
	return "Get a visual board rendering with task counts per state, showing priority markers."
}
func (t *tpBoardVisualTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{}, nil)
}
func (t *tpBoardVisualTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	cfg, err := t.m.loadConfig()
	if err != nil {
		return NewErrorResult(err.Error())
	}
	tasks, err := tpAllTasks(t.m.dir, cfg)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	tpSortTasks(tasks, cfg)
	byState := make(map[string][]tpTask)
	for _, t2 := range tasks {
		byState[t2.State] = append(byState[t2.State], t2)
	}
	var sb strings.Builder
	sb.WriteString("# Task Board (Visual)\n\n")
	states := []string{"backlog", "next", "in_progress", "done", "rejected"}
	for _, state := range states {
		stasks := byState[state]
		displayName := tpTitleCase(strings.ReplaceAll(state, "_", " "))
		fmt.Fprintf(&sb, "## %s (%d)\n", displayName, len(stasks))
		for _, t2 := range stasks {
			marker := " "
			if t2.Priority == "P0" || t2.Priority == "P1" {
				marker = "*"
			}
			fmt.Fprintf(&sb, "  %s %s: %s [%s]\n", marker, t2.ID, t2.Title, t2.Priority)
		}
		sb.WriteString("\n")
	}
	return NewTextResult(strings.TrimRight(sb.String(), "\n"))
}

// ---------------------------------------------------------------------------
// taskplanner_list
// ---------------------------------------------------------------------------

type tpListTool struct{ m *TaskplannerModule }

func (t *tpListTool) Name() string { return "taskplanner_list" }
func (t *tpListTool) Description() string {
	return "List tasks in a specific state. State: backlog, next, in_progress, done, or rejected."
}
func (t *tpListTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"state": PropEnum("the state to list: backlog, next, in_progress, done, rejected",
			"backlog", "next", "in_progress", "done", "rejected"),
	}, []string{"state"})
}
func (t *tpListTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	cfg, err := t.m.loadConfig()
	if err != nil {
		return NewErrorResult(err.Error())
	}
	state := ArgString(args, "state")
	if state == "" {
		return NewErrorResult("state is required")
	}
	key := tpCanonicalState(state)
	fileName, ok := cfg.stateFileName(key)
	if !ok {
		return NewErrorResult(fmt.Sprintf("unknown state: %s", state))
	}
	tasks, err := tpParseFile(filepath.Join(t.m.dir, fileName), key, fileName)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	tpSortTasks(tasks, cfg)
	return NewTextResult(tpTasksToText(tasks))
}

// ---------------------------------------------------------------------------
// taskplanner_get
// ---------------------------------------------------------------------------

type tpGetTool struct{ m *TaskplannerModule }

func (t *tpGetTool) Name() string { return "taskplanner_get" }
func (t *tpGetTool) Description() string {
	return "Get full details of a specific task by ID (e.g. TASK-088). Searches all state files."
}
func (t *tpGetTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"id": Prop("string", "task ID, e.g. TASK-088"),
	}, []string{"id"})
}
func (t *tpGetTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	cfg, err := t.m.loadConfig()
	if err != nil {
		return NewErrorResult(err.Error())
	}
	id := ArgString(args, "id")
	if id == "" {
		return NewErrorResult("id is required")
	}
	task, err := tpFindTask(t.m.dir, cfg, id)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	if task == nil {
		return NewTextResult(fmt.Sprintf("Task %s not found.", id))
	}
	return NewTextResult(tpTaskToFullText(task))
}

// ---------------------------------------------------------------------------
// taskplanner_create
// ---------------------------------------------------------------------------

type tpCreateTool struct{ m *TaskplannerModule }

func (t *tpCreateTool) Name() string { return "taskplanner_create" }
func (t *tpCreateTool) Description() string {
	return "Create a new task in BACKLOG.md. Auto-generates the next TASK-### ID from config.json."
}
func (t *tpCreateTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"title":    Prop("string", "task title"),
		"priority": Prop("string", "priority P0-P4, default P2"),
		"tags":     Prop("string", "comma-separated tags"),
		"plan":     Prop("string", "plan text for the ### Plan section"),
	}, []string{"title"})
}
func (t *tpCreateTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	cfg, err := t.m.loadConfig()
	if err != nil {
		return NewErrorResult(err.Error())
	}
	title := ArgString(args, "title")
	if title == "" {
		return NewErrorResult("title is required")
	}
	priority := ArgString(args, "priority")
	if priority == "" {
		priority = "P2"
	}
	tags := ArgString(args, "tags")
	if tags == "" {
		tags = "untagged"
	}
	plan := ArgString(args, "plan")

	id := fmt.Sprintf("%s-%03d", cfg.IdPrefix, cfg.NextId)
	block := tpBuildTaskBlock(id, title, priority, tags, plan)

	fileName, ok := cfg.stateFileName("backlog")
	if !ok {
		fileName = "BACKLOG.md"
	}
	fp := filepath.Join(t.m.dir, fileName)
	lines, err := tpReadFileLines(fp)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	if len(lines) == 0 {
		lines = []string{"# Backlog", ""}
	}
	newLines := tpInsertTaskBlock(lines, block, cfg.InsertPosition)
	if err := tpWriteLines(fp, newLines); err != nil {
		return NewErrorResult(err.Error())
	}
	cfg.NextId++
	if err := tpSaveConfig(t.m.dir, cfg); err != nil {
		return NewErrorResult(fmt.Sprintf("created task but failed to save config: %v", err))
	}
	return NewTextResult(fmt.Sprintf("Created %s: %s in %s\nPriority: %s | Tags: %s", id, title, fileName, priority, tags))
}

// ---------------------------------------------------------------------------
// taskplanner_move
// ---------------------------------------------------------------------------

type tpMoveTool struct{ m *TaskplannerModule }

func (t *tpMoveTool) Name() string { return "taskplanner_move" }
func (t *tpMoveTool) Description() string {
	return "Move a task from its current state to another state. Cuts from source file, pastes in target file."
}
func (t *tpMoveTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"id": Prop("string", "task ID to move"),
		"toState": PropEnum("target state: backlog, next, in_progress, done, rejected",
			"backlog", "next", "in_progress", "done", "rejected"),
	}, []string{"id", "toState"})
}
func (t *tpMoveTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	cfg, err := t.m.loadConfig()
	if err != nil {
		return NewErrorResult(err.Error())
	}
	id := ArgString(args, "id")
	if id == "" {
		return NewErrorResult("id is required")
	}
	toState := ArgString(args, "toState")
	if toState == "" {
		return NewErrorResult("toState is required")
	}

	task, err := tpFindTask(t.m.dir, cfg, id)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	if task == nil {
		return NewTextResult(fmt.Sprintf("Task %s not found.", id))
	}
	toKey := tpCanonicalState(toState)
	toFile, ok := cfg.stateFileName(toKey)
	if !ok {
		return NewErrorResult(fmt.Sprintf("unknown target state: %s", toState))
	}
	if tpCanonicalState(task.State) == toKey {
		return NewTextResult(fmt.Sprintf("Task %s is already in %s.", id, toKey))
	}

	// Remove from source file.
	srcPath := filepath.Join(t.m.dir, task.FileName)
	srcLines, err := tpReadFileLines(srcPath)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	srcLines = tpRemoveTaskBlock(srcLines, id)
	if err := tpWriteLines(srcPath, srcLines); err != nil {
		return NewErrorResult(err.Error())
	}

	// Rebuild block with updated timestamp.
	block := tpBuildTaskBlock(task.ID, task.Title, task.Priority, task.Tags, task.Plan)

	// Insert into target file.
	dstPath := filepath.Join(t.m.dir, toFile)
	dstLines, err := tpReadFileLines(dstPath)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	if len(dstLines) == 0 {
		header := "# " + tpTitleCase(strings.ReplaceAll(toKey, "_", " "))
		dstLines = []string{header, ""}
	}
	newDst := tpInsertTaskBlock(dstLines, block, cfg.InsertPosition)
	if err := tpWriteLines(dstPath, newDst); err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(fmt.Sprintf("Moved %s from %s to %s.", id, task.State, toKey))
}

// ---------------------------------------------------------------------------
// taskplanner_update
// ---------------------------------------------------------------------------

type tpUpdateTool struct{ m *TaskplannerModule }

func (t *tpUpdateTool) Name() string { return "taskplanner_update" }
func (t *tpUpdateTool) Description() string {
	return "Update a task's title, priority, tags, description, or plan."
}
func (t *tpUpdateTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"id":          Prop("string", "task ID to update"),
		"title":       Prop("string", "new title"),
		"priority":    Prop("string", "new priority P0-P4"),
		"tags":        Prop("string", "new comma-separated tags"),
		"plan":        Prop("string", "new plan text"),
		"description": Prop("string", "new description text (replaces body before ### Plan)"),
	}, []string{"id"})
}
func (t *tpUpdateTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	cfg, err := t.m.loadConfig()
	if err != nil {
		return NewErrorResult(err.Error())
	}
	id := ArgString(args, "id")
	if id == "" {
		return NewErrorResult("id is required")
	}

	task, err := tpFindTask(t.m.dir, cfg, id)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	if task == nil {
		return NewTextResult(fmt.Sprintf("Task %s not found.", id))
	}

	title := task.Title
	if v := ArgString(args, "title"); v != "" {
		title = v
	}
	priority := task.Priority
	if v := ArgString(args, "priority"); v != "" {
		priority = v
	}
	tags := task.Tags
	if v := ArgString(args, "tags"); v != "" {
		tags = v
	}
	plan := task.Plan
	if v := ArgString(args, "plan"); v != "" {
		plan = v
	}
	description := ArgString(args, "description")

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
	fp := filepath.Join(t.m.dir, task.FileName)
	lines, err := tpReadFileLines(fp)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	lines = tpRemoveTaskBlock(lines, task.ID)
	lines = tpInsertTaskBlock(lines, newBlock, cfg.InsertPosition)
	if err := tpWriteLines(fp, lines); err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(fmt.Sprintf("Updated %s.", task.ID))
}

// ---------------------------------------------------------------------------
// taskplanner_delete
// ---------------------------------------------------------------------------

type tpDeleteTool struct{ m *TaskplannerModule }

func (t *tpDeleteTool) Name() string { return "taskplanner_delete" }
func (t *tpDeleteTool) Description() string {
	return "Delete a task from its state file."
}
func (t *tpDeleteTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"id": Prop("string", "task ID to delete"),
	}, []string{"id"})
}
func (t *tpDeleteTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	cfg, err := t.m.loadConfig()
	if err != nil {
		return NewErrorResult(err.Error())
	}
	id := ArgString(args, "id")
	if id == "" {
		return NewErrorResult("id is required")
	}

	task, err := tpFindTask(t.m.dir, cfg, id)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	if task == nil {
		return NewTextResult(fmt.Sprintf("Task %s not found.", id))
	}
	fp := filepath.Join(t.m.dir, task.FileName)
	lines, err := tpReadFileLines(fp)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	lines = tpRemoveTaskBlock(lines, id)
	if err := tpWriteLines(fp, lines); err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(fmt.Sprintf("Deleted %s from %s.", id, task.State))
}
