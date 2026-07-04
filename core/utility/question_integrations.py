#!/usr/bin/env python3
#[@GHOST]{file_path="core/utility/question_integrations.py" date="2026-08-18" author="Devin" session_id="question-integrations" context="Integrates CuriosityController, ChatInterrogationEngine, CodeQuestionProofEngine, DatabaseQuestionEngine, DynamicQuestionGenerator, ArchitectureQuestion, UserQuestionTracker into the question system"}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self-_ no-print"}
#[@FILEID]{id="question_integrations.py" domain="utility" authority="QuestionIntegrations"}
#[@SUMMARY]{summary="Integration layer — adds schema-driven, chat-interrogation, code-proof, architecture, and user-question-tracking capabilities to the question system"}
#[@CLASS]{class="QuestionIntegrations" domain="utility" authority="single"}
#[@METHOD]{methods="Run,SchemaQuestions,ChatInterrogation,CodeProof,ArchitectureCheck,UserQuestionTrack,DynamicGenerate,FullInvestigate"}

"""
QuestionIntegrations — integrates 7 question patterns into the question system.

Patterns integrated from:
1. CuriosityController (Dom_Graph_EngineV2.py) — schema-driven question generation
2. ChatInterrogationEngine — interrogate chat history with questions
3. CodeQuestionProofEngine — prove code correctness with questions
4. DatabaseQuestionEngine — generate questions from DB schema
5. DynamicQuestionGenerator — generate questions based on context
6. ArchitectureQuestion — architecture-specific question patterns
7. View_user_questions.py — track user questions with style_mode

All results saved to QuestionStore.
"""

import os
import re
import json
import sqlite3
import subprocess
from datetime import datetime

from question_store import QuestionStore, ANSWER_YES, ANSWER_NO, ANSWER_UNKNOWN, ANSWER_ACTION

# ── CONSTANTS ──────────────────────────────────────────────────

SCHEMA_DB_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/code_store_variations/v20_hybrid_best.db"
AUTOCOMPLETE_DB = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Smart_system_seach/autocomplete.db"
MYSQL_USER = "root"

# Architecture question patterns (from ArchitectureQuestion class)
ARCHITECTURE_PATTERNS = {
    "separation": "Is there separation of concerns? (UI / logic / data / config)",
    "coupling": "Are modules loosely coupled? (can one change without breaking others)",
    "cohesion": "Is each module highly cohesive? (does one thing well)",
    "layering": "Are layers respected? (UI does not touch DB directly)",
    "dependency_direction": "Do dependencies point downward? (high-level does not import low-level)",
    "single_responsibility": "Does each class have one responsibility?",
    "open_closed": "Is the design open for extension, closed for modification?",
    "interface_stability": "Are interfaces stable? (changing interface does not break callers)",
    "error_boundary": "Are error boundaries clear? (where does try/except live)",
    "testability": "Is each module testable in isolation?",
    "config_driven": "Is behavior config-driven or hardcoded?",
    "dispatch_pattern": "Is there a Run() dispatch or direct method calls?",
    "state_management": "Is state managed via self.state dict or scattered self._ attributes?",
    "return_contract": "Do methods return Tuple3 or raw values?",
    "naming_consistency": "Are names consistent? (PascalCase classes, UPPERCASE constants)",
    "file_organization": "Is file organization clear? (one class per file, Config.py for constants)",
    "import_graph": "Is the import graph acyclic? (no circular imports)",
    "entry_point": "Is there a clear entry point? (main.py or if __name__ block)",
}

# Code proof patterns (from CodeQuestionProofEngine class)
CODE_PROOF_CHECKS = {
    "compile": "Does the file compile? (py_compile passes)",
    "print_statements": "Are there print() statements? (forbidden in VBStyle)",
    "decorators": "Are there @property/@staticmethod/@classmethod? (forbidden)",
    "self_underscore": "Are there self._ attributes? (use self.state dict)",
    "tabs": "Are there tab characters? (spaces only)",
    "trailing_whitespace": "Is there trailing whitespace? (forbidden)",
    "hardcoded_values": "Are there hardcoded values? (move to Config.py)",
    "run_dispatch": "Does the class have Run(self, command, params=None)?",
    "tuple3_return": "Do methods return Tuple3 (1, data, None) or (0, None, error)?",
    "ghost_header": "Does the file have #[@GHOST] header?",
    "vbstyle_header": "Does the file have #[@VBSTYLE] header?",
    "fileid_header": "Does the file have #[@FILEID] header?",
    "summary_header": "Does the file have #[@SUMMARY] header?",
    "class_header": "Does the file have #[@CLASS] header?",
    "method_header": "Does the file have #[@METHOD] header?",
    "pascal_case": "Are class names PascalCase? (no underscores)",
    "uppercase_constants": "Are constants UPPERCASE? (at class level)",
    "init_signature": "Is __init__(self, mem=None, db=None, param=None)?",
    "state_dict": "Is there self.state = {config, catalog, results}?",
    "p_helper": "Is there _p(self, params, key, default) helper?",
}

# Local file search directories (the gap that missed the dedupe_explorer answer)
LOCAL_SEARCH_DIRS = [
    "/Users/wws/Downloads",
    "/Users/wws/Qdrant_mysql_mlx_vector_engine/chat_mover",
    "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_DecisionTrees",
    "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph",
    "/Users/wws/Qdrant_mysql_mlx_vector_engine/core",
    "/Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack",
    "/Users/wws/contestsystem",
    "/Users/wws/Documents",
]
LOCAL_SEARCH_EXTENSIONS = [".md", ".py", ".txt", ".json", ".yaml", ".sql", ".sh"]
LOCAL_SEARCH_MAX_RESULTS = 50
LOCAL_SEARCH_CONTEXT_LINES = 5

# Creation markers — lines that indicate a file was created/edited in a chat
CREATION_MARKERS = [
    "Edited relevant file",
    "Created file",
    "created file",
    "I'll create",
    "Let me create",
    "Let me build",
    "I made",
    "I created",
    "writing the",
    "here's the code",
    "Here is the code",
    "Here's a version",
]

# Chat interrogation patterns (from ChatInterrogationEngine class)
CHAT_INTERROGATION_QUERIES = {
    "devin_messages": "SELECT session_id, role, LEFT(content, 500) as preview FROM devin_messages WHERE content LIKE '%{kw}%' ORDER BY created_at DESC LIMIT 10",
    "devin_transcripts": "SELECT id, session_id FROM devin_transcripts WHERE raw_json LIKE '%{kw}%' LIMIT 10",
    "know_questions": "SELECT id, LEFT(question, 300) FROM vb_shared.know_questions WHERE question LIKE '%{kw}%' LIMIT 10",
    "know_answers": "SELECT question_id, LEFT(answer, 300) FROM vb_shared.know_answers WHERE answer LIKE '%{kw}%' LIMIT 10",
    "learned_rules": "SELECT pattern, fix_action, confidence FROM vb_shared.learned_rules WHERE pattern LIKE '%{kw}%' ORDER BY confidence DESC LIMIT 10",
    "know_problems": "SELECT problem, description FROM vb_shared.know_problems WHERE problem LIKE '%{kw}%' LIMIT 10",
    "know_solutions": "SELECT solution, description FROM vb_shared.know_solutions WHERE solution LIKE '%{kw}%' LIMIT 10",
    "governance": "SELECT rule_name, rule_body FROM vb_shared.governance WHERE rule_body LIKE '%{kw}%' LIMIT 5",
    "vb_classes": "SELECT class_name, class_id FROM vb_code_test.vb_classes WHERE class_name LIKE '%{kw}%' LIMIT 10",
    "vb_methods": "SELECT method_name FROM vb_code_test.vb_methods WHERE method_name LIKE '%{kw}%' LIMIT 10",
    "codebase_python": "SELECT filename, full_path, line_count FROM CODEBASE.python_files WHERE filename LIKE '%{kw}%' LIMIT 10",
    "codebase_structure": "SELECT object_name, object_type FROM CODEBASE.python_structure WHERE object_name LIKE '%{kw}%' LIMIT 10",
}

# User question style modes (from View_user_questions.py)
STYLE_FRUSTRATED = "frustrated"
STYLE_CALM = "calm"
STYLE_NEUTRAL = "neutral"

# Frustration keywords for auto-detection
FRUSTRATION_KEYWORDS = ["why", "wtf", "stupid", "broken", "again", "still", "not working",
                        "keeps", "every time", "always", "never", "hate", "annoying",
                        "fix this", "help", "urgent", "now", "wrong"]
CALM_KEYWORDS = ["please", "thank", "could you", "would you", "might", "perhaps",
                 "consider", "suggest", "option", "alternative", "what if"]


