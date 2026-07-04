# Generic Ingestion Dedup Pipeline

It's not specific to chats. It's a **generic ingestion dedup pipeline** that works on any file type:

**Scan → Fingerprint → Compare → Classify → Import → Verify**

- **Scan** = walk disk folders, list files with name, size, type, hash
- **Fingerprint** = compute content hash + metadata signature
- **Compare** = match against all DB tables across all databases (by filename, hash, size)
- **Classify** = mark each file as `IN_DB`, `DUPLICATE`, or `NEW`
- **Import** = ingest only `NEW` files
- **Verify** = confirm DB count = disk count

Same pipeline whether it's chat markdowns, Python source files, C code, JSON exports, or anything else. The classify step is the universal "do I already have this?" gate.
