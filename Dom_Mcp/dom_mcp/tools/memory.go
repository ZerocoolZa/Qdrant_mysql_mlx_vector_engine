package tools

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"
	"sync"
)

// MemoryModule provides a JSON-file-backed knowledge graph memory store.
type MemoryModule struct {
	mu   sync.Mutex
	path string
}

// Entity is a knowledge graph node.
type Entity struct {
	Name         string   `json:"name"`
	EntityType   string   `json:"entityType"`
	Observations []string `json:"observations"`
}

// Relation is a directed edge between two entities.
type Relation struct {
	From         string `json:"from"`
	To           string `json:"to"`
	RelationType string `json:"relationType"`
}

// KnowledgeGraph is the full in-memory graph.
type KnowledgeGraph struct {
	Entities  []Entity   `json:"entities"`
	Relations []Relation `json:"relations"`
}

// NewMemoryModule creates a memory module backed by a JSON file.
func NewMemoryModule(memoryFile string) (*MemoryModule, error) {
	if memoryFile == "" {
		return nil, fmt.Errorf("memory_file is required")
	}
	m := &MemoryModule{path: memoryFile}
	// Ensure the file exists (empty graph if not).
	if _, err := os.Stat(memoryFile); os.IsNotExist(err) {
		if err := m.save(&KnowledgeGraph{}); err != nil {
			return nil, err
		}
	}
	return m, nil
}

func (m *MemoryModule) Name() string { return "memory" }

func (m *MemoryModule) Tools() []Tool {
	return []Tool{
		&createEntitiesTool{m: m},
		&createRelationsTool{m: m},
		&addObservationsTool{m: m},
		&deleteEntitiesTool{m: m},
		&deleteRelationsTool{m: m},
		&deleteObservationsTool{m: m},
		&searchNodesTool{m: m},
		&readGraphTool{m: m},
		&openNodesTool{m: m},
	}
}

// load reads the graph from the JSON file.
func (m *MemoryModule) load() (*KnowledgeGraph, error) {
	data, err := os.ReadFile(m.path)
	if err != nil {
		if os.IsNotExist(err) {
			return &KnowledgeGraph{}, nil
		}
		return nil, err
	}
	var g KnowledgeGraph
	if len(data) == 0 {
		return &g, nil
	}
	if err := json.Unmarshal(data, &g); err != nil {
		return nil, fmt.Errorf("unmarshal memory: %w", err)
	}
	return &g, nil
}

// save writes the graph to the JSON file.
func (m *MemoryModule) save(g *KnowledgeGraph) error {
	data, err := json.MarshalIndent(g, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(m.path, data, 0o644)
}

// --- create_entities ---

type createEntitiesTool struct{ m *MemoryModule }

func (t *createEntitiesTool) Name() string { return "create_entities" }
func (t *createEntitiesTool) Description() string {
	return "Create multiple new entities in the knowledge graph."
}
func (t *createEntitiesTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"entities": PropArray("object", "List of entity objects to create."),
	}, []string{"entities"})
}
func (t *createEntitiesTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	raw := ArgArray(args, "entities")
	if len(raw) == 0 {
		return NewErrorResult("entities is required")
	}
	entities := make([]Entity, 0, len(raw))
	for _, v := range raw {
		b, _ := json.Marshal(v)
		var e Entity
		if err := json.Unmarshal(b, &e); err != nil {
			return NewErrorResult(fmt.Sprintf("invalid entity: %v", err))
		}
		entities = append(entities, e)
	}
	t.m.mu.Lock()
	defer t.m.mu.Unlock()
	g, err := t.m.load()
	if err != nil {
		return NewErrorResult(err.Error())
	}
	existing := make(map[string]bool)
	for _, e := range g.Entities {
		existing[e.Name] = true
	}
	var created []Entity
	for _, e := range entities {
		if existing[e.Name] {
			continue
		}
		g.Entities = append(g.Entities, e)
		created = append(created, e)
		existing[e.Name] = true
	}
	if err := t.m.save(g); err != nil {
		return NewErrorResult(err.Error())
	}
	return JSONResult(created)
}

