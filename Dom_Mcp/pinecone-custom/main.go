// pinecone-custom-mcp: a native Go MCP server for Pinecone.
//
// Replaces the npx @pinecone-database/mcp Node.js server (~40-70 MB RAM)
// with a native Go binary (~10 MB RAM) speaking MCP JSON-RPC over stdio.
//
// Built with the official Go MCP SDK: github.com/modelcontextprotocol/go-sdk
// All Pinecone calls use net/http stdlib (no external deps beyond the SDK).
//
// Required env: PINECONE_API_KEY
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

const (
	pineconeAPIBase = "https://api.pinecone.io"
	pineconeAPIKey  = "PINECONE_API_KEY"
	httpTimeout     = 60 * time.Second
)

// pineconeClient wraps HTTP calls to the Pinecone REST API.
type pineconeClient struct {
	apiKey string
	http   *http.Client
}

func newPineconeClient() (*pineconeClient, error) {
	key := os.Getenv(pineconeAPIKey)
	if key == "" {
		return nil, fmt.Errorf("PINECONE_API_KEY environment variable is not set")
	}
	return &pineconeClient{
		apiKey: key,
		http:   &http.Client{Timeout: httpTimeout},
	}, nil
}

// do performs an HTTP request to Pinecone and returns the raw body bytes.
// When fullURL is true, path is treated as an absolute URL (index host).
func (c *pineconeClient) do(method, path string, body any, fullURL bool) ([]byte, int, error) {
	var url string
	if fullURL {
		url = path
	} else {
		url = pineconeAPIBase + path
	}

	var reader io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			return nil, 0, fmt.Errorf("marshal request body: %w", err)
		}
		reader = bytes.NewReader(b)
	}

	req, err := http.NewRequest(method, url, reader)
	if err != nil {
		return nil, 0, fmt.Errorf("build request: %w", err)
	}
	req.Header.Set("Api-Key", c.apiKey)
	req.Header.Set("X-Pinecone-Api-Version", "2024-07")
	req.Header.Set("Accept", "application/json")
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	resp, err := c.http.Do(req)
	if err != nil {
		return nil, 0, fmt.Errorf("http request: %w", err)
	}
	defer resp.Body.Close()

	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, resp.StatusCode, fmt.Errorf("read response: %w", err)
	}
	if resp.StatusCode >= 400 {
		return data, resp.StatusCode, fmt.Errorf("pinecone API error (HTTP %d): %s", resp.StatusCode, truncate(string(data), 500))
	}
	return data, resp.StatusCode, nil
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "..."
}

// textResult builds an MCP CallToolResult with a single text content block.
func textResult(text string, isError bool) *mcp.CallToolResult {
	return &mcp.CallToolResult{
		Content: []mcp.Content{
			&mcp.TextContent{Text: text},
		},
		IsError: isError,
	}
}

// jsonText pretty-prints raw JSON bytes, falling back to the raw string.
func jsonText(b []byte) string {
	var dst bytes.Buffer
	if err := json.Indent(&dst, b, "", "  "); err == nil {
		return dst.String()
	}
	return string(b)
}

// errResult wraps an error into an MCP error tool result.
func errResult(err error) *mcp.CallToolResult {
	return textResult("Error: "+err.Error(), true)
}

// ---------------------------------------------------------------------------
// Tool argument structs. Struct tags drive the JSON Schema for tool inputs:
// `json:"name"` sets the argument key; `jsonschema:"desc"` sets the
// description. omitempty marks optional fields.
// ---------------------------------------------------------------------------

type listIndexesArgs struct{}

type describeIndexArgs struct {
	Name string `json:"name" jsonschema:"the name of the index to describe"`
}

type describeIndexStatsArgs struct {
	Name string `json:"name" jsonschema:"the name of the index to get stats for"`
}

type searchDocsArgs struct {
	Query  string `json:"query" jsonschema:"the natural-language query to search the Pinecone documentation"`
	TopK   int    `json:"topK,omitempty" jsonschema:"optional max number of results to return (default 10)"`
	Region string `json:"region,omitempty" jsonschema:"optional Pinecone region (e.g. us-east-1)"`
}

type createIndexForModelArgs struct {
	Name      string `json:"name" jsonschema:"the name for the new index"`
	Dimension int    `json:"dimension,omitempty" jsonschema:"optional vector dimension (required for non-integrated-embedding indexes)"`
	Metric    string `json:"metric,omitempty" jsonschema:"similarity metric: cosine, euclidean, or dotproduct"`
	Cloud     string `json:"cloud,omitempty" jsonschema:"cloud provider: aws, gcp, or azure"`
	Region    string `json:"region,omitempty" jsonschema:"cloud region for the index"`
	Deletion  string `json:"deletionProtection,omitempty" jsonschema:"optional deletion protection: enabled or disabled"`
	Namespace string `json:"namespace,omitempty" jsonschema:"optional namespace for the index"`
	// Integrated embedding model fields.
	Model         string `json:"model,omitempty" jsonschema:"the integrated inference model name to embed text (e.g. multilingual-e5-large)"`
	ModelType     string `json:"modelType,omitempty" jsonschema:"optional model type (e.g. embed)"`
	ModelProvider string `json:"modelProvider,omitempty" jsonschema:"optional model provider (e.g. cohere)"`
}

