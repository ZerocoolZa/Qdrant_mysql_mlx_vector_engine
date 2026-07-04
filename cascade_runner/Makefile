CC      = cc
CFLAGS  = -O2 -Wall -Wextra -std=c11
TARGET  = cascade
SRC     = cascade.c

.PHONY: all clean install

all: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) -o $(TARGET) $(SRC)

install: $(TARGET)
	cp $(TARGET) /usr/local/bin/$(TARGET)

clean:
	rm -f $(TARGET)