// --- create_relations ---

type createRelationsTool struct{ m *MemoryModule }

func (t *createRelationsTool) Name() string { return "create_relations" }
func (t *createRelationsTool) Description() string {
	return "Create multiple new relations between entities in the knowledge graph."
}
func (t *createRelationsTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"relations": PropArray("object", "List of relation objects to create."),
	}, []string{"relations"})
}
func (t *createRelationsTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	raw := ArgArray(args, "relations")
	if len(raw) == 0 {
		return NewErrorResult("relations is required")
	}
	relations := make([]Relation, 0, len(raw))
	for _, v := range raw {
		b, _ := json.Marshal(v)
		var r Relation
		if err := json.Unmarshal(b, &r); err != nil {
			return NewErrorResult(fmt.Sprintf("invalid relation: %v", err))
		}
		relations = append(relations, r)
	}
	t.m.mu.Lock()
	defer t.m.mu.Unlock()
	g, err := t.m.load()
	if err != nil {
		return NewErrorResult(err.Error())
	}
	known := make(map[string]bool)
	for _, e := range g.Entities {
		known[e.Name] = true
	}
	var created []Relation
	for _, r := range relations {
		if !known[r.From] || !known[r.To] {
			continue
		}
		g.Relations = append(g.Relations, r)
		created = append(created, r)
	}
	if err := t.m.save(g); err != nil {
		return NewErrorResult(err.Error())
	}
	return JSONResult(created)
}

// --- search_nodes ---

type searchNodesTool struct{ m *MemoryModule }

func (t *searchNodesTool) Name() string { return "search_nodes" }
func (t *searchNodesTool) Description() string {
	return "Search for nodes in the knowledge graph by query string."
}
func (t *searchNodesTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"query": Prop("string", "Search query to match against entity names, types, and observations."),
		"limit": Prop("integer", "Maximum number of results (default 10)."),
	}, []string{"query"})
}
func (t *searchNodesTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	query := strings.ToLower(ArgString(args, "query"))
	limit := ArgInt(args, "limit", 10)
	if query == "" {
		return NewErrorResult("query is required")
	}
	t.m.mu.Lock()
	defer t.m.mu.Unlock()
	g, err := t.m.load()
	if err != nil {
		return NewErrorResult(err.Error())
	}
	type scored struct {
		e    Entity
		rank int
	}
	var matches []scored
	for _, e := range g.Entities {
		rank := 0
		if strings.Contains(strings.ToLower(e.Name), query) {
			rank += 100
		}
		if strings.Contains(strings.ToLower(e.EntityType), query) {
			rank += 50
		}
		for _, obs := range e.Observations {
			if strings.Contains(strings.ToLower(obs), query) {
				rank += 20
			}
		}
		if rank > 0 {
			matches = append(matches, scored{e, rank})
		}
	}
	sort.Slice(matches, func(i, j int) bool { return matches[i].rank > matches[j].rank })
	if limit > 0 && len(matches) > limit {
		matches = matches[:limit]
	}
	results := make([]Entity, 0, len(matches))
	for _, m := range matches {
		results = append(results, m.e)
	}
	return JSONResult(results)
}

// --- read_graph ---

type readGraphTool struct{ m *MemoryModule }

func (t *readGraphTool) Name() string { return "read_graph" }
func (t *readGraphTool) Description() string {
	return "Read the entire knowledge graph."
}
func (t *readGraphTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{}, nil)
}
func (t *readGraphTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	t.m.mu.Lock()
	defer t.m.mu.Unlock()
	g, err := t.m.load()
	if err != nil {
		return NewErrorResult(err.Error())
	}
	return JSONResult(g)
}

// --- open_nodes ---

type openNodesTool struct{ m *MemoryModule }