type upsertRecordsArgs struct {
	Name      string        `json:"name" jsonschema:"the name of the index to upsert into"`
	Namespace string        `json:"namespace,omitempty" jsonschema:"optional namespace (default empty)"`
	Records   []interface{} `json:"records" jsonschema:"array of records to upsert; each record is an object with an _id field and fields to embed/store"`
}

type searchRecordsArgs struct {
	Name      string                 `json:"name" jsonschema:"the name of the index to search"`
	Namespace string                 `json:"namespace,omitempty" jsonschema:"optional namespace (default empty)"`
	Query     map[string]interface{} `json:"query" jsonschema:"search query object, e.g. {\"topK\":10,\"inputs\":{\"text\":\"<query text>\"}}"`
	Rerank    map[string]interface{} `json:"rerank,omitempty" jsonschema:"optional rerank object, e.g. {\"model\":\"bge-reranker-v2-m3\",\"topN\":10}"`
}

type cascadingSearchArgs struct {
	Name       string                 `json:"name" jsonschema:"the name of the index to search"`
	Namespace  string                 `json:"namespace,omitempty" jsonschema:"optional namespace (default empty)"`
	Query      map[string]interface{} `json:"query" jsonschema:"search query object, e.g. {\"topK\":10,\"inputs\":{\"text\":\"<query text>\"}}"`
	Rerank     map[string]interface{} `json:"rerank,omitempty" jsonschema:"rerank configuration, e.g. {\"model\":\"bge-reranker-v2-m3\",\"topN\":10,\"query\":{\"text\":\"<query>\"}}"`
}

type rerankDocumentsArgs struct {
	Model     string                 `json:"model" jsonschema:"the rerank model to use, e.g. bge-reranker-v2-m3"`
	Query     string                 `json:"query" jsonschema:"the query to rerank documents against"`
	Documents []map[string]interface{} `json:"documents" jsonschema:"array of documents to rerank; each is an object, e.g. {\"text\":\"...\"}"`
	TopN      int                    `json:"topN,omitempty" jsonschema:"optional max number of reranked results to return"`
	ReturnDocuments string           `json:"returnDocuments,omitempty" jsonschema:"optional: whether to return full documents (true) or just indices (false)"`
}

// ---------------------------------------------------------------------------
// Tool handlers
// ---------------------------------------------------------------------------

func handleListIndexes(ctx context.Context, req *mcp.CallToolRequest, _ listIndexesArgs) (*mcp.CallToolResult, any, error) {
	pc, err := newPineconeClient()
	if err != nil {
		return errResult(err), nil, nil
	}
	data, _, err := pc.do(http.MethodGet, "/indexes", nil, false)
	if err != nil {
		return errResult(err), nil, nil
	}
	return textResult(jsonText(data), false), nil, nil
}

func handleDescribeIndex(ctx context.Context, req *mcp.CallToolRequest, args describeIndexArgs) (*mcp.CallToolResult, any, error) {
	if args.Name == "" {
		return errResult(fmt.Errorf("name is required")), nil, nil
	}
	pc, err := newPineconeClient()
	if err != nil {
		return errResult(err), nil, nil
	}
	data, _, err := pc.do(http.MethodGet, "/indexes/"+args.Name, nil, false)
	if err != nil {
		return errResult(err), nil, nil
	}
	return textResult(jsonText(data), false), nil, nil
}

func handleDescribeIndexStats(ctx context.Context, req *mcp.CallToolRequest, args describeIndexStatsArgs) (*mcp.CallToolResult, any, error) {
	if args.Name == "" {
		return errResult(fmt.Errorf("name is required")), nil, nil
	}
	pc, err := newPineconeClient()
	if err != nil {
		return errResult(err), nil, nil
	}
	data, _, err := pc.do(http.MethodGet, "/indexes/"+args.Name+"/stats", nil, false)
	if err != nil {
		return errResult(err), nil, nil
	}
	return textResult(jsonText(data), false), nil, nil
}

