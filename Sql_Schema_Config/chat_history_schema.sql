-- ──────────────────────────────────────────────────────────────────────────
-- Chat_History — MySQL Schema for Chat Storage
--
-- Sources:
--   - Cascade .md chat files (163 files in chat_resources) — the standard
--   - ChatGPT export JSON (208 conversations, 226 MB)
--   - Devin/Windsurf sessions.db (SQLite, 267 MB, 27 sessions)
--   - vb_shared.graph_conversations (102 Q&A pairs, already in MySQL)
--
-- WHY THIS DESIGN:
--   Chats are just evidence of the truth. The content is the point —
--   what you said, what the AI said. Not metadata about file paths,
--   working directories, or tool execution logs.
--
--   The .md files are the standard. They have: a filename, a date, and
--   conversation text (## User / ### Planner Response). That's it.
--   Every other source gets normalized down to that same shape.
--
--   What we keep:
--     1. sessions — auto-increment id, filename (duplicates allowed),
--        model tells you which AI produced it, created_at is the file date
--     2. messages — role + content, the actual conversation
--     3. prompts — what you typed, searchable
--
--   What we dropped and why:
--     - tool_calls: file edit metadata, not conversation content
--     - message_edges: graph structure, not needed — we only want messages
--     - rendered_commits: 20 MB of HTML snapshots, zero knowledge value
--     - working_dir: only Devin has it, you don't search by directory
--     - source column: the model name IS the source (gpt-4o-mini = ChatGPT,
--       claude-sonnet-4 = Cascade, etc.)
--     - last_activity: created_at is enough
--     - metadata JSON: dump whatever extras into the model column or skip
--     - parent_node_id, root_node_id, execution_index: graph fields that
--       add nothing for linear chat transcripts
--
--   3 tables. Simple to query. Simple to migrate from any source.
-- ──────────────────────────────────────────────────────────────────────────

CREATE DATABASE IF NOT EXISTS Chat_History
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE Chat_History;

-- ─── SESSIONS ──────────────────────────────────────────────────────────────
-- One row per chat. Duplicate filenames are allowed (same name in different folders).

CREATE TABLE sessions (
  id              BIGINT AUTO_INCREMENT PRIMARY KEY,
  title           VARCHAR(300) NOT NULL,             -- filename or conversation title
  model           VARCHAR(100),                      -- gpt-4o-mini, claude-sonnet-4, etc.
  created_at      BIGINT,                            -- file date / conversation date (unix)
  imported_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- when it entered MySQL
  INDEX idx_title (title)
);

-- ─── MESSAGES ──────────────────────────────────────────────────────────────
-- The actual conversation: what the user said, what the AI said.
-- Linear ordering by node_id within each session.

CREATE TABLE messages (
  row_id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  session_id      BIGINT NOT NULL,
  node_id         INT NOT NULL,                      -- sequential within session
  role            VARCHAR(20) NOT NULL,              -- user|assistant|system|tool
  content         LONGTEXT,                          -- the message text
  created_at      BIGINT,                            -- unix timestamp (if known)
  FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
  INDEX idx_session (session_id),
  INDEX idx_session_node (session_id, node_id),
  INDEX idx_role (role)
);

-- ─── PROMPTS ───────────────────────────────────────────────────────────────
-- What the user typed. Distinct from full messages (which include system/assistant).

CREATE TABLE prompts (
  id              BIGINT AUTO_INCREMENT PRIMARY KEY,
  session_id      BIGINT NOT NULL,
  content         TEXT NOT NULL,
  timestamp       BIGINT,
  FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
  INDEX idx_session (session_id),
  INDEX idx_timestamp (timestamp)
);
