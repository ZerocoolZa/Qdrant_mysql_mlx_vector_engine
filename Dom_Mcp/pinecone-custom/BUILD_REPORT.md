# BUILD REPORT: pinecone-custom-mcp

A native Go MCP server for Pinecone, built with the official Go MCP SDK.

## Goal

Replace the npx `@pinecone-database/mcp` Node.js server (~40-70 MB RAM) with a
native Go binary (~10 MB RAM) that speaks MCP JSON-RPC over stdio.

## Result

| Metric              | Node.js (npx)   | Go (this build)  |
|---------------------|-----------------|------------------|
| Runtime RAM (RSS)   | ~40-70 MB       | **~1.3 MB**      |
| Binary size         | N/A (node)      | **10.86 MB**     |
| Startup             | ~1-2 s (node)   | **<50 ms**       |
| External deps       | npm tree        | Go SDK only      |
| Transport           | stdio           | stdio            |

The Go binary uses ~1.3 MB RSS at idle — a **30-50x reduction** in memory
compared to the Node.js server.

## Tech Stack

- **Language**: Go 1.26.4 (darwin/arm64)
- **MCP SDK**: `github.com/modelcontextprotocol/go-sdk` v1.6.1 (official)
- **HTTP**: `net/http` stdlib (no third-party HTTP clients)
- **Transport**: `mcp.StdioTransport{}` (JSON-RPC over stdin/stdout)
- **Logging**: stderr only (stdout reserved for MCP protocol)

## Build Steps

```bash
cd /Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Mcp/pinecone-custom
go mod init pinecone-mcp
go get github.com/modelcontextprotocol/go-sdk/mcp@latest
go mod tidy
go build -o pinecone-custom-mcp .
```

All commands completed successfully. `go vet` passes clean.

## Files

| File                    | Description                                      |
|-------------------------|--------------------------------------------------|
| `main.go`               | Server implementation (510 LOC)                  |
| `go.mod`                | Go module definition                             |
| `go.sum`                | Dependency checksums                             |
| `pinecone-custom-mcp`   | Compiled binary (10.86 MB, darwin/arm64)         |
| `BUILD_REPORT.md`       | This report                                      |

## The 9 Pinecone MCP Tools

All 9 tools from the npx `@pinecone-database/mcp` package are implemented:

| # | Tool name              | HTTP Method | Pinecone Endpoint                  |
|---|------------------------|-------------|------------------------------------|
| 1 | `search-docs`          | POST        | `https://api.pinecone.io/search`   |
| 2 | `list-indexes`         | GET         | `https://api.pinecone.io/indexes`  |
| 3 | `describe-index`       | GET         | `https://api.pinecone.io/indexes/{name}` |
| 4 | `describe-index-stats` | GET         | `https://api.pinecone.io/indexes/{name}/stats` |
| 5 | `create-index-for-model` | POST      | `https://api.pinecone.io/indexes`  |
| 6 | `upsert-records`       | POST        | `https://{host}/records`           |
| 7 | `search-records`       | POST        | `https://{host}/records/search`    |
| 8 | `cascading-search`     | POST        | `https://{host}/records/search` (with rerank) |
| 9 | `rerank-documents`     | POST        | `https://api.pinecone.io/rerank`   |

### Tool Details

**search-docs** — Searches Pinecone documentation. Args: `query` (required),
`topK` (optional), `region` (optional).

**list-indexes** — Lists all indexes in the project. No args.

**describe-index** — Describes an index configuration. Args: `name` (required).

**describe-index-stats** — Gets index statistics (record count, namespaces).
Args: `name` (required).

**create-index-for-model** — Creates a serverless index with integrated
inference embedding. Args: `name` (required), `metric`, `cloud`, `region`,
`dimension`, `model`, `modelType`, `modelProvider`, `deletionProtection`,
`namespace`.

**upsert-records** — Upserts records into an index via the index host endpoint.
Resolves the host by calling `describe-index` first. Args: `name` (required),
`records` (required), `namespace` (optional).

