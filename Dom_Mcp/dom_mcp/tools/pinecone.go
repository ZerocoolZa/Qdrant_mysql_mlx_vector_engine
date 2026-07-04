package tools

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"
)

// PineconeModule is an HTTP client to the Pinecone vector DB API.
type PineconeModule struct {
	apiKey    string
	index     string
	host      string
	timeoutMs int
	client    *http.Client
}

// NewPineconeModule creates a Pinecone module from config.
// The API key is read from the environment variable named by apiKeyEnv,
// falling back to the apiKey config value when the env var is unset/empty.
func NewPineconeModule(apiKeyEnv, apiKeyFallback, index, host string, timeoutMs int) (*PineconeModule, error) {
	apiKey := ""
	if apiKeyEnv != "" {
		apiKey = os.Getenv(apiKeyEnv)
	}
	if apiKey == "" {
		apiKey = apiKeyFallback
	}
	if timeoutMs <= 0 {
		timeoutMs = 30000
	}
	m := &PineconeModule{
		apiKey:    apiKey,
		index:     index,
		host:      host,
		timeoutMs: timeoutMs,
		client: &http.Client{
			Timeout: time.Duration(timeoutMs) * time.Millisecond,
		},
	}
	return m, nil
}

func (m *PineconeModule) Name() string { return "pinecone" }

func (m *PineconeModule) Tools() []Tool {
	return []Tool{
		&listIndexesTool{m: m},
		&describeIndexTool{m: m},
		&describeIndexStatsTool{m: m},
		&createIndexForModelTool{m: m},
		&searchRecordsTool{m: m},
		&upsertRecordsTool{m: m},
		&searchDocsTool{m: m},
		&cascadingSearchTool{m: m},
		&rerankDocumentsTool{m: m},
	}
}

// controlHost returns the Pinecone control-plane API base URL.
func (m *PineconeModule) controlHost() string {
	return "https://api.pinecone.io"
}

// dataHost returns the index data-plane host.
func (m *PineconeModule) dataHost() string {
	if m.host != "" {
		return m.host
	}
	return ""
}

// ensureHost returns the data-plane host, auto-discovering it from
// describe_index when not explicitly configured.
func (m *PineconeModule) ensureHost() (string, error) {
	if m.host != "" {
		return m.host, nil
	}
	if m.index == "" {
		return "", fmt.Errorf("pinecone host not configured and no default index set (set [tools.pinecone] host or index in config)")
	}
	out, err := m.do(context.Background(), http.MethodGet, m.controlHost()+"/indexes/"+m.index, nil)
	if err != nil {
		return "", fmt.Errorf("auto-discover host failed: %w", err)
	}
	var resp struct {
		Host string `json:"host"`
	}
	if err := json.Unmarshal([]byte(out), &resp); err != nil {
		return "", fmt.Errorf("parse index description: %w", err)
	}
	if resp.Host == "" {
		return "", fmt.Errorf("index %s has no host field", m.index)
	}
	m.host = resp.Host
	return m.host, nil
}

// do performs an HTTP request to the Pinecone API.
func (m *PineconeModule) do(ctx context.Context, method, url string, body any) (string, error) {
	if m.apiKey == "" {
		return "", fmt.Errorf("pinecone API key not set (set api_key in config or the env var named by api_key_env)")
	}
	var reqBody io.Reader
	if body != nil {
		data, err := json.Marshal(body)
		if err != nil {
			return "", fmt.Errorf("marshal body: %w", err)
		}
		reqBody = bytes.NewReader(data)
	}
	req, err := http.NewRequestWithContext(ctx, method, url, reqBody)
	if err != nil {
		return "", err
	}
	req.Header.Set("Api-Key", m.apiKey)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Pinecone-API-Version", "2024-07")
	resp, err := m.client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", err
	}
	if resp.StatusCode >= 400 {
		return "", fmt.Errorf("pinecone API %s: %s", resp.Status, string(respBody))
	}
	return string(respBody), nil
}

// doWithVersion performs an HTTP request with a custom X-Pinecone-API-Version header.
func (m *PineconeModule) doWithVersion(ctx context.Context, method, url string, body any, apiVersion string) (string, error) {
	if m.apiKey == "" {
		return "", fmt.Errorf("pinecone API key not set (set api_key in config or the env var named by api_key_env)")
	}
	var reqBody io.Reader
	if body != nil {
		data, err := json.Marshal(body)
		if err != nil {
			return "", fmt.Errorf("marshal body: %w", err)
		}
		reqBody = bytes.NewReader(data)
	}
	req, err := http.NewRequestWithContext(ctx, method, url, reqBody)
	if err != nil {
		return "", err
	}
	req.Header.Set("Api-Key", m.apiKey)
	req.Header.Set("Content-Type", "application/json")
	if apiVersion == "" {
		apiVersion = "2024-07"
	}
	req.Header.Set("X-Pinecone-API-Version", apiVersion)
	resp, err := m.client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", err
	}
	if resp.StatusCode >= 400 {
		return "", fmt.Errorf("pinecone API %s: %s", resp.Status, string(respBody))
	}
	return string(respBody), nil
}

