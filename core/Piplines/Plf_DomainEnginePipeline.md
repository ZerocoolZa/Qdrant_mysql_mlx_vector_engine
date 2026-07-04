# PLF_DOMAIN_ENGINE_PIPELINE — Domain Engine Ingest & Consolidation Pipeline

#[@GHOST]{[@file<Plf_DomainEnginePipeline.md>][@state<active>][@date<2026-07-04>][@ver<1.0>][@auth<Cascade>]}
#[@VBSTYLE]{[@auth<system>][@role<pipeline>][@return<none>][@orch<none>][@mem<none>][@db<none>]}

---

## 1. PROBLEM

Domain classes are scattered across multiple separate .py files in a domain directory.
They should be consolidated into ONE nested-class file (dom_web.py) with the main
controller class and all component classes nested inside.

The existing `pt_domain_engine.py` (1240 lines) is NOT VBStyle compliant:
- `Main()` is a free function, not inside a class
- `Main()` and `GuidedCLI` use `sys.stdout.write` directly (violates PRT: No Print Statements)
- No Report class for output
- No `read_state()` / `SetConfig()` / `_p()` on the CLI entry point
- Mixes CLI logic, business logic, and generation logic in one blob
- The 6 ingest sub-classes don't exist yet

---

## 2. GRAPH REASONING (8-Graph Analysis)

### 2.1 Plan Graph — What are we building?

A VBStyle-compliant domain engine with an ingest pipeline that:
- Scans a domain directory for real class files
- Extracts their implementations
- Maps them to the domain definition
- Shows a plan (real/stub/merged per class, yin-yang gaps)
- Consolidates into one nested-class file
- Cleans up the separate files

### 2.2 Spec Graph — What exactly exists?

**5 real class files in Dom_Web/:**

| File | Class | Methods | Lines | VBStyle Issues |
|---|---|---|---|---|
| HttpClient.py | HttpClient | get, post, set_header, set_auth, Run | 97 | `import base64` inside method (should be top) |
| HtmlParser.py | HtmlParser | parse, _create_parser, extract_text, extract_links, Run | 133 | `_create_parser` hidden method (HUD violation); `DomHtmlParser` nested class inside method |
| JsonParser.py | JsonParser | parse, extract_value, Run | 72 | CLEAN |
| XmlParser.py | XmlParser | parse, extract_elements, extract_attributes, Run | 85 | CLEAN |
| WebScraperWithWgetFallback.py | WebScraperWithWgetFallback | fetch, fetch_with_urllib, fetch_with_wget, mirror_site, download_file, set_config, get_config, Run | 212 | `json.dumps` in status command (LAW14 violation); `os.makedirs` side effect in `__init__`; `import json` for output |

**Domain definition (web.json — INPUT, not output):**
28 classes: Browser, Request, Response, Session, Cookie, Header, URL, HTTP, HTTPS,
Download, Upload, Cache, Parser, Scraper, Crawler, Spider, Auth, Proxy, DNS, SSL,
RateLimiter, Retry, Redirect, Compression, Robots, Monitor, Security, Validator.

**5 have real implementations. 23 are stubs.**

### 2.3 Flow Graph — How does it move?

```
FileScanner.FindClassFiles(directory)
    ↓ list of file paths
ClassExtractor.ExtractAll(files)
    ↓ list of {name, methods, imports, body}
ClassMapper.MapToDefinition(extracted, definition)
    ↓ {matched, unmatched, merges}
DomainGrapher.BuildPlan(mappings, definition)
    ↓ structured plan (real/stub/merged/partial per class)
DomainGrapher.ShowPlan(plan)
    ↓ Report class renders plan to screen (NOT sys.stdout.write)
    ↓ USER REVIEWS PLAN — pause here
Consolidator.BuildFile(plan, definition)
    ↓ complete dom_*.py content (real code ingested + stubs generated)
Consolidator.WriteFile(content, output_path)
    ↓ file written to disk
Cleaner.VerifyConsolidation(output_file, expected_classes)
    ↓ py_compile passes, all classes present, no duplicates
Cleaner.DeleteSeparateFiles(original_files)
    ↓ original files removed
```

### 2.4 Lifecycle Graph — When does it run?

1. **Plan phase** — `python pt_domain_engine.py plan web Dom_Web/` → shows plan, does NOT consolidate
2. **Review phase** — user reads plan, decides to proceed
3. **Ingest phase** — `python pt_domain_engine.py ingest web Dom_Web/` → consolidates + cleans
4. **Verify phase** — py_compile + VBStyle check on output

