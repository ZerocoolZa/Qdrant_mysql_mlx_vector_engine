#[@GHOST]{file_path="Cascade_toolStack/vbast/Makefile" date="2026-06-29" author="Devin" session_id="vbast-bcl-stamp" context="Build system for VBAST — compiles all BCL unit C files into vbast binary"}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
#[@FILEID]{id="Makefile" domain="vbast" authority="BuildSystem"}
#[@SUMMARY]{summary="Makefile — builds vbast binary from 6 BCL unit C files, supports MySQL and no-MySQL modes"}
#[@CLASS]{class="BuildSystem" domain="vbast" authority="single"}
#[@METHOD]{methods="all,mysql,test,install,clean"}

# Compiler
CC       = cc
CFLAGS   = -O2 -Wall -Wextra -Wno-unused-parameter

# tree-sitter paths (Homebrew)
TS_INC   = /opt/homebrew/Cellar/tree-sitter/0.26.9/include
TS_LIB   = /opt/homebrew/Cellar/tree-sitter/0.26.9/lib
TSP_INC  = /opt/homebrew/Cellar/tree-sitter-python/0.25.0/include
TSP_LIB  = /opt/homebrew/Cellar/tree-sitter-python/0.25.0/lib
TSC_INC  = /opt/homebrew/Cellar/tree-sitter-c/0.23.4/include
TSC_LIB  = /opt/homebrew/Cellar/tree-sitter-c/0.23.4/lib

# MySQL paths (optional, for --store)
MYSQL_INC = $(shell brew --prefix mysql@8.0 2>/dev/null)/include/mysql
MYSQL_LIB = $(shell brew --prefix mysql@8.0 2>/dev/null)/lib
SSL_LIB   = $(shell brew --prefix openssl@3 2>/dev/null)/lib

# Targets
TARGET   = vbast
SRC      = vbast.c ast_walker.c bcl_stamper.c graph_builder.c vbstyle_check.c mysql_store.c
HEADER   = vbast.h

.PHONY: all clean test install

# Build without MySQL (default)
all: $(TARGET)

$(TARGET): $(SRC) $(HEADER)
	$(CC) $(CFLAGS) -I$(TS_INC) -I$(TSP_INC) -I$(TSC_INC) \
	    -o $(TARGET) $(SRC) \
	    -L$(TS_LIB) -ltree-sitter \
	    -L$(TSP_LIB) -ltree-sitter-python \
	    -L$(TSC_LIB) -ltree-sitter-c \
	    -Wl,-rpath,$(TS_LIB) -Wl,-rpath,$(TSP_LIB) -Wl,-rpath,$(TSC_LIB)

# Build with MySQL support (for --store)
mysql: $(SRC) $(HEADER)
	$(CC) $(CFLAGS) -I$(TS_INC) -I$(TSP_INC) -I$(TSC_INC) -I$(MYSQL_INC) \
	    -DCASCADE_USE_MYSQL \
	    -o $(TARGET) $(SRC) \
	    -L$(TS_LIB) -ltree-sitter \
	    -L$(TSP_LIB) -ltree-sitter-python \
	    -L$(TSC_LIB) -ltree-sitter-c \
	    -L$(MYSQL_LIB) -L$(SSL_LIB) -lmysqlclient -lz -lssl -lcrypto -lresolv \
	    -Wl,-rpath,$(TS_LIB) -Wl,-rpath,$(TSP_LIB) -Wl,-rpath,$(TSC_LIB) -Wl,-rpath,$(MYSQL_LIB) -Wl,-rpath,$(SSL_LIB)

# Test on dom_system.py
test: $(TARGET)
	@echo "=== Test 1: Full analysis ==="
	./$(TARGET) "/Users/wws/contestsystem/VBSTYLE_MASTER _CORE/VBstyle_Python/Domains/dom_system.py"
	@echo ""
	@echo "=== Test 2: Check only ==="
	./$(TARGET) "/Users/wws/contestsystem/VBSTYLE_MASTER _CORE/VBstyle_Python/Domains/dom_system.py" --check
	@echo ""
	@echo "=== Test 3: AST only ==="
	./$(TARGET) "/Users/wws/contestsystem/VBSTYLE_MASTER _CORE/VBstyle_Python/Domains/dom_system.py" --ast
	@echo ""
	@echo "=== Test 4: BCL stamps ==="
	./$(TARGET) "/Users/wws/contestsystem/VBSTYLE_MASTER _CORE/VBstyle_Python/Domains/dom_system.py" --bcl
	@echo ""
	@echo "=== Test 5: Graph only ==="
	./$(TARGET) "/Users/wws/contestsystem/VBSTYLE_MASTER _CORE/VBstyle_Python/Domains/dom_system.py" --graph
	@echo ""
	@echo "=== Test 6: JSON output ==="
	./$(TARGET) "/Users/wws/contestsystem/VBSTYLE_MASTER _CORE/VBstyle_Python/Domains/dom_system.py" --json
	@echo ""
	@echo "=== All tests passed ==="

# Install to ~/bin
install: $(TARGET)
	cp $(TARGET) ~/bin/$(TARGET)
	@echo "Installed to ~/bin/$(TARGET)"

# Clean
clean:
	rm -f $(TARGET)
