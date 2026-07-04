<!-- [@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<Spec for Chat Core integration. Documents ChatGui.py classes, features, ChatInputBar capabilities and gaps. No VBStyle violations (spec doc).>][@todos<none>]} -->
# SPEC: Chat Core Integration

## 1. WHAT EXISTS — ChatGui.py (1,220 lines)

### Classes
| Class | Lines | Role |
|-------|-------|------|
| DevinWorker | 41-78 | QThread — runs `devin -p` CLI, emits finished/error signals |
| MysqlSearchWorker | 81-134 | QThread — searches vb_shared/vb_code_test tables |
| SessionListWorker | 137-188 | QThread — fetches devin_sessions from MySQL |
| TokenLoaderWorker | 191-215 | QThread — loads @ tokens from vb_shared.tokens |
| ChatInputBar | 218-311 | QLineEdit — slash command popup + @ token popup |
| ChatGui | 314-1220 | QMainWindow — full GUI: chat area, splitter, toolbar, KB tab, sessions tab, menu, settings |

### ChatGui Features (current)
- Chat display: QScrollArea + QFrame bubbles (user/assistant/system) with _AddMessage
- Input bar: ChatInputBar with /slash popup and @token popup
- Send button: invokes DevinWorker thread
- Clear chat button
- CWD label
- Right panel: QSplitter with QTabWidget (Knowledge Base + Sessions)
- Vertical toolbar: 2 toggle buttons (KB, Sessions) — outside splitter
- Knowledge Base tab: search field, table combo (5 tables), results table, result count
- Sessions tab: session list, refresh, new session, context menu (resume/copy/new)
- Menu bar: File (New/Clear/Quit), View (Toggle KB/Sessions/Refresh), Settings (Font/OnTop), Help
- Settings dialog: font size spinboxes, always-on-top checkbox
- Theme: hardcoded VSCode dark colors
- Window: right-side docked, 25% width, 90% height, always-on-top

### ChatGui Features (user added recently)
- Themes: 5 presets in Config_ChatGui.py (VSCode Dark, Midnight Blue, Solarized Dark, GitHub Dark, Monokai)
- Bubble config: error color, padding, label font, time font
- Status indicator colors: READY/BUSY/ERROR
- Role labels: YOU/DEVIN/SYSTEM/ERROR
- Window opacity setting

### What ChatInputBar HAS
- Slash command popup (/help, /clear, /search, etc.)
- @ token popup (loads from MySQL or fallback list)
- Popup navigation (Up/Down/Enter/Esc)
- No predictive text, no ghost text, no autocomplete, no learning

### What ChatInputBar LACKS
- Ghost text predictive autocomplete (word_freq prefix matching)
- Bigram prediction (most common next word after space)
- Trigram prediction (2 previous words → next word)
- User history (learned vocabulary over time)
- Style detection (calm/neutral/frustrated mode)
- Ranked suggestions (combining all 5 sources with weights)

---

## 2. WHAT EXISTS — Dom_Smart_system_seach (autocomplete engine)

### Gui_Smart_search.py — GhostLineEdit (lines 160-295)
| Feature | Implementation |
|---------|---------------|
| Ghost text | Grey predictive text drawn in paintEvent after cursor |
| Mode 1: mid-word | Prefix match against word_freq Counter — most frequent word starting with typed chars |
| Mode 2: after space | Bigram prediction via SQLite query — SELECT w2 FROM bigrams WHERE w1=? |
| Accept | Tab key accepts ghost text, inserts at cursor position |
| Timer | 250ms debounce after textChanged before updating ghost |
| set_model() | Loads word_freq Counter + opens SQLite connection to autocomplete.db |

### Engine_smart_search.py — Autocomplete Functions
| Function | Purpose |
|----------|---------|
| AcBigramNext(conn, word) | Query bigrams table for most common next word |
| AcTrigramNext(conn, w1, w2) | Query trigrams table for most common next word |
| AcPrefixSearch(conn, prefix) | Query word_freq table for prefix matches |
| AcSymbolSearch(prefix) | Search class/method names from codebase |
| AcUserHistoryPrefix(conn, word, ctx) | Query user_history for previously accepted words |
| AcRecordAccept(conn, word, context) | Record accepted word into user_history (learns over time) |
| AcRankedSuggestions(conn, current_word, prev_words) | Combine all 5 sources with weights, return ranked list |
| DetectStyleMode(text) | Detect calm/neutral/frustrated from typing patterns |
| LoadAutocomplete() | Generator — loads word_freq, bigrams, trigrams from MySQL into SQLite |