func handleSearchDocs(ctx context.Context, req *mcp.CallToolRequest, args searchDocsArgs) (*mcp.CallToolResult, any, error) {
	if args.Query == "" {
		return errResult(fmt.Errorf("query is required")), nil, nil
	}
	pc, err := newPineconeClient()
	if err != nil {
		return errResult(err), nil, nil
	}
	body := map[string]interface{}{
		"query":  args.Query,
		"topK":   args.TopK,
		"region": args.Region,
	}
	data, _, err := pc.do(http.MethodPost, "/search", body, false)
	if err != nil {
		return errResult(err), nil, nil
	}
	return textResult(jsonText(data), false), nil, nil
}

func handleCreateIndexForModel(ctx context.Context, req *mcp.CallToolRequest, args createIndexForModelArgs) (*mcp.CallToolResult, any, error) {
	if args.Name == "" {
		return errResult(fmt.Errorf("name is required")), nil, nil
	}
	pc, err := newPineconeClient()
	if err != nil {
		return errResult(err), nil, nil
	}
	body := map[string]interface{}{
		"name":   args.Name,
		"metric": args.Metric,
		"spec": map[string]interface{}{
			"serverless": map[string]interface{}{
				"cloud":  args.Cloud,
				"region": args.Region,
			},
		},
	}
	if args.Deletion != "" {
		body["deletionProtection"] = args.Deletion
	}
	if args.Dimension > 0 {
		body["dimension"] = args.Dimension
	}
	if args.Model != "" {
		embed := map[string]interface{}{
			"model":     args.Model,
			"field":     map[string]string{"type": "text", "name": "chunk_text"},
			"metric":    args.Metric,
			"namespace": args.Namespace,
		}
		if args.ModelType != "" {
			embed["modelType"] = args.ModelType
		}
		if args.ModelProvider != "" {
			embed["modelProvider"] = args.ModelProvider
		}
		body["embed"] = embed
	}
	data, status, err := pc.do(http.MethodPost, "/indexes", body, false)
	if err != nil && status != 201 {
		return errResult(err), nil, nil
	}
	return textResult(jsonText(data), false), nil, nil
}

// resolveHost fetches the index description and returns its host endpoint.
func (c *pineconeClient) resolveHost(indexName string) (string, error) {
	data, _, err := c.do(http.MethodGet, "/indexes/"+indexName, nil, false)
	if err != nil {
		return "", fmt.Errorf("resolve index host: %w", err)
	}
	var idx struct {
		Host string `json:"host"`
	}
	if err := json.Unmarshal(data, &idx); err != nil {
		return "", fmt.Errorf("parse index description: %w", err)
	}
	if idx.Host == "" {
		return "", fmt.Errorf("index %q has no host field", indexName)
	}
	return "https://" + idx.Host, nil
}

func handleUpsertRecords(ctx context.Context, req *mcp.CallToolRequest, args upsertRecordsArgs) (*mcp.CallToolResult, any, error) {
	if args.Name == "" {
		return errResult(fmt.Errorf("name is required")), nil, nil
	}
	if len(args.Records) == 0 {
		return errResult(fmt.Errorf("records is required and must be non-empty")), nil, nil
	}
	pc, err := newPineconeClient()
	if err != nil {
		return errResult(err), nil, nil
	}
	host, err := pc.resolveHost(args.Name)
	if err != nil {
		return errResult(err), nil, nil
	}
	path := host + "/records"
	if args.Namespace != "" {
		path += "?namespace=" + args.Namespace
	}
	data, _, err := pc.do(http.MethodPost, path, args.Records, true)
	if err != nil {
		return errResult(err), nil, nil
	}
	return textResult(jsonText(data), false), nil, nil
}

func handleSearchRecords(ctx context.Context, req *mcp.CallToolRequest, args searchRecordsArgs) (*mcp.CallToolResult, any, error) {
	if args.Name == "" {
		return errResult(fmt.Errorf("name is required")), nil, nil
	}
	if args.Query == nil {
		return errResult(fmt.Errorf("query is required")), nil, nil
	}
	pc, err := newPineconeClient()
	if err != nil {
		return errResult(err), nil, nil
	}
	host, err := pc.resolveHost(args.Name)
	if err != nil {
		return errResult(err), nil, nil
	}
	path := host + "/records/search"
	if args.Namespace != "" {
		path += "?namespace=" + args.Namespace
	}
	body := map[string]interface{}{"query": args.Query}
	if args.Rerank != nil {
		body["rerank"] = args.Rerank
	}
	data, _, err := pc.do(http.MethodPost, path, body, true)
	if err != nil {
		return errResult(err), nil, nil
	}
	return textResult(jsonText(data), false), nil, nil
}