### 2.5 Dependency Graph — Why does it connect?

- FileScanner → ClassExtractor: scanner output feeds extractor
- ClassExtractor → ClassMapper: extracted classes feed mapper
- ClassMapper → DomainGrapher: mappings feed plan builder
- DomainGrapher → Consolidator: plan feeds file builder
- Consolidator → Cleaner: written file feeds verifier
- DomainEngine.Run → all 6: dispatch orchestrates the pipeline

### 2.6 Error Graph — Where does it fail?

- **Directory not found** → FileScanner returns (0, None, error)
- **No class files found** → FileScanner returns (1, [], None) — empty list, not error
- **File parse error** → ClassExtractor returns (0, None, error) for that file, continues others
- **No mapping found** → ClassMapper marks as STUB, not an error
- **py_compile fails** → Cleaner returns (0, None, error), files NOT deleted
- **Class count mismatch** → Cleaner returns (0, None, error), files NOT deleted

### 2.7 Orchestration Graph — Who calls who?

```
DomainEngine.Run("ingest", {domain, directory})
    → IngestDirectory(domain, directory)
        → self.scanner = self.FileScanner()
        → self.extractor = self.ClassExtractor()
        → self.mapper = self.ClassMapper()
        → self.grapher = self.DomainGrapher()
        → self.consolidator = self.Consolidator()
        → self.cleaner = self.Cleaner()
        → scanner.Run("find", {directory: directory})
        → extractor.Run("extract_all", {files: file_list})
        → mapper.Run("map", {extracted: extracted, definition: definition})
        → grapher.Run("plan", {mappings: mappings, definition: definition})
        → grapher.Run("show", {plan: plan})
        → consolidator.Run("build", {plan: plan, definition: definition})
        → consolidator.Run("write", {content: content, path: output_path})
        → cleaner.Run("verify", {output_file: output_path, classes: class_list})
        → cleaner.Run("delete", {files: original_files})
```

### 2.8 Gap Graph — What's missing?

**Gaps in the CURRENT plan (now fixed):**
- ~~dom_web_symbols.json as output~~ → REMOVED. Violates LAW14. Symbols rendered to screen via Report.
- ~~No Report class~~ → ADDED. All output goes through Report class, not sys.stdout.write.
- ~~Main() free function~~ → REPLACED with Cli class with Run dispatch.
- ~~No VBStyle fix-up during ingest~~ → ADDED. Consolidator fixes violations during merge.
- ~~_create_parser hidden method~~ → RENAMED to CreateParser during ingest.
- ~~json.dumps in status~~ → REPLACED with Report class output during ingest.
- ~~DomHtmlParser nested class in method~~ → HANDLED. Stays as inner class, re-indented.
- ~~import base64 inside method~~ → MOVED to top of consolidated file.
- ~~os.makedirs in __init__~~ → MOVED to a InitDirs method, called from Run.