### Config_smart_system.py — Autocomplete Config
| Constant | Value |
|----------|-------|
| AUTOCOMPLETE_DB_NAME | 'autocomplete.db' |
| TIMER_AUTOCOMPLETE | 250ms |
| AUTOCOMPLETE_PREFIX_LIMIT | 20 |
| RANK_WEIGHT_USER_HISTORY | 120 (highest) |
| RANK_WEIGHT_SYMBOL | 100 |
| RANK_WEIGHT_TRIGRAM | 80 |
| RANK_WEIGHT_BIGRAM | 60 |
| RANK_WEIGHT_PREFIX | 40 (lowest) |
| STOP_WORDS | 59 common English words |
| SQL_SELECT_BIGRAM_NEXT | SELECT w2, freq FROM bigrams WHERE w1=? ORDER BY freq DESC LIMIT 20 |
| SQL_SELECT_TRIGRAM_NEXT | SELECT w3, freq FROM trigrams WHERE w1=? AND w2=? ORDER BY freq DESC LIMIT 20 |
| SQL_SELECT_WORD_PREFIX | SELECT word, freq FROM word_freq WHERE word LIKE ? ORDER BY freq DESC LIMIT 20 |
| SQL_CREATE_USER_HISTORY | CREATE TABLE IF NOT EXISTS user_history (...) |
| SQL_UPSERT_USER_HISTORY | INSERT ... ON CONFLICT DO UPDATE SET freq = freq + 1 |

### autocomplete.db (225KB, exists at Dom_Smart_system_seach/autocomplete.db)
**ACTUAL TABLES (verified):** user_questions (7,217 rows), qa_pairs (12,487 rows), sqlite_sequence
**MISSING TABLES:** word_freq, bigrams, trigrams, user_history — NOT BUILT YET

The qa_pairs table has the user's chat history (question + answer + style + source + file).
This is the "model knows me" data — 12,487 Q&A pairs from the user's own conversations.
Sample: ("ARE TEY FIXED UP NO FUNY MISSING ERROS?", "Yes. All tokens verified...", "neutral", "cascade", ...)

The word_freq/bigrams/trigrams tables need to be built from qa_pairs BEFORE ghost text can work.
Engine_smart_search.py has LoadAutocomplete() which builds from MySQL token_registry.word_locations,
but we can also build directly from qa_pairs in autocomplete.db (no MySQL dependency needed).

---

## 3. WHAT NEEDS TO BE BUILT — GhostChatInput

### Goal
Replace ChatInputBar with GhostChatInput that merges:
1. Slash command popup (existing)
2. @ token popup (existing)
3. Ghost text predictive autocomplete (from GhostLineEdit)
4. Bigram/trigram prediction (from Engine_smart_search)
5. User history learning (from Engine_smart_search)
6. Ranked suggestions (from Engine_smart_search)

### Class: GhostChatInput(QLineEdit)

#### State
- slash_commands: list (from config)
- at_tokens: list (loaded from MySQL)
- popup: QListView (shared for slash + @)
- popup_mode: "slash" | "at" | None
- _ghost_text: str (grey predictive text)
- _word_freq: Counter (loaded from autocomplete.db)
- _ac_conn: sqlite3.Connection (to autocomplete.db)
- _ghost_timer: QTimer (250ms debounce)

#### Methods
| Method | Purpose |
|--------|---------|
| __init__ | Setup UI, fonts, placeholder, timers, textChanged signal |
| SetTokens(tokens) | Load @ tokens from MySQL |
| SetAutocompleteModel(word_freq, db_path) | Load word freq + open SQLite connection |
| _OnTextChanged(text) | Route to slash popup, @ popup, or ghost timer |
| _GetCurrentWord() | Extract word being typed (after last space) |
| _GetPreviousWord() | Get word before cursor (for bigram prediction) |
| _UpdateGhost() | Mode 1: prefix match. Mode 2: bigram query. Draw ghost text. |
| _AcceptGhost() | Tab key — insert ghost text at cursor, record to user_history |
| _ShowPopup(items, mode) | Show QListView popup for slash/@ |
| _HidePopup() | Hide popup |
| _OnPopupSelected(index) | Handle slash/@ selection |
| keyPressEvent(event) | Route: Tab→accept ghost, Esc/arrows→popup, Enter→popup or send |
| paintEvent(event) | Draw ghost text in grey after cursor position |

#### Key Behavior — Priority Order
1. If popup visible → arrow keys navigate popup, Enter selects, Esc closes
2. If Tab pressed and ghost text exists → accept ghost text
3. If text starts with "/" and no space → slash command popup
4. If text contains "@" → token popup
5. Otherwise → ghost text autocomplete timer starts (250ms debounce)
6. On ghost accept → record word to user_history (learning)

