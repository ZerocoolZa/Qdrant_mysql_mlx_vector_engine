# BCL SYMBOL GRAMMAR — LIVE SYMBOLIC WORKSPACE

BCL is not just a bracket language. It is a **live symbolic workspace** — an interactive
symbolic operating environment where the chat interface, GUI editor, configuration system,
compiler, and AI agents all manipulate the same underlying object graph.

---

## THE 6-LAYER MODEL

Every symbol, expression, and packet in BCL has a defined place in this hierarchy:

```
Layer 5  Prediction       autocomplete, intent completion, workflow completion
Layer 4  Workflows        GUI, Graph, Compiler, AI, Database
Layer 3  Commands         build, scan, verify, report, save
Layer 2  Objects          window, menu, toolbar, button, graph, node, edge, task
Layer 1  Grammar          navigation, selection, branching, assignment, query, flow
Layer 0  Characters       ? ! . , -> >> [] {} ()
```

### Layer 0 — Characters (symbol operators)

These are not punctuation. They are **operators with defined semantics**:

| Symbol | Name | Semantics |
|---|---|---|
| `?` | query | Query / uncertainty — ask a question |
| `!` | assert | Assert / force — declare something must be true |
| `?!` | investigate | What now? — investigate, probe deeper |
| `->` | flow | Flow — directional transformation or routing |
| `>>` | advance | Continue / advance to next step |
| `>>?` | next query | What is the next step after this? |
| `[]` | selection | Selection or tuple — choose from options |
| `{}` | container | Container — holds nested content (BCL bracket body) |
| `()` | tuple | Tuple — ordered values with weights `("a";"b";92)` |
| `.` | navigate | Navigation into an object — path access |
| `,` | separate | Separator between items |
| `=` | assign | Assignment — set a value |
| `|` | pipe | Pipe — chain operations |
| `@` | tag | Tag marker — precedes a BCL tag name |
| `;` | delim | Delimiter — separates tuple fields |

### Layer 1 — Grammar (operations)

Operations that use the symbol operators:

| Operation | Symbols used | Example |
|---|---|---|
| Navigation | `.` | `.window.title` — navigate to window.title |
| Selection | `[]` | `[window|menu|toolbar]` — select from options |
| Branching | `?` `!` | `condition ? true : false` |
| Assignment | `=` | `.window.width.max=1920` |
| Query | `?` `?!` | `?status` — query current status |
| Flow | `->` `>>` | `scan -> graph -> verify` |
| Container | `{}` | `[@TAG]{content}` — BCL packet body |
| Tuple | `()` | `("key";"value";92)` — weighted tuple |
| Pipe | `\|` | `query \| filter \| sort` |

### Layer 2 — Objects (live object graph)

Objects are addresses into a live object graph. They are not free-form strings.

| Object path | What it addresses |
|---|---|
| `.window` | The window object |
| `.window.title` | Window title property |
| `.window.width.max` | Window maximum width constraint |
| `.window.width.min` | Window minimum width constraint |
| `.toolbar` | The toolbar object |
| `.toolbar.file` | File menu in toolbar |
| `.menu.edit` | Edit menu |
| `.button.ok` | OK button |
| `.graph` | The graph object |
| `.graph.nodes` | Nodes in the graph |
| `.graph.edges` | Edges in the graph |
| `.task` | Current task object |
| `.task.status` | Task status |
| `.task.id` | Task identifier |

Typing `.window.title` is effectively a **query against the live GUI tree**.

### Layer 3 — Commands (actions)

Commands operate on objects:

| Command | What it does |
|---|---|
| `build` | Build the project or graph |
| `scan` | Scan files for ingestion |
| `verify` | Run verification checks |
| `report` | Generate a report |
| `save` | Save current state |
| `load` | Load saved state |
| `run` | Execute a task or unit |
| `query` | Query the object graph |
| `edit` | Edit an object property |
| `create` | Create a new object |
| `delete` | Remove an object |

### Layer 4 — Workflows (domains)

Workflows combine commands and objects into multi-step processes:

| Workflow | Objects | Commands |
|---|---|---|
| GUI | window, menu, toolbar, button, panel | edit, create, save, load |
| Graph | nodes, edges, classes, methods | build, scan, query, verify |
| Compiler | files, AST, IR, stamps | build, verify, report |
| AI | tasks, packets, results | run, query, dispatch |
| Database | tables, rows, queries | query, insert, update, delete |

### Layer 5 — Prediction (intelligence)

The prediction layer provides intelligent assistance:

| Feature | What it does |
|---|---|
| Autocomplete | Suggest next symbol, object, or command |
| Intent completion | Infer user intent from partial input |
| Workflow completion | Suggest next step in a multi-step process |
| Context prediction | Predict what the user needs based on current state |

---

## INTERACTIVE GRAMMAR — DOT AS A COMMAND

The `.` (dot) is not just a character. It is a **command**.

```
User types: .
     |
     v
  GUI tree displayed
     |
     +-- window
     +-- toolbar
     +-- statusbar
     +-- menu
     +-- button
     +-- panel
     +-- ...
     |
     v
  User selects one (highlight, edit, save)
```

This is similar to how an IDE lets you navigate an abstract syntax tree,
except it uses BCL's own symbolic protocol.

### Dot navigation examples:

```
.                    -- show the root object tree
.window              -- show window properties
.window.title        -- get current window title
.window.title="BCL"  -- set window title (live update)
.window.width.max    -- get max width constraint
.window.width.max=1920  -- set max width (live update)
.toolbar             -- show toolbar properties
.toolbar.file        -- show file menu items
.menu.edit           -- show edit menu items
.button.ok           -- show OK button properties
```