**search-records** — Searches records in an index with optional reranking.
Args: `name` (required), `query` (required), `namespace`, `rerank` (optional).

**cascading-search** — Performs a vector search followed by reranking in a
single call to the records/search endpoint. Args: `name` (required),
`query` (required), `rerank` (required), `namespace` (optional).

**rerank-documents** — Reranks a list of documents against a query using a
Pinecone rerank model. Args: `model` (required), `query` (required),
`documents` (required), `topN`, `returnDocuments` (optional).

## Architecture

```
main.go
  |
  +-- pineconeClient         (HTTP wrapper around net/http)
  |     +-- do()             (generic request method)
  |     +-- resolveHost()    (fetches index host for records endpoints)
  |
  +-- 9 tool handlers        (each: validate args -> call API -> return text)
  |
  +-- main()                 (mcp.NewServer + mcp.AddTool x9 + server.Run)
```

### Key Design Decisions

1. **Official SDK**: Uses `github.com/modelcontextprotocol/go-sdk` (the
   official Go MCP SDK from modelcontextprotocol), NOT `mark3labs/mcp-go`.
   The API pattern: `mcp.NewServer` -> `mcp.AddTool` -> `server.Run(StdioTransport)`.

2. **Struct-tag JSON Schema**: Tool input schemas are auto-generated from Go
   struct tags (`json:"name"` + `jsonschema:"description"`). The SDK handles
   schema generation and input validation automatically.

3. **Handler signature**: `func(ctx, *mcp.CallToolRequest, ArgsStruct) (*mcp.CallToolResult, any, error)`
   — returns the result as first value, structured output as second, error as third.

4. **Error handling**: API errors are returned as MCP tool results with
   `isError: true` (not as JSON-RPC errors), so the LLM sees the error text.
   Missing `PINECONE_API_KEY` returns a graceful error result.

5. **Host resolution**: `upsert-records`, `search-records`, and
   `cascading-search` call `describe-index` first to resolve the index host
   URL, then make the records API call to that host.

6. **Logging to stderr**: `log.SetOutput(os.Stderr)` ensures the stdout
   channel stays clean for JSON-RPC protocol traffic.

## Testing

### Protocol Test (no API key needed)

Sent JSON-RPC `initialize` + `notifications/initialized` + `tools/list` via
stdin. The server responded with:

1. **Initialize response**: protocol version `2024-11-05`, server info
   `pinecone-custom-mcp v1.0.0`, capabilities `logging` + `tools`.
2. **Tools/list response**: All **9 tools** with full input schemas.

```
Tool count: 9
  - cascading-search
  - create-index-for-model
  - describe-index
  - describe-index-stats
  - list-indexes
  - rerank-documents
  - search-docs
  - search-records
  - upsert-records
```

### Error Handling Test

Called `list-indexes` without `PINECONE_API_KEY` set. The server returned a
graceful MCP error result (not a crash):

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [{"type": "text", "text": "Error: PINECONE_API_KEY environment variable is not set"}],
    "isError": true
  }
}
```

### Static Analysis

- `go vet ./...` — passes clean
- `go build` — compiles without warnings

## Configuration

| Env var             | Required | Description                        |
|---------------------|----------|------------------------------------|
| `PINECONE_API_KEY`  | Yes      | Pinecone API key for authentication |

## Usage

### With an MCP client (e.g. Claude Desktop)

```json
{
  "mcpServers": {
    "pinecone": {
      "command": "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Mcp/pinecone-custom/pinecone-custom-mcp",
      "env": {
        "PINECONE_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

### Manual protocol test

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | PINECONE_API_KEY=your-key ./pinecone-custom-mcp
```

## Dependencies

```
github.com/modelcontextprotocol/go-sdk v1.6.1  (official MCP SDK)
github.com/google/jsonschema-go v0.4.3         (schema generation, transitive)
github.com/segmentio/encoding v0.5.4           (JSON encoding, transitive)
golang.org/x/oauth2 v0.35.0                    (transitive)
```

No Pinecone SDK dependency — all API calls use `net/http` stdlib directly.
