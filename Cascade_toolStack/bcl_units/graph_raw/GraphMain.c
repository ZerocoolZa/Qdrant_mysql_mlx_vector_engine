// GraphMain — entry point for the Max Graph Engine
// Parses config, loads stored graph from MySQL, runs query, exports results as JSON

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Print usage
static void usage(const char *prog) {
    fprintf(stderr, "Usage: %s --config <path> --query <keyword> [--max-depth N] [--output <path>]
", prog);
    fprintf(stderr, "  --config   Path to TOML config file
");
    fprintf(stderr, "  --query    Search keyword to start traversal
");
    fprintf(stderr, "  --max-depth Max expansion depth (default: from config)
");
    fprintf(stderr, "  --output   Output file for JSON result (default: stdout)
");
    fprintf(stderr, "  --context  Query context: engineering, physics, ui, search, deep
");
    fprintf(stderr, "  --list     List all classes in the graph engine DB
");
    fprintf(stderr, "  --stats    Print graph stats after traversal
");
}

// Parse command line args
typedef struct Args {
    const char *config_path;
    const char *query;
    const char *output_path;
    const char *context;
    int max_depth;
    int list;
    int stats;
} Args;

static Args parse_args(int argc, char **argv) {
    Args a = {NULL, NULL, NULL, NULL, 0, 0, 0};
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--config") == 0 && i + 1 < argc) {
            a.config_path = argv[++i];
        } else if (strcmp(argv[i], "--query") == 0 && i + 1 < argc) {
            a.query = argv[++i];
        } else if (strcmp(argv[i], "--output") == 0 && i + 1 < argc) {
            a.output_path = argv[++i];
        } else if (strcmp(argv[i], "--context") == 0 && i + 1 < argc) {
            a.context = argv[++i];
        } else if (strcmp(argv[i], "--max-depth") == 0 && i + 1 < argc) {
            a.max_depth = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--list") == 0) {
            a.list = 1;
        } else if (strcmp(argv[i], "--stats") == 0) {
            a.stats = 1;
        } else if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
            usage(argv[0]);
            exit(0);
        }
    }
    return a;
}

int main(int argc, char **argv) {
    Args a = parse_args(argc, argv);
    
    if (a.list) {
        // List mode: just print what's in the graph
        fprintf(stderr, "Graph engine — list mode (not implemented in C, use c_class_builder.py list)
");
        return 0;
    }
    
    if (!a.config_path) {
        fprintf(stderr, "Error: --config required
");
        usage(argv[0]);
        return 1;
    }
    
    // 1. Load config
    Config *cfg = config_create();
    if (config_load(cfg, a.config_path) != 0) {
        fprintf(stderr, "Error: cannot load config from %s
", a.config_path);
        config_free(cfg);
        return 1;
    }
    
    // 2. Create graph
    Graph *g = graph_create(100);
    if (!g) {
        fprintf(stderr, "Error: cannot create graph
");
        config_free(cfg);
        return 1;
    }
    
    // 3. Apply config to graph
    config_apply_to_graph(cfg, g);
    config_free(cfg);
    
    // 4. Set context if specified
    if (a.context) {
        policy_set_context(&g->policy, a.context);
    }
    
    // 5. Override max depth if specified
    if (a.max_depth > 0) {
        g->policy.hard_limit = a.max_depth;
    }
    
    // 6. Load stored graph from MySQL
    int loaded = store_load_all(g);
    if (loaded < 0) {
        fprintf(stderr, "Warning: cannot load from MySQL (continuing with empty graph)
");
        loaded = 0;
    }
    
    // 7. If query specified, search and expand
    if (a.query) {
        // Search for matching nodes
        int found = store_search_nodes(g, a.query, 20);
        
        // Run recursive expansion
        int expanded = graph_query(g, a.query, a.max_depth);
        
        if (a.stats) {
            char pol_buf[256], exec_buf[256];
            policy_dump(&g->policy, pol_buf, sizeof(pol_buf));
            executor_dump(&g->executor, exec_buf, sizeof(exec_buf));
            fprintf(stderr, "Graph stats:
");
            fprintf(stderr, "  Nodes: %d
", graph_node_count(g));
            fprintf(stderr, "  Edges: %d
", graph_edge_count(g));
            fprintf(stderr, "  Loaded from MySQL: %d
", loaded);
            fprintf(stderr, "  Search results: %d
", found);
            fprintf(stderr, "  Expanded: %d
", expanded);
            fprintf(stderr, "  %s
", pol_buf);
            fprintf(stderr, "  %s
", exec_buf);
        }
    }
    
    // 8. Export as JSON
    int buf_size = 1024 * 1024;  // 1MB buffer
    char *json_buf = (char *)malloc(buf_size);
    if (json_buf) {
        graph_export_json(g, json_buf, buf_size);
        if (a.output_path) {
            FILE *f = fopen(a.output_path, "w");
            if (f) {
                fputs(json_buf, f);
                fclose(f);
                fprintf(stderr, "Result written to %s
", a.output_path);
            } else {
                fprintf(stderr, "Error: cannot write to %s
", a.output_path);
            }
        } else {
            printf("%s
", json_buf);
        }
        free(json_buf);
    }
    
    // 9. Cleanup
    graph_free(g);
    return 0;
}