// --- list_indexes ---

type listIndexesTool struct{ m *PineconeModule }

func (t *listIndexesTool) Name() string { return "pinecone_list_indexes" }
func (t *listIndexesTool) Description() string {
	return "List all Pinecone indexes in the project."
}
func (t *listIndexesTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{}, nil)
}
func (t *listIndexesTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	out, err := t.m.do(ctx, http.MethodGet, t.m.controlHost()+"/indexes", nil)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(out)
}

// --- describe_index ---

type describeIndexTool struct{ m *PineconeModule }

func (t *describeIndexTool) Name() string { return "pinecone_describe_index" }
func (t *describeIndexTool) Description() string {
	return "Get detailed metadata for a specific Pinecone index."
}
func (t *describeIndexTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"index": Prop("string", "Name of the index to describe."),
	}, []string{"index"})
}
func (t *describeIndexTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	index := ArgString(args, "index")
	if index == "" {
		index = t.m.index
	}
	if index == "" {
		return NewErrorResult("index is required (or set [tools.pinecone] index in config)")
	}
	out, err := t.m.do(ctx, http.MethodGet, t.m.controlHost()+"/indexes/"+index, nil)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(out)
}

// --- search_records ---

type searchRecordsTool struct{ m *PineconeModule }

func (t *searchRecordsTool) Name() string { return "pinecone_search_records" }
func (t *searchRecordsTool) Description() string {
	return "Search records in a Pinecone index using vector or text query."
}
func (t *searchRecordsTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"query":     Prop("string", "Text query to search for."),
		"top_k":     Prop("integer", "Number of top results to return (default 10)."),
		"namespace": Prop("string", "Optional namespace within the index."),
		"index":     Prop("string", "Index name (defaults to configured index)."),
	}, []string{"query"})
}
func (t *searchRecordsTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	query := ArgString(args, "query")
	if query == "" {
		return NewErrorResult("query is required")
	}
	topK := ArgInt(args, "top_k", 10)
	namespace := ArgString(args, "namespace")
	host, err := t.m.ensureHost()
	if err != nil {
		return NewErrorResult(err.Error())
	}
	body := map[string]any{
		"query": map[string]any{
			"top_k": topK,
			"inputs": map[string]any{
				"text": query,
			},
		},
	}
	if namespace != "" {
		body["namespace"] = namespace
	}
	url := fmt.Sprintf("https://%s/search", host)
	out, err := t.m.do(ctx, http.MethodPost, url, body)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(out)
}

// --- upsert_records ---

type upsertRecordsTool struct{ m *PineconeModule }

func (t *upsertRecordsTool) Name() string { return "pinecone_upsert_records" }
func (t *upsertRecordsTool) Description() string {
	return "Upsert records (vectors with metadata) into a Pinecone index."
}
func (t *upsertRecordsTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"records":   PropArray("object", "List of record objects to upsert."),
		"namespace": Prop("string", "Optional namespace within the index."),
	}, []string{"records"})
}
func (t *upsertRecordsTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	records := ArgArray(args, "records")
	if len(records) == 0 {
		return NewErrorResult("records is required")
	}
	namespace := ArgString(args, "namespace")
	host, err := t.m.ensureHost()
	if err != nil {
		return NewErrorResult(err.Error())
	}
	body := map[string]any{
		"records": records,
	}
	if namespace != "" {
		body["namespace"] = namespace
	}
	url := fmt.Sprintf("https://%s/records/upsert", host)
	out, err := t.m.do(ctx, http.MethodPost, url, body)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(out)
}

// --- describe_index_stats ---

type describeIndexStatsTool struct{ m *PineconeModule }

func (t *describeIndexStatsTool) Name() string { return "pinecone_describe_index_stats" }
func (t *describeIndexStatsTool) Description() string {
	return "Get statistics for a specific Pinecone index (vector count, dimension, etc)."
}
func (t *describeIndexStatsTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"index": Prop("string", "Name of the index."),
	}, []string{"index"})
}
func (t *describeIndexStatsTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	host, err := t.m.ensureHost()
	if err != nil {
		return NewErrorResult(err.Error())
	}
	url := fmt.Sprintf("https://%s/describe_index_stats", host)
	out, err := t.m.do(ctx, http.MethodPost, url, map[string]any{})
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(out)
}

// --- create_index_for_model ---

type createIndexForModelTool struct{ m *PineconeModule }

