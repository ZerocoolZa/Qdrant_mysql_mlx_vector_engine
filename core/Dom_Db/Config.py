#!/usr/bin/env python3
[@GHOST]{
    ("file_path: /Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Db/Config.py";"date: 2026-06-29";"author: cascade";"session_id: db-module-loader";"context: Config spec for Dom_Db module loader — BCL blocks, rules, glossary")
}
[@VBSTYLE]{
    ("standard: VBStyle";"version: 2";"rules: CamelCase; UPPERCASE; BCL-in-BCL-out; Run dispatch")
}
[@FILEID]{
    ("id: Config.py";"domain: Dom_Db";"authority: Config")
}
[@SUMMARY]{
    ("Config for Dom_Db — DB module loader. Paths to SQLite code databases, table names, default domain filters. Spec file, not executable Python.")
}
[@CLASS]{
    ("class: Config";"domain: Dom_Db";"authority: single")
}
[@METHOD]{
    ("Run";"read_state";"set_config";"_p";"__init__")
}
[@REVIEW]{
    ("date: 2026-06-29";"reviewer: cascade";"status: pass";"notes: Config spec for Dom_Db loader. BCL blocks define flow stages from OpenDb to Report. Glossary defines BCL as one grammar with many dialects, BCLIR, Graph, ChatCompression. Rules 1-25 cover naming, formatting, BCL/BCLIR/Graph storage. Spec file not executable Python.";"todos: none")
}

