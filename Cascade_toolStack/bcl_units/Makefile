# [@GHOST]{file_path="Cascade_toolStack/bcl_units/Makefile" date="2026-06-29" author="cascade" session_id="bcl-toolstack-units" context="Build system for BCL tool units — one binary, many units"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="UPPERCASE constants"}

CC       = cc
CFLAGS   = -O2 -Wall -Wextra -Wno-unused-parameter

# OpenSSL paths
SSL_LIB   = $(shell brew --prefix openssl@3 2>/dev/null)/lib
SSL_INC   = $(shell brew --prefix openssl@3 2>/dev/null)/include

# MySQL client paths (hardcoded — mysql_config output intercepted by msearch shell fn)
MYSQL_LIB  = /opt/homebrew/Cellar/mysql@8.0/8.0.46_1/lib
MYSQL_INC  = /opt/homebrew/Cellar/mysql@8.0/8.0.46_1/include/mysql

# tree-sitter paths (for VBAST units — ast_walker, graph_builder, etc.)
TS_LIB    = /opt/homebrew/Cellar/tree-sitter/0.26.9/lib
TS_INC    = /opt/homebrew/Cellar/tree-sitter/0.26.9/include
TSP_LIB   = /opt/homebrew/Cellar/tree-sitter-python/0.25.0/lib
TSP_INC   = /opt/homebrew/Cellar/tree-sitter-python/0.25.0/include
TSC_LIB   = /opt/homebrew/Cellar/tree-sitter-c/0.23.4/lib
TSC_INC   = /opt/homebrew/Cellar/tree-sitter-c/0.23.4/include

LIBS      = -lsqlite3 -lcrypto -lmysqlclient -lz -lzstd -lresolv \
            -ltree-sitter -ltree-sitter-python -ltree-sitter-c
LDFLAGS   = -L$(SSL_LIB) -Wl,-rpath,$(SSL_LIB) \
            -L$(MYSQL_LIB) -Wl,-rpath,$(MYSQL_LIB) \
            -L/opt/homebrew/opt/zstd/lib -Wl,-rpath,/opt/homebrew/opt/zstd/lib \
            -L$(TS_LIB) -Wl,-rpath,$(TS_LIB) \
            -L$(TSP_LIB) -Wl,-rpath,$(TSP_LIB) \
            -L$(TSC_LIB) -Wl,-rpath,$(TSC_LIB)
INCFLAGS  = -I$(SSL_INC) -I$(MYSQL_INC) -I$(TS_INC) -I$(TSP_INC) -I$(TSC_INC)

# Targets
TARGET    = bcl_tool

# All unit source files
UNIT_SRCS = bcl_tool_main.c \
            bcl_pb_reader.c \
            bcl_chat_ingest.c \
            bcl_cleaner.c \
            bcl_search_help.c \
            bcl_search_registry.c \
            bcl_search_ranking.c \
            bcl_search_vector.c \
            bcl_search_composite.c \
            bcl_mdmerge.c \
            bcl_discovery.c \
            bcl_schemalint.c \
            bcl_vbcheck.c \
            bcl_ghostctl.c \
            bcl_smartcli.c \
            bcl_wcmd.c \
            bcl_codeingest.c \
            bcl_cognitive_core.c \
            bcl_error_fix.c \
            bcl_windir.c \
            bcl_destruction_guard.c \
            bcl_graph_core.c \
            bcl_graph_config.c \
            bcl_graph_view.c \
            bcl_graph_policy.c \
            bcl_graph_expand.c \
            bcl_graph_store.c \
            bcl_graph_compiler.c \
            bcl_graph_optimizer.c \
            bcl_graph_trace.c \
            bcl_graph_cache.c \
            bcl_graph_learning.c \
            bcl_search_web.c \
            bcl_search_fs.c \
            bcl_search_db.c \
            bcl_ast_walker.c \
            bcl_vbstyle_check.c \
            bcl_graph_builder.c \
            bcl_bcl_stamper.c \
            bcl_mysql_store.c \
            bcl_rule_reader.c \
            bcl_rule_writer.c \
            bcl_rule_engine.c \
            bcl_rule_enforcer.c \
            bcl_rule_gap_graph.c \
            bcl_rule_cluster_graph.c \
            bcl_rule_coverage_graph.c \
            bcl_code_index.c \
            bcl_Reports.c

.PHONY: all clean test install

all: $(TARGET)

$(TARGET): $(UNIT_SRCS) bcl_toolstack.h vbast.h
	$(CC) $(CFLAGS) $(INCFLAGS) -o $(TARGET) $(UNIT_SRCS) $(LDFLAGS) $(LIBS)

test: $(TARGET)
	@echo "=== Test 1: List units ==="
	./$(TARGET) list
	@echo ""
	@echo "=== Test 2: PB Reader scan ==="
	./$(TARGET) pb_reader scan
	@echo ""
	@echo "=== Test 3: PB Reader stats ==="
	./$(TARGET) pb_reader stats
	@echo ""
	@echo "=== Test 4: Dispatch via BCL packet ==="
	./$(TARGET) dispatch '[@CMD]{scan}[@UNIT]{pb_reader}'
	@echo ""
	@echo "=== All tests passed ==="

install: $(TARGET)
	cp $(TARGET) ../Built_tools/$(TARGET)
	@echo "Installed to Built_tools/"

clean:
	rm -f $(TARGET)