func (t *createIndexForModelTool) Name() string { return "pinecone_create_index_for_model" }
func (t *createIndexForModelTool) Description() string {
	return "Create a new Pinecone index that uses an integrated inference model to embed text."
}
func (t *createIndexForModelTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"name":   Prop("string", "Name for the new index."),
		"model":  Prop("string", "Model name for integrated inference (e.g. multilingual-e5-large)."),
		"metric": Prop("string", "Distance metric (cosine, euclidean, dotproduct)."),
		"region": Prop("string", "Cloud region for the index (default us-east-1)."),
		"cloud":  Prop("string", "Cloud provider for the index (default aws)."),
	}, []string{"name", "model"})
}
func (t *createIndexForModelTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	name := ArgString(args, "name")
	model := ArgString(args, "model")
	if name == "" || model == "" {
		return NewErrorResult("name and model are required")
	}
	metric := ArgString(args, "metric")
	if metric == "" {
		metric = "cosine"
	}
	region := ArgString(args, "region")
	if region == "" {
		region = "us-east-1"
	}
	cloud := ArgString(args, "cloud")
	if cloud == "" {
		cloud = "aws"
	}
	body := map[string]any{
		"name":   name,
		"metric": metric,
		"region": region,
		"cloud":  cloud,
		"embed": map[string]any{
			"model": model,
		},
	}
	out, err := t.m.do(ctx, http.MethodPost, t.m.controlHost()+"/indexes", body)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(out)
}

// --- search_docs ---

type searchDocsTool struct{ m *PineconeModule }

func (t *searchDocsTool) Name() string { return "pinecone_search_docs" }
func (t *searchDocsTool) Description() string {
	return "Search Pinecone documentation for relevant content."
}
func (t *searchDocsTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"query": Prop("string", "Search query for documentation."),
		"top_k": Prop("integer", "Number of results (default 5)."),
	}, []string{"query"})
}
func (t *searchDocsTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	query := ArgString(args, "query")
	if query == "" {
		return NewErrorResult("query is required")
	}
	topK := ArgInt(args, "top_k", 5)
	host, err := t.m.ensureHost()
	if err != nil {
		return NewErrorResult(err.Error())
	}
	body := map[string]any{
		"query": map[string]any{
			"top_k": topK,
			"inputs": map[string]any{
				"text": query,
			},
		},
	}
	url := fmt.Sprintf("https://%s/search", host)
	out, err := t.m.do(ctx, http.MethodPost, url, body)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(out)
}

// --- cascading_search ---

type cascadingSearchTool struct{ m *PineconeModule }

func (t *cascadingSearchTool) Name() string { return "pinecone_cascading_search" }
func (t *cascadingSearchTool) Description() string {
	return "Search records with cascading reranking for higher precision."
}
func (t *cascadingSearchTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"query":     Prop("string", "Text query to search for."),
		"top_k":     Prop("integer", "Number of results (default 10)."),
		"namespace": Prop("string", "Optional namespace."),
		"rerank":    Prop("boolean", "Whether to rerank results (default true)."),
	}, []string{"query"})
}
func (t *cascadingSearchTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	query := ArgString(args, "query")
	if query == "" {
		return NewErrorResult("query is required")
	}
	topK := ArgInt(args, "top_k", 10)
	namespace := ArgString(args, "namespace")
	host, err := t.m.ensureHost()
	if err != nil {
		return NewErrorResult(err.Error())
	}
	body := map[string]any{
		"query": map[string]any{
			"top_k": topK,
			"inputs": map[string]any{
				"text": query,
			},
		},
		"rerank": map[string]any{
			"model":   "bge-reranker-v2-m3",
			"top_n":   topK,
			"enabled": true,
		},
	}
	if namespace != "" {
		body["namespace"] = namespace
	}
	url := fmt.Sprintf("https://%s/search", host)
	out, err := t.m.do(ctx, http.MethodPost, url, body)
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(out)
}

// --- rerank_documents ---

type rerankDocumentsTool struct{ m *PineconeModule }

func (t *rerankDocumentsTool) Name() string { return "pinecone_rerank_documents" }
func (t *rerankDocumentsTool) Description() string {
	return "Rerank a list of documents using a Pinecone reranking model."
}
func (t *rerankDocumentsTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"query":     Prop("string", "Query to rerank against."),
		"documents": PropArray("string", "List of document texts to rerank."),
		"top_n":     Prop("integer", "Number of top documents to return."),
		"model":     Prop("string", "Rerank model (default bge-reranker-v2-m3)."),
	}, []string{"query", "documents"})
}
func (t *rerankDocumentsTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	query := ArgString(args, "query")
	docs := ArgArray(args, "documents")
	if query == "" || len(docs) == 0 {
		return NewErrorResult("query and documents are required")
	}
	topN := ArgInt(args, "top_n", len(docs))
	model := ArgString(args, "model")
	if model == "" {
		model = "bge-reranker-v2-m3"
	}
	body := map[string]any{
		"query":     query,
		"documents": docs,
		"top_n":     topN,
		"model":     model,
	}
	out, err := t.m.doWithVersion(ctx, http.MethodPost, t.m.controlHost()+"/rerank", body, "2025-04")
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return NewTextResult(out)
}
