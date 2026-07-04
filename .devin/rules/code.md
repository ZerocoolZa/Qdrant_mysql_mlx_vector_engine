# CODE RULES INDEX

All code in this workspace must follow these rules:

1. **config_file_rule.md** — Mandatory Config file per folder + FILE_INDEX + No Hardcoding + Single Source of Truth (R1-R8)
2. **vbstyle_rules.md** — Full VBStyle rules:
   - Headers: Ghost, VBStyle, AI Guide, Class, Method (H1-H5)
   - Naming: PascalCase, UPPERCASE, camelCase, No underscore (N1-N4)
   - Code Style: No print, no decorators, no hardcode, no tabs, no enums, no hidden imports (C1-C7)
   - Architecture: Run() dispatch, Tuple3, state dict, config singleton, dispatch map, no memory units, remote dest (V1-V8)
   - File Organization: Import order, structure order, whitespace (F1-F3)
   - Error Handling: Tuple3 errors, no bare except, descriptive messages, log on error, no silent failures (E1-E5)
   - Logging: logging module, log levels, rotating logs, log format (L1-L4)
   - SQL & Schema: Embedded schema, boot cold, no inline SQL, parameterized queries, idempotent seeds (S1-S5)
   - Environment Variables: Naming, override pattern, documentation, no required env vars (EV1-EV4)
   - Documentation: ABOUT/HELP/README constants, config registry (D1-D5)
   - Database Access: Connection class, cleanup, reconnect, transactions (DB1-DB4)
   - Testing: Test before implement, naming, isolation, verify commands (T1-T4)
   - Dependencies: Python 3.13+, requirements.txt, no unnecessary deps, specific imports (DEP1-DEP4)
   - Security: No credentials in code/logs/seed, file permissions (SEC1-SEC4)
   - BCL Tokens: Bracket format, weight last, semicolons, capital names, real parser (B1-B5)
   - Static Resources: Embed as base64, compress, no file sprawl (SR1-SR3)
   - Config Registry: Registry file, content, maintenance (CR1-CR3)
   - File Naming: snake_case, no generic names, one class per file (FN1-FN3)
   - Import Rules: No circular, config first, no wildcards (IM1-IM3)
   - Pipeline: Idempotent, resumable, batch processing, self-healing (P1-P4)
3. **system-memory-mysql-search.md** — MySQL knowledge base search before writing code
4. **cascade-workflows-and-features.md** — Cascade workflow and feature authoring guide
5. **devin-docs-index.md** — Devin documentation index