func (t *openNodesTool) Name() string { return "open_nodes" }
func (t *openNodesTool) Description() string {
	return "Retrieve specific nodes by name from the knowledge graph."
}
func (t *openNodesTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"names": PropArray("string", "List of entity names to retrieve."),
	}, []string{"names"})
}
func (t *openNodesTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	names := ArgStringArray(args, "names")
	if len(names) == 0 {
		return NewErrorResult("names is required")
	}
	t.m.mu.Lock()
	defer t.m.mu.Unlock()
	g, err := t.m.load()
	if err != nil {
		return NewErrorResult(err.Error())
	}
	want := make(map[string]bool)
	for _, n := range names {
		want[n] = true
	}
	var entities []Entity
	for _, e := range g.Entities {
		if want[e.Name] {
			entities = append(entities, e)
		}
	}
	return JSONResult(KnowledgeGraph{Entities: entities})
}

// --- add_observations ---

type addObservationsTool struct{ m *MemoryModule }

func (t *addObservationsTool) Name() string { return "add_observations" }
func (t *addObservationsTool) Description() string {
	return "Add new observations to existing entities in the knowledge graph."
}
func (t *addObservationsTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"observations": PropArray("object", "List of {entityName, observations} objects."),
	}, []string{"observations"})
}
func (t *addObservationsTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	raw := ArgArray(args, "observations")
	if len(raw) == 0 {
		return NewErrorResult("observations is required")
	}
	type obsAdd struct {
		EntityName   string   `json:"entityName"`
		Observations []string `json:"observations"`
	}
	var adds []obsAdd
	for _, v := range raw {
		b, _ := json.Marshal(v)
		var oa obsAdd
		if err := json.Unmarshal(b, &oa); err != nil {
			return NewErrorResult(fmt.Sprintf("invalid observation: %v", err))
		}
		adds = append(adds, oa)
	}
	t.m.mu.Lock()
	defer t.m.mu.Unlock()
	g, err := t.m.load()
	if err != nil {
		return NewErrorResult(err.Error())
	}
	entityMap := make(map[string]*Entity)
	for i := range g.Entities {
		entityMap[g.Entities[i].Name] = &g.Entities[i]
	}
	var results []map[string]any
	for _, oa := range adds {
		e, ok := entityMap[oa.EntityName]
		if !ok {
			results = append(results, map[string]any{"entityName": oa.EntityName, "error": "entity not found"})
			continue
		}
		existing := make(map[string]bool)
		for _, obs := range e.Observations {
			existing[obs] = true
		}
		var added []string
		for _, obs := range oa.Observations {
			if !existing[obs] {
				e.Observations = append(e.Observations, obs)
				existing[obs] = true
				added = append(added, obs)
			}
		}
		results = append(results, map[string]any{"entityName": oa.EntityName, "added": added})
	}
	if err := t.m.save(g); err != nil {
		return NewErrorResult(err.Error())
	}
	return JSONResult(results)
}

// --- delete_entities ---

type deleteEntitiesTool struct{ m *MemoryModule }

func (t *deleteEntitiesTool) Name() string { return "delete_entities" }
func (t *deleteEntitiesTool) Description() string {
	return "Delete entities and their relations from the knowledge graph."
}
func (t *deleteEntitiesTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"entityNames": PropArray("string", "List of entity names to delete."),
	}, []string{"entityNames"})
}
func (t *deleteEntitiesTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	names := ArgStringArray(args, "entityNames")
	if len(names) == 0 {
		return NewErrorResult("entityNames is required")
	}
	t.m.mu.Lock()
	defer t.m.mu.Unlock()
	g, err := t.m.load()
	if err != nil {
		return NewErrorResult(err.Error())
	}
	toDelete := make(map[string]bool)
	for _, n := range names {
		toDelete[n] = true
	}
	var kept []Entity
	for _, e := range g.Entities {
		if !toDelete[e.Name] {
			kept = append(kept, e)
		}
	}
	g.Entities = kept
	var keptRels []Relation
	for _, r := range g.Relations {
		if !toDelete[r.From] && !toDelete[r.To] {
			keptRels = append(keptRels, r)
		}
	}
	g.Relations = keptRels
	if err := t.m.save(g); err != nil {
		return NewErrorResult(err.Error())
	}
	return JSONResult(map[string]any{"deleted": names})
}

