package tools

import (
	"context"
	"database/sql"
	"fmt"
	"strings"

	_ "modernc.org/sqlite"
)

// SqliteModule provides SQLite query tools using the pure-Go modernc.org/sqlite driver.
type SqliteModule struct {
	db *sql.DB
}

// NewSqliteModule opens the SQLite database at dbPath.
func NewSqliteModule(dbPath string) (*SqliteModule, error) {
	if dbPath == "" {
		return nil, fmt.Errorf("sqlite db_path is required")
	}
	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		return nil, fmt.Errorf("open sqlite %s: %w", dbPath, err)
	}
	if err := db.Ping(); err != nil {
		db.Close()
		return nil, fmt.Errorf("ping sqlite %s: %w", dbPath, err)
	}
	return &SqliteModule{db: db}, nil
}

// Close closes the database connection.
func (m *SqliteModule) Close() error {
	if m.db != nil {
		return m.db.Close()
	}
	return nil
}

func (m *SqliteModule) Name() string { return "sqlite" }

func (m *SqliteModule) Tools() []Tool {
	return []Tool{
		&listTablesTool{m: m},
		&describeTableTool{m: m},
		&readQueryTool{m: m},
		&writeQueryTool{m: m},
		&createTableTool{m: m},
	}
}

// --- list_tables ---

type listTablesTool struct{ m *SqliteModule }

func (t *listTablesTool) Name() string { return "list_tables" }
func (t *listTablesTool) Description() string {
	return "List all tables in the SQLite database."
}
func (t *listTablesTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{}, nil)
}
func (t *listTablesTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	rows, err := t.m.db.QueryContext(ctx,
		"SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
	if err != nil {
		return NewErrorResult(fmt.Sprintf("query: %v", err))
	}
	defer rows.Close()
	var tables []string
	for rows.Next() {
		var name string
		if err := rows.Scan(&name); err != nil {
			return NewErrorResult(fmt.Sprintf("scan: %v", err))
		}
		tables = append(tables, name)
	}
	return JSONResult(map[string]any{"tables": tables})
}

// --- describe_table ---

type describeTableTool struct{ m *SqliteModule }

func (t *describeTableTool) Name() string { return "describe_table" }
func (t *describeTableTool) Description() string {
	return "Get the schema (column definitions) of a specific table."
}
func (t *describeTableTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"table": Prop("string", "Name of the table to describe."),
	}, []string{"table"})
}
func (t *describeTableTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	table := ArgString(args, "table")
	if table == "" {
		return NewErrorResult("table is required")
	}
	rows, err := t.m.db.QueryContext(ctx, fmt.Sprintf("PRAGMA table_info(%s)", quoteIdent(table)))
	if err != nil {
		return NewErrorResult(fmt.Sprintf("pragma: %v", err))
	}
	defer rows.Close()
	type colInfo struct {
		CID     int    `json:"cid"`
		Name    string `json:"name"`
		Type    string `json:"type"`
		NotNull bool   `json:"notnull"`
		Default any    `json:"default"`
		PK      bool   `json:"pk"`
	}
	var cols []colInfo
	for rows.Next() {
		var c colInfo
		var notnull, pk int
		if err := rows.Scan(&c.CID, &c.Name, &c.Type, &notnull, &c.Default, &pk); err != nil {
			return NewErrorResult(fmt.Sprintf("scan: %v", err))
		}
		c.NotNull = notnull == 1
		c.PK = pk == 1
		cols = append(cols, c)
	}
	return JSONResult(map[string]any{"table": table, "columns": cols})
}

// --- read_query ---

type readQueryTool struct{ m *SqliteModule }

func (t *readQueryTool) Name() string { return "read_query" }
func (t *readQueryTool) Description() string {
	return "Execute a read-only SELECT query and return rows as JSON."
}
func (t *readQueryTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"query": Prop("string", "SELECT SQL query to execute."),
	}, []string{"query"})
}
func (t *readQueryTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	query := ArgString(args, "query")
	if query == "" {
		return NewErrorResult("query is required")
	}
	q := strings.TrimSpace(query)
	upper := strings.ToUpper(q)
	if !strings.HasPrefix(upper, "SELECT") && !strings.HasPrefix(upper, "WITH") {
		return NewErrorResult("read_query only supports SELECT or WITH queries")
	}
	rows, err := t.m.db.QueryContext(ctx, query)
	if err != nil {
		return NewErrorResult(fmt.Sprintf("query: %v", err))
	}
	defer rows.Close()
	cols, err := rows.Columns()
	if err != nil {
		return NewErrorResult(fmt.Sprintf("columns: %v", err))
	}
	var results []map[string]any
	for rows.Next() {
		vals := make([]any, len(cols))
		ptrs := make([]any, len(cols))
		for i := range vals {
			ptrs[i] = &vals[i]
		}
		if err := rows.Scan(ptrs...); err != nil {
			return NewErrorResult(fmt.Sprintf("scan: %v", err))
		}
		row := make(map[string]any, len(cols))
		for i, c := range cols {
			row[c] = vals[i]
		}
		results = append(results, row)
	}
	return JSONResult(map[string]any{"columns": cols, "rows": results, "rowCount": len(results)})
}

// --- write_query ---

type writeQueryTool struct{ m *SqliteModule }

func (t *writeQueryTool) Name() string { return "write_query" }
func (t *writeQueryTool) Description() string {
	return "Execute an INSERT, UPDATE, or DELETE statement and return rows affected."
}
func (t *writeQueryTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"query": Prop("string", "INSERT/UPDATE/DELETE SQL statement."),
	}, []string{"query"})
}
func (t *writeQueryTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	query := ArgString(args, "query")
	if query == "" {
		return NewErrorResult("query is required")
	}
	res, err := t.m.db.ExecContext(ctx, query)
	if err != nil {
		return NewErrorResult(fmt.Sprintf("exec: %v", err))
	}
	affected, _ := res.RowsAffected()
	lastID, _ := res.LastInsertId()
	return JSONResult(map[string]any{"rowsAffected": affected, "lastInsertId": lastID})
}

// --- create_table ---

type createTableTool struct{ m *SqliteModule }

func (t *createTableTool) Name() string { return "create_table" }
func (t *createTableTool) Description() string {
	return "Create a new table with a given DDL statement."
}
func (t *createTableTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"query": Prop("string", "CREATE TABLE SQL statement."),
	}, []string{"query"})
}
func (t *createTableTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	query := ArgString(args, "query")
	if query == "" {
		return NewErrorResult("query is required")
	}
	upper := strings.ToUpper(strings.TrimSpace(query))
	if !strings.HasPrefix(upper, "CREATE TABLE") {
		return NewErrorResult("create_table requires a CREATE TABLE statement")
	}
	if _, err := t.m.db.ExecContext(ctx, query); err != nil {
		return NewErrorResult(fmt.Sprintf("exec: %v", err))
	}
	return NewTextResult("Table created successfully.")
}

// quoteIdent wraps an identifier in double quotes for safe SQL interpolation.
func quoteIdent(name string) string {
	return "\"" + strings.ReplaceAll(name, "\"", "\"\"") + "\""
}