// handleCascadingSearch performs a search with reranking (cascading retrieval).
// It runs a vector search then applies a rerank model on the results, returning
// the reranked hits. The Pinecone records/search endpoint accepts a "rerank"
// field in the request body to perform this in a single call.
func handleCascadingSearch(ctx context.Context, req *mcp.CallToolRequest, args cascadingSearchArgs) (*mcp.CallToolResult, any, error) {
	if args.Name == "" {
		return errResult(fmt.Errorf("name is required")), nil, nil
	}
	if args.Query == nil {
		return errResult(fmt.Errorf("query is required")), nil, nil
	}
	if args.Rerank == nil {
		return errResult(fmt.Errorf("rerank is required for cascading search")), nil, nil
	}
	pc, err := newPineconeClient()
	if err != nil {
		return errResult(err), nil, nil
	}
	host, err := pc.resolveHost(args.Name)
	if err != nil {
		return errResult(err), nil, nil
	}
	path := host + "/records/search"
	if args.Namespace != "" {
		path += "?namespace=" + args.Namespace
	}
	body := map[string]interface{}{
		"query":  args.Query,
		"rerank": args.Rerank,
	}
	data, _, err := pc.do(http.MethodPost, path, body, true)
	if err != nil {
		return errResult(err), nil, nil
	}
	return textResult(jsonText(data), false), nil, nil
}

// handleRerankDocuments calls the Pinecone rerank API to rerank a list of
// documents against a query using a reranking model.
func handleRerankDocuments(ctx context.Context, req *mcp.CallToolRequest, args rerankDocumentsArgs) (*mcp.CallToolResult, any, error) {
	if args.Model == "" {
		return errResult(fmt.Errorf("model is required")), nil, nil
	}
	if args.Query == "" {
		return errResult(fmt.Errorf("query is required")), nil, nil
	}
	if len(args.Documents) == 0 {
		return errResult(fmt.Errorf("documents is required and must be non-empty")), nil, nil
	}
	pc, err := newPineconeClient()
	if err != nil {
		return errResult(err), nil, nil
	}
	body := map[string]interface{}{
		"model":     args.Model,
		"query":     args.Query,
		"documents": args.Documents,
	}
	if args.TopN > 0 {
		body["topN"] = args.TopN
	}
	if args.ReturnDocuments != "" {
		body["returnDocuments"] = args.ReturnDocuments
	}
	data, _, err := pc.do(http.MethodPost, "/rerank", body, false)
	if err != nil {
		return errResult(err), nil, nil
	}
	return textResult(jsonText(data), false), nil, nil
}

// ---------------------------------------------------------------------------
// Server setup
// ---------------------------------------------------------------------------

func main() {
	// Route logs to stderr so the stdio JSON-RPC stream stays clean.
	log.SetOutput(os.Stderr)

	server := mcp.NewServer(&mcp.Implementation{
		Name:    "pinecone-custom-mcp",
		Version: "v1.0.0",
	}, nil)

	// list-indexes
	mcp.AddTool(server,
		&mcp.Tool{Name: "list-indexes", Description: "List all Pinecone indexes in the current project."},
		handleListIndexes)

	// describe-index
	mcp.AddTool(server,
		&mcp.Tool{Name: "describe-index", Description: "Describe the configuration of a Pinecone index by name."},
		handleDescribeIndex)

	// describe-index-stats
	mcp.AddTool(server,
		&mcp.Tool{Name: "describe-index-stats", Description: "Get statistics (record count, namespaces) for a Pinecone index."},
		handleDescribeIndexStats)

	// search-docs
	mcp.AddTool(server,
		&mcp.Tool{Name: "search-docs", Description: "Search the official Pinecone documentation for the given natural-language query."},
		handleSearchDocs)

	// create-index-for-model
	mcp.AddTool(server,
		&mcp.Tool{Name: "create-index-for-model", Description: "Create a new Pinecone index that uses an integrated inference model to embed text as vectors."},
		handleCreateIndexForModel)

	// upsert-records
	mcp.AddTool(server,
		&mcp.Tool{Name: "upsert-records", Description: "Insert or update records in a Pinecone index with integrated inference."},
		handleUpsertRecords)

	// search-records
	mcp.AddTool(server,
		&mcp.Tool{Name: "search-records", Description: "Search for records in a Pinecone index using a text query with integrated inference embedding. Supports metadata filtering and reranking."},
		handleSearchRecords)

	// cascading-search
	mcp.AddTool(server,
		&mcp.Tool{Name: "cascading-search", Description: "Perform a cascading search: run a vector search on a Pinecone index, then rerank the results with a rerank model in a single call."},
		handleCascadingSearch)

	// rerank-documents
	mcp.AddTool(server,
		&mcp.Tool{Name: "rerank-documents", Description: "Rerank a list of documents against a query using a Pinecone rerank model (e.g. bge-reranker-v2-m3)."},
		handleRerankDocuments)

	// Run over stdio until the client disconnects.
	if err := server.Run(context.Background(), &mcp.StdioTransport{}); err != nil {
		log.Printf("pinecone-custom-mcp server failed: %v", err)
		os.Exit(1)
	}
}
