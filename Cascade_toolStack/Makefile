# [@GHOST]{[@file<Makefile>][@domain<search>][@role<build>][@auth<cascade>][@date<2026-06-22>][@ver<5.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<build>][@return<binary>][@no<hardcoded_paths>]}

# ── Compiler ──
CC       = cc
CFLAGS   = -O2 -Wall -Wextra -Wno-unused-parameter

# ── MySQL paths (auto-detected from Homebrew) ──
MYSQL_INC = $(shell brew --prefix mysql@8.0 2>/dev/null)/include
MYSQL_LIB = $(shell brew --prefix mysql@8.0 2>/dev/null)/lib

# ── OpenSSL paths ──
SSL_LIB   = $(shell brew --prefix openssl@3 2>/dev/null)/lib

# ── Libraries ──
LIBS      = -lmysqlclient -lz -lssl -lcrypto -lresolv -lsqlite3
LDFLAGS   = -L$(MYSQL_LIB) -L$(SSL_LIB) -Wl,-rpath,$(MYSQL_LIB) -Wl,-rpath,$(SSL_LIB)
INCFLAGS  = -I$(MYSQL_INC)

# ── Targets ──
TARGET    = msearch_v5
SPINE_TEST = spine_test
CEK       = cascade_cli
SRC       = msearch_v5.c
SPINE_SRC = cascade_spine.c
HEADER    = cascade_toolstack.h
CEK_SRC   = bin_tools/cascade_cli.c

.PHONY: all clean test spine-test install config-db cek

all: $(TARGET) $(SPINE_TEST) $(CEK)

$(TARGET): $(SRC) $(HEADER)
	$(CC) $(CFLAGS) $(INCFLAGS) -DCASCADE_USE_MYSQL -o $(TARGET) $(SRC) $(LDFLAGS) $(LIBS)

# Spine self-test (no MySQL needed — just core unit + mainunit + boot)
$(SPINE_TEST): $(SPINE_SRC) $(HEADER)
	$(CC) $(CFLAGS) -DSPINE_TEST -o $(SPINE_TEST) $(SPINE_SRC) -lpthread

# ── Cascade Execution Kernel (CEK v4) — no external libs needed ──
$(CEK): $(CEK_SRC)
	$(CC) $(CFLAGS) -o $(CEK) $(CEK_SRC) -lm

cek: $(CEK)
	@echo "CEK v4 built: ./$(CEK)"

# ── Create config database ──
config-db:
	@mkdir -p ~/.config/cascade
	@sqlite3 ~/.config/cascade/cascade.db < config_seed.sql
	@echo "Config DB created at ~/.config/cascade/cascade.db"

# ── Quick test ──
test: $(TARGET)
	@echo "=== Test 1: Basic search ==="
	./$(TARGET) "VBStyle" --table instructions --limit 5
	@echo ""
	@echo "=== Test 2: JSON output ==="
	./$(TARGET) "Tuple3" --json --limit 3
	@echo ""
	@echo "=== Test 3: Qdrant stats ==="
	./$(TARGET) --qstats
	@echo ""
	@echo "=== Test 4: Semantic search ==="
	./$(TARGET) "MemUnit" --semantic --top 3
	@echo ""
	@echo "=== Test 5: Hybrid search ==="
	./$(TARGET) "bracket authority" --hybrid --top 3
	@echo ""
	@echo "=== Test 6: Where to store ==="
	./$(TARGET) --where "new rule"
	@echo ""
	@echo "=== Test 7: SQL injection attempt ==="
	./$(TARGET) "it's a test" --limit 2
	@echo ""
	@echo "=== All msearch tests passed ==="

# ── Spine self-test (no MySQL needed) ──
spine-test: $(SPINE_TEST)
	./$(SPINE_TEST)

# ── Install to Built_tools/ ──
install: $(TARGET) $(CEK)
	@cp $(TARGET) Built_tools/$(TARGET)
	@cp $(CEK) Built_tools/$(CEK)
	@echo "Installed to Built_tools/"

# ── Clean ──
clean:
	rm -f $(TARGET) $(SPINE_TEST) $(CEK)
