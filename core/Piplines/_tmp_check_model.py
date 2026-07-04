import struct, sys

path = sys.argv[1] if len(sys.argv) > 1 else "model.bin"
with open(path, "rb") as f:
    magic = f.read(4)
    dims = struct.unpack("<i", f.read(4))[0]
    vocab_size = struct.unpack("<i", f.read(4))[0]
    f.read(4 + 4 + 4 + 8 + 8)  # epochs, window, neg, lr_start, lr_end
    words = []
    for _ in range(vocab_size):
        wlen = struct.unpack("<i", f.read(4))[0]
        word = f.read(wlen).decode("utf-8")
        words.append(word)
    # Check specific words
    for q in ["sqlite", "bcl", "embed", "search", "model", "parse", "graph", "config"]:
        if q in words:
            print("FOUND: %s" % q)
        else:
            print("MISSING: %s" % q)
    print("\nFirst 30 words:")
    for w in words[:30]:
        print("  %s" % w)
    print("\nTotal vocab: %d" % vocab_size)