// --- delete_relations ---

type deleteRelationsTool struct{ m *MemoryModule }

func (t *deleteRelationsTool) Name() string { return "delete_relations" }
func (t *deleteRelationsTool) Description() string {
	return "Delete relations from the knowledge graph."
}
func (t *deleteRelationsTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"relations": PropArray("object", "List of {from, to, relationType} to delete."),
	}, []string{"relations"})
}
func (t *deleteRelationsTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	raw := ArgArray(args, "relations")
	if len(raw) == 0 {
		return NewErrorResult("relations is required")
	}
	var toDelete []Relation
	for _, v := range raw {
		b, _ := json.Marshal(v)
		var r Relation
		if err := json.Unmarshal(b, &r); err != nil {
			return NewErrorResult(fmt.Sprintf("invalid relation: %v", err))
		}
		toDelete = append(toDelete, r)
	}
	t.m.mu.Lock()
	defer t.m.mu.Unlock()
	g, err := t.m.load()
	if err != nil {
		return NewErrorResult(err.Error())
	}
	delSet := make(map[string]bool)
	for _, r := range toDelete {
		delSet[r.From+"|"+r.To+"|"+r.RelationType] = true
	}
	var kept []Relation
	for _, r := range g.Relations {
		if !delSet[r.From+"|"+r.To+"|"+r.RelationType] {
			kept = append(kept, r)
		}
	}
	g.Relations = kept
	if err := t.m.save(g); err != nil {
		return NewErrorResult(err.Error())
	}
	return JSONResult(map[string]any{"deleted": len(toDelete)})
}

// --- delete_observations ---

type deleteObservationsTool struct{ m *MemoryModule }

func (t *deleteObservationsTool) Name() string { return "delete_observations" }
func (t *deleteObservationsTool) Description() string {
	return "Delete specific observations from entities in the knowledge graph."
}
func (t *deleteObservationsTool) InputSchema() map[string]any {
	return Schema(map[string]map[string]any{
		"deletions": PropArray("object", "List of {entityName, observations} to delete."),
	}, []string{"deletions"})
}
func (t *deleteObservationsTool) Execute(ctx context.Context, args map[string]any) *ToolResult {
	raw := ArgArray(args, "deletions")
	if len(raw) == 0 {
		return NewErrorResult("deletions is required")
	}
	type obsDel struct {
		EntityName   string   `json:"entityName"`
		Observations []string `json:"observations"`
	}
	var dels []obsDel
	for _, v := range raw {
		b, _ := json.Marshal(v)
		var od obsDel
		if err := json.Unmarshal(b, &od); err != nil {
			return NewErrorResult(fmt.Sprintf("invalid deletion: %v", err))
		}
		dels = append(dels, od)
	}
	t.m.mu.Lock()
	defer t.m.mu.Unlock()
	g, err := t.m.load()
	if err != nil {
		return NewErrorResult(err.Error())
	}
	delMap := make(map[string]map[string]bool)
	for _, od := range dels {
		m := make(map[string]bool)
		for _, obs := range od.Observations {
			m[obs] = true
		}
		delMap[od.EntityName] = m
	}
	for i := range g.Entities {
		if dm, ok := delMap[g.Entities[i].Name]; ok {
			var kept []string
			for _, obs := range g.Entities[i].Observations {
				if !dm[obs] {
					kept = append(kept, obs)
				}
			}
			g.Entities[i].Observations = kept
		}
	}
	if err := t.m.save(g); err != nil {
		return NewErrorResult(err.Error())
	}
	return JSONResult(map[string]any{"deleted_from": len(dels)})
}