#### Ghost Text Logic
- Mode 1 (mid-word, len >= 1): Scan word_freq.most_common(500), find first word starting with current prefix
- Mode 2 (after space): Query bigrams table for previous word → most common next word
- Draw: paintEvent draws ghost text in grey (RGB 120,130,145) at cursor x position

#### Learning Loop
- On Tab accept → AcRecordAccept(conn, accepted_word, previous_word)
- user_history table tracks (word, context, freq) — context = previous word
- Next time same context appears, user history gets RANK_WEIGHT_USER_HISTORY (120) — highest priority

---

## 4. WHAT NEEDS TO BE BUILT — AutocompleteLoaderWorker

### Goal
QThread that loads word_freq from autocomplete.db into Counter at startup.

### Class: AutocompleteLoaderWorker(QThread)

#### Methods
| Method | Purpose |
|--------|---------|
| __init__ | Store db_path |
| run() | 1. Check if word_freq table exists. 2. If not, build from qa_pairs. 3. Load word_freq into Counter. 4. Emit Counter. |
| _BuildTablesIfMissing() | Create word_freq/bigrams/trigrams/user_history tables. Tokenize qa_pairs. Populate. |
| finished signal | pyqtSignal(Counter, int) — Counter + word count |

#### Flow
1. ChatGui.__init__ → start AutocompleteLoaderWorker
2. Worker opens autocomplete.db
3. Checks: SELECT COUNT(*) FROM word_freq — if 0, run _BuildTablesIfMissing()
4. _BuildTablesIfMissing: tokenize all qa_pairs (question + answer), build word_freq + bigrams + trigrams
5. Load word_freq into Counter: SELECT word, freq FROM word_freq
6. Emit Counter via finished signal
7. ChatGui._OnAutocompleteLoaded → input_field.SetAutocompleteModel(counter, db_path)
8. Input field opens its own SQLite connection for bigram queries

---

## 5. WHAT NEEDS TO BE BUILT — ChatGui modifications

### Changes to ChatGui class

#### __init__
- After _BuildMenu(), start AutocompleteLoaderWorker
- Connect finished signal to _OnAutocompleteLoaded

#### New method: _OnAutocompleteLoaded(word_freq)
- Call self.input_field.SetAutocompleteModel(word_freq, AUTOCOMPLETE_DB_PATH)
- Append system message: "Predictive text loaded (N words, bigram model active)"

#### _BuildUi — input_field creation
- Replace `ChatInputBar()` with `GhostChatInput()`
- All existing styling, returnPressed connection, etc. stay the same

#### _OnSend
- After sending, if ghost text was accepted, the word is already recorded
- No changes needed — learning happens in GhostChatInput._AcceptGhost

---

## 6. WHAT NEEDS TO BE BUILT — Config_ChatGui.py additions

### Already has
- Colors, fonts, DB config, slash commands, fallback tokens
- Autocomplete DB path, timer, limits, ranking weights
- SQL queries for bigram/trigram/word_freq/user_history
- Stop words, window settings, toolbar, splitter, bubbles, themes

### Missing — needs to be added
| Constant | Value | Purpose |
|----------|-------|---------|
| GHOST_TEXT_COLOR | QColor or RGB tuple | Single source for ghost text color |
| AUTOCOMPLETE_WORD_SCAN | 500 | Max words to scan for prefix match |
| AUTOCOMPLETE_PREFIX_MIN | 1 | Min chars before prefix match activates |
| AUTOCOMPLETE_MIN_WORD_LEN | 2 | Min word length for tokenization |
| LRU_CACHE_SIZE | 5000 | (future) Cache for bigram query results |

Note: AUTOCOMPLETE_WORD_SCAN, AUTOCOMPLETE_PREFIX_MIN, AUTOCOMPLETE_MIN_WORD_LEN already exist in Config_ChatGui.py (lines 113-115). GHOST_TEXT_R/G/B already exist (lines 49-51). So Config is actually complete.

---

## 7. GAP ANALYSIS

### Gaps in ChatGui.py
| # | Gap | Severity | Fix |
|---|-----|----------|-----|
| 1 | ChatInputBar has no ghost text | HIGH | Replace with GhostChatInput |
| 2 | No autocomplete DB connection | HIGH | Add AutocompleteLoaderWorker |
| 3 | No word_freq loading | HIGH | Load in worker, pass to SetAutocompleteModel |
| 4 | No bigram/trigram prediction | HIGH | Query autocomplete.db in _UpdateGhost |
| 5 | No user history learning | MEDIUM | AcRecordAccept on Tab accept |
| 6 | No style detection | LOW | Future: DetectStyleMode on send |
| 7 | Hardcoded "Menlo" font in many places | LOW | Should use FONT_FAMILY from config |
| 8 | Hardcoded "vb_code_test" in MysqlSearchWorker | LOW | Should use DB_CODE_TEST from config |
| 9 | Themes defined but not applied | MEDIUM | Future: theme switching in settings |
| 10 | BUBBLE_COLOR_ERROR etc defined but not used | LOW | Future: error bubbles in _AddMessage |

