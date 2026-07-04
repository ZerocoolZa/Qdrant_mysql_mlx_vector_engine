package tools

import (
	"context"
	"database/sql"
	"fmt"
	"strings"

	_ "github.com/go-sql-driver/mysql"
)

// MysqlModule provides MySQL query tools using the pure-Go go-sql-driver/mysql driver.
// Supports cross-database operations, show databases/tables, describe, count, and
// safe read/write queries with WHERE-clause enforcement for UPDATE/DELETE.
type MysqlModule struct {
	db *sql.DB
}

// NewMysqlModule opens the MySQL database connection.
func NewMysqlModule(host string, port int, user, password, database string) (*MysqlModule, error) {
	if host == "" {
		host = "localhost"
	}
	if port == 0 {
		port = 3306
	}
	if user == "" {
		user = "root"
	}
	dsn := fmt.Sprintf("%s:%s@tcp(%s:%d)/%s?parseTime=true&multiStatements=true", user, password, host, port, database)
	db, err := sql.Open("mysql", dsn)
	if err != nil {
		return nil, fmt.Errorf("open mysql %s:%d/%s: %w", host, port, database, err)
	}
	if err := db.Ping(); err != nil {
		db.Close()
		return nil, fmt.Errorf("ping mysql %s:%d/%s: %w", host, port, database, err)
	}
	return &MysqlModule{db: db}, nil
}

// Close closes the database connection.
func (m *MysqlModule) Close() error {
	if m.db != nil {
		return m.db.Close()
	}
	return nil
}

func (m *MysqlModule) Name() string { return "mysql" }

func (m *MysqlModule) Tools() []Tool {
	return []Tool{
		&mysqlShowDatabasesTool{m: m},
		&mysqlShowTablesTool{m: m},
		&mysqlDescribeTableTool{m: m},
		&mysqlTableInfoTool{m: m},
		&mysqlCountRowsTool{m: m},
		&mysqlReadQueryTool{m: m},
		&mysqlWriteQueryTool{m: m},
		&mysqlSelectTool{m: m},
		&mysqlInsertTool{m: m},
		&mysqlUpdateTool{m: m},
		&mysqlDeleteTool{m: m},
	}
}

// --- mysql_show_databases ---

type mysqlShowDatabasesTool struct{ m *MysqlModule }

func (t *mysqlShowDatabasesTool) Name() string { return "mysql_show_databases" }
func (t *mysqlShowDatabasesTool) Description() string {
	return "List all available MySQL databases."
}
func (t *mysqlShowDatabasesTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{}, nil)
}
func (t *mysqlShowDatabasesTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	rows, err := t.m.db.QueryContext(ctx, "SHOW DATABASES")
	if err != nil {
		return NewErrorResult(fmt.Sprintf("query: %v", err))
	}
	defer rows.Close()
	var dbs []string
	for rows.Next() {
		var name string
		if err := rows.Scan(&name); err != nil {
			return NewErrorResult(fmt.Sprintf("scan: %v", err))
		}
		dbs = append(dbs, name)
	}
	return JSONResult(map[string]any{"databases": dbs})
}

// --- mysql_show_tables ---

type mysqlShowTablesTool struct{ m *MysqlModule }

func (t *mysqlShowTablesTool) Name() string { return "mysql_show_tables" }
func (t *mysqlShowTablesTool) Description() string {
	return "List all tables in a MySQL database. Optional 'database' parameter for cross-database queries."
}
func (t *mysqlShowTablesTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"database": Prop("string", "Database name (optional — uses default if omitted)."),
	}, nil)
}
func (t *mysqlShowTablesTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	dbName := ArgString(args, "database")
	var rows *sql.Rows
	var err error
	if dbName != "" {
		rows, err = t.m.db.QueryContext(ctx, fmt.Sprintf("SHOW TABLES FROM %s", mysqlQuoteIdent(dbName)))
	} else {
		rows, err = t.m.db.QueryContext(ctx, "SHOW TABLES")
	}
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
	return JSONResult(map[string]any{"tables": tables, "database": dbName})
}

// --- mysql_describe_table ---

type mysqlDescribeTableTool struct{ m *MysqlModule }