"""
Rules
1.  All CamelCase
2.  No underscores
3.  Proper formatting
4.  BCL block stays uncommented — it is spec, not code
5.  Token names CamelCase: @DbLoader, @Type, @Table, @Permission, @Auth
6.  Values CamelCase: Sqlite, Mysql, Auto, ReadOnly, Oauth2, ApiKey
7.  Empty string "" means none/unset — always included as an option
8.  BCL spec block above Python implementation — spec is contract, code below fulfills it
9.  This is a spec file, not executable Python — .py extension is convention only
10. Never imported, never compiled, never run — treat as text/markdown
11. Do not add # comments to BCL block — it is not Python code
12. [@Flow] is a directed graph — each stage is a node, edges are data flowing between them
13. Flow: OpenDb -> LoadMetadata -> Parse -> Validate -> BuildGraph -> LoadIntoMemUnit -> Execute -> Index -> Extract -> Writeback -> Report
14. Config is a self-describing contract — [@Schema] defines data shape, [@Flow] defines execution graph, [@Adapters] define per-DB translations
15. Indexer skips generated files — they are outputs, not inputs
16. Indexer writeback is idempotent — re-indexing produces same result
17. Indexer extracts className, classCode, domain, methodName, methodCode, BCL stamps, dependencies, graph edges
18. Indexer writes back to DB tables: classes, methods, bclStamps, graphEdges
19. Indexer updates [@GeneratedFiles] with fresh indexes after writeback
20. Every class in the DB has three things stored with it: BCL, BCLIR, and Graph
21. BCL = header stamps (GHOST, VBSTYLE, CLASS, METHOD) — identity and rules
22. BCLIR = BCL intermediate representation — parsed internal structure of the code
23. Graph = per-class dependency graph (calls, state reads, state writes, imports)
24. BuildGraph does not build a new graph — it reads per-class graphs from DB and assembles them into the loader dependency graph
25. DB is the source of truth for BCL, BCLIR, and Graph — the loader just reads them
26. BCL in, BCL out — not Tuple3; the BCL string IS the interface; every unit is interchangeable
27. CamelCase everything — not PascalCase; capital first letter of each word, rest lowercase; e.g. Config, ReadOnly, Oauth2, ApiKey, not CONFIG or config or config_readonly
28. BCL must always follow the same format — [@Tag]{ ("item";"item";"item") } for lists, [@Tag]{ "item";"item" } for blocks
29. Semicolons go outside quotes — "item"; not "item;" — the semicolon is a separator, not part of the value
30. Last item before closing bracket has no semicolon — ("a";"b";"c") not ("a";"b";"c;")
"""
"""
Glossary

1.  BCL — Bracket Command Language. BCL is not one language — it is one grammar with many dialects. The parser never changes — it only understands brackets. The dictionary determines which dialect a packet belongs to and what semantics apply.

    Two forms: Config (passive, describes state) and Command (active, executes through MemUnit).

    Every unit speaks exactly one language: BCL Packet -> Parser -> Dispatch -> BCL Packet.

    Dictionary-first architecture: dictionary defines symbols (not just tags). Each symbol has id, kind, datatype, container, parent, children, repeatable, validator, version, status, authority. Names can change, IDs cannot (BCL0001). Dictionary is the grammar — like SQL has INFORMATION_SCHEMA.

    Header stamps on every file: [@GHOST], [@VBSTYLE], [@CLASS], [@METHOD], [@SUMMARY], [@FILEID]. A hierarchical annotation and aggregation system over code: BCL per function = structured metadata (inputs, outputs, intent, IO, domain tags). It describes what the file IS, not what it DOES. Stored in the DB per class.

    Pipeline: Lexer -> Parser -> Validator -> Fixer -> Engine -> IR Compiler -> Projector -> Exporter

    BCL Spec (formal, not code):
    Vol 1: Lexical rules | Vol 2: Grammar | Vol 3: Packet rules | Vol 4: Dictionary
    Vol 5: Execution | Vol 6: Errors | Vol 7: Namespaces | Vol 8: Versioning
    Vol 9: Validation | Vol 10: Serialization | Vol 11: Streaming | Vol 12: Extensions

    Language -> Dictionary -> Parser -> Runtime -> Applications (not Parser -> Language)

    Dialect taxonomy (one grammar, many semantic vocabularies):

    Command — runtime instruction dispatch unit (executes actions via RUN/CMD/PARAM packets inside MemUnit)
    Communication — structured message transport layer (AI to AI and module to module BCL packet exchange)
    Control — execution authority layer (routes commands, enforces permissions, decides which unit runs)
    Config — system configuration layer (defaults, overrides, runtime settings, backend selection, limits)
    Compression — structural encoding layer (reduces verbose state into dense bracket-based representation)
    Complaint — diagnostic feedback layer (warnings, anomalies, non-fatal errors, system observations)
    Correction — repair and patch layer (auto-generated fixes from validation failures or execution mismatches)
    Core — foundational runtime layer (MemUnit, parser, dictionary, executor, base contracts, system bootstrap)
    Computation — execution layer (actual processing logic inside graph engines, analyzers, and workers)
    Parser — syntactic interpretation layer (converts BCL text packets into structured in-memory nodes)
    Dictionary — grammar/registry layer (authoritative list of valid tags, categories, and constraints)
    MemUnit — in-RAM orchestration layer (SQLite :memory: bus for commands, results, events, state)
    Executor — dispatch engine (maps CMD to unit, ensures lazy init, runs UnitRun, returns BCL output)
    Graph — structural reasoning layer (nodes, edges, relationships, dependency and call structure models)
    Ingestion — input acquisition layer (file scan, hashing, AST extraction, source storage into DB)
    Store — persistence abstraction layer (SQLite/MySQL backend access for nodes, edges, sourceFiles)
    Trace — runtime observation layer (execution logging, replay system, impact analysis, audit trail)
    Report — output synthesis layer (complexity, dependency, health, graph summaries, diagnostics)
    IR — intermediate representation layer (AST to normalized structure with certainty tiers)
    CLI — external interface layer (user interaction, command entry, stdout BCL emission)
    Validation — enforcement layer (schema checks, tag validation, rule compliance, error detection)
    Registry — command mapping layer (cmdKey to unit routing table inside muCliRegistry)
    State — runtime state layer (persistent key-value state inside MemUnit muState table)
    Event — system event layer (append-only audit log inside muEvents)

    Each dialect has allowed packet roots: [@Task], [@Config], [@Graph], [@Chat], [@Err], [@Run], [@Cmd], [@State], [@Query], [@Review], [@Audit], [@Deploy], etc.

    One parser, one grammar, many dialects. Every tool shares parsing infrastructure, specializes only in dialects it understands.

2.  BCLIR — BCL Intermediate Representation. The parsed internal structure of the code. When the indexer scans a .py file, it builds an AST and converts it into BCLIR: a normalized representation of classes, methods, parameters, signatures, return types, and body structure. BCLIR is language-agnostic — it abstracts away Python syntax into a common form. Stored in the DB per class.

3.  Graph — Per-class dependency graph. For each class, the graph records: which methods call which other methods (CALL edges), which methods read self.state keys (STATE_READ edges), which methods write self.state keys (STATE_WRITE edges), and which modules the class imports (IMPORT edges). The graph is the relationship map for that class. Stored in the DB per class. BuildGraph in the flow reads all per-class graphs from the DB and assembles them into one loader dependency graph for DbModuleLoader to determine load order.

4.  ChatCompression — BCL Compression dialect applied to chat logs. Raw chat is verbose and unstructured. ChatCompression scans chat for structured facts and converts them to BCL tokens: [@Decision], [@Error], [@Fix], [@File], [@Result], [@Failed], [@Rule], [@Learning]. This gives queryable compression at approximately 100:1 ratio versus raw chat. Three layers: BCL tokens for lookup (~80% of actionable info in ~1% of words), checkpoint for context (~65% capture), chat log for archaeology (100% but verbose). Chat is read bottom-up (latest state first), error-focused pass finds problems and resolutions, user-intent pass finds priorities and reasoning. Compressed tokens are stored in DB and searchable via magnetic search.
"""
config =
[@DbLoader]
{
     [@Flow]
    {
        [@OpenDb]
        {
            "Open connection to {dbType} at {dbPath}";
            "Verify schema version";
            "Load connection metadata"
        }
        [@LoadMetadata]
        {
            "Read class names, domains, dependencies from DB";
            "Read BCL stamps from DB";
            "Read graph edges from DB";
            "Read BCLIR nodes from DB";
            "No class code loaded — metadata only"
        }
        [@Parse]
        {
            "Tokenize BCL headers into node tree";
            "Extract [@Tag]{content} packets";
            "Syntax only — no semantic validation"
        }
        [@Validate]
        {
            "Check parsed tree against dictionary rules";
            "Validate tag existence, parent/child rules";
            "Validate required children, repeatable constraints";
            "Block forbidden patterns (exec, eval)"
        }
        [@BuildGraph]
        {
            "Extract CALL edges from metadata";
            "Extract STATE_READ, STATE_WRITE edges";
            "Extract IMPORT, DEPENDS_ON edges";
            "Topological sort with cycle detection"
        }
        [@LoadIntoMemUnit]
        {
            "Open SQLite :memory: connection";
            "Create mu_commands, mu_results, mu_events, mu_state, mu_errors tables";
            "Insert metadata into MemUnit tables";
            "Register loaded classes in runtime registry";
            "No class code executed — metadata only"
        }
        [@Execute]
        {
            "Dispatch command through mu_commands";
            "Load class code on demand from DB";
            "Compile and exec in isolated namespace";
            "Inject resolved dependencies";
            "Return result through mu_results"
        }
        [@Index]
        {
            "Read [@Files] list from config";
            "Parse AST from each code file";
            "Read schema definitions from ancillary files";
            "Skip generated files"
        }
        [@Extract]
        {
            "Extract className, classCode, domain from each class";
            "Extract methodName, methodCode, params, signature from each method";
            "Extract BCL stamps from file headers";
            "Extract dependencies (imports, calls, state access)";
            "Extract graph edges (CALL, STATE_READ, STATE_WRITE, IMPORT)"
        }
        [@Writeback]
        {
            "Write extracted classes to DB classes table";
            "Write extracted methods to DB methods table";
            "Write BCL stamps to DB bclStamps table";
            "Write graph edges to DB graphEdges table";
            "Update [@GeneratedFiles] with fresh indexes"
        }
        [@Report]
        {
            "Collect loaded class count, failed count, dependency count";
            "Collect graph edges, cycle warnings, missing dependencies";
            "Collect execution results, errors, timing";
            "BCL in, BCL out — input is BCL spec, output is BCL report"
        }
    }
    [@Files]
    {
        [@CodeFiles]
        {
            ("DbModuleLoader.py";"DbModuleLoader_v3_2_fixes.py";"Config.py";"DbValidator.py";"DbImportResolver.py";"DbDiagnostics.py";"DbRuntimeManager.py")
        }
        [@AncillaryFiles]
        {
            ("Schema.sql";"Migrations.sql";"SeedData.json";"QueryTemplates.sql";"BclDictionary.json")
        }
        [@GeneratedFiles]
        {
            ("GraphIndex.json";"ClassRegistry.json";"MethodRegistry.json";"DependencyMap.json";"BclStamps.json")
        }
    }
    [@Indexer]
    {
        ("OnDemand";"OnFileChange";"OnStartup";"Interval";"Manual")
    }
    [@Type]
    {
        ("Sqlite";"Mysql";"Mariadb";"Psql";"Mongo";"Qdrant";"Redis";"Mssql";"Oracle";"Couchbase";"Couchdb";"Elasticsearch";"Dynamodb";"Firebase";"Supabase";"Neon";"Turso";"Planetscale";"Xata")
    }
    [@Table]
    {
        ("Auto","Explicit")
    }
    [@Permission]
    {
        ("ReadOnly";"ReadWrite";"ReadWriteExecute";"Admin";"SchemaModify";"FullAccess")
    }
    [@Auth]
    {
        ("None";"Password";"Token";"Oauth2";"Certificate";"ApiKey";"ConnectionString")
    }
    [@Schema]
    {
        [@Collections]
        {
            "Classes": { "fields": ("className:Text";"classCode:Text";"domain:Text";"description:Text";"sourceFile:Text";"lineStart:Integer";"isVbstyle:Boolean";"hasRunMethod:Boolean";"hasBcl:Boolean";"version:Integer";"createdAt:Timestamp";"id:Integer:PrimaryKey:AutoIncrement") };
            "Methods": { "fields": ("methodName:Text";"methodCode:Text";"params:Text";"signature:Text";"isDunder:Boolean";"returnsBcl:Boolean";"classId:Integer:ForeignKey";"id:Integer:PrimaryKey:AutoIncrement") };
            "BclClasses": { "fields": ("className:Text";"classCode:Text";"domain:Text";"bclHeader:Text";"version:Integer";"id:Integer:PrimaryKey:AutoIncrement") };
            "BclMethods": { "fields": ("methodName:Text";"methodCode:Text";"bclStamp:Text";"classId:Integer:ForeignKey";"id:Integer:PrimaryKey:AutoIncrement") };
            "VbClasses": { "fields": ("className:Text";"classCode:Text";"domain:Text";"vbstyle:Boolean";"version:Integer";"id:Integer:PrimaryKey:AutoIncrement") };
            "VbMethods": { "fields": ("methodName:Text";"methodCode:Text";"vbStamp:Text";"classId:Integer:ForeignKey";"id:Integer:PrimaryKey:AutoIncrement") }
        }
        [@TypeMapping]
        {
            "Text": { "Sqlite": "TEXT";"Mysql": "VARCHAR(255)";"Psql": "TEXT";"Mongo": "string";"Qdrant": "keyword";"Redis": "string" };
            "Integer": { "Sqlite": "INTEGER";"Mysql": "INT";"Psql": "INTEGER";"Mongo": "int";"Qdrant": "integer";"Redis": "integer" };
            "Boolean": { "Sqlite": "INTEGER";"Mysql": "TINYINT(1)";"Psql": "BOOLEAN";"Mongo": "bool";"Qdrant": "bool";"Redis": "integer" };
            "Timestamp": { "Sqlite": "DATETIME";"Mysql": "TIMESTAMP";"Psql": "TIMESTAMP";"Mongo": "date";"Qdrant": "integer";"Redis": "integer" };
            "Float": { "Sqlite": "REAL";"Mysql": "FLOAT";"Psql": "REAL";"Mongo": "double";"Qdrant": "float";"Redis": "float" };
            "Blob": { "Sqlite": "BLOB";"Mysql": "BLOB";"Psql": "BYTEA";"Mongo": "binData";"Qdrant": "keyword";"Redis": "string" }
        }
        [@Adapters]
        {
            [@Sqlite]
            {
                "CreateCollection": "CREATE TABLE IF NOT EXISTS {tableName} ({columns})";
                "DropCollection": "DROP TABLE IF EXISTS {tableName}";
                "Select": "SELECT {columns} FROM {tableName} WHERE {conditions}";
                "Insert": "INSERT INTO {tableName} ({columns}) VALUES ({values})";
                "Upsert": "INSERT OR REPLACE INTO {tableName} ({columns}) VALUES ({values})";
                "Update": "UPDATE {tableName} SET {assignments} WHERE {conditions}";
                "Delete": "DELETE FROM {tableName} WHERE {conditions}";
                "AddColumn": "ALTER TABLE {tableName} ADD COLUMN {columnName} {columnType}";
                "DropColumn": "ALTER TABLE {tableName} DROP COLUMN {columnName}";
                "RenameColumn": "ALTER TABLE {tableName} RENAME COLUMN {oldName} TO {newName}";
                "RenameTable": "ALTER TABLE {tableName} RENAME TO {newTableName}"
            }
            [@Mysql]
            {
                "CreateCollection": "CREATE TABLE IF NOT EXISTS {tableName} ({columns}) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4";
                "DropCollection": "DROP TABLE IF EXISTS {tableName}";
                "Select": "SELECT {columns} FROM {tableName} WHERE {conditions}";
                "Insert": "INSERT INTO {tableName} ({columns}) VALUES ({values})";
                "Upsert": "INSERT INTO {tableName} ({columns}) VALUES ({values}) ON DUPLICATE KEY UPDATE {updates}";
                "Update": "UPDATE {tableName} SET {assignments} WHERE {conditions}";
                "Delete": "DELETE FROM {tableName} WHERE {conditions}";
                "AddColumn": "ALTER TABLE {tableName} ADD COLUMN {columnName} {columnType}";
                "DropColumn": "ALTER TABLE {tableName} DROP COLUMN {columnName}";
                "RenameColumn": "ALTER TABLE {tableName} CHANGE {oldName} {newName} {columnType}";
                "RenameTable": "RENAME TABLE {tableName} TO {newTableName}"
            }
            [@Psql]
            {
                "CreateCollection": "CREATE TABLE IF NOT EXISTS {tableName} ({columns})";
                "DropCollection": "DROP TABLE IF EXISTS {tableName}";
                "Select": "SELECT {columns} FROM {tableName} WHERE {conditions}";
                "Insert": "INSERT INTO {tableName} ({columns}) VALUES ({values})";
                "Upsert": "INSERT INTO {tableName} ({columns}) VALUES ({values}) ON CONFLICT ({conflictColumns}) DO UPDATE SET {updates}";
                "Update": "UPDATE {tableName} SET {assignments} WHERE {conditions}";
                "Delete": "DELETE FROM {tableName} WHERE {conditions}";
                "AddColumn": "ALTER TABLE {tableName} ADD COLUMN {columnName} {columnType}";
                "DropColumn": "ALTER TABLE {tableName} DROP COLUMN {columnName}";
                "RenameColumn": "ALTER TABLE {tableName} RENAME COLUMN {oldName} TO {newName}";
                "RenameTable": "ALTER TABLE {tableName} RENAME TO {newTableName}"
            }
            [@Mongo]
            {
                "CreateCollection": "db.createCollection('{tableName}')";
                "DropCollection": "db.{tableName}.drop()";
                "Select": "db.{tableName}.find({{conditions}})";
                "Insert": "db.{tableName}.insertOne({{document}})";
                "Upsert": "db.{tableName}.updateOne({{filter}}, {{$set: {document}}}, {{upsert: true}})";
                "Update": "db.{tableName}.updateMany({{filter}}, {{$set: {updates}}})";
                "Delete": "db.{tableName}.deleteMany({{filter}})";
                "AddColumn": "db.{tableName}.updateMany({{}}, {{$set: {{ {columnName}: {defaultValue} }}}})";
                "DropColumn": "db.{tableName}.updateMany({{}}, {{$unset: {{ {columnName}: '' }}}})";
                "RenameColumn": "db.{tableName}.updateMany({{}}, {{$rename: {{ {oldName}: '{newName}' }}}})";
                "RenameTable": "db.{tableName}.renameCollection('{newTableName}')"
            }
            [@Qdrant]
            {
                "CreateCollection": "PUT /collections/{tableName} {{ vectors: {{ size: {vectorSize}, distance: '{distance}' }} }}";
                "DropCollection": "DELETE /collections/{tableName}";
                "Select": "POST /collections/{tableName}/points/search {{ vector: {vector}, limit: {limit} }}";
                "Insert": "PUT /collections/{tableName}/points {{ points: [{point}] }}";
                "Upsert": "PUT /collections/{tableName}/points {{ points: [{point}] }}";
                "Update": "POST /collections/{tableName}/points/payload {{ payload: {payload} }}";
                "Delete": "POST /collections/{tableName}/points/delete {{ points: {pointIds} }}";
                "AddColumn": "POST /collections/{tableName}/payload_schema {{ {columnName}: {{ data_type: '{dataType}' }} }}";
                "DropColumn": "DELETE /collections/{tableName}/payload_schema/{columnName}";
                "RenameColumn": "";
                "RenameTable": ""
            }
            [@Redis]
            {
                "CreateCollection": "";
                "DropCollection": "DEL {tableName}";
                "Select": "HGETALL {tableName}";
                "Insert": "HSET {tableName} {field} {value}";
                "Upsert": "HSET {tableName} {field} {value}";
                "Update": "HSET {tableName} {field} {newValue}";
                "Delete": "HDEL {tableName} {field}";
                "AddColumn": "";
                "DropColumn": "HDEL {tableName} {columnName}";
                "RenameColumn": "HRENAME {tableName} {oldName} {newName}";
                "RenameTable": "RENAME {tableName} {newTableName}"
            }
        }
        [@PreparedStatements]
        {
            "SelectByClass": "SELECT classCode, className, domain FROM {tableName} WHERE className = ?";
            "SelectByDomain": "SELECT className, classCode FROM {tableName} WHERE domain = ?";
            "SelectByMethod": "SELECT methodName, methodCode FROM {methodsTable} WHERE classId = ?";
            "InsertClass": "INSERT INTO {tableName} (className, classCode, domain) VALUES (?, ?, ?)";
            "UpdateClass": "UPDATE {tableName} SET classCode = ?, domain = ? WHERE className = ?";
            "DeleteClass": "DELETE FROM {tableName} WHERE className = ?";
            "UpsertClass": "INSERT OR REPLACE INTO {tableName} (className, classCode, domain) VALUES (?, ?, ?)"
        }
    }
    [@Connection]
    {
        ("Host";"Port";"Database";"Username";"Password";"Timeout";"MaxConnections";"MinConnections";"RetryAttempts";"RetryDelay";"Keepalive";"ConnectionPoolSize";"SslMode";"SslCert";"SslKey")
    }
    [@Transaction]
    {
        ("ReadUncommitted";"ReadCommitted";"RepeatableRead";"Serializable";"AutoCommit";"NestedTransactions";"BatchCommit";"RollbackOnerror")
    }
    [@Indexing]
    {
        ("Btree";"Hash";"Gin";"Gist";"Vector";"FullText";"Spatial";"Composite";"Unique";"Partial")
    }
    [@Migration]
    {
        ("VersionTracking";"Rollback";"Forward";"SeedData";"ChecksumValidation";"DryRun";"BatchSize")
    }
    [@Backup]
    {
        ("Snapshot";"Export";"Import";"Restore";"Schedule";"Incremental";"Compression";"Encryption";"RetentionDays")
    }
    [@Replication]
    {
        ("Master";"ReadReplica";"Sync";"Async";"SemiSync";"Cascade";"AutomaticFailover";"LoadBalancer")
    }
    [@Encoding]
    {
        ("Utf8";"Utf16";"Utf32";"Latin1";"Ascii";"Binary";"Collation")
    }
    [@Caching]
    {
        ("QueryCache";"ResultCache";"Ttl";"CacheSize";"CacheEviction";"CacheWarming";"DistributedCache")
    }
    [@Logging]
    {
        ("QueryLog";"SlowQueryThreshold";"AuditLog";"LogLevel";"ErrorLog";"ConnectionLog";"TransactionLog")
    }
   
}
DB_TYPES = (
    "Sqlite",
    "Mysql",
    "Mariadb",
    "Psql",
    "Mongo",
    "Qdrant",
    "Redis",
    "Mssql",
    "Oracle",
    "Couchbase",
    "Couchdb",
    "Elasticsearch",
    "Dynamodb",
    "Firebase",
    "Supabase",
    "Neon",
    "Turso",
    "Planetscale",
    "Xata",
    "",
)

#[@Table]
#{
#    ("Auto","Explicit")
#}
TABLE_MODES = (
    "Auto",
    "Explicit",
)

TABLE_MODE_AUTO = "Auto"
TABLE_MODE_EXPLICIT = "Explicit"

#[@Permission]
#{
#    ("ReadOnly";"ReadWrite";"ReadWriteExecute";"Admin";"SchemaModify";"FullAccess")
#}
PERMISSIONS = (
    "ReadOnly",
    "ReadWrite",
    "ReadWriteExecute",
    "Admin",
    "SchemaModify",
    "FullAccess",
)

#[@Auth]
#{
#    ("None";"Password";"Token";"Oauth2";"Certificate";"ApiKey";"ConnectionString")
#}
AUTH_MODES = (
    "None",
    "Password",
    "Token",
    "Oauth2",
    "Certificate",
    "ApiKey",
    "ConnectionString",
)
 