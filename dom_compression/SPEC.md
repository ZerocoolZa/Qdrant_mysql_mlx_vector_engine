# dom_compression — VBStyle Compression Domain Spec

## Domain Name
`dom_compression`

## Purpose
Complete VBStyle domain covering the ENTIRE space of compression, archiving, and decompression. One unified module that handles all archive formats (ZIP, TAR, GZ, BZ2, XZ, RAR, 7Z) with full CRUD operations — read, write, edit, update, modify, verify, search, stream, convert, split, join, encrypt, decrypt, repair, strip, rename, merge, diff, optimize, benchmark, hash, walk, batch. 24 classes. Nothing missing. Complete domain closure.

## Location
`/Users/wws/Qdrant_mysql_mlx_vector_engine/dom_compression/`

## Supported Formats

| Format | Extension(s) | Library | Built-in |
|--------|-------------|---------|----------|
| ZIP | .zip | zipfile | Yes |
| TAR | .tar | tarfile | Yes |
| GZIP | .gz, .tgz, .tar.gz | gzip, tarfile | Yes |
| BZIP2 | .bz2, .tbz2, .tar.bz2 | bz2, tarfile | Yes |
| XZ | .xz, .txz, .tar.xz | lzma, tarfile | Yes |
| RAR | .rar | rarfile | No (needs unrar) |
| 7Z | .7z | py7zr | No (pip) |

## Classes (24) — Complete Domain

### 1. Compress
Create archives from files or directories.
- Run dispatch key: `compress`
- Inputs: source path(s), output path, format, level (0-9), options
- Operations:
  - Compress single file → archive
  - Compress directory → archive (recursive)
  - Compress multiple files → archive
  - Choose compression level (store/fast/normal/max)
  - Choose format (zip/tar/gz/bz2/xz/7z)
- Returns: Tuple3 `(ok, archive_path, error)`

### 2. Extract
Pull files out of archives to disk.
- Run dispatch key: `extract`
- Inputs: archive path, destination, file filter (optional), overwrite flag
- Operations:
  - Extract all files
  - Extract single file by name
  - Extract matching pattern (glob)
  - Extract to specific directory
  - Overwrite control
- Returns: Tuple3 `(ok, extracted_count, error)`

### 3. Read
Read file contents inside archives without extracting.
- Run dispatch key: `read`
- Inputs: archive path, file name inside archive, encoding
- Operations:
  - Read file as text (utf-8)
  - Read file as bytes
  - Read JSON file and return parsed object
  - Read multiple files in one call
- Returns: Tuple3 `(ok, content, error)`

### 4. Write
Add files to existing archives or create new ones.
- Run dispatch key: `write`
- Inputs: archive path, file name, content/data, mode (append/create)
- Operations:
  - Add file to existing archive
  - Create new archive with file
  - Append multiple files
  - Write text content as file inside archive
  - Write bytes as file inside archive
- Returns: Tuple3 `(ok, files_written, error)`

### 5. Info
Get metadata about archives and their contents.
- Run dispatch key: `info`
- Inputs: archive path, file name (optional)
- Operations:
  - Archive info (format, size, file count, compression ratio)
  - File info inside archive (size, compressed size, date, CRC)
  - Archive health summary
- Returns: Tuple3 `(ok, info_dict, error)`

### 6. List
List contents of archives with filtering and sorting.
- Run dispatch key: `list`
- Inputs: archive path, filter pattern, sort by, sort order
- Operations:
  - List all files
  - List by extension filter
  - List by name pattern (glob)
  - List directories only
  - List files only
  - Sort by name/size/date/compression
- Returns: Tuple3 `(ok, file_list, error)`

### 7. Search
Search for text or patterns inside archives without extracting.
- Run dispatch key: `search`
- Inputs: archive path, search term, file filter, regex flag
- Operations:
  - Search for text in all files
  - Search in specific files only
  - Regex search
  - Case-sensitive / case-insensitive
  - Return matching lines with context
- Returns: Tuple3 `(ok, matches, error)`

### 8. Stream
Stream large files from archives in chunks for low RAM usage.
- Run dispatch key: `stream`
- Inputs: archive path, file name, chunk size, callback
- Operations:
  - Stream file in fixed-size chunks
  - Stream lines (for text files)
  - Stream JSON objects (for JSONL)
  - Stream to callback function
  - Stream to file handle
- Returns: Tuple3 `(ok, total_bytes, error)`

### 9. Convert
Convert between archive formats.
- Run dispatch key: `convert`
- Inputs: source archive, target format, options
- Operations:
  - ZIP → TAR
  - TAR → ZIP
  - RAR → ZIP
  - 7Z → ZIP
  - GZ → BZ2
  - Any → Any (read + recompress)
- Returns: Tuple3 `(ok, output_path, error)`

### 10. Verify
Check archive integrity and detect corruption.
- Run dispatch key: `verify`
- Inputs: archive path, deep flag
- Operations:
  - Check archive structure
  - Verify CRC/checksums
  - Test extraction (dry run)
  - Detect corruption
  - Report damaged files
- Returns: Tuple3 `(ok, report, error)`

### 11. Split
Split large archives into smaller parts.
- Run dispatch key: `split`
- Inputs: archive path, part size, output dir
- Operations:
  - Split by size (e.g. 100MB parts)
  - Split by count (e.g. 5 parts)
  - Named parts (part01, part02, ...)
- Returns: Tuple3 `(ok, part_list, error)`

### 12. Join
Rejoin split archives into single file.
- Run dispatch key: `join`
- Inputs: part paths or pattern, output path
- Operations:
  - Join numbered parts
  - Auto-detect part order
  - Verify joined file integrity
- Returns: Tuple3 `(ok, output_path, error)`

### 13. Encrypt
Password protect archives.
- Run dispatch key: `encrypt`
- Inputs: archive path, password, method
- Operations:
  - Encrypt ZIP with password
  - Encrypt 7Z with password
  - Choose encryption method (AES-256, ZipCrypto)
- Returns: Tuple3 `(ok, archive_path, error)`

### 14. Decrypt
Open password protected archives.
- Run dispatch key: `decrypt`
- Inputs: archive path, password
- Operations:
  - Open encrypted archive
  - Extract with password
  - Read with password
  - Remove password (decrypt + re-save unprotected)
- Returns: Tuple3 `(ok, content, error)`

### 15. Repair
Fix corrupted archives and recover data from damaged files.
- Run dispatch key: `repair`
- Inputs: archive path, output path, recovery options
- Operations:
  - Repair ZIP central directory
  - Recover partial data from corrupted archive
  - Rebuild archive structure
  - Extract undamaged files from corrupted archive
  - Report unrecoverable files
- Returns: Tuple3 `(ok, recovered_count, error)`

### 16. Strip
Remove files from inside an archive without full re-creation.
- Run dispatch key: `strip`
- Inputs: archive path, file name(s) or pattern
- Operations:
  - Remove single file from archive
  - Remove multiple files by pattern
  - Remove by extension filter
  - Remove empty directories
  - Return removed file list
- Returns: Tuple3 `(ok, removed_count, error)`

### 17. Rename
Rename files inside an archive without extracting.
- Run dispatch key: `rename`
- Inputs: archive path, old name, new name (or mapping dict)
- Operations:
  - Rename single file
  - Batch rename with mapping dict
  - Rename by pattern (regex find/replace)
  - Rename directories
  - Preserve file metadata after rename
- Returns: Tuple3 `(ok, renamed_count, error)`

### 18. Merge
Combine multiple archives into a single archive.
- Run dispatch key: `merge`
- Inputs: archive paths (list), output path, format
- Operations:
  - Merge multiple ZIPs into one
  - Merge archives of different formats
  - Handle filename conflicts (skip/overwrite/rename)
  - Preserve directory structure
  - Merge with deduplication
- Returns: Tuple3 `(ok, output_path, error)`

### 19. Diff
Compare two archives and show differences.
- Run dispatch key: `diff`
- Inputs: archive path A, archive path B, options
- Operations:
  - List files only in A
  - List files only in B
  - List files in both but different (size/hash)
  - List identical files
  - Content-level diff for text files
  - Return structured diff report
- Returns: Tuple3 `(ok, diff_report, error)`

### 20. Optimize
Recompress archives with better ratio and deduplication.
- Run dispatch key: `optimize`
- Inputs: archive path, output path, target format, level
- Operations:
  - Recompress with maximum compression
  - Deduplicate identical files
  - Remove redundant metadata
  - Choose best algorithm per file type
  - Report before/after size comparison
- Returns: Tuple3 `(ok, savings_report, error)`

### 21. Benchmark
Test compression speed and ratio across formats and levels.
- Run dispatch key: `benchmark`
- Inputs: source path, formats to test, levels to test
- Operations:
  - Compress with each format (zip/tar/gz/bz2/xz/7z)
  - Compress with each level (0-9)
  - Measure time, size, ratio
  - Return ranked results
  - Recommend best format/level for the data
- Returns: Tuple3 `(ok, benchmark_report, error)`