func (t *mysqlDescribeTableTool) Name() string { return "mysql_describe_table" }
func (t *mysqlDescribeTableTool) Description() string {
	return "Show column structure of a MySQL table. Optional 'database' parameter for cross-database queries."
}
func (t *mysqlDescribeTableTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"table":    Prop("string", "Name of the table to describe."),
		"database": Prop("string", "Database name (optional — uses default if omitted)."),
	}, []string{"table"})
}
func (t *mysqlDescribeTableTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	table := ArgString(args, "table")
	if table == "" {
		return NewErrorResult("table is required")
	}
	dbName := ArgString(args, "database")
	var query string
	if dbName != "" {
		query = fmt.Sprintf("DESCRIBE %s.%s", mysqlQuoteIdent(dbName), mysqlQuoteIdent(table))
	} else {
		query = fmt.Sprintf("DESCRIBE %s", mysqlQuoteIdent(table))
	}
	rows, err := t.m.db.QueryContext(ctx, query)
	if err != nil {
		return NewErrorResult(fmt.Sprintf("describe: %v", err))
	}
	defer rows.Close()
	type colInfo struct {
		Field   string `json:"field"`
		Type    string `json:"type"`
		Null    string `json:"null"`
		Key     string `json:"key"`
		Default any    `json:"default"`
		Extra   string `json:"extra"`
	}
	var cols []colInfo
	for rows.Next() {
		var c colInfo
		if err := rows.Scan(&c.Field, &c.Type, &c.Null, &c.Key, &c.Default, &c.Extra); err != nil {
			return NewErrorResult(fmt.Sprintf("scan: %v", err))
		}
		cols = append(cols, c)
	}
	return JSONResult(map[string]any{"table": table, "columns": cols})
}

// --- mysql_table_info ---

type mysqlTableInfoTool struct{ m *MysqlModule }

func (t *mysqlTableInfoTool) Name() string { return "mysql_table_info" }
func (t *mysqlTableInfoTool) Description() string {
	return "Comprehensive table analysis: structure, indexes, row count, and constraints."
}
func (t *mysqlTableInfoTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"table":    Prop("string", "Name of the table to analyze."),
		"database": Prop("string", "Database name (optional — uses default if omitted)."),
	}, []string{"table"})
}
func (t *mysqlTableInfoTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	table := ArgString(args, "table")
	if table == "" {
		return NewErrorResult("table is required")
	}
	dbName := ArgString(args, "database")
	var prefix string
	if dbName != "" {
		prefix = fmt.Sprintf("%s.%s", mysqlQuoteIdent(dbName), mysqlQuoteIdent(table))
	} else {
		prefix = mysqlQuoteIdent(table)
	}

	// Columns
	colRows, err := t.m.db.QueryContext(ctx, fmt.Sprintf("DESCRIBE %s", prefix))
	if err != nil {
		return NewErrorResult(fmt.Sprintf("describe: %v", err))
	}
	defer colRows.Close()
	type colInfo struct {
		Field   string `json:"field"`
		Type    string `json:"type"`
		Null    string `json:"null"`
		Key     string `json:"key"`
		Default any    `json:"default"`
		Extra   string `json:"extra"`
	}
	var cols []colInfo
	for colRows.Next() {
		var c colInfo
		if err := colRows.Scan(&c.Field, &c.Type, &c.Null, &c.Key, &c.Default, &c.Extra); err != nil {
			return NewErrorResult(fmt.Sprintf("scan col: %v", err))
		}
		cols = append(cols, c)
	}

	// Indexes
	idxRows, err := t.m.db.QueryContext(ctx, fmt.Sprintf("SHOW INDEX FROM %s", prefix))
	if err != nil {
		return JSONResult(map[string]any{"table": table, "columns": cols, "indexes": nil, "error": fmt.Sprintf("show index: %v", err)})
	}
	defer idxRows.Close()
	type idxInfo struct {
		KeyName  string `json:"key_name"`
		Column   string `json:"column_name"`
		NonUnique bool  `json:"non_unique"`
		SeqInIdx int    `json:"seq_in_index"`
	}
	var indexes []idxInfo
	for idxRows.Next() {
		var seq, nonUnique int
		var keyName, colName string
		// SHOW INDEX returns many columns — we only need a few
		scanCols := make([]any, 16)
		scanPtrs := make([]any, 16)
		for i := range scanCols {
			scanPtrs[i] = &scanCols[i]
		}
		if err := idxRows.Scan(scanPtrs...); err != nil {
			// Fallback: try minimal scan
			continue
		}
		if s, ok := scanCols[1].(string); ok {
			keyName = s
		}
		if s, ok := scanCols[4].(string); ok {
			colName = s
		}
		if n, ok := scanCols[0].(int64); ok {
			nonUnique = int(n)
		}
		if n, ok := scanCols[3].(int64); ok {
			seq = int(n)
		}
		indexes = append(indexes, idxInfo{
			KeyName:   keyName,
			Column:    colName,
			NonUnique: nonUnique == 1,
			SeqInIdx:  seq,
		})
	}

	// Row count (approximate — fast on large tables)
	var rowCount int64
	_ = t.m.db.QueryRowContext(ctx, fmt.Sprintf("SELECT COUNT(*) FROM %s", prefix)).Scan(&rowCount)

	return JSONResult(map[string]any{
		"table":     table,
		"columns":   cols,
		"indexes":   indexes,
		"rowCount":  rowCount,
	})
}