**Gaps in the DOMAIN (things that don't exist yet):**
- 23 of 28 classes are stubs (no real implementation)
- Yin-yang pairs missing: Connect/Disconnect, Encrypt/Decrypt, Compress/Extract
- No real Browser, Request, Response, Session, Cookie, Header, URL implementations
- No real Auth, Proxy, DNS, SSL, RateLimiter, Retry, Redirect implementations
- No real Compression, Robots, Monitor, Security, Validator implementations

---

## 3. CLASS MAPPING (separate files → JSON classes)

| Separate File | JSON Class | Mapping Logic | VBStyle Fixes During Ingest |
|---|---|---|---|
| HttpClient | HTTP | Semantic match (HttpClient → HTTP) | Move `import base64` to top |
| HtmlParser | Parser | Parser has HTML method; HtmlParser does HTML | Rename `_create_parser` → `CreateParser`; keep `DomHtmlParser` as inner class |
| JsonParser | Parser | Parser has JSON method; JsonParser does JSON | None needed |
| XmlParser | Parser | Parser has XML method; XmlParser does XML | None needed |
| WebScraperWithWgetFallback | Scraper | Substring match (contains "Scraper") | Remove `import json`; replace `json.dumps` with Report output; move `os.makedirs` to InitDirs |

**MERGE CASE:** HtmlParser + JsonParser + XmlParser → all merge into single `Parser` class.
Parser JSON methods: HTML, JSON, XML, YAML, RSS, Sitemap.
After merge: HTML/JSON/XML get real implementations, YAML/RSS/Sitemap remain stubs.

**METHOD NAME MAPPING (Scraper):**
| Real Method | JSON Method | Rename? |
|---|---|---|
| fetch | Fetch | Yes (PascalCase) |
| fetch_with_urllib | FetchWithUrllib | Yes (PascalCase, internal helper) |
| fetch_with_wget | FetchWithWget | Yes (PascalCase, internal helper) |
| mirror_site | Mirror | Yes (PascalCase, mapped to JSON method name) |
| download_file | Download | Yes (PascalCase, mapped to JSON method name) |
| set_config | SetConfig | Yes (PascalCase) |
| get_config | GetConfig | Yes (PascalCase) |
| Run | Run | No |

**METHOD NAME MAPPING (HTTP):**
| Real Method | JSON Method | Rename? |
|---|---|---|
| get | Get | Yes (PascalCase) |
| post | Post | Yes (PascalCase) |
| set_header | SetHeader | Yes (PascalCase) |
| set_auth | SetAuth | Yes (PascalCase) |
| Run | Run | No |

**METHOD NAME MAPPING (Parser — merged):**
| Source File | Real Method | JSON Method | Rename? |
|---|---|---|---|
| HtmlParser | parse | HTML | Yes (mapped to JSON method name) |
| HtmlParser | extract_text | ExtractText | Yes (PascalCase) |
| HtmlParser | extract_links | ExtractLinks | Yes (PascalCase) |
| HtmlParser | _create_parser | CreateParser | Yes (remove underscore + PascalCase) |
| JsonParser | parse | JSON | Yes (mapped to JSON method name) |
| JsonParser | extract_value | ExtractValue | Yes (PascalCase) |
| XmlParser | parse | XML | Yes (mapped to JSON method name) |
| XmlParser | extract_elements | ExtractElements | Yes (PascalCase) |
| XmlParser | extract_attributes | ExtractAttributes | Yes (PascalCase) |

---

## 4. ARCHITECTURE — VBStyle Compliant Structure

### 4.1 pt_domain_engine.py (the engine — rewritten)

```
class DomainEngine:
    """Domain engine — universal CLI for creating, validating, generating, ingesting domains."""

    EXCLUDED_PATTERNS = ("pt_domain_engine", "create_domain", "__init__", "Config_", "dom_", "test_", "setup")
    GRAPH_VIEWERS = {...}  # UPPERCASE constant
    VALID_EDGE_TYPES = {...}  # UPPERCASE constant

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "definitions_dir": ...,
            "graph_dir": ...,
            "domain": None,
            "definition": None,
            "ingest_plan": None,
            "stats": {},
            "generated_files": [],
        }

    def _p(self, params, key, default=None): ...
    def read_state(self): ...
    def SetConfig(self, params): ...

    # --- Existing methods (kept, cleaned) ---
    def ListDomains(self): ...
    def LoadDomainDefinition(self, domain_name): ...
    def SaveDomainDefinition(self, definition, domain_name): ...
    def ValidateDomain(self, domain_name): ...
    def BuildHeader(self, definition): ...
    def BuildMainClass(self, definition): ...
    def BuildNestedClasses(self, definition): ...
    def WritePython(self, definition, output_dir): ...
    def WriteMarkdownTree(self, definition, output_dir): ...
    def WriteGraphviz(self, definition, output_dir): ...
    def WriteMermaid(self, definition, output_dir): ...
    def WriteSymbolIndex(self, definition, output_dir): ...  # OUTPUT IS .txt NOT .json (LAW14)
    def WriteGraphData(self, definition, output_dir): ...  # This is .py, not .json — OK
    def WriteConfigData(self, definition, output_dir): ...
    def GenerateAll(self, domain_name, output_dir): ...
    def ValidateVBStyle(self, filepath): ...

    # --- NEW: Ingest pipeline ---
    def IngestDirectory(self, domain, directory): ...
    def ShowIngestPlan(self, domain, directory): ...  # plan only, no consolidation

    # --- 6 nested sub-classes ---
    class FileScanner: ...
    class ClassExtractor: ...
    class ClassMapper: ...
    class DomainGrapher: ...
    class Consolidator: ...
    class Cleaner: ...

    # --- Report sub-class (replaces sys.stdout.write) ---
    class Report:
        """All output goes through Report class. Never sys.stdout.write, never print."""
        def __init__(self, mem=None, db=None, param=None):
            self.state = {"output": []}
        def Write(self, text): ...  # accumulate
        def WriteLn(self, text): ...  # accumulate + newline
        def Flush(self): ...  # write accumulated to sys.stdout in one call
        def Clear(self): ...  # clear buffer
        def Run(self, command, params): ...

    # --- CLI sub-class (replaces free Main() function) ---
    class Cli:
        """CLI entry point — VBStyle compliant replacement for Main()."""
        def __init__(self, mem=None, db=None, param=None):
            self.state = {"engine": None, "report": None}
        def ParseArgs(self, argv): ...
        def Execute(self, args): ...
        def Run(self, command, params): ...

    def Run(self, command, params=None): ...
```

### 4.2 dom_web.py (the consolidated domain file — generated)

```
class Web:
    """Web domain controller / authority."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "catalog": [],
            "results": [],
            "errors": [],
            "meta": {"last_command": None, "last_component": None},
        }
        self.browser = self.Browser()
        self.request = self.Request()
        self.http = self.HTTP()           # REAL (ingested from HttpClient.py)
        self.parser = self.Parser()       # REAL (merged from 3 parser files)
        self.scraper = self.Scraper()     # REAL (ingested from WebScraperWithWgetFallback.py)
        # ... 23 more stub components

    def _p(self, params, key, default=None): ...
    def read_state(self): ...
    def SetConfig(self, params): ...
    def Run(self, command, params=None): ...  # dispatch to nested classes

    # --- REAL: ingested from HttpClient.py ---
    class HTTP:
        def __init__(self, mem=None, db=None, param=None):
            self.state = {"user_agent": ..., "timeout": ..., "headers": {}, "cookies": {}, "auth": None}
        def Get(self, url, headers=None): ...      # real urllib code
        def Post(self, url, data=None, headers=None): ...  # real urllib code
        def SetHeader(self, key, value): ...
        def SetAuth(self, username, password): ...  # base64 import at FILE top
        def Run(self, command, params=None): ...

    # --- REAL: merged from HtmlParser.py + JsonParser.py + XmlParser.py ---
    class Parser:
        def __init__(self, mem=None, db=None, param=None):
            self.state = {
                "current_tag": None, "current_attrs": {}, "current_data": "",
                "in_script": False, "in_style": False,
                "links": [], "images": [], "headings": [], "metadata": {},
                "parsed": None, "keys": [], "root": None, "elements": [],
            }
        def HTML(self, html_content): ...          # real code from HtmlParser.parse
        def JSON(self, json_content): ...          # real code from JsonParser.parse
        def XML(self, xml_content): ...            # real code from XmlParser.parse
        def YAML(self, yaml_content): ...          # STUB
        def RSS(self, rss_content): ...            # STUB
        def Sitemap(self, sitemap_content): ...    # STUB
        def ExtractText(self, html_content): ...   # real code from HtmlParser
        def ExtractLinks(self, html_content, base_url=None): ...  # real
        def ExtractValue(self, json_content, dot_path): ...      # real
        def ExtractElements(self, xml_content, tag): ...         # real
        def ExtractAttributes(self, xml_content, tag): ...       # real
        def CreateParser(self): ...                 # real (renamed from _create_parser)
            class DomHtmlParser(HTMLParser): ...    # inner class, stays
        def Run(self, command, params=None): ...    # merged dispatch

    # --- REAL: ingested from WebScraperWithWgetFallback.py ---
    class Scraper:
        def __init__(self, mem=None, db=None, param=None):
            self.state = {
                "use_wget_fallback": True,
                "wget_path": ..., "timeout": ..., "user_agent": ...,
                "output_dir": ..., "last_method_used": None, "last_error": None,
            }
            # NO os.makedirs here — moved to InitDirs
        def InitDirs(self): ...                     # moved from __init__
        def Fetch(self, url, output_file=None): ... # real urllib+wget fallback
        def FetchWithUrllib(self, url, output_file=None): ...  # real
        def FetchWithWget(self, url, output_file=None): ...    # real
        def Mirror(self, url, options=None): ...    # real wget mirror
        def Download(self, url, filename=None, resume=False, limit_rate=None): ...  # real
        def SetConfig(self, key, value): ...
        def GetConfig(self, key): ...
        def Status(self): ...                       # Report output, NOT json.dumps
        def Run(self, command, params=None): ...

    # --- 25 STUB classes (generated from JSON definition) ---
    class Browser: ...
    class Request: ...
    class Response: ...
    class Session: ...
    class Cookie: ...
    class Header: ...
    class URL: ...
    class HTTPS: ...
    class Download: ...
    class Upload: ...
    class Cache: ...
    class Crawler: ...
    class Spider: ...
    class Auth: ...
    class Proxy: ...
    class DNS: ...
    class SSL: ...
    class RateLimiter: ...
    class Retry: ...
    class Redirect: ...
    class Compression: ...
    class Robots: ...
    class Monitor: ...
    class Security: ...
    class Validator: ...
```

---

## 5. THE 6 NESTED SUB-CLASSES (detailed spec)

### 5.1 FileScanner

```
Purpose: Find *.py class files in a directory, filter out non-class files.
Excluded: pt_domain_engine, create_domain, __init__, Config_*, dom_*, test_*, setup

State: {directory, files, excluded}
Methods:
  FindClassFiles(directory) → (1, [file_paths], None)
  Run(command, params):
    "find" → FindClassFiles(params["directory"])
```

### 5.2 ClassExtractor

```
Purpose: Read a .py file, extract class name + full method bodies + imports.
Uses Python AST (ast module) to parse reliably.

State: {extracted: [], imports: []}
Methods:
  ExtractClass(filepath) → (1, {name, methods, imports, body}, None)
    - Parse file with ast.parse()
    - Find ClassDef nodes
    - For each class: extract name, methods (FunctionDef), full source of each method
    - Collect all Import/ImportFrom nodes
  ExtractAll(filepaths) → (1, [extracted_classes], None)
  Run(command, params):
    "extract" → ExtractClass(params["filepath"])
    "extract_all" → ExtractAll(params["files"])
```

### 5.3 ClassMapper

```
Purpose: Map extracted classes to domain definition classes.
Fuzzy match + merge detection.

State: {mappings: {}, merges: [], unmatched: []}
Methods:
  MapToDefinition(extracted_classes, definition) → (1, {matched, unmatched, merges}, None)
  FuzzyMatch(extracted_name, definition_classes) → (1, best_match_name, None)
    Match rules (in priority order):
      1. Exact name match (case-insensitive)
      2. Substring match (extracted contains definition name or vice versa)
         e.g. "HttpClient" contains "HTTP" → match HTTP
         e.g. "WebScraperWithWgetFallback" contains "Scraper" → match Scraper
      3. Semantic keyword match:
         "Html" → Parser (HTML method)
         "Json" → Parser (JSON method)
         "Xml" → Parser (XML method)
  DetectMerges(mappings) → (1, merge_groups, None)
    Groups files that map to the same JSON class
    e.g. HtmlParser + JsonParser + XmlParser → all map to Parser
  Run(command, params):
    "map" → MapToDefinition(params["extracted"], params["definition"])
```

### 5.4 DomainGrapher

```
Purpose: Build and show the plan. What's real, what's stub, what merges, yin-yang gaps.
All output goes through Report class, NOT sys.stdout.write.

State: {plan: {}, summary: {}}
Methods:
  BuildPlan(mappings, definition) → (1, plan, None)
    For each JSON class:
      status = "REAL" | "MERGED" | "STUB" | "PARTIAL"
      methods_real = [methods with real implementations]
      methods_stub = [methods that will be stubs]
      source_files = [source files this came from]
      vbstyle_fixes = [list of fixes applied during ingest]
  ShowPlan(plan, report) → (1, None, None)
    Renders plan to screen via Report class
  ShowYinYang(plan, report) → (1, None, None)
    Shows complete pairs and missing pairs
  Run(command, params):
    "plan" → BuildPlan(params["mappings"], params["definition"])
    "show" → ShowPlan(params["plan"], params["report"])
    "yinyang" → ShowYinYang(params["plan"], params["report"])
```

### 5.5 Consolidator

```
Purpose: Cut, move, paste real class implementations into one nested-class file.
Fixes VBStyle violations during merge.

State: {output_path, content, merged_count, stub_count}
Methods:
  BuildNestedClass(extracted, indent_level) → (1, indented_code, None)
    - Takes real method bodies from extracted class
    - Indents for nesting inside main class (4 spaces per level)
    - Preserves self.state, __init__, all methods, Run dispatch
    - Fixes VBStyle violations:
        - Rename _method → Method (remove underscore, PascalCase)
        - Move imports to file top
        - Replace json.dumps with Report output
        - Move os.makedirs from __init__ to InitDirs
  MergeClasses(extracted_list, target_class_name) → (1, merged_class, None)
    - Combines methods from multiple extracted classes into one
    - Merges self.state dicts (union of all keys)
    - Combines Run dispatches (all commands from all sources)
    - Keeps inner classes (like DomHtmlParser) at correct indent
  BuildStubClass(class_def, indent_level) → (1, stub_code, None)
    - Generates VBStyle compliant stub with __init__, self.state, methods, Run
  BuildFile(plan, definition) → (1, file_content, None)
    1. Header (GHOST/VBSTYLE/FILEID/SUMMARY/CLASS/METHOD)
    2. Imports (merged from all extracted files + standard imports)
    3. Main controller class (with __init__, self.state, Run dispatch)
    4. Nested classes (real ones ingested + fixed, stubs generated)
  WriteFile(content, output_path) → (1, path, None)
  Run(command, params):
    "build" → BuildFile(params["plan"], params["definition"])
    "write" → WriteFile(params["content"], params["path"])
    "merge" → MergeClasses(params["extracted_list"], params["target_name"])
```

### 5.6 Cleaner

```
Purpose: Delete separate class files after successful consolidation.
Does NOT delete if verification fails.

State: {deleted_files: [], verified: False, output_file: None}
Methods:
  DeleteSeparateFiles(file_list) → (1, deleted_count, None)
    Only called AFTER VerifyConsolidation succeeds
  VerifyConsolidation(output_file, expected_classes) → (1, True, None) or (0, None, error)
    - py_compile passes
    - All expected classes present in output (grep for "class ClassName")
    - No duplicate class definitions
    - All real method bodies present (check for key method signatures)
  Run(command, params):
    "verify" → VerifyConsolidation(params["output_file"], params["classes"])
    "delete" → DeleteSeparateFiles(params["files"])
```

---

## 6. REPORT CLASS (replaces all sys.stdout.write)

```
class Report:
    """All output goes through Report. Never sys.stdout.write in class methods, never print."""
    def __init__(self, mem=None, db=None, param=None):
        self.state = {"buffer": [], "total_lines": 0}
    def Write(self, text): → (1, None, None)  # append to buffer
    def WriteLn(self, text): → (1, None, None)  # append + newline
    def Flush(self): → (1, line_count, None)  # write buffer to sys.stdout in one call, clear
    def Clear(self): → (1, None, None)  # clear buffer
    def Run(self, command, params):
        "write" → Write(params["text"])
        "writeln" → WriteLn(params["text"])
        "flush" → Flush()
        "clear" → Clear()
```

This satisfies PRT (No Print Statements) — no method uses print() or sys.stdout.write
directly. The Report class is the single controlled output channel.

---

## 7. CLI CLASS (replaces free Main() function)

```
class Cli:
    """CLI entry point — VBStyle compliant."""
    def __init__(self, mem=None, db=None, param=None):
        self.state = {"engine": None, "report": None}
    def ParseArgs(self, argv): → (1, parsed_args, None)
    def Execute(self, args): → (1, result, None)
        Creates DomainEngine, dispatches command, renders output via Report
    def Run(self, command, params):
        "parse" → ParseArgs(params["argv"])
        "execute" → Execute(params["args"])
```

Entry point at bottom of file:
```python
if __name__ == "__main__":
    cli = DomainEngine.Cli()
    cli.Run("execute", {"argv": sys.argv})
```

---

## 8. LAW14 COMPLIANCE (No JSON Output)

**JSON is allowed as INPUT:**
- domain_definitions/*.json — domain definitions read by the engine
- Config files that happen to be JSON — if they're input

**JSON is NEVER allowed as OUTPUT:**
- ~~dom_web_symbols.json~~ → REMOVED. WriteSymbolIndex now outputs .txt
- ~~WebScraperWithWgetFallback.status using json.dumps~~ → REPLACED with Report output
- ~~Any other .json output files~~ → NONE generated

**All output goes to screen via Report class.**

---

## 9. FILE LOCATION CHANGES

| Current | Target | Action |
|---|---|---|
| Dom_Web/pt_domain_engine.py | /pt_domain_engine.py | MOVE (it's a tool, not a domain component) |
| Dom_Web/domain_definitions/ | /domain_definitions/ | MOVE (shared across all domains) |
| Dom_Web/HttpClient.py | DELETE | Ingested into dom_web.py |
| Dom_Web/HtmlParser.py | DELETE | Ingested into dom_web.py |
| Dom_Web/JsonParser.py | DELETE | Ingested into dom_web.py |
| Dom_Web/XmlParser.py | DELETE | Ingested into dom_web.py |
| Dom_Web/WebScraperWithWgetFallback.py | DELETE | Ingested into dom_web.py |
| Dom_Web/Dom_Web_v2.py | DELETE | Old half-baked copy |
| Dom_Web/create_domain.py | DELETE | Old v1 engine, replaced |
| Dom_Web/Dom_Web.py | BACKUP then DELETE | Old pre-refactor, replaced by generated dom_web.py |
| PT_DOMAIN_ENGINE_PLAN.md | DELETE | Replaced by this pipeline file |

---

## 10. CLI COMMANDS

```
python pt_domain_engine.py ingest <domain> <directory>    Full ingest pipeline (scan→plan→consolidate→clean)
python pt_domain_engine.py plan <domain> <directory>      Show ingest plan without consolidating
python pt_domain_engine.py scan <directory>               Just scan and list class files
python pt_domain_engine.py yinyang <domain>               Show yin-yang gap analysis
python pt_domain_engine.py list                           List available domain definitions
python pt_domain_engine.py validate <domain>              Validate a domain definition
python pt_domain_engine.py check <filepath>               Validate VBStyle compliance
python pt_domain_engine.py graphs                         List available graph viewers
python pt_domain_engine.py graph <viewer> <domain>        Launch a graph viewer
python pt_domain_engine.py <domain> [output_dir]          Generate all outputs + validate
```

---

## 11. VBSTYLE COMPLIANCE CHECKS

The rewritten `pt_domain_engine.py` must pass:
1. `py_compile` passes
2. `grep print(` = zero (PRT)
3. `grep @staticmethod|@property|@classmethod` = zero (DEC)
4. `grep self\._` = zero (NHUS)
5. All methods return Tuple3 (TUPLE3)
6. Run() exists on DomainEngine and all nested classes
7. read_state() exists on DomainEngine and all nested classes
8. SetConfig() exists on DomainEngine and all nested classes
9. _p() helper exists on DomainEngine and all nested classes
10. GHOST + VBSTYLE + FILEID + SUMMARY + CLASS + METHOD headers present
11. No JSON output files (LAW14)
12. No sys.stdout.write in class methods (PRT — only Report.Flush uses it)
13. No hardcoded values (constants at top)
14. PascalCase classes, UPPERCASE constants

The generated `dom_web.py` must also pass all of the above.

---

## 12. EXECUTION ORDER

1. Write this pipeline file ← DONE
2. Rewrite pt_domain_engine.py with VBStyle compliant structure:
   - DomainEngine class with 6 nested ingest sub-classes
   - Report sub-class (replaces sys.stdout.write)
   - Cli sub-class (replaces free Main())
   - All existing methods cleaned (no sys.stdout.write)
   - WriteSymbolIndex outputs .txt not .json (LAW14)
3. Move pt_domain_engine.py to workspace root
4. Move domain_definitions/ to workspace root
5. Run: `python pt_domain_engine.py plan web Dom_Web/` → show the plan
6. User reviews plan
7. Run: `python pt_domain_engine.py ingest web Dom_Web/` → consolidate + clean
8. Verify: py_compile dom_web.py passes
9. Verify: VBStyle check passes on dom_web.py
10. Verify: VBStyle check passes on pt_domain_engine.py
11. Delete old files (Dom_Web_v2.py, create_domain.py, Dom_Web.py)
12. Delete PT_DOMAIN_ENGINE_PLAN.md (replaced by this file)

---

## 13. MYSQL LAW REGISTERED

LAW14: "JSON Is Never Allowed As Output"
- law_code: LAW14
- law_name: JSON Is Never Allowed As Output
- law_text: JSON files are never allowed as output. JSON creates file sprawl. All output goes to screen using the Report class. JSON is allowed as INPUT (domain definitions, config files) but never as OUTPUT. The Report class renders to screen. No .json output files.
- domain: fileops
- category: forbidden
- status: locked
- priority: p0

Pattern NJO (No JSON Output) linked to LAW14 via pattern_law.