### Gaps in Config_ChatGui.py
| # | Gap | Severity | Fix |
|---|-----|----------|-----|
| 1 | DB_CODE_TEST defined but ChatGui uses hardcoded "vb_code_test" | LOW | Replace in ChatGui |
| 2 | FONT_FAMILY defined but ChatGui uses hardcoded "Menlo" | LOW | Replace in ChatGui |

### Gaps in autocomplete.db
| # | Gap | Severity | Fix |
|---|-----|----------|-----|
| 1 | word_freq table MISSING | HIGH | Build from qa_pairs (Phase 0) |
| 2 | bigrams table MISSING | HIGH | Build from qa_pairs (Phase 0) |
| 3 | trigrams table MISSING | HIGH | Build from qa_pairs (Phase 0) |
| 4 | user_history table MISSING | MEDIUM | Create on first connect (SQL_CREATE_USER_HISTORY) |

### Not Gaps (already handled)
- Stop words: already in Config_ChatGui.py
- SQL queries: already in Config_ChatGui.py
- Ranking weights: already in Config_ChatGui.py
- Ghost text color: already in Config_ChatGui.py (RGB)
- Autocomplete DB path: already in Config_ChatGui.py

---

## 8. INTEGRATION PLAN (ordered)

### Phase 0: Build autocomplete tables in autocomplete.db
- Create word_freq, bigrams, trigrams, user_history tables in autocomplete.db
- Tokenize all qa_pairs (12,487 rows) — question + answer text
- Build word_freq: count every word (excluding stop words, len > 2)
- Build bigrams: count every (word_i, word_i+1) pair
- Build trigrams: count every (word_i, word_i+1, word_i+2) triple
- Create indexes: idx_word_prefix, idx_bigram_w1, idx_bigram_w1_freq, idx_tri
- This is the "model knows me" step — learns the user's vocabulary from their own chat history
- Runs once at first startup, cached in SQLite for subsequent runs

### Phase 1: Build GhostChatInput class (in ChatGui.py)
- Replace ChatInputBar (lines 218-311) with GhostChatInput
- GhostChatInput extends ChatInputBar with ghost text + autocomplete
- All existing slash/@ popup code preserved
- New: _ghost_text, _word_freq, _ac_conn, _ghost_timer
- New: SetAutocompleteModel, _GetCurrentWord, _GetPreviousWord, _UpdateGhost, _AcceptGhost
- Modified: _OnTextChanged (add ghost timer start for non-slash/@ text)
- Modified: keyPressEvent (add Tab → accept ghost)
- New: paintEvent (draw ghost text)

### Phase 2: Build AutocompleteLoaderWorker class (in ChatGui.py)
- New QThread class after TokenLoaderWorker
- Opens autocomplete.db, loads word_freq into Counter
- Emits Counter via finished signal

### Phase 3: Wire up ChatGui
- In __init__: start AutocompleteLoaderWorker after _BuildMenu()
- New method _OnAutocompleteLoaded(word_freq)
- In _BuildUi: replace ChatInputBar() with GhostChatInput()
- Replace hardcoded "Menlo" with FONT_FAMILY throughout
- Replace hardcoded "vb_code_test" with DB_CODE_TEST

### Phase 4: Test
- py_compile both files
- Run GUI — verify slash popup, @ popup, ghost text, Tab accept
- Verify autocomplete.db loads without error
- Verify user_history records on Tab accept

---

## 9. FILE STRUCTURE

```
Dom_Graph/
  Config_ChatGui.py     ← ALL constants (245 lines, done)
  ChatGui.py            ← GUI + workers + GhostChatInput (modified)
  SPEC_CHAT_CORE.md     ← This spec
```

No new files needed beyond the spec. All code goes into existing files.

---

## 10. WHAT IS NOT IN SCOPE

- Theme switching UI (themes defined in config, not yet applied)
- DetectStyleMode integration (style detection exists but not wired to UI)
- AcRankedSuggestions full integration (5-source ranking — future, ghost text uses simple prefix+bigram first)
- AcSymbolSearch integration (searching class/method names — future)
- Chat history persistence to MySQL (devin_chat_turns table exists but not used)
- Multi-line input (QTextEdit instead of QLineEdit — future)
- Copy/paste message bubbles
- Search within chat history