---

## LIVE OBJECT EDITING

The GUI exists in memory. Instead of opening a property editor, you type directly:

```
.window.width.max=1920
```

The GUI immediately changes. The configuration is updated. The model sees the change.
Everything stays synchronized.

### What this blurs:

- **Editor** — you type to edit properties
- **Command line** — you type commands to execute
- **Configuration file** — you type settings inline
- **GUI designer** — you type to modify the visual interface
- **AI chat** — you type to communicate with AI

They are all manipulating the **same underlying object graph**.

### Synchronization model:

```
User types: .window.title="BCL Studio"
     |
     v
  Object graph updated
     |
     +-- GUI re-renders immediately
     +-- Config file updated
     +-- Model/state updated
     +-- AI sees the change
     +-- Event logged in MemUnit
```

No separate save step. No separate editor. No separate config file.
The object graph IS the source of truth. Every interface is a view into it.

---

## SEMANTIC SHORTCUTS (three-letter tokens)

Instead of typing natural language questions, semantic compression:

| Shortcut | Meaning | Equivalent natural language |
|---|---|---|
| `?` | query | "What is the status?" |
| `?!` | investigate | "What's wrong? What now?" |
| `>>` | advance | "Continue to the next step" |
| `>>?` | next query | "What's the next step after this?" |
| `!` | assert | "This must be true" |
| `->` | flow | "Transform this into that" |
| `?status` | query status | "What is the current status?" |
| `?graph` | query graph | "Show me the graph" |
| `>>save` | advance + save | "Save and continue" |
| `->verify` | flow + verify | "Then verify" |

These are not abbreviations. They are **semantic operators** with defined meaning.
The parser recognizes them and dispatches to the appropriate handler.

---

## RELATIONSHIP TO BCL BRACKET GRAMMAR

The symbol grammar and the bracket grammar are complementary:

```
Symbol grammar:  .window.title="BCL Studio"
Bracket grammar: [@CONFIG]{[@WINDOW]{[@TITLE]{BCL Studio}}}
```

Both express the same thing. The symbol grammar is for **interactive use** (typing in a terminal).
The bracket grammar is for **packet exchange** (AI-to-AI, unit-to-unit).

### Conversion:

| Symbol form | Bracket form |
|---|---|
| `.window.title` | `[@QUERY]{[@WINDOW]{[@TITLE]{}}}` |
| `.window.title="BCL"` | `[@CONFIG]{[@WINDOW]{[@TITLE]{BCL}}}` |
| `scan -> graph -> verify` | `[@PIPELINE]{[@STAGE]{scan}[@STAGE]{graph}[@STAGE]{verify}}` |
| `?status` | `[@QUERY]{[@CMD]{status}}` |
| `>>?` | `[@QUERY]{[@CMD]{next_step}}` |

The parser handles bracket syntax. The interactive handler handles symbol syntax.
Both produce the same internal node tree. Both query the same dictionary.

---

## FORMAL GRAMMAR DEFINITION (for BCL_SPEC.md)

### Terminal symbols:

```
ATOM     ::= [@TAG]{CONTENT}
TAG      ::= [A-Z_][A-Z0-9_]*
CONTENT  ::= (ATOM | TUPLE | TEXT)*
TUPLE    ::= (FIELD (; FIELD)* (; WEIGHT)?)
FIELD    ::= TEXT
WEIGHT   ::= [0-9]+
TEXT     ::= [^{}]*  (raw text, no brackets)
```

### Symbol operators:

```
NAV      ::= . PATH
PATH     ::= IDENT (. IDENT)*
IDENT    ::= [a-z_][a-z0-9_]*
ASSIGN   ::= PATH = VALUE
QUERY    ::= ? (IDENT)?
INVEST   ::= ?!
FLOW     ::= -> IDENT
ADVANCE  ::= >> (IDENT | ?)
ASSERT   ::= ! EXPRESSION
PIPE     ::= | IDENT
SELECTION::= [OPTION (| OPTION)*]
```

### Interactive expressions:

```
EXPR     ::= NAV | ASSIGN | QUERY | INVEST | FLOW | ADVANCE | ASSERT | PIPE | SELECTION | ATOM
CHAIN    ::= EXPR (PIPE EXPR)*
```

### Object paths:

```
OBJ      ::= . (window | menu | toolbar | button | panel | graph | task | node | edge | file | class | method | config | state | ...)
PROPPATH ::= OBJ (. IDENT)*
```

---

## IMPLEMENTATION NOTES

### For the C engine:
- The symbol grammar is handled by the CLI interactive handler, not the BCL parser
- The BCL parser handles bracket syntax only (as per parser/validator separation)
- The CLI converts symbol expressions to BCL packets before dispatching to MemUnit
- The dictionary defines valid object paths and their properties

### For the GUI:
- The object graph is the live model — GUI widgets are views into it
- Typing `.window.title="X"` updates the model, which triggers GUI re-render
- The GUI can also update the model (e.g., dragging a window edge) — same object graph
- All changes go through the MemUnit as events (audit trail)

### For AI agents:
- AI receives BCL packets (bracket form) — not symbol expressions
- AI can emit BCL packets that modify the object graph
- The object graph is queryable via `[@QUERY]{[@OBJ]{window.title}}`
- Changes by AI trigger the same synchronization as user typing
