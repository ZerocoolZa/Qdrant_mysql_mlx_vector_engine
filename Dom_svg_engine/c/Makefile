# Wizard SVG Animation Engine — Makefile

CC = cc
CFLAGS = -O2 -Wall -Wextra -std=c11 -D_POSIX_C_SOURCE=200809L
LDFLAGS = -lm

ENGINE_SRCS = wizard_engine_core.c wizard_engine_scene.c \
              wizard_engine_particles.c wizard_engine_svg.c \
              wizard_engine_json.c wizard_engine_main.c

ENGINE_OBJS = $(ENGINE_SRCS:.c=.o)

LIB_SRCS = wizard_engine_core.c wizard_engine_scene.c \
           wizard_engine_particles.c wizard_engine_svg.c \
           wizard_engine_json.c

LIB_OBJS = $(LIB_SRCS:.c=.o)

.PHONY: all clean lib demo mcp-demo test

all: wizard_engine libwizard_engine.dylib

# CLI executable
wizard_engine: $(ENGINE_OBJS)
	$(CC) $(CFLAGS) -o $@ $(ENGINE_OBJS) $(LDFLAGS)

# Shared library for Python ctypes
libwizard_engine.dylib: $(LIB_OBJS)
	$(CC) -shared $(CFLAGS) -o $@ $(LIB_OBJS) $(LDFLAGS)

# Demo scenes
demo: wizard_engine
	./wizard_engine --demo ../examples/wizard_idle.svg

mcp-demo: wizard_engine
	./wizard_engine --mcp-demo ../examples/mcp_nodes.svg

# Compile test
test: wizard_engine
	./wizard_engine --demo /tmp/test_wizard.svg && echo "TEST PASSED" || echo "TEST FAILED"

clean:
	rm -f *.o wizard_engine libwizard_engine.dylib

%.o: %.c wizard_engine.h
	$(CC) $(CFLAGS) -c -o $@ $<
