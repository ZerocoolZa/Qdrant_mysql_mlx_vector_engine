# Wizard SVG Animation Engine — Makefile

.PHONY: all clean c-engine python demo mcp-demo test run-studio

all: c-engine

# Build the C engine + shared library
c-engine:
	cd c && make all

# Demo scenes
demo: c-engine
	cd c && make demo

mcp-demo: c-engine
	cd c && make mcp-demo

# Run the Qt studio (requires PyQt6)
run-studio: c-engine
	cd python && python3 wizard_studio.py

# Test
test: c-engine
	cd c && make test

# Clean everything
clean:
	cd c && make clean