class QuestionIntegrations:
    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "schema_db": SCHEMA_DB_PATH,
                "autocomplete_db": AUTOCOMPLETE_DB,
                "mysql_user": MYSQL_USER,
                "max_chat_results": 10,
                "max_schema_questions": 50
            },
            "results": None,
            "error": None,
            "store": None,
            "problem_id": None
        }
        self.store = QuestionStore()

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def _now(self):
        return datetime.now().isoformat()

    def _run_cmd(self, cmd, timeout=10):
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            return r.stdout
        except Exception:
            return ""

    def _mysql(self, db, query):
        return self._run_cmd(f"mysql -u {MYSQL_USER} {db} -e \"{query}\" 2>/dev/null", timeout=15)

    def Run(self, command, params=None):
        if command == "schema_questions":
            return self.SchemaQuestions(params)
        elif command == "chat_interrogation":
            return self.ChatInterrogation(params)
        elif command == "local_file_search":
            return self.LocalFileSearch(params)
        elif command == "find_creation":
            return self.FindCreation(params)
        elif command == "magnetic_radius":
            return self.MagneticRadius(params)
        elif command == "code_questions":
            return self.CodeQuestions(params)
        elif command == "codebase_index":
            return self.CodebaseIndex(params)
        elif command == "codebase_search":
            return self.CodebaseSearch(params)
        elif command == "code_proof":
            return self.CodeProof(params)
        elif command == "architecture_check":
            return self.ArchitectureCheck(params)
        elif command == "user_question_track":
            return self.UserQuestionTrack(params)
        elif command == "dynamic_generate":
            return self.DynamicGenerate(params)
        elif command == "full_investigate":
            return self.FullInvestigate(params)
        else:
            return (0, None, (1, f"unknown_command:{command}", 0))

    # ════════════════════════════════════════════════════════════════
    # 1. SCHEMA QUESTIONS — from CuriosityController / DatabaseQuestionEngine
    # Reads a DB schema and generates questions about what it finds
    # ════════════════════════════════════════════════════════════════

    def SchemaQuestions(self, params):
        """Generate questions from a SQLite database schema.
        Pattern: CuriosityController.discover_schema() + generate_questions()"""
        db_path = self._p(params, "db_path", self.state["config"]["schema_db"])
        problem_id = self._p(params, "problem_id")
        if not os.path.exists(db_path):
            return (0, None, (2, f"db not found: {db_path}", 0))
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        # Discover schema
        c.execute("""SELECT name FROM sqlite_master WHERE type='table'
                     AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%_fts%'
                     AND name NOT LIKE 'search_idx%' ORDER BY name""")
        tables = [r[0] for r in c.fetchall()]
        questions_generated = 0
        for table_name in tables:
            # Get columns
            c.execute(f"PRAGMA table_info({table_name})")
            columns = [{"name": col[1], "type": col[2], "not_null": col[3], "is_pk": col[5] == 1}
                       for col in c.fetchall()]
            col_names = [col["name"] for col in columns]
            # Get row count
            c.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = c.fetchone()[0]
            # Generate questions based on what we found
            # Empty table question
            if count == 0 and not table_name.startswith("_"):
                self._save_q(problem_id, "database_state.empty_table",
                             f"Schema: Table '{table_name}' has 0 rows — is it supposed to be empty?")
                questions_generated += 1
            # Hierarchy question
            if "parent_id" in col_names:
                self._save_q(problem_id, "database_state.hierarchy",
                             f"Schema: Table '{table_name}' has parent_id — is the hierarchy chain complete?")
                questions_generated += 1
            # BCL identity question
            if "bcl_token" in col_names:
                self._save_q(problem_id, "database_state.bcl_identity",
                             f"Schema: Do all BCL tokens in '{table_name}' have required fields?")
                questions_generated += 1
            # Closure question
            if "closure_pct" in col_names:
                self._save_q(problem_id, "database_state.closure",
                             f"Schema: Are all entities in '{table_name}' fully closed (100%)?")
                questions_generated += 1
            # Domain question
            if "domain" in col_names:
                self._save_q(problem_id, "database_state.domain",
                             f"Schema: Are all domains in '{table_name}' used in orchestration?")
                questions_generated += 1
            # Method pairs question
            if "method_name" in col_names:
                self._save_q(problem_id, "database_state.method_pairs",
                             f"Schema: Are there method pairs missing their opposite in '{table_name}'?")
                questions_generated += 1
            # NULL data quality
            for col in columns:
                if col["not_null"] == 0 and not col["is_pk"] and count > 10:
                    if col["name"] not in ("created_at", "updated_at", "description", "notes"):
                        self._save_q(problem_id, "database_state.data_quality",
                                     f"Schema: Column '{col['name']}' in '{table_name}' — how many NULLs?")
                        questions_generated += 1
            if questions_generated >= self.state["config"]["max_schema_questions"]:
                break
        conn.close()
        return (1, {
            "db_path": db_path,
            "tables_scanned": len(tables),
            "questions_generated": questions_generated
        }, None)

    # ════════════════════════════════════════════════════════════════
    # 2. CHAT INTERROGATION — from ChatInterrogationEngine
    # Searches all chat history sources for a keyword
    # ════════════════════════════════════════════════════════════════

    def ChatInterrogation(self, params):
        """Interrogate all chat history sources for a keyword.
        Pattern: ChatInterrogationEngine — search devin_messages, transcripts,
        know_questions, know_answers, learned_rules, governance, vb_classes, CODEBASE"""
        keyword = self._p(params, "keyword")
        problem_id = self._p(params, "problem_id")
        if not keyword:
            return (0, None, (2, "missing keyword", 0))
        results = {}
        total_found = 0
        for source, query_template in CHAT_INTERROGATION_QUERIES.items():
            db = "devin" if "devin" in source else "vb_shared" if "vb_" in source or "know" in source or "governance" in source or "learned" in source else "vb_code_test" if "vb_class" in source or "vb_method" in source else "CODEBASE"
            query = query_template.format(kw=keyword.replace("'", "\\'"))
            output = self._mysql(db, query)
            lines = [l for l in output.strip().split("\n") if l.strip()] if output.strip() else []
            count = max(0, len(lines) - 1)  # subtract header
            results[source] = {"count": count, "sample": lines[1][:200] if count > 0 and len(lines) > 1 else ""}
            total_found += count
            # Save question to store
            self._save_q(problem_id, f"chat_history.{source}",
                         f"ChatInterrogation: Is '{keyword}' mentioned in {source}?")
            # Save answer
            if count > 0:
                self._save_a(problem_id, f"chat_history.{source}",
                             ANSWER_YES, f"found {count} matches in {source}: {results[source]['sample'][:100]}",
                             "mysql_query")
            else:
                self._save_a(problem_id, f"chat_history.{source}",
                             ANSWER_NO, f"not found in {source}", "mysql_query")
        return (1, {
            "keyword": keyword,
            "sources_checked": len(results),
            "total_matches": total_found,
            "results": results
        }, None)

    # ════════════════════════════════════════════════════════════════
    # 2b. LOCAL FILE SEARCH — the gap that missed the answer
    # Searches Downloads/, chat_mover/, and project dirs for a keyword
    # This is what actually solved the dedupe_explorer mystery
    # ════════════════════════════════════════════════════════════════

    def LocalFileSearch(self, params):
        """Search local files for a keyword across all configured directories.
        This fills the gap that ChatInterrogation missed — it only searched
        MySQL, but the answer was in /Users/wws/Downloads/*.md files."""
        keyword = self._p(params, "keyword")
        problem_id = self._p(params, "problem_id")
        dirs = self._p(params, "dirs", LOCAL_SEARCH_DIRS)
        extensions = self._p(params, "extensions", LOCAL_SEARCH_EXTENSIONS)
        max_results = self._p(params, "max_results", LOCAL_SEARCH_MAX_RESULTS)
        context_lines = self._p(params, "context_lines", LOCAL_SEARCH_CONTEXT_LINES)
        if not keyword:
            return (0, None, (2, "missing keyword", 0))
        results = []
        total_matches = 0
        for search_dir in dirs:
            if not os.path.isdir(search_dir):
                continue
            # Walk the directory tree
            for root, dirs_list, files in os.walk(search_dir):
                # Skip hidden dirs and common noise
                dirs_list[:] = [d for d in dirs_list if not d.startswith(".")
                               and d not in ("__pycache__", "node_modules", ".git",
                                            "Library", "Application Support")]
                for fname in files:
                    # Check extension
                    ext = os.path.splitext(fname)[1].lower()
                    if ext not in extensions:
                        continue
                    fpath = os.path.join(root, fname)
                    try:
                        # Skip large files (>5MB)
                        if os.path.getsize(fpath) > 5 * 1024 * 1024:
                            continue
                        with open(fpath, "r", errors="ignore") as fh:
                            lines = fh.readlines()
                        for i, line in enumerate(lines):
                            if keyword.lower() in line.lower():
                                total_matches += 1
                                # Get context
                                start = max(0, i - context_lines)
                                end = min(len(lines), i + context_lines + 1)
                                context = "".join(lines[start:end]).strip()
                                # Check for creation markers in context
                                is_creation = any(marker in context for marker in CREATION_MARKERS)
                                # Get file timestamp
                                try:
                                    mtime = os.path.getmtime(fpath)
                                    mtime_str = datetime.fromtimestamp(mtime).isoformat()
                                except Exception:
                                    mtime_str = ""
                                results.append({
                                    "file": fpath,
                                    "filename": fname,
                                    "line": i + 1,
                                    "match": line.strip()[:200],
                                    "context": context[:500],
                                    "is_creation": is_creation,
                                    "creation_markers": [m for m in CREATION_MARKERS if m in context],
                                    "file_mtime": mtime_str,
                                    "dir": search_dir
                                })
                                if len(results) >= max_results:
                                    break
                        if len(results) >= max_results:
                            break
                    except Exception:
                        continue
                if len(results) >= max_results:
                    break
            if len(results) >= max_results:
                break
        # Save questions and answers to store
        files_with_matches = {}
        creation_files = []
        for r in results:
            fpath = r["file"]
            if fpath not in files_with_matches:
                files_with_matches[fpath] = {"count": 0, "is_creation": False, "filename": r["filename"]}
            files_with_matches[fpath]["count"] += 1
            if r["is_creation"]:
                files_with_matches[fpath]["is_creation"] = True
                creation_files.append(r)
        # Save to question store
        if problem_id:
            for fpath, info in files_with_matches.items():
                qid = self._save_q(problem_id, "chat_history.local_file",
                                   f"LocalSearch: Does {info['filename']} mention '{keyword}'?")
                if qid:
                    self.store.Run("answer", {
                        "question_id": qid,
                        "answer": ANSWER_YES,
                        "evidence": f"{info['count']} matches in {fpath}",
                        "source": "local_file_search"
                    })
                if info["is_creation"]:
                    qid2 = self._save_q(problem_id, "causality.creation",
                                        f"LocalSearch: Was '{keyword}' CREATED in {info['filename']}?")
                    if qid2:
                        self.store.Run("answer", {
                            "question_id": qid2,
                            "answer": ANSWER_YES,
                            "evidence": "creation marker found near keyword match",
                            "source": "local_file_search"
                        })
        return (1, {
            "keyword": keyword,
            "dirs_searched": len(dirs),
            "files_with_matches": len(files_with_matches),
            "total_matches": total_matches,
            "creation_files": len(creation_files),
            "results": results[:20],
            "files_summary": [{"file": k, "count": v["count"], "is_creation": v["is_creation"]}
                              for k, v in files_with_matches.items()]
        }, None)

    # ════════════════════════════════════════════════════════════════
    # 2c. FIND CREATION — find which chat/file created a target file
    # Combines LocalFileSearch + creation marker detection + context extraction
    # ════════════════════════════════════════════════════════════════

    def FindCreation(self, params):
        """Find which chat file created a target file.
        Searches for the filename keyword, detects creation markers,
        and extracts the user prompt that triggered the creation.
        Also traces back to the ROOT PROBLEM that caused the file to be needed."""
        target_file = self._p(params, "target_file")
        problem_id = self._p(params, "problem_id")
        trace_root = self._p(params, "trace_root", True)
        if not target_file:
            return (0, None, (2, "missing target_file", 0))
        # Extract keyword from filename (without path and extension)
        keyword = os.path.splitext(os.path.basename(target_file))[0]
        # Run local file search
        ok, search_data, err = self.LocalFileSearch({
            "keyword": keyword,
            "problem_id": problem_id,
            "max_results": 200,
            "context_lines": 10
        })
        if not ok:
            return (0, search_data, err)
        # Find creation files — check ALL results, not just first 20
        creation_results = []
        all_results = search_data.get("results", [])
        for r in all_results:
            if r["is_creation"]:
                creation_results.append(self._extract_creation_context(r))
        # If we didn't find enough creation results in the truncated list,
        # re-search the creation files directly
        if len(creation_results) < 3:
            for fs in search_data.get("files_summary", []):
                if fs["is_creation"]:
                    fpath = fs["file"]
                    if not any(cr["file"] == fpath for cr in creation_results):
                        try:
                            with open(fpath, "r", errors="ignore") as fh:
                                lines = fh.readlines()
                            for i, line in enumerate(lines):
                                if keyword.lower() in line.lower():
                                    start = max(0, i - 10)
                                    end = min(len(lines), i + 11)
                                    context = "".join(lines[start:end]).strip()
                                    if any(m in context for m in CREATION_MARKERS):
                                        r = {
                                            "file": fpath,
                                            "filename": os.path.basename(fpath),
                                            "line": i + 1,
                                            "match": line.strip()[:200],
                                            "context": context[:500],
                                            "is_creation": True,
                                            "creation_markers": [m for m in CREATION_MARKERS if m in context],
                                            "file_mtime": ""
                                        }
                                        try:
                                            r["file_mtime"] = datetime.fromtimestamp(
                                                os.path.getmtime(fpath)).isoformat()
                                        except Exception:
                                            pass
                                        creation_results.append(self._extract_creation_context(r))
                                        break
                        except Exception:
                            continue
        # Sort by: (1) has "Let me build/create" marker, (2) earliest line number
        def creation_score(r):
            has_build = any(m in r["creation_markers"] for m in ["Let me build", "Let me create", "I'll create", "I created", "I made"])
            return (0 if has_build else 1, r["line"])
        creation_results.sort(key=creation_score)
        # Trace root cause — find what problem started the investigation
        root_cause = None
        if trace_root and creation_results:
            best = creation_results[0]
            root_cause = self._trace_root_cause(best["file"], best["line"], problem_id)
        # Save the key findings to store
        if problem_id and creation_results:
            best = creation_results[0]
            qid = self._save_q(problem_id, "causality.root_cause",
                               f"FindCreation: Which file created '{keyword}'?")
            if qid:
                self.store.Run("answer", {
                    "question_id": qid,
                    "answer": ANSWER_YES,
                    "evidence": f"created in {best['filename']} at line {best['line']}, user prompt: {best['user_prompt'][:100]}",
                    "source": "find_creation"
                })
            if best["user_prompt"]:
                qid2 = self._save_q(problem_id, "causality.trigger",
                                    f"FindCreation: What user prompt triggered creation of '{keyword}'?")
                if qid2:
                    self.store.Run("answer", {
                        "question_id": qid2,
                        "answer": ANSWER_YES,
                        "evidence": best["user_prompt"][:200],
                        "source": "find_creation"
                    })
            if root_cause:
                qid3 = self._save_q(problem_id, "causality.original_problem",
                                    f"FindCreation: What ROOT PROBLEM caused '{keyword}' to be needed?")
                if qid3:
                    self.store.Run("answer", {
                        "question_id": qid3,
                        "answer": ANSWER_YES,
                        "evidence": f"root cause at line {root_cause['line']}: {root_cause['user_prompt'][:150]}",
                        "source": "trace_root_cause"
                    })
        return (1, {
            "target_file": target_file,
            "keyword": keyword,
            "files_with_matches": search_data["files_with_matches"],
            "total_matches": search_data["total_matches"],
            "creation_files_found": len(creation_results),
            "creation_results": creation_results,
            "best_guess": creation_results[0] if creation_results else None,
            "root_cause": root_cause
        }, None)

    def _trace_root_cause(self, chat_file, creation_line, problem_id=None):
        """Trace backwards from the creation line to find the ROOT PROBLEM
        that started the investigation. Reads all '### User Input' sections
        before the creation line and finds the one that states a PROBLEM
        that is causally related to the creation.

        Strategy: find the EARLIEST user input that:
        1. States a problem (not a request to create something)
        2. Is in the same topic chain as the creation (connected by topic shifts)
        3. Is close enough to be causally related (within ~500 lines)
        """
        try:
            with open(chat_file, "r", errors="ignore") as fh:
                lines = fh.readlines()
        except Exception:
            return None
        # Find all "### User Input" headers before the creation line
        user_inputs = []
        for i in range(creation_line - 1):
            text = lines[i].strip() if i < len(lines) else ""
            if text == "### User Input" or text.startswith("### User Input"):
                for j in range(i + 1, min(i + 20, creation_line)):
                    user_text = lines[j].strip() if j < len(lines) else ""
                    if user_text and not user_text.startswith("###") and not user_text.startswith("*"):
                        user_inputs.append({"line": j + 1, "text": user_text})
                        break
        if not user_inputs:
            return None
        # Problem vs request keywords
        problem_keywords = ["why", "what", "how", "error", "broken", "slow", "much",
                           "space", "big", "size", "problem", "wrong", "weird",
                           "happened", "cause", "issue", "bug", "fix", "inspect",
                           "check", "sure", "duplicate", "waste", "gb", "mb"]
        request_keywords = ["make", "create", "build", "do this", "can you",
                           "please", "add", "remove", "update", "change",
                           "cascade", "amube", "chatgpt", "mabe", "maybe"]
        # Score each user input
        scored = []
        for ui in user_inputs:
            text = ui["text"]
            text_lower = text.lower()
            # Skip lines that look like process output (tab-separated data, command output)
            is_data = ("\t" in text and text.count("\t") > 3) or text.startswith("Devin Helper") or text.startswith("#!/usr")
            if is_data:
                # Data lines are not user problems — skip them
                scored.append({
                    "line": ui["line"],
                    "user_prompt": text[:300],
                    "problem_score": 0,
                    "request_score": 0,
                    "net_score": -1,
                    "distance": creation_line - ui["line"],
                    "is_problem": False,
                    "is_request": False,
                    "is_data": True
                })
                continue
            problem_score = sum(1 for kw in problem_keywords if kw in text_lower)
            request_score = sum(1 for kw in request_keywords if kw in text_lower)
            net_score = problem_score - request_score
            distance = creation_line - ui["line"]
            scored.append({
                "line": ui["line"],
                "user_prompt": text[:300],
                "problem_score": problem_score,
                "request_score": request_score,
                "net_score": net_score,
                "distance": distance,
                "is_problem": net_score > 0,
                "is_request": request_score > problem_score,
                "is_data": False
            })
        # Find the root cause:
        # The root cause is the user input that STARTED the topic chain
        # leading to the creation. We look for the earliest problem input
        # that is within a reasonable distance (500 lines) of the creation.
        # Topic shifts (large gaps between user inputs) indicate new topics.
        # We want the problem input at the START of the final topic chain.
        # Find the root cause — the problem that STARTED the investigation
        # Strategy: find the problem input that has the highest "causal relevance"
        # to the creation. We do this by:
        # 1. Finding all problem inputs
        # 2. Scoring each by: (a) problem_score, (b) proximity to creation,
        #    (c) whether it starts a new sub-topic (gap from previous input)
        # 3. The root cause is the earliest problem that has high relevance
        #    AND is followed by a chain of related inputs leading to creation
        problem_inputs = [s for s in scored if s["is_problem"] and not s.get("is_data")]
        if not problem_inputs:
            # No problem inputs — use the first input
            root = scored[0] if scored else None
        else:
            # Score each problem by causal relevance
            # Higher score = more likely to be the root cause
            for p in problem_inputs:
                # Proximity: closer to creation = slightly higher
                # But NOT too close — the root cause is usually EARLIER, not later
                # So we penalize inputs that are too close (< 100 lines from creation)
                proximity = max(0, 100 - abs(p["distance"] - 300) / 10)
                # Topic starter: if there's a gap > 50 lines before this input,
                # it likely starts a new topic — this is the KEY signal
                prev_input = None
                for s in scored:
                    if s["line"] < p["line"]:
                        prev_input = s
                    else:
                        break
                topic_starter = 0
                if prev_input:
                    gap = p["line"] - prev_input["line"]
                    if gap > 50:
                        topic_starter = 10  # big gap = new topic = likely root
                # Problem strength
                problem_strength = p["problem_score"] * 2
                # Total causal relevance
                p["causal_score"] = problem_strength + topic_starter + proximity / 10
            # The root cause is the problem with the highest causal score
            root = max(problem_inputs, key=lambda x: x["causal_score"])
        # Build the causal chain — from root to creation
        chain = []
        root_line = root["line"] if root else 0
        for s in scored:
            if s["line"] >= root_line:
                chain.append({
                    "step": len(chain) + 1,
                    "line": s["line"],
                    "user_prompt": s["user_prompt"][:200],
                    "type": "problem" if s["is_problem"] else "request",
                    "distance_from_creation": s["distance"]
                })
        return {
            "chat_file": chat_file,
            "creation_line": creation_line,
            "root_line": root["line"] if root else 0,
            "root_prompt": root["user_prompt"] if root else "",
            "root_type": "problem" if root and root["is_problem"] else "request",
            "total_user_inputs_before_creation": len(user_inputs),
            "causal_chain": chain
        }

    # ════════════════════════════════════════════════════════════════
    # 2d. MAGNETIC RADIUS — pull in FULL chat content around key points
    # Like a magnetic field: each key point (root cause, creation, each
    # user input) attracts ALL surrounding context within a radius.
    # Returns the FULL conversation, not truncated snippets.
    # ════════════════════════════════════════════════════════════════

    def MagneticRadius(self, params):
        """Pull in full chat content around key points like a magnetic field.
        For each key point (root cause, creation, user inputs), extract
        ALL lines within a radius — the full user message + full Cascade
        response + any commands run.

        radius: number of lines to pull in around each key point (default 50)
        include_commands: include *User accepted command* lines (default True)
        include_planner: include ### Planner Response sections (default True)
        include_code: include code blocks (default True)
        """
        target_file = self._p(params, "target_file")
        chat_file = self._p(params, "chat_file")
        radius = self._p(params, "radius", 50)
        include_commands = self._p(params, "include_commands", True)
        include_planner = self._p(params, "include_planner", True)
        include_code = self._p(params, "include_code", True)
        problem_id = self._p(params, "problem_id")
        if not chat_file and not target_file:
            return (0, None, (2, "missing chat_file or target_file", 0))
        # Extract keyword from target_file (if given)
        keyword = None
        if target_file:
            keyword = os.path.splitext(os.path.basename(target_file))[0]
        # If target_file given but no chat_file, find the chat file first
        if not chat_file and keyword:
            ok, search_data, err = self.LocalFileSearch({
                "keyword": keyword,
                "max_results": 50,
                "context_lines": 5
            })
            if not ok:
                return (0, search_data, err)
            # Find the best creation file
            for r in search_data.get("results", []):
                if r["is_creation"]:
                    chat_file = r["file"]
                    break
            if not chat_file:
                # Use the first file with matches
                for fs in search_data.get("files_summary", []):
                    chat_file = fs["file"]
                    break
            if not chat_file:
                return (0, None, (3, "no chat file found for keyword", 0))
        if not os.path.exists(chat_file):
            return (0, None, (3, f"file not found: {chat_file}", 0))
        # Read the full chat file
        try:
            with open(chat_file, "r", errors="ignore") as fh:
                all_lines = fh.readlines()
        except Exception as e:
            return (0, None, (3, f"read error: {e}", 0))
        total_lines = len(all_lines)
        # Find the creation line (if keyword given)
        creation_line = None
        if keyword:
            for i, line in enumerate(all_lines):
                if keyword.lower() in line.lower():
                    context_start = max(0, i - 10)
                    context_end = min(total_lines, i + 11)
                    context = "".join(all_lines[context_start:context_end])
                    if any(m in context for m in CREATION_MARKERS):
                        creation_line = i + 1
                        break
        # Find all ### User Input and ### Planner Response sections
        sections = []
        current_section = None
        for i, line in enumerate(all_lines):
            stripped = line.strip()
            if stripped == "### User Input" or stripped.startswith("### User Input"):
                if current_section:
                    sections.append(current_section)
                current_section = {
                    "type": "user_input",
                    "header_line": i + 1,
                    "header_text": stripped,
                    "content_start": i + 1,
                    "content": [],
                    "content_lines": []
                }
            elif stripped == "### Planner Response" or stripped.startswith("### Planner Response"):
                if current_section:
                    sections.append(current_section)
                current_section = {
                    "type": "planner_response",
                    "header_line": i + 1,
                    "header_text": stripped,
                    "content_start": i + 1,
                    "content": [],
                    "content_lines": []
                }
            elif stripped.startswith("### ") and current_section:
                # New section header — save current and stop
                sections.append(current_section)
                current_section = None
            elif current_section:
                current_section["content"].append(line.rstrip("\n"))
                current_section["content_lines"].append(i + 1)
        if current_section:
            sections.append(current_section)
        # Now build the magnetic radius view
        # Key points: creation line, root cause, each user input
        key_points = []
        # Add creation point
        if creation_line:
            key_points.append({
                "type": "creation",
                "line": creation_line,
                "label": f"CREATION of {keyword}" if keyword else "CREATION"
            })
        # Add all user input points
        for s in sections:
            if s["type"] == "user_input":
                content_text = "\n".join(s["content"]).strip()
                if not content_text:
                    continue
                key_points.append({
                    "type": "user_input",
                    "line": s["header_line"],
                    "label": content_text[:100],
                    "section": s
                })
        # Add all planner response points
        for s in sections:
            if s["type"] == "planner_response":
                content_text = "\n".join(s["content"]).strip()
                if not content_text:
                    continue
                # Check if this section contains the creation keyword
                is_creation_section = False
                if keyword and keyword.lower() in content_text.lower():
                    if any(m in content_text for m in CREATION_MARKERS):
                        is_creation_section = True
                key_points.append({
                    "type": "planner_response",
                    "line": s["header_line"],
                    "label": content_text[:100],
                    "section": s,
                    "is_creation_section": is_creation_section
                })
        # Sort key points by line number
        key_points.sort(key=lambda x: x["line"])
        # Build the magnetic radius output
        # For each key point, pull in all content within the radius
        # But merge overlapping radiuses into continuous blocks
        radius_blocks = []
        for kp in key_points:
            center = kp["line"]
            start = max(1, center - radius)
            end = min(total_lines, center + radius)
            # Check if this overlaps with the last block
            if radius_blocks and start <= radius_blocks[-1]["end"] + 1:
                # Merge
                radius_blocks[-1]["end"] = max(radius_blocks[-1]["end"], end)
                radius_blocks[-1]["key_points"].append(kp)
            else:
                radius_blocks.append({
                    "start": start,
                    "end": end,
                    "key_points": [kp]
                })
        # Extract full content for each block
        blocks_output = []
        for block in radius_blocks:
            block_lines = []
            for i in range(block["start"] - 1, block["end"]):
                if i < total_lines:
                    line_text = all_lines[i].rstrip("\n")
                    # Filter based on params
                    if not include_commands and line_text.startswith("*User accepted"):
                        continue
                    if not include_commands and line_text.startswith("*Checked command"):
                        continue
                    if not include_planner and line_text.strip() == "### Planner Response":
                        continue
                    # Skip code blocks if requested
                    if not include_code and line_text.startswith("```"):
                        continue
                    block_lines.append({
                        "line": i + 1,
                        "text": line_text
                    })
            blocks_output.append({
                "block_number": len(blocks_output) + 1,
                "start_line": block["start"],
                "end_line": block["end"],
                "line_count": block["end"] - block["start"] + 1,
                "key_points": [{
                    "type": kp["type"],
                    "line": kp["line"],
                    "label": kp["label"],
                    "is_creation_section": kp.get("is_creation_section", False)
                } for kp in block["key_points"]],
                "content": block_lines
            })
        # Find the root cause (if we have a creation line)
        root_cause = None
        if creation_line:
            root_cause = self._trace_root_cause(chat_file, creation_line, problem_id)
        # Build summary
        summary = {
            "chat_file": chat_file,
            "chat_filename": os.path.basename(chat_file),
            "total_lines": total_lines,
            "total_sections": len(sections),
            "total_user_inputs": sum(1 for s in sections if s["type"] == "user_input"),
            "total_planner_responses": sum(1 for s in sections if s["type"] == "planner_response"),
            "creation_line": creation_line,
            "creation_keyword": keyword,
            "radius": radius,
            "blocks_extracted": len(blocks_output),
            "total_lines_extracted": sum(b["line_count"] for b in blocks_output),
            "root_cause": root_cause,
            "blocks": blocks_output
        }
        # Save to question store
        if problem_id and creation_line:
            qid = self._save_q(problem_id, "causality.magnetic_radius",
                               f"MagneticRadius: Full context around creation of '{keyword}'?")
            if qid:
                self.store.Run("answer", {
                    "question_id": qid,
                    "answer": ANSWER_YES,
                    "evidence": f"extracted {len(blocks_output)} blocks, {sum(b['line_count'] for b in blocks_output)} lines from {chat_file}",
                    "source": "magnetic_radius"
                })
        return (1, summary, None)

    # ════════════════════════════════════════════════════════════════
    # 2e. CODE QUESTIONS — scan .py files and generate questions
    # Reads a Python file, extracts classes/methods/imports/variables,
    # and generates questions about what it finds:
    #   - What is this class? What does it do?
    #   - How is it made? (constructor, init pattern)
    #   - Where is it used? (cross-file search)
    #   - What does this method do?
    #   - What are the dependencies?
    #   - What is the return type?
    #   - What is this variable for?
    # ════════════════════════════════════════════════════════════════

    def CodeQuestions(self, params):
        """Scan a .py file and generate questions about what it finds.
        Extracts: classes, methods, imports, module-level variables,
        Run() dispatch commands, state dict keys, constants.
        For each, generates questions like:
          - What is X? How is it made? Where is it used?
        Also auto-answers some questions by searching the codebase."""
        file_path = self._p(params, "file_path")
        problem_id = self._p(params, "problem_id")
        search_uses = self._p(params, "search_uses", True)
        if not file_path:
            return (0, None, (2, "missing file_path", 0))
        if not os.path.exists(file_path):
            return (0, None, (3, f"file not found: {file_path}", 0))
        try:
            with open(file_path, "r", errors="ignore") as fh:
                source = fh.read()
            lines = source.split("\n")
        except Exception as e:
            return (0, None, (3, f"read error: {e}", 0))
        questions = []
        facts = []
        # ── 1. FILE-LEVEL QUESTIONS ──
        questions.append({
            "category": "file.purpose",
            "question": f"What is the purpose of {os.path.basename(file_path)}?",
            "line": 1,
            "type": "what"
        })
        questions.append({
            "category": "file.location",
            "question": f"Why is {os.path.basename(file_path)} located at {os.path.dirname(file_path)}?",
            "line": 1,
            "type": "why"
        })
        # Check for headers
        if "#[@GHOST]" in source:
            facts.append({"category": "file.ghost_header", "fact": "Has GHOST header", "line": 1})
        else:
            questions.append({"category": "file.ghost_header", "question": f"Does {os.path.basename(file_path)} have a GHOST header?", "line": 1, "type": "what"})
        if "#[@VBSTYLE]" in source:
            facts.append({"category": "file.vbstyle_header", "fact": "Has VBSTYLE header", "line": 1})
        if "#[@FILEID]" in source:
            facts.append({"category": "file.fileid_header", "fact": "Has FILEID header", "line": 1})
        # ── 2. IMPORT QUESTIONS ──
        imports = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                imports.append({"line": i + 1, "text": stripped})
        for imp in imports:
            module_name = imp["text"].split()[1] if imp["text"].startswith("import ") else imp["text"].split()[1]
            questions.append({
                "category": "import.what",
                "question": f"What does {module_name} provide?",
                "line": imp["line"],
                "type": "what",
                "evidence": imp["text"]
            })
            questions.append({
                "category": "import.why",
                "question": f"Why is {module_name} imported? What is it used for?",
                "line": imp["line"],
                "type": "why",
                "evidence": imp["text"]
            })
            questions.append({
                "category": "import.where",
                "question": f"Where else in the codebase is {module_name} used?",
                "line": imp["line"],
                "type": "where",
                "evidence": imp["text"]
            })
        # ── 3. CLASS QUESTIONS ──
        classes = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Match: class ClassName( or class ClassName:
            m = re.match(r'^class\s+([A-Za-z_][A-Za-z0-9_]*)\s*[\(:]', stripped)
            if m:
                class_name = m.group(1)
                classes.append({"name": class_name, "line": i + 1})
        for cls in classes:
            cn = cls["name"]
            questions.append({
                "category": "class.what",
                "question": f"What is {cn}? What does it do?",
                "line": cls["line"],
                "type": "what"
            })
            questions.append({
                "category": "class.how_made",
                "question": f"How is {cn} made? What is its constructor pattern?",
                "line": cls["line"],
                "type": "how"
            })
            questions.append({
                "category": "class.where_used",
                "question": f"Where is {cn} used in the codebase?",
                "line": cls["line"],
                "type": "where"
            })
            questions.append({
                "category": "class.domain",
                "question": f"What domain does {cn} own? What is its authority?",
                "line": cls["line"],
                "type": "what"
            })
            questions.append({
                "category": "class.dependencies",
                "question": f"What does {cn} depend on? What classes does it use?",
                "line": cls["line"],
                "type": "what"
            })
            questions.append({
                "category": "class.state",
                "question": f"What state does {cn} manage? What keys are in self.state?",
                "line": cls["line"],
                "type": "what"
            })
            # Auto-answer: search for uses in codebase
            if search_uses:
                uses = self._search_codebase_uses(cn, file_path)
                if uses:
                    facts.append({
                        "category": "class.where_used",
                        "fact": f"{cn} is used in {len(uses)} files: {', '.join(uses[:5])}",
                        "line": cls["line"]
                    })
        # ── 4. METHOD QUESTIONS ──
        methods = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Match: def methodName(self, ... or def methodName(...
            m = re.match(r'^def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(', stripped)
            if m:
                method_name = m.group(1)
                # Find which class this belongs to
                owning_class = None
                for cls in classes:
                    if cls["line"] < i + 1:
                        owning_class = cls["name"]
                methods.append({
                    "name": method_name,
                    "line": i + 1,
                    "class": owning_class,
                    "signature": stripped
                })
        for meth in methods:
            mn = meth["name"]
            cn = meth["class"] or "module"
            full_name = f"{cn}.{mn}" if meth["class"] else mn
            # Skip __dunder__ methods except __init__ and Run
            if mn.startswith("__") and mn not in ("__init__",):
                continue
            questions.append({
                "category": "method.what",
                "question": f"What does {full_name}() do?",
                "line": meth["line"],
                "type": "what",
                "evidence": meth["signature"]
            })
            questions.append({
                "category": "method.how",
                "question": f"How does {full_name}() work? What is its logic?",
                "line": meth["line"],
                "type": "how",
                "evidence": meth["signature"]
            })
            questions.append({
                "category": "method.returns",
                "question": f"What does {full_name}() return? What is the return type?",
                "line": meth["line"],
                "type": "what",
                "evidence": meth["signature"]
            })
            if mn == "Run":
                # Special questions for Run() dispatch
                questions.append({
                    "category": "method.dispatch",
                    "question": f"What commands does {cn}.Run() dispatch? What are the dispatch keys?",
                    "line": meth["line"],
                    "type": "what",
                    "evidence": meth["signature"]
                })
                # Auto-answer: extract dispatch keys from Run method
                dispatch_keys = self._extract_dispatch_keys(lines, meth["line"])
                if dispatch_keys:
                    facts.append({
                        "category": "method.dispatch",
                        "fact": f"{cn}.Run() dispatches: {', '.join(dispatch_keys)}",
                        "line": meth["line"]
                    })
            if mn == "__init__":
                questions.append({
                    "category": "method.init",
                    "question": f"What does {cn}.__init__() set up? What are the initial state keys?",
                    "line": meth["line"],
                    "type": "what",
                    "evidence": meth["signature"]
                })
            questions.append({
                "category": "method.where_called",
                "question": f"Where is {full_name}() called from?",
                "line": meth["line"],
                "type": "where",
                "evidence": meth["signature"]
            })
        # ── 5. STATE DICT QUESTIONS ──
        state_keys = self._extract_state_keys(source)
        for key in state_keys:
            questions.append({
                "category": "state.what",
                "question": f"What is self.state['{key}'] for? What does it store?",
                "line": 1,
                "type": "what"
            })
        # ── 6. CONSTANT QUESTIONS ──
        constants = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Match UPPERCASE constants at module level
            m = re.match(r'^([A-Z][A-Z0-9_]*)\s*=', stripped)
            if m and not stripped.startswith("#"):
                constants.append({"name": m.group(1), "line": i + 1})
        for const in constants:
            questions.append({
                "category": "constant.what",
                "question": f"What is {const['name']}? What value does it hold?",
                "line": const["line"],
                "type": "what"
            })
            questions.append({
                "category": "constant.why",
                "question": f"Why is {const['name']} a constant? Is it configurable?",
                "line": const["line"],
                "type": "why"
            })
        # ── 7. RUN() DISPATCH COMMAND QUESTIONS ──
        # Already handled above, but also generate questions about each command
        # ── 8. CROSS-FILE QUESTIONS ──
        # For each class, ask: does it have tests? does it have docs?
        for cls in classes:
            cn = cls["name"]
            questions.append({
                "category": "class.tests",
                "question": f"Does {cn} have tests? Where are they?",
                "line": cls["line"],
                "type": "where"
            })
            questions.append({
                "category": "class.docs",
                "question": f"Does {cn} have documentation? Where is it documented?",
                "line": cls["line"],
                "type": "where"
            })
            questions.append({
                "category": "class.origin",
                "question": f"When was {cn} created? What chat created it?",
                "line": cls["line"],
                "type": "when"
            })
        # ── 9. VARIABLE / TYPE QUESTIONS ──
        # Find type hints and ask about them
        type_hints = re.findall(r'(\w+)\s*:\s*([A-Za-z_][A-Za-z0-9_\[\]]*)', source)
        seen_hints = set()
        for var_name, type_name in type_hints:
            key = (var_name, type_name)
            if key in seen_hints:
                continue
            seen_hints.add(key)
            if type_name in ("str", "int", "float", "bool", "list", "dict", "tuple", "set", "Optional", "Any"):
                continue  # Skip built-in types
            questions.append({
                "category": "type.what",
                "question": f"What is {type_name}? Where is it defined?",
                "line": 1,
                "type": "what"
            })
        # ── Save to question store ──
        if problem_id:
            for q in questions:
                qid = self._save_q(problem_id, q["category"], q["question"])
                # Auto-answer facts
                for f in facts:
                    if f["category"] == q["category"]:
                        if qid:
                            self.store.Run("answer", {
                                "question_id": qid,
                                "answer": ANSWER_YES,
                                "evidence": f["fact"],
                                "source": "code_questions"
                            })
                        break
        # ── Summary ──
        summary = {
            "file_path": file_path,
            "filename": os.path.basename(file_path),
            "total_lines": len(lines),
            "classes_found": len(classes),
            "methods_found": len(methods),
            "imports_found": len(imports),
            "constants_found": len(constants),
            "state_keys_found": len(state_keys),
            "questions_generated": len(questions),
            "facts_auto_answered": len(facts),
            "classes": [{"name": c["name"], "line": c["line"]} for c in classes],
            "methods": [{"name": m["name"], "class": m["class"], "line": m["line"]} for m in methods],
            "imports": [{"line": i["line"], "text": i["text"]} for i in imports],
            "constants": [{"name": c["name"], "line": c["line"]} for c in constants],
            "state_keys": state_keys,
            "facts": facts,
            "questions": questions
        }
        return (1, summary, None)

    def _search_codebase_uses(self, keyword, exclude_file=None):
        """Search the codebase for files that use a keyword (class name, etc.)."""
        results = []
        search_dirs = [
            "/Users/wws/Qdrant_mysql_mlx_vector_engine/core",
            "/Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack",
            "/Users/wws/Qdrant_mysql_mlx_vector_engine/chat_mover",
        ]
        for search_dir in search_dirs:
            if not os.path.isdir(search_dir):
                continue
            for root, dirs_list, files in os.walk(search_dir):
                dirs_list[:] = [d for d in dirs_list if not d.startswith(".")
                               and d not in ("__pycache__", "node_modules", ".git")]
                for fname in files:
                    if not fname.endswith(".py"):
                        continue
                    fpath = os.path.join(root, fname)
                    if exclude_file and os.path.samefile(fpath, exclude_file):
                        continue
                    try:
                        with open(fpath, "r", errors="ignore") as fh:
                            content = fh.read()
                        if keyword in content:
                            results.append(fname)
                    except Exception:
                        continue
        return list(set(results))[:20]

    def _extract_dispatch_keys(self, lines, run_line):
        """Extract dispatch command keys from a Run() method."""
        keys = []
        in_run = False
        for i in range(run_line - 1, min(run_line + 100, len(lines))):
            line = lines[i].strip()
            if "def Run(" in line:
                in_run = True
                continue
            if not in_run:
                continue
            # Match: if command == "key" or elif command == "key"
            m = re.match(r'(?:elif|if)\s+command\s*==\s*["\']([^"\']+)["\']', line)
            if m:
                keys.append(m.group(1))
            # End of method
            if i > run_line + 1 and line.startswith("def ") and "Run(" not in line:
                break
        return keys

    def _extract_state_keys(self, source):
        """Extract self.state dict keys from source code."""
        keys = []
        # Match: self.state = {"key": ...} or self.state["key"]
        # Pattern 1: self.state = { "key1": ..., "key2": ... }
        m = re.search(r'self\.state\s*=\s*\{([^}]+)\}', source)
        if m:
            state_block = m.group(1)
            # Extract quoted keys
            key_matches = re.findall(r'["\']([^"\']+)["\']\s*:', state_block)
            keys.extend(key_matches)
        # Pattern 2: self.state["key"] = ...
        key_matches = re.findall(r'self\.state\[\s*["\']([^"\']+)["\']\s*\]', source)
        for k in key_matches:
            if k not in keys:
                keys.append(k)
        return list(set(keys))

    # ════════════════════════════════════════════════════════════════
    # 2f. CODEBASE INDEX — scan all .py and .md files, extract words,
    # phrases, class names, method names, docstrings, comments, markdown
    # headings. Build an inverted index (word → files/lines).
    # Then answer questions by searching the index.
    # ════════════════════════════════════════════════════════════════

    def CodebaseIndex(self, params):
        """Scan all .py and .md files in the codebase, extract words/phrases,
        build an inverted index, and save to SQLite.

        index_path: where to save the index DB (default: ~/.codebase_index.db)
        scan_dirs: list of dirs to scan (default: project dirs)
        rebuild: if True, rebuild from scratch (default: False)
        """
        index_path = self._p(params, "index_path",
                             os.path.expanduser("~/.codebase_index.db"))
        scan_dirs = self._p(params, "scan_dirs", [
            "/Users/wws/Qdrant_mysql_mlx_vector_engine/core",
            "/Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack",
            "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_DecisionTrees",
            "/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph",
            "/Users/wws/Qdrant_mysql_mlx_vector_engine/chat_mover",
            "/Users/wws/Qdrant_mysql_mlx_vector_engine/BookSystem",
        ])
        rebuild = self._p(params, "rebuild", False)
        problem_id = self._p(params, "problem_id")
        # Build or open index
        if rebuild and os.path.exists(index_path):
            os.remove(index_path)
        idx_conn = sqlite3.connect(index_path)
        idx_conn.execute("""CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filepath TEXT UNIQUE,
            filename TEXT,
            ext TEXT,
            line_count INTEGER,
            file_size INTEGER,
            scanned_at TEXT
        )""")
        idx_conn.execute("""CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL,
            file_id INTEGER NOT NULL,
            line_num INTEGER NOT NULL,
            context TEXT,
            word_type TEXT,
            FOREIGN KEY (file_id) REFERENCES files(id)
        )""")
        idx_conn.execute("""CREATE TABLE IF NOT EXISTS phrases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phrase TEXT NOT NULL,
            file_id INTEGER NOT NULL,
            line_num INTEGER NOT NULL,
            phrase_type TEXT,
            FOREIGN KEY (file_id) REFERENCES files(id)
        )""")
        idx_conn.execute("""CREATE INDEX IF NOT EXISTS idx_words_word ON words(word)""")
        idx_conn.execute("""CREATE INDEX IF NOT EXISTS idx_words_file ON words(file_id)""")
        idx_conn.execute("""CREATE INDEX IF NOT EXISTS idx_phrases_phrase ON phrases(phrase)""")
        idx_conn.execute("""CREATE INDEX IF NOT EXISTS idx_phrases_file ON phrases(file_id)""")
        # Check if already indexed
        file_count = idx_conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        if file_count > 0 and not rebuild:
            # Already indexed — just return stats
            word_count = idx_conn.execute("SELECT COUNT(*) FROM words").fetchone()[0]
            phrase_count = idx_conn.execute("SELECT COUNT(*) FROM phrases").fetchone()[0]
            unique_words = idx_conn.execute("SELECT COUNT(DISTINCT word) FROM words").fetchone()[0]
            unique_phrases = idx_conn.execute("SELECT COUNT(DISTINCT phrase) FROM phrases").fetchone()[0]
            idx_conn.close()
            return (1, {
                "status": "already_indexed",
                "index_path": index_path,
                "files_indexed": file_count,
                "total_words": word_count,
                "unique_words": unique_words,
                "total_phrases": phrase_count,
                "unique_phrases": unique_phrases
            }, None)
        # Scan files
        stats = {"files": 0, "words": 0, "phrases": 0, "skipped": 0}
        # Stop words — don't index these
        STOP_WORDS = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "must", "can", "shall", "to", "of", "in",
            "on", "at", "by", "for", "with", "about", "against", "between",
            "into", "through", "during", "before", "after", "above", "below",
            "from", "up", "down", "out", "off", "over", "under", "again",
            "further", "then", "once", "here", "there", "when", "where", "why",
            "how", "all", "each", "few", "more", "most", "other", "some", "such",
            "no", "nor", "not", "only", "own", "same", "so", "than", "too",
            "very", "s", "t", "just", "don", "now", "self", "none", "true",
            "false", "and", "or", "if", "else", "elif", "while", "for", "try",
            "except", "finally", "return", "yield", "import", "from", "as",
            "pass", "break", "continue", "global", "nonlocal", "lambda", "with",
            "this", "that", "these", "those", "it", "its", "they", "them",
            "their", "we", "us", "our", "you", "your", "he", "she", "his", "her",
        }
        # What to extract from .py files:
        # 1. Class names (PascalCase)
        # 2. Method/function names (snake_case or camelCase)
        # 3. Constants (UPPER_CASE)
        # 4. String literals (docstrings, comments)
        # 5. Variable names
        # 6. Import module names
        # What to extract from .md files:
        # 1. Headings (#, ##, ###)
        # 2. Bold text (**text**)
        # 3. Code blocks (```...```)
        # 4. Regular text (split into words)
        for scan_dir in scan_dirs:
            if not os.path.isdir(scan_dir):
                continue
            for root, dirs_list, files in os.walk(scan_dir):
                dirs_list[:] = [d for d in dirs_list if not d.startswith(".")
                               and d not in ("__pycache__", "node_modules", ".git",
                                            "treasure_trove_backup", ".tasks", ".context")]
                for fname in files:
                    ext = os.path.splitext(fname)[1].lower()
                    if ext not in (".py", ".md", ".txt", ".sql", ".sh", ".c", ".h"):
                        continue
                    fpath = os.path.join(root, fname)
                    try:
                        fsize = os.path.getsize(fpath)
                        if fsize > 2 * 1024 * 1024:  # skip >2MB
                            stats["skipped"] += 1
                            continue
                        with open(fpath, "r", errors="ignore") as fh:
                            lines = fh.readlines()
                        # Insert file record
                        idx_conn.execute(
                            "INSERT OR IGNORE INTO files (filepath, filename, ext, line_count, file_size, scanned_at) VALUES (?, ?, ?, ?, ?, ?)",
                            (fpath, fname, ext, len(lines), fsize, datetime.now().isoformat())
                        )
                        file_row = idx_conn.execute(
                            "SELECT id FROM files WHERE filepath=?", (fpath,)
                        ).fetchone()
                        if not file_row:
                            continue
                        file_id = file_row[0]
                        stats["files"] += 1
                        # Extract based on file type
                        for i, line in enumerate(lines):
                            stripped = line.strip()
                            if not stripped:
                                continue
                            line_num = i + 1
                            if ext == ".py":
                                self._index_py_line(idx_conn, file_id, line_num, stripped, STOP_WORDS, stats)
                            elif ext == ".md":
                                self._index_md_line(idx_conn, file_id, line_num, stripped, STOP_WORDS, stats)
                            else:
                                # Generic: just extract words
                                self._index_words(idx_conn, file_id, line_num, stripped, STOP_WORDS, stats, "generic")
                    except Exception:
                        continue
        idx_conn.commit()
        # Final stats
        word_count = idx_conn.execute("SELECT COUNT(*) FROM words").fetchone()[0]
        phrase_count = idx_conn.execute("SELECT COUNT(*) FROM phrases").fetchone()[0]
        unique_words = idx_conn.execute("SELECT COUNT(DISTINCT word) FROM words").fetchone()[0]
        unique_phrases = idx_conn.execute("SELECT COUNT(DISTINCT phrase) FROM phrases").fetchone()[0]
        idx_conn.close()
        # Save to question store
        if problem_id:
            qid = self._save_q(problem_id, "codebase.index",
                               f"CodebaseIndex: How many files indexed?")
            if qid:
                self.store.Run("answer", {
                    "question_id": qid,
                    "answer": ANSWER_YES,
                    "evidence": f"indexed {stats['files']} files, {unique_words} unique words, {unique_phrases} unique phrases",
                    "source": "codebase_index"
                })
        return (1, {
            "status": "indexed",
            "index_path": index_path,
            "files_indexed": stats["files"],
            "files_skipped": stats["skipped"],
            "total_words": word_count,
            "unique_words": unique_words,
            "total_phrases": phrase_count,
            "unique_phrases": unique_phrases
        }, None)

    def _index_py_line(self, conn, file_id, line_num, line, stop_words, stats):
        """Extract words/phrases from a Python line."""
        # 1. Class definitions
        m = re.match(r'^class\s+([A-Za-z_][A-Za-z0-9_]*)', line)
        if m:
            name = m.group(1)
            conn.execute("INSERT INTO words (word, file_id, line_num, context, word_type) VALUES (?, ?, ?, ?, ?)",
                        (name, file_id, line_num, line[:200], "class_name"))
            conn.execute("INSERT INTO phrases (phrase, file_id, line_num, phrase_type) VALUES (?, ?, ?, ?)",
                        (f"class {name}", file_id, line_num, "class_def"))
            stats["words"] += 1
            stats["phrases"] += 1
        # 2. Method/function definitions
        m = re.match(r'^def\s+([A-Za-z_][A-Za-z0-9_]*)', line)
        if m:
            name = m.group(1)
            conn.execute("INSERT INTO words (word, file_id, line_num, context, word_type) VALUES (?, ?, ?, ?, ?)",
                        (name, file_id, line_num, line[:200], "method_name"))
            conn.execute("INSERT INTO phrases (phrase, file_id, line_num, phrase_type) VALUES (?, ?, ?, ?)",
                        (f"def {name}", file_id, line_num, "method_def"))
            stats["words"] += 1
            stats["phrases"] += 1
        # 3. Constants (UPPER_CASE)
        m = re.match(r'^([A-Z][A-Z0-9_]{2,})\s*=', line)
        if m:
            name = m.group(1)
            conn.execute("INSERT INTO words (word, file_id, line_num, context, word_type) VALUES (?, ?, ?, ?, ?)",
                        (name, file_id, line_num, line[:200], "constant"))
            stats["words"] += 1
        # 4. Comments and docstrings
        if line.startswith("#"):
            # Extract words from comment
            self._index_words(conn, file_id, line_num, line.lstrip("#"), stop_words, stats, "comment")
        elif '"""' in line or "'''" in line:
            self._index_words(conn, file_id, line_num, line, stop_words, stats, "docstring")
        # 5. String literals
        for str_match in re.finditer(r'["\']([^"\']{3,})["\']', line):
            text = str_match.group(1)
            if len(text) > 3:
                conn.execute("INSERT INTO phrases (phrase, file_id, line_num, phrase_type) VALUES (?, ?, ?, ?)",
                            (text, file_id, line_num, "string_literal"))
                stats["phrases"] += 1
        # 6. General words (variable names, etc.)
        self._index_words(conn, file_id, line_num, line, stop_words, stats, "code")

    def _index_md_line(self, conn, file_id, line_num, line, stop_words, stats):
        """Extract words/phrases from a Markdown line."""
        # 1. Headings
        m = re.match(r'^(#{1,6})\s+(.+)', line)
        if m:
            heading_text = m.group(2).strip()
            conn.execute("INSERT INTO phrases (phrase, file_id, line_num, phrase_type) VALUES (?, ?, ?, ?)",
                        (heading_text, file_id, line_num, "heading"))
            stats["phrases"] += 1
            self._index_words(conn, file_id, line_num, heading_text, stop_words, stats, "heading")
            return
        # 2. Bold text
        for bold_match in re.finditer(r'\*\*([^*]+)\*\*', line):
            text = bold_match.group(1)
            conn.execute("INSERT INTO phrases (phrase, file_id, line_num, phrase_type) VALUES (?, ?, ?, ?)",
                        (text, file_id, line_num, "bold"))
            stats["phrases"] += 1
        # 3. Code blocks — skip the ``` markers but index content
        if line.startswith("```"):
            return
        # 4. Regular text
        self._index_words(conn, file_id, line_num, line, stop_words, stats, "markdown")

    def _index_words(self, conn, file_id, line_num, text, stop_words, stats, word_type):
        """Extract individual words from text and store in index."""
        # Split on non-alphanumeric (keep underscores for code identifiers)
        words = re.findall(r'[A-Za-z_][A-Za-z0-9_]{2,}', text)
        seen = set()
        for word in words:
            wl = word.lower()
            if wl in stop_words or wl in seen:
                continue
            seen.add(word)
            # Determine word type
            wtype = word_type
            if word.isupper() and len(word) > 3:
                wtype = "constant"
            elif word[0].isupper() and any(c.islower() for c in word):
                wtype = "class_name"
            elif "_" in word and word.islower():
                wtype = "snake_case"
            elif word[0].islower() and any(c.isupper() for c in word):
                wtype = "camelCase"
            conn.execute("INSERT INTO words (word, file_id, line_num, context, word_type) VALUES (?, ?, ?, ?, ?)",
                        (word, file_id, line_num, text[:200], wtype))
            stats["words"] += 1

    def CodebaseSearch(self, params):
        """Search the codebase index for a keyword or phrase.
        Returns all files/lines where the word appears, with context.
        This is the 'Google for your codebase' — type a word, get answers."""
        keyword = self._p(params, "keyword")
        index_path = self._p(params, "index_path",
                             os.path.expanduser("~/.codebase_index.db"))
        search_type = self._p(params, "search_type", "word")  # word, phrase, fuzzy
        limit = self._p(params, "limit", 50)
        problem_id = self._p(params, "problem_id")
        if not keyword:
            return (0, None, (2, "missing keyword", 0))
        if not os.path.exists(index_path):
            return (0, None, (3, "index not found — run codebase_index first", 0))
        conn = sqlite3.connect(index_path)
        results = []
        if search_type == "phrase":
            # Search phrases
            rows = conn.execute(
                """SELECT p.phrase, p.line_num, p.phrase_type, f.filepath, f.filename
                   FROM phrases p JOIN files f ON p.file_id = f.id
                   WHERE p.phrase LIKE ? ORDER BY f.filename, p.line_num LIMIT ?""",
                (f"%{keyword}%", limit)
            ).fetchall()
            for row in rows:
                results.append({
                    "phrase": row[0],
                    "line": row[1],
                    "type": row[2],
                    "file": row[3],
                    "filename": row[4]
                })
        elif search_type == "fuzzy":
            # Fuzzy: search words that contain the keyword as substring
            rows = conn.execute(
                """SELECT DISTINCT w.word, w.word_type, COUNT(*) as cnt
                   FROM words w WHERE w.word LIKE ? 
                   GROUP BY w.word, w.word_type ORDER BY cnt DESC LIMIT ?""",
                (f"%{keyword}%", limit)
            ).fetchall()
            for row in rows:
                results.append({
                    "word": row[0],
                    "type": row[1],
                    "occurrences": row[2]
                })
        else:
            # Exact word search
            rows = conn.execute(
                """SELECT w.word, w.line_num, w.context, w.word_type, f.filepath, f.filename
                   FROM words w JOIN files f ON w.file_id = f.id
                   WHERE w.word = ? OR w.word LIKE ?
                   ORDER BY f.filename, w.line_num LIMIT ?""",
                (keyword, f"{keyword}%", limit)
            ).fetchall()
            for row in rows:
                results.append({
                    "word": row[0],
                    "line": row[1],
                    "context": row[2],
                    "type": row[3],
                    "file": row[4],
                    "filename": row[5]
                })
        # Also search phrases
        phrase_rows = conn.execute(
            """SELECT p.phrase, p.line_num, p.phrase_type, f.filepath, f.filename
               FROM phrases p JOIN files f ON p.file_id = f.id
               WHERE p.phrase LIKE ? LIMIT ?""",
            (f"%{keyword}%", limit)
        ).fetchall()
        phrase_results = []
        for row in phrase_rows:
            phrase_results.append({
                "phrase": row[0],
                "line": row[1],
                "type": row[2],
                "file": row[3],
                "filename": row[4]
            })
        # Get stats
        total_files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        total_words = conn.execute("SELECT COUNT(*) FROM words").fetchone()[0]
        conn.close()
        # Save to question store
        if problem_id and results:
            qid = self._save_q(problem_id, "codebase.search",
                               f"CodebaseSearch: Where does '{keyword}' appear?")
            if qid:
                self.store.Run("answer", {
                    "question_id": qid,
                    "answer": ANSWER_YES,
                    "evidence": f"found in {len(set(r.get('filename','') for r in results))} files, {len(results)} occurrences",
                    "source": "codebase_search"
                })
        return (1, {
            "keyword": keyword,
            "search_type": search_type,
            "word_results": len(results),
            "phrase_results": len(phrase_results),
            "total_files_indexed": total_files,
            "total_words_indexed": total_words,
            "results": results,
            "phrase_results_data": phrase_results
        }, None)

    # ════════════════════════════════════════════════════════════════
    # 3. CODE PROOF — from CodeQuestionProofEngine
    # Verifies code correctness with VBStyle checks
    # ════════════════════════════════════════════════════════════════

    def CodeProof(self, params):
        """Run VBStyle proof checks on a file.
        Pattern: CodeQuestionProofEngine — verify code against VBStyle rules"""
        file_path = self._p(params, "file_path")
        problem_id = self._p(params, "problem_id")
        if not file_path or not os.path.exists(file_path):
            return (0, None, (2, f"file not found: {file_path}", 0))
        with open(file_path, "r") as f:
            content = f.read()
        results = {}
        for check_name, question in CODE_PROOF_CHECKS.items():
            ans = ANSWER_UNKNOWN
            evidence = ""
            # Run the actual check
            if check_name == "compile":
                r = self._run_cmd(f"python3 -m py_compile '{file_path}' 2>&1", timeout=10)
                ans = ANSWER_YES if r.strip() == "" else ANSWER_NO
                evidence = "compiles clean" if ans == ANSWER_YES else f"compile error: {r.strip()[:100]}"
            elif check_name == "print_statements":
                count = len(re.findall(r"\bprint\s*\(", content))
                ans = ANSWER_NO if count > 0 else ANSWER_YES
                evidence = f"{count} print() statements found" if count > 0 else "no print statements"
            elif check_name == "decorators":
                count = len(re.findall(r"@(property|staticmethod|classmethod)", content))
                ans = ANSWER_NO if count > 0 else ANSWER_YES
                evidence = f"{count} forbidden decorators" if count > 0 else "no forbidden decorators"
            elif check_name == "self_underscore":
                count = len(re.findall(r"self\._[a-z]", content))
                ans = ANSWER_NO if count > 0 else ANSWER_YES
                evidence = f"{count} self._ attributes" if count > 0 else "no self._ attributes"
            elif check_name == "tabs":
                count = content.count("\t")
                ans = ANSWER_NO if count > 0 else ANSWER_YES
                evidence = f"{count} tab characters" if count > 0 else "no tabs"
            elif check_name == "trailing_whitespace":
                lines = content.split("\n")
                count = sum(1 for l in lines if l != l.rstrip())
                ans = ANSWER_NO if count > 0 else ANSWER_YES
                evidence = f"{count} lines with trailing whitespace" if count > 0 else "no trailing whitespace"
            elif check_name == "hardcoded_values":
                # Check for hardcoded DB paths, URLs, IPs
                hpaths = re.findall(r'["\']/(Users|tmp|var|opt|home)/[^"\']+["\']', content)
                ans = ANSWER_NO if len(hpaths) > 2 else ANSWER_YES
                evidence = f"{len(hpaths)} hardcoded paths" if hpaths else "no obvious hardcoded paths"
            elif check_name == "run_dispatch":
                has_run = bool(re.search(r"def\s+Run\s*\(\s*self\s*,\s*command", content))
                ans = ANSWER_YES if has_run else ANSWER_NO
                evidence = "Run() dispatch found" if has_run else "no Run() dispatch"
            elif check_name == "tuple3_return":
                has_tuple = bool(re.search(r"return\s*\(\s*[01]\s*,", content))
                ans = ANSWER_YES if has_tuple else ANSWER_NO
                evidence = "Tuple3 returns found" if has_tuple else "no Tuple3 returns"
            elif check_name == "ghost_header":
                ans = ANSWER_YES if "[@GHOST]" in content[:500] else ANSWER_NO
                evidence = "has #[@GHOST]" if ans == ANSWER_YES else "missing #[@GHOST]"
            elif check_name == "vbstyle_header":
                ans = ANSWER_YES if "[@VBSTYLE]" in content[:500] else ANSWER_NO
                evidence = "has #[@VBSTYLE]" if ans == ANSWER_YES else "missing #[@VBSTYLE]"
            elif check_name == "fileid_header":
                ans = ANSWER_YES if "[@FILEID]" in content[:500] else ANSWER_NO
                evidence = "has #[@FILEID]" if ans == ANSWER_YES else "missing #[@FILEID]"
            elif check_name == "summary_header":
                ans = ANSWER_YES if "[@SUMMARY]" in content[:500] else ANSWER_NO
                evidence = "has #[@SUMMARY]" if ans == ANSWER_YES else "missing #[@SUMMARY]"
            elif check_name == "class_header":
                ans = ANSWER_YES if "[@CLASS]" in content[:500] else ANSWER_NO
                evidence = "has #[@CLASS]" if ans == ANSWER_YES else "missing #[@CLASS]"
            elif check_name == "method_header":
                ans = ANSWER_YES if "[@METHOD]" in content[:500] else ANSWER_NO
                evidence = "has #[@METHOD]" if ans == ANSWER_YES else "missing #[@METHOD]"
            elif check_name == "pascal_case":
                classes = re.findall(r"class\s+(\w+)", content)
                bad = [c for c in classes if "_" in c or c[0].islower()]
                ans = ANSWER_NO if bad else ANSWER_YES
                evidence = f"non-PascalCase: {bad}" if bad else "all PascalCase"
            elif check_name == "uppercase_constants":
                # Check for lowercase constants (ALL_CAPS at module level)
                consts = re.findall(r"^([A-Z][A-Z_0-9]+)\s*=", content, re.MULTILINE)
                ans = ANSWER_YES if consts else ANSWER_UNKNOWN
                evidence = f"found {len(consts)} UPPERCASE constants" if consts else "no constants found"
            elif check_name == "init_signature":
                has_init = bool(re.search(r"def\s+__init__\s*\(\s*self\s*,\s*mem\s*=\s*None\s*,\s*db\s*=\s*None\s*,\s*param\s*=\s*None", content))
                ans = ANSWER_YES if has_init else ANSWER_NO
                evidence = "correct __init__ signature" if has_init else "wrong __init__ signature"
            elif check_name == "state_dict":
                has_state = bool(re.search(r"self\.state\s*=\s*\{", content))
                ans = ANSWER_YES if has_state else ANSWER_NO
                evidence = "has self.state dict" if has_state else "no self.state dict"
            elif check_name == "p_helper":
                has_p = bool(re.search(r"def\s+_p\s*\(\s*self\s*,\s*params", content))
                ans = ANSWER_YES if has_p else ANSWER_NO
                evidence = "has _p() helper" if has_p else "no _p() helper"
            results[check_name] = {"answer": ans, "evidence": evidence, "question": question}
            # Save to store
            qid = self._save_q(problem_id, f"state.code_proof.{check_name}", question)
            if qid:
                self.store.Run("answer", {
                    "question_id": qid,
                    "answer": ans,
                    "evidence": evidence,
                    "source": "code_proof_check"
                })
        passed = sum(1 for r in results.values() if r["answer"] == ANSWER_YES)
        failed = sum(1 for r in results.values() if r["answer"] == ANSWER_NO)
        unknown = sum(1 for r in results.values() if r["answer"] == ANSWER_UNKNOWN)
        return (1, {
            "file_path": file_path,
            "checks_run": len(results),
            "passed": passed,
            "failed": failed,
            "unknown": unknown,
            "results": results
        }, None)

    # ════════════════════════════════════════════════════════════════
    # 4. ARCHITECTURE CHECK — from ArchitectureQuestion
    # Asks architecture-specific questions about a file or project
    # ════════════════════════════════════════════════════════════════

    def ArchitectureCheck(self, params):
        """Generate architecture questions for a file or project.
        Pattern: ArchitectureQuestion — separation, coupling, cohesion, layering"""
        file_path = self._p(params, "file_path")
        project_dir = self._p(params, "project_dir")
        problem_id = self._p(params, "problem_id")
        results = {}
        for pattern_name, question in ARCHITECTURE_PATTERNS.items():
            qid = self._save_q(problem_id, f"composition.architecture.{pattern_name}", question)
            results[pattern_name] = {"question": question, "question_id": qid}
        return (1, {
            "questions_generated": len(results),
            "patterns": list(results.keys()),
            "results": results
        }, None)

    # ════════════════════════════════════════════════════════════════
    # 5. USER QUESTION TRACKING — from View_user_questions.py
    # Tracks user questions with style_mode (frustrated/calm/neutral)
    # ════════════════════════════════════════════════════════════════

    def UserQuestionTrack(self, params):
        """Track a user question with auto-detected style mode.
        Pattern: View_user_questions.py — user_questions table with style_mode"""
        question = self._p(params, "question")
        source = self._p(params, "source", "chat")
        problem_id = self._p(params, "problem_id")
        if not question:
            return (0, None, (2, "missing question", 0))
        # Auto-detect style mode
        qlower = question.lower()
        style = STYLE_NEUTRAL
        if any(kw in qlower for kw in FRUSTRATION_KEYWORDS):
            style = STYLE_FRUSTRATED
        elif any(kw in qlower for kw in CALM_KEYWORDS):
            style = STYLE_CALM
        # Save to autocomplete.db (if it exists)
        db_path = self.state["config"]["autocomplete_db"]
        if os.path.exists(os.path.dirname(db_path)):
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute("""CREATE TABLE IF NOT EXISTS user_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                style_mode TEXT DEFAULT 'neutral',
                source TEXT,
                created_at TEXT
            )""")
            c.execute("INSERT INTO user_questions (question, style_mode, source, created_at) VALUES (?,?,?,?)",
                      (question, style, source, self._now()))
            conn.commit()
            conn.close()
        # Also save to question store
        qid = self._save_q(problem_id, "intent.user_question", f"User asked: {question}")
        if qid:
            self.store.Run("answer", {
                "question_id": qid,
                "answer": ANSWER_ACTION,
                "evidence": f"style_mode={style}, source={source}",
                "source": "user_input"
            })
        return (1, {
            "question": question,
            "style_mode": style,
            "source": source,
            "question_id": qid
        }, None)

    # ════════════════════════════════════════════════════════════════
    # 6. DYNAMIC GENERATE — from DynamicQuestionGenerator
    # Generates questions dynamically based on context
    # ════════════════════════════════════════════════════════════════

    def DynamicGenerate(self, params):
        """Dynamically generate questions based on context.
        Pattern: DynamicQuestionGenerator — context-aware question generation"""
        context = self._p(params, "context", "")
        target = self._p(params, "target", "")
        problem_id = self._p(params, "problem_id")
        questions = []
        # Generate based on context keywords
        ctx_lower = context.lower()
        if "refactor" in ctx_lower:
            questions.extend([
                ("composition.parts", f"Dynamic: What are the natural split points in {target}?"),
                ("relationship.depends_on", f"Dynamic: What does {target} depend on that would break if split?"),
                ("state.compliance", f"Dynamic: Does {target} comply with VBStyle after refactor?"),
                ("alternatives.split", f"Dynamic: What is the minimum viable split for {target}?"),
                ("risk.failure_mode", f"Dynamic: What breaks if {target} is split incorrectly?"),
            ])
        if "bug" in ctx_lower or "error" in ctx_lower or "fix" in ctx_lower:
            questions.extend([
                ("causality.root_cause", f"Dynamic: What is the root cause of the bug in {target}?"),
                ("state.broken", f"Dynamic: What exactly is broken in {target}?"),
                ("evidence.reproducibility", f"Dynamic: Can the bug in {target} be reproduced?"),
                ("risk.recoverability", f"Dynamic: Can the fix be reverted if it makes things worse?"),
            ])
        if "search" in ctx_lower or "find" in ctx_lower:
            questions.extend([
                ("existence.physical", f"Dynamic: Does {target} exist on disk?"),
                ("existence.digital", f"Dynamic: Does {target} exist in a database?"),
                ("location.current", f"Dynamic: Where is {target} located?"),
                ("time.creation", f"Dynamic: When was {target} created?"),
                ("authorship", f"Dynamic: Who created {target}?"),
            ])
        if "test" in ctx_lower:
            questions.extend([
                ("state.tested", f"Dynamic: Is {target} tested?"),
                ("evidence.verifiability", f"Dynamic: Can {target}'s behavior be verified?"),
                ("intent.success_criteria", f"Dynamic: What are the success criteria for {target}'s tests?"),
            ])
        if "database" in ctx_lower or "schema" in ctx_lower:
            questions.extend([
                ("existence.digital", f"Dynamic: Does {target} exist in the database?"),
                ("composition.structure", f"Dynamic: What is the schema structure for {target}?"),
                ("relationship.depends_on", f"Dynamic: What tables does {target} depend on?"),
            ])
        # If no specific context, generate generic questions
        if not questions:
            questions.extend([
                ("existence.physical", f"Dynamic: Does {target} exist?"),
                ("identity.name", f"Dynamic: What is {target} called?"),
                ("location.current", f"Dynamic: Where is {target}?"),
                ("time.creation", f"Dynamic: When was {target} created?"),
                ("state.current_state", f"Dynamic: What state is {target} in?"),
            ])
        # Save all generated questions
        saved = 0
        for cat, q in questions:
            qid = self._save_q(problem_id, cat, q)
            if qid:
                saved += 1
        return (1, {
            "context": context,
            "target": target,
            "questions_generated": len(questions),
            "questions_saved": saved,
            "questions": [q for _, q in questions]
        }, None)

    # ════════════════════════════════════════════════════════════════
    # 7. FULL INVESTIGATE — runs all integrations together
    # Combines: schema + chat + code proof + architecture + dynamic
    # ════════════════════════════════════════════════════════════════

    def FullInvestigate(self, params):
        """Run all question integrations in sequence.
        Combines schema questions, chat interrogation, code proof,
        architecture check, and dynamic generation."""
        problem_name = self._p(params, "problem")
        target_file = self._p(params, "target_file")
        keyword = self._p(params, "keyword")
        context = self._p(params, "context", "")
        db_path = self._p(params, "db_path")
        # Register problem
        ok, pdata, perr = self.store.Run("register_problem", {"name": problem_name})
        pid = pdata["problem_id"]
        self.state["problem_id"] = pid
        results = {}
        # 1. Dynamic generate (always)
        ok1, dyn_data, err1 = self.DynamicGenerate({
            "problem_id": pid,
            "context": context,
            "target": target_file or keyword or problem_name
        })
        results["dynamic"] = {"ok": ok1, "data": dyn_data, "error": err1}
        # 2. Chat interrogation (if keyword)
        if keyword:
            ok2, chat_data, err2 = self.ChatInterrogation({
                "problem_id": pid,
                "keyword": keyword
            })
            results["chat"] = {"ok": ok2, "data": chat_data, "error": err2}
        # 2b. Local file search (if keyword — the gap that missed the answer)
        if keyword:
            ok2b, local_data, err2b = self.LocalFileSearch({
                "keyword": keyword,
                "problem_id": pid
            })
            results["local_search"] = {"ok": ok2b, "data": local_data, "error": err2b}
        # 2c. Find creation (if target_file — auto-extract keyword from filename)
        if target_file:
            ok2c, creation_data, err2c = self.FindCreation({
                "target_file": target_file,
                "problem_id": pid
            })
            results["find_creation"] = {"ok": ok2c, "data": creation_data, "error": err2c}
        # 3. Code proof (if file exists)
        if target_file and os.path.exists(target_file):
            ok3, proof_data, err3 = self.CodeProof({
                "problem_id": pid,
                "file_path": target_file
            })
            results["code_proof"] = {"ok": ok3, "data": proof_data, "error": err3}
        # 4. Architecture check (if file or project)
            ok4, arch_data, err4 = self.ArchitectureCheck({
                "problem_id": pid,
                "file_path": target_file
            })
            results["architecture"] = {"ok": ok4, "data": arch_data, "error": err4}
        # 5. Schema questions (if db_path)
        if db_path and os.path.exists(db_path):
            ok5, schema_data, err5 = self.SchemaQuestions({
                "problem_id": pid,
                "db_path": db_path
            })
            results["schema"] = {"ok": ok5, "data": schema_data, "error": err5}
        # 6. Cognitive loop (constraint + solution + mistake)
        ok6, loop_data, err6 = self.store.Run("cognitive_loop", {"problem_id": pid})
        results["cognitive_loop"] = {"ok": ok6, "data": loop_data, "error": err6}
        # 7. Collapse check
        ok7, collapse_data, err7 = self.store.Run("collapse_check", {"problem_id": pid})
        results["collapse"] = {"ok": ok7, "data": collapse_data, "error": err7}
        # 8. Full report
        ok8, report_data, err8 = self.store.Run("full_report", {"problem_id": pid})
        results["report"] = {"ok": ok8, "data": report_data, "error": err8}
        return (1, {
            "problem_id": pid,
            "problem": problem_name,
            "integrations_run": list(results.keys()),
            "results": results,
            "collapse": collapse_data if ok7 else None,
            "report": report_data["report"] if ok8 and report_data else ""
        }, None)

    # ── HELPERS ───────────────────────────────────────────────────

    def _extract_creation_context(self, r):
        """Extract user prompt and context from a creation match result.
        The user prompt is BEFORE '### Planner Response' header.
        The Cascade response is AFTER it. We want the user prompt."""
        fpath = r["file"]
        line_num = r["line"]
        user_prompt = ""
        cascade_response = ""
        try:
            with open(fpath, "r", errors="ignore") as fh:
                lines = fh.readlines()
            # Search backwards for user prompt
            # First skip past the "### Planner Response" header —
            # the user prompt is BEFORE it, the Cascade response is AFTER it
            passed_planner_header = False
            for j in range(line_num - 1, max(0, line_num - 50), -1):
                text = lines[j].strip() if j < len(lines) else ""
                if not text:
                    continue
                # Detect "### Planner Response" or "### Response" header
                if text.startswith("###") and ("Response" in text or "Planner" in text or "Assistant" in text):
                    passed_planner_header = True
                    continue
                # Skip Cascade action markers (lines starting with *)
                if text.startswith("*"):
                    continue
                # Skip markdown headers
                if text.startswith("#") or text.startswith("```") or text.startswith("---"):
                    continue
                # Skip code blocks
                if text.startswith("    ") or text.startswith("\t"):
                    continue
                # Skip URLs and file paths
                if text.startswith("http") or text.startswith("/"):
                    continue
                # If we haven't passed the planner header yet, this is the Cascade response
                if not passed_planner_header:
                    if not cascade_response:
                        cascade_response = text
                    continue
                # We're now in the user's section (before ### Planner Response)
                # This is the user prompt
                user_prompt = text
                break
            # Fallback: if we didn't find a user prompt, use cascade_response
            if not user_prompt and cascade_response:
                user_prompt = f"[Cascade response]: {cascade_response[:150]}"
        except Exception:
            pass
        return {
            "file": fpath,
            "filename": r["filename"],
            "line": line_num,
            "match_line": r["match"][:200],
            "context": r["context"][:500],
            "creation_markers": r["creation_markers"],
            "user_prompt": user_prompt,
            "cascade_response": cascade_response[:200],
            "file_mtime": r.get("file_mtime", "")
        }

    def _save_q(self, problem_id, category, question):
        """Save a question to the store and return question_id."""
        if not problem_id:
            return None
        ok, data, err = self.store.Run("ask", {
            "problem_id": problem_id,
            "question": question,
            "category": category,
            "depth": 0
        })
        return data["question_id"] if data else None

    def _save_a(self, problem_id, category, answer, evidence, source):
        """Save an answer for the most recent question in a category."""
        if not problem_id:
            return
        # Find the question_id by category (most recent)
        ok, group_data, err = self.store.Run("group", {"problem_id": problem_id})
        if not ok or not group_data:
            return
        items = group_data["grouped"].get(category, [])
        if not items:
            return
        qid = items[-1]["question_id"]
        self.store.Run("answer", {
            "question_id": qid,
            "answer": answer,
            "evidence": evidence,
            "source": source
        })

    def close(self):
        self.store.close()


if __name__ == "__main__":
    import sys
    qi = QuestionIntegrations()
    if len(sys.argv) < 2:
        print("Usage: question_integrations.py <command> [json_params]")
        print("Commands: schema_questions, chat_interrogation, local_file_search,")
        print("          find_creation, magnetic_radius, code_questions,")
        print("          codebase_index, codebase_search, code_proof,")
        print("          architecture_check, user_question_track, dynamic_generate,")
        print("          full_investigate")
        sys.exit(1)
    cmd = sys.argv[1]
    params = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    ok, data, error = qi.Run(cmd, params)
    if ok:
        if isinstance(data, dict) and "report" in data:
            print(data["report"])
        else:
            print(json.dumps(data, indent=2, default=str))
    else:
        print(f"ERROR: {error}")
    qi.close()