// --- mysql_count_rows ---

type mysqlCountRowsTool struct{ m *MysqlModule }

func (t *mysqlCountRowsTool) Name() string { return "mysql_count_rows" }
func (t *mysqlCountRowsTool) Description() string {
	return "Count rows in a table with optional WHERE conditions."
}
func (t *mysqlCountRowsTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"table":    Prop("string", "Table name."),
		"database": Prop("string", "Database name (optional)."),
		"where":    Prop("string", "WHERE clause (optional, e.g. \"status = 'active'\""),
	}, []string{"table"})
}
func (t *mysqlCountRowsTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	table := ArgString(args, "table")
	if table == "" {
		return NewErrorResult("table is required")
	}
	dbName := ArgString(args, "database")
	where := ArgString(args, "where")
	var prefix string
	if dbName != "" {
		prefix = fmt.Sprintf("%s.%s", mysqlQuoteIdent(dbName), mysqlQuoteIdent(table))
	} else {
		prefix = mysqlQuoteIdent(table)
	}
	query := fmt.Sprintf("SELECT COUNT(*) FROM %s", prefix)
	if where != "" {
		query += " WHERE " + where
	}
	var count int64
	if err := t.m.db.QueryRowContext(ctx, query).Scan(&count); err != nil {
		return NewErrorResult(fmt.Sprintf("count: %v", err))
	}
	return JSONResult(map[string]any{"table": table, "count": count})
}

// --- mysql_read_query ---

type mysqlReadQueryTool struct{ m *MysqlModule }

func (t *mysqlReadQueryTool) Name() string { return "mysql_read_query" }
func (t *mysqlReadQueryTool) Description() string {
	return "Execute a read-only SELECT query on MySQL and return rows as JSON."
}
func (t *mysqlReadQueryTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"query":    Prop("string", "SELECT SQL query to execute."),
		"database": Prop("string", "Database to USE before running the query (optional)."),
	}, []string{"query"})
}
func (t *mysqlReadQueryTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	query := ArgString(args, "query")
	if query == "" {
		return NewErrorResult("query is required")
	}
	dbName := ArgString(args, "database")
	upper := strings.ToUpper(strings.TrimSpace(query))
	if !strings.HasPrefix(upper, "SELECT") && !strings.HasPrefix(upper, "WITH") && !strings.HasPrefix(upper, "SHOW") && !strings.HasPrefix(upper, "DESCRIBE") && !strings.HasPrefix(upper, "EXPLAIN") {
		return NewErrorResult("mysql_read_query only supports SELECT, WITH, SHOW, DESCRIBE, or EXPLAIN queries")
	}
	if dbName != "" {
		if _, err := t.m.db.ExecContext(ctx, fmt.Sprintf("USE %s", mysqlQuoteIdent(dbName))); err != nil {
			return NewErrorResult(fmt.Sprintf("use database: %v", err))
		}
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

// --- mysql_write_query ---

type mysqlWriteQueryTool struct{ m *MysqlModule }

func (t *mysqlWriteQueryTool) Name() string { return "mysql_write_query" }
func (t *mysqlWriteQueryTool) Description() string {
	return "Execute an INSERT, UPDATE, DELETE, CREATE, ALTER, or DROP statement and return rows affected."
}
func (t *mysqlWriteQueryTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"query":    Prop("string", "SQL statement (INSERT/UPDATE/DELETE/CREATE/ALTER/DROP)."),
		"database": Prop("string", "Database to USE before running the query (optional)."),
	}, []string{"query"})
}
func (t *mysqlWriteQueryTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	query := ArgString(args, "query")
	if query == "" {
		return NewErrorResult("query is required")
	}
	dbName := ArgString(args, "database")
	if dbName != "" {
		if _, err := t.m.db.ExecContext(ctx, fmt.Sprintf("USE %s", mysqlQuoteIdent(dbName))); err != nil {
			return NewErrorResult(fmt.Sprintf("use database: %v", err))
		}
	}
	res, err := t.m.db.ExecContext(ctx, query)
	if err != nil {
		return NewErrorResult(fmt.Sprintf("exec: %v", err))
	}
	affected, _ := res.RowsAffected()
	lastID, _ := res.LastInsertId()
	return JSONResult(map[string]any{"rowsAffected": affected, "lastInsertId": lastID})
}

