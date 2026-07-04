# Bloodhound Makefile
#[@GHOST]
#[@VBSTYLE]
#[@FILEID] Makefile
#[@SUMMARY] Build target: make && make install

CC = cc
CFLAGS = -Wall -Wextra -O2 -D_DARWIN_C_SOURCE -I/opt/homebrew/include
LDFLAGS = -L/opt/homebrew/opt/lmdb/lib -llmdb -L/opt/homebrew/opt/zstd/lib -lzstd

SRCS = bh_main.c bh_db.c bh_scanner.c bh_nose.c bh_query.c bh_sync.c bh_report.c
OBJS = $(SRCS:.c=.o)
TARGET = bloodhound

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) -o $@ $(OBJS) $(LDFLAGS)

%.o: %.c bloodhound.h
	$(CC) $(CFLAGS) -c $< -o $@

install: $(TARGET)
	cp $(TARGET) /usr/local/bin/

clean:
	rm -f $(OBJS) $(TARGET)

.PHONY: all install clean