### 22. Hash
Compute hashes of files inside archives without extracting.
- Run dispatch key: `hash`
- Inputs: archive path, file name(s), algorithm
- Operations:
  - Compute MD5 of file inside archive
  - Compute SHA256 of file inside archive
  - Compute CRC32 (from archive metadata)
  - Hash all files in archive
  - Return hash dictionary {filename: hash}
- Returns: Tuple3 `(ok, hash_dict, error)`

### 23. Walk
Recursively handle nested archives (zip inside tar inside gz).
- Run dispatch key: `walk`
- Inputs: archive path, max depth, callback
- Operations:
  - Detect and open nested archives
  - Walk recursively to max depth
  - List all files across all nested layers
  - Extract from nested archives
  - Flatten nested structure
  - Call callback for each file at each depth
- Returns: Tuple3 `(ok, file_tree, error)`

### 24. Batch
Operate on multiple archives at once.
- Run dispatch key: `batch`
- Inputs: archive paths (list or glob pattern), operation, params
- Operations:
  - Batch compress (compress 50 folders)
  - Batch extract (extract 100 zips)
  - Batch verify (verify all archives in directory)
  - Batch convert (convert all RARs to ZIPs)
  - Batch search (search across multiple archives)
  - Batch rename (rename across multiple archives)
  - Parallel execution with thread pool
  - Progress reporting across batch
  - Collect results from all operations
- Returns: Tuple3 `(ok, results_list, error)`

## File Structure

```
dom_compression/
    Config.py                  — VBStyle config (formats, levels, library paths)
    Compress.py                — Class Compress
    Extract.py                 — Class Extract
    Read.py                    — Class Read
    Write.py                   — Class Write
    Info.py                    — Class Info
    List.py                    — Class List
    Search.py                  — Class Search
    Stream.py                  — Class Stream
    Convert.py                 — Class Convert
    Verify.py                  — Class Verify
    Split.py                   — Class Split
    Join.py                    — Class Join
    Encrypt.py                 — Class Encrypt
    Decrypt.py                 — Class Decrypt
    Repair.py                  — Class Repair
    Strip.py                   — Class Strip
    Rename.py                  — Class Rename
    Merge.py                   — Class Merge
    Diff.py                    — Class Diff
    Optimize.py                — Class Optimize
    Benchmark.py               — Class Benchmark
    Hash.py                    — Class Hash
    Walk.py                    — Class Walk
    Batch.py                   — Class Batch
    Config_dom_compression.py  — Auto-generated VBStyle config index
```

## VBStyle Rules

- Every class has `Run(command, params)` dispatch entry
- Every method returns Tuple3 `(ok, data, error)`
- No decorators, no print, no hardcoded paths
- PascalCase classes, UPPERCASE constants
- `self.state` dict (no `self._`)
- Ghost + VBStyle + Class + Method headers on every file
- Config follows BookSystem/config.py gold standard pattern

## Config Keys

| Key | Default | Description |
|-----|---------|-------------|
| DEFAULT_FORMAT | zip | Default archive format |
| DEFAULT_LEVEL | 6 | Default compression level (0-9) |
| DEFAULT_CHUNK_SIZE | 65536 | Stream chunk size in bytes |
| DEFAULT_ENCODING | utf-8 | Text encoding |
| RAR_BINARY | /usr/bin/unrar | Path to unrar binary |
| MAX_SEARCH_RESULTS | 1000 | Max search matches returned |
| TEMP_DIR | /tmp | Temp directory for operations |
| VERIFY_DEEP | false | Deep verification by default |
| MAX_WALK_DEPTH | 10 | Max nested archive depth |
| BATCH_THREADS | 4 | Parallel threads for batch operations |
| DEFAULT_HASH_ALGO | sha256 | Default hash algorithm |
| BENCHMARK_LEVELS | 0,1,3,6,9 | Compression levels to benchmark |
| CONFLICT_MODE | skip | Filename conflict mode (skip/overwrite/rename) |
| REPAIR_MAX_RECOVER | all | Max files to recover in repair (all/N) |

## Dependencies

| Package | Purpose | Required |
|---------|---------|----------|
| zipfile | ZIP format | Built-in |
| tarfile | TAR format | Built-in |
| gzip | GZIP format | Built-in |
| bz2 | BZIP2 format | Built-in |
| lzma | XZ format | Built-in |
| rarfile | RAR format | Optional (needs unrar) |
| py7zr | 7Z format | Optional (pip) |

## Verify

```bash
python3 -c "from dom_compression.Compress import Compress; c=Compress(); print(c.Run('compress', {'source': '/tmp/test.txt', 'output': '/tmp/test.zip'}))"
```

Success = Tuple3 with ok=True and archive path.