// --- mysql_select (smart builder) ---

type mysqlSelectTool struct{ m *MysqlModule }

func (t *mysqlSelectTool) Name() string { return "mysql_select" }
func (t *mysqlSelectTool) Description() string {
	return "Smart SELECT builder with WHERE, LIMIT, ORDER BY, and optional database parameter."
}
func (t *mysqlSelectTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"table":    Prop("string", "Table name to select from."),
		"columns":  PropArray("string", "Columns to select (default: *)."),
		"where":    Prop("string", "WHERE clause (optional)."),
		"limit":    Prop("integer", "Maximum rows to return (default: 100)."),
		"order_by": Prop("string", "ORDER BY clause (optional)."),
		"database": Prop("string", "Database name (optional)."),
	}, []string{"table"})
}
func (t *mysqlSelectTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	table := ArgString(args, "table")
	if table == "" {
		return NewErrorResult("table is required")
	}
	dbName := ArgString(args, "database")
	cols := ArgStringArray(args, "columns")
	where := ArgString(args, "where")
	limit := ArgInt(args, "limit", 100)
	orderBy := ArgString(args, "order_by")

	colStr := "*"
	if len(cols) > 0 {
		quoted := make([]string, len(cols))
		for i, c := range cols {
			quoted[i] = mysqlQuoteIdent(c)
		}
		colStr = strings.Join(quoted, ", ")
	}

	var prefix string
	if dbName != "" {
		prefix = fmt.Sprintf("%s.%s", mysqlQuoteIdent(dbName), mysqlQuoteIdent(table))
	} else {
		prefix = mysqlQuoteIdent(table)
	}

	query := fmt.Sprintf("SELECT %s FROM %s", colStr, prefix)
	if where != "" {
		query += " WHERE " + where
	}
	if orderBy != "" {
		query += " ORDER BY " + orderBy
	}
	query += fmt.Sprintf(" LIMIT %d", limit)

	rows, err := t.m.db.QueryContext(ctx, query)
	if err != nil {
		return NewErrorResult(fmt.Sprintf("query: %v", err))
	}
	defer rows.Close()
	resultCols, err := rows.Columns()
	if err != nil {
		return NewErrorResult(fmt.Sprintf("columns: %v", err))
	}
	var results []map[string]any
	for rows.Next() {
		vals := make([]any, len(resultCols))
		ptrs := make([]any, len(resultCols))
		for i := range vals {
			ptrs[i] = &vals[i]
		}
		if err := rows.Scan(ptrs...); err != nil {
			return NewErrorResult(fmt.Sprintf("scan: %v", err))
		}
		row := make(map[string]any, len(resultCols))
		for i, c := range resultCols {
			row[c] = vals[i]
		}
		results = append(results, row)
	}
	return JSONResult(map[string]any{"columns": resultCols, "rows": results, "rowCount": len(results)})
}

// --- mysql_insert (safe key-value builder) ---

type mysqlInsertTool struct{ m *MysqlModule }

func (t *mysqlInsertTool) Name() string { return "mysql_insert" }
func (t *mysqlInsertTool) Description() string {
	return "Insert data with key-value pairs. Safe parameterized query."
}
func (t *mysqlInsertTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"table":    Prop("string", "Table name."),
		"database": Prop("string", "Database name (optional)."),
		"data":     Prop("object", "Key-value pairs of column names to values."),
	}, []string{"table", "data"})
}
func (t *mysqlInsertTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	table := ArgString(args, "table")
	if table == "" {
		return NewErrorResult("table is required")
	}
	dbName := ArgString(args, "database")
	dataRaw, ok := args["data"].(map[string]any)
	if !ok || len(dataRaw) == 0 {
		return NewErrorResult("data is required and must be a non-empty object")
	}

	var prefix string
	if dbName != "" {
		prefix = fmt.Sprintf("%s.%s", mysqlQuoteIdent(dbName), mysqlQuoteIdent(table))
	} else {
		prefix = mysqlQuoteIdent(table)
	}

	keys := make([]string, 0, len(dataRaw))
	placeholders := make([]string, 0, len(dataRaw))
	values := make([]any, 0, len(dataRaw))
	for k, v := range dataRaw {
		keys = append(keys, mysqlQuoteIdent(k))
		placeholders = append(placeholders, "?")
		values = append(values, v)
	}

	query := fmt.Sprintf("INSERT INTO %s (%s) VALUES (%s)", prefix, strings.Join(keys, ", "), strings.Join(placeholders, ", "))
	res, err := t.m.db.ExecContext(ctx, query, values...)
	if err != nil {
		return NewErrorResult(fmt.Sprintf("insert: %v", err))
	}
	affected, _ := res.RowsAffected()
	lastID, _ := res.LastInsertId()
	return JSONResult(map[string]any{"rowsAffected": affected, "lastInsertId": lastID})
}

// --- mysql_update (safe, WHERE required) ---

type mysqlUpdateTool struct{ m *MysqlModule }

func (t *mysqlUpdateTool) Name() string { return "mysql_update" }
func (t *mysqlUpdateTool) Description() string {
	return "Update rows with key-value pairs. WHERE clause is REQUIRED for safety."
}
func (t *mysqlUpdateTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"table":    Prop("string", "Table name."),
		"database": Prop("string", "Database name (optional)."),
		"data":     Prop("object", "Key-value pairs of column names to new values."),
		"where":    Prop("string", "WHERE clause (REQUIRED — no full-table updates allowed)."),
	}, []string{"table", "data", "where"})
}
func (t *mysqlUpdateTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	table := ArgString(args, "table")
	if table == "" {
		return NewErrorResult("table is required")
	}
	dbName := ArgString(args, "database")
	dataRaw, ok := args["data"].(map[string]any)
	if !ok || len(dataRaw) == 0 {
		return NewErrorResult("data is required and must be a non-empty object")
	}
	where := ArgString(args, "where")
	if where == "" {
		return NewErrorResult("where clause is REQUIRED for mysql_update — full-table updates are not allowed")
	}

	var prefix string
	if dbName != "" {
		prefix = fmt.Sprintf("%s.%s", mysqlQuoteIdent(dbName), mysqlQuoteIdent(table))
	} else {
		prefix = mysqlQuoteIdent(table)
	}

	setParts := make([]string, 0, len(dataRaw))
	values := make([]any, 0, len(dataRaw)+1)
	for k, v := range dataRaw {
		setParts = append(setParts, fmt.Sprintf("%s = ?", mysqlQuoteIdent(k)))
		values = append(values, v)
	}

	query := fmt.Sprintf("UPDATE %s SET %s WHERE %s", prefix, strings.Join(setParts, ", "), where)
	res, err := t.m.db.ExecContext(ctx, query, values...)
	if err != nil {
		return NewErrorResult(fmt.Sprintf("update: %v", err))
	}
	affected, _ := res.RowsAffected()
	return JSONResult(map[string]any{"rowsAffected": affected})
}

// --- mysql_delete (safe, WHERE required) ---

type mysqlDeleteTool struct{ m *MysqlModule }

func (t *mysqlDeleteTool) Name() string { return "mysql_delete" }
func (t *mysqlDeleteTool) Description() string {
	return "Delete rows from a table. WHERE clause is REQUIRED for safety."
}
func (t *mysqlDeleteTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"table":    Prop("string", "Table name."),
		"database": Prop("string", "Database name (optional)."),
		"where":    Prop("string", "WHERE clause (REQUIRED — no full-table deletes allowed)."),
	}, []string{"table", "where"})
}
func (t *mysqlDeleteTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	table := ArgString(args, "table")
	if table == "" {
		return NewErrorResult("table is required")
	}
	dbName := ArgString(args, "database")
	where := ArgString(args, "where")
	if where == "" {
		return NewErrorResult("where clause is REQUIRED for mysql_delete — full-table deletes are not allowed")
	}

	var prefix string
	if dbName != "" {
		prefix = fmt.Sprintf("%s.%s", mysqlQuoteIdent(dbName), mysqlQuoteIdent(table))
	} else {
		prefix = mysqlQuoteIdent(table)
	}

	query := fmt.Sprintf("DELETE FROM %s WHERE %s", prefix, where)
	res, err := t.m.db.ExecContext(ctx, query)
	if err != nil {
		return NewErrorResult(fmt.Sprintf("delete: %v", err))
	}
	affected, _ := res.RowsAffected()
	return JSONResult(map[string]any{"rowsAffected": affected})
}

// mysqlQuoteIdent wraps an identifier in backticks for safe MySQL SQL interpolation.
func mysqlQuoteIdent(name string) string {
	return "`" + strings.ReplaceAll(name, "`", "``") + "`"
}
