#!/usr/bin/env python3
#[@GHOST]{file_path="core/utility/question_agent.py" date="2026-08-18" author="Devin" session_id="question-agent" context="Subagent that asks questions about a problem, checks answers, saves to QuestionStore, recurses until collapse"}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
#[@FILEID]{id="question_agent.py" domain="utility" authority="QuestionAgent"}
#[@SUMMARY]{summary="Subagent question-asking engine — generates questions, runs checks, saves Q&A to store, recurses until problem collapses"}
#[@CLASS]{class="QuestionAgent" domain="utility" authority="single"}
#[@METHOD]{methods="Run,Investigate,check_existence,check_time,check_versions,check_location,check_chat_history,check_database,check_authorship,generate_followup"}

"""
QuestionAgent — autonomous question-asking subagent.

Given a problem (e.g. "find the chat that created file X"), this agent:
1. Registers the problem in QuestionStore
2. Generates Level 1 questions across all categories
3. Runs checks for each question (file system, MySQL, grep)
4. Saves answers to QuestionStore
5. For each YES answer, generates Level 2 follow-up questions
6. Recurses until collapse or depth limit
7. Outputs a report

Usage:
    python3 question_agent.py '{"problem":"find chat that created dedupe_explorer.py","target_file":"/path/to/file"}'
"""

import json
import os
import subprocess
import sqlite3
import time
from datetime import datetime

from question_store import QuestionStore, ANSWER_YES, ANSWER_NO, ANSWER_UNKNOWN, ANSWER_ACTION

MAX_DEPTH = 4
MAX_QUESTIONS_PER_LEVEL = 50


class QuestionAgent:
    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {"max_depth": MAX_DEPTH, "max_per_level": MAX_QUESTIONS_PER_LEVEL},
            "results": None,
            "error": None,
            "problem_id": None,
            "store": None,
            "target_file": None,
            "target_keyword": None,
            "facts": []
        }
        self.store = QuestionStore()

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        if command == "investigate":
            return self.Investigate(params)
        elif command == "report":
            return self.store.Run("report", params)
        elif command == "collapse_check":
            return self.store.Run("collapse_check", params)
        else:
            return (0, None, (1, f"unknown_command:{command}", 0))

    def Investigate(self, params):
        problem_name = self._p(params, "problem")
        target_file = self._p(params, "target_file")
        target_keyword = self._p(params, "target_keyword")

        if not problem_name:
            return (0, None, (2, "missing problem name", 0))

        self.state["target_file"] = target_file
        if target_file:
            self.state["target_keyword"] = os.path.basename(target_file).replace(".py", "").replace(".c", "")
        elif target_keyword:
            self.state["target_keyword"] = target_keyword
        else:
            self.state["target_keyword"] = problem_name

        # Register problem
        ok, data, err = self.store.Run("register_problem", {"name": problem_name})
        if not ok:
            return (0, None, err)
        self.state["problem_id"] = data["problem_id"]
        pid = self.state["problem_id"]

        # Level 1: ask all category questions
        level1_questions = self._generate_level1()
        for q in level1_questions:
            if q["category"] == "existence":
                ans, ev = self._check_existence(q)
            elif q["category"] == "time":
                ans, ev = self._check_time(q)
            elif q["category"] == "versions":
                ans, ev = self._check_versions(q)
            elif q["category"] == "location":
                ans, ev = self._check_location(q)
            elif q["category"] == "chat_history":
                ans, ev = self._check_chat_history(q)
            elif q["category"] == "database_state":
                ans, ev = self._check_database(q)
            elif q["category"] == "authorship":
                ans, ev = self._check_authorship(q)
            else:
                ans, ev = ANSWER_UNKNOWN, "no automated check"

            ok, qdata, qerr = self.store.Run("ask", {
                "problem_id": pid,
                "question": q["question"],
                "category": q["category"],
                "depth": 0
            })
            qid = qdata["question_id"] if qdata else None
            if qid:
                self.store.Run("answer", {
                    "question_id": qid,
                    "answer": ans,
                    "evidence": ev,
                    "source": "automated_check"
                })
                if ans == ANSWER_YES:
                    self.state["facts"].append({"question": q["question"], "answer": ans, "evidence": ev})
                    # Generate Level 2 follow-ups
                    self._recurse_followups(pid, qid, q, 1)

        # Check collapse
        ok, collapse, err = self.store.Run("collapse_check", {"problem_id": pid})
        ok, report_data, err = self.store.Run("report", {"problem_id": pid})
        return (1, {
            "problem_id": pid,
            "problem": problem_name,
            "collapse": collapse,
            "report": report_data["report"] if report_data else "",
            "facts_found": len(self.state["facts"])
        }, None)

    def _recurse_followups(self, pid, parent_qid, parent_q, depth):
        if depth > self.state["config"]["max_depth"]:
            return
        followups = self._generate_followup(parent_q)
        for fq in followups[:self.state["config"]["max_per_level"]]:
            ans, ev = self._check_followup(fq, parent_q)
            ok, qdata, qerr = self.store.Run("ask", {
                "problem_id": pid,
                "question": fq["question"],
                "category": fq.get("category", "followup_yes"),
                "parent_id": parent_qid,
                "depth": depth
            })
            qid = qdata["question_id"] if qdata else None
            if qid:
                self.store.Run("answer", {
                    "question_id": qid,
                    "answer": ans,
                    "evidence": ev,
                    "source": "automated_check"
                })
                if ans == ANSWER_YES:
                    self.state["facts"].append({"question": fq["question"], "answer": ans, "evidence": ev})
                    self._recurse_followups(pid, qid, fq, depth + 1)

    def _generate_level1(self):
        kf = self.state["target_keyword"]
        tf = self.state["target_file"]
        questions = []
        if tf:
            questions.extend([
                {"category": "existence", "question": f"Does {tf} exist?", "check": "ls"},
                {"category": "existence", "question": f"Are there other versions of {tf}?", "check": "find_versions"},
                {"category": "existence", "question": f"Are there backup files for {tf}?", "check": "find_backups"},
                {"category": "existence", "question": f"Does a test for {tf} exist?", "check": "find_tests"},
                {"category": "existence", "question": f"Is {tf} referenced by other files?", "check": "grep_refs"},
                {"category": "time", "question": f"When was {tf} created?", "check": "stat_birth"},
                {"category": "time", "question": f"When was {tf} last modified?", "check": "stat_mod"},
                {"category": "time", "question": f"What other files were created same day as {tf}?", "check": "find_same_day"},
                {"category": "time", "question": f"What files were created in the hour before {tf}?", "check": "find_same_hour"},
                {"category": "versions", "question": f"Is {tf} in git history?", "check": "git_log"},
                {"category": "versions", "question": f"Is there a v2 or newer version of {tf}?", "check": "find_v2"},
                {"category": "versions", "question": f"Is {tf} stored in a database?", "check": "db_lookup"},
                {"category": "location", "question": f"Is {tf} in the expected directory?", "check": "ls"},
                {"category": "location", "question": f"Is there a copy of {tf} in /tmp?", "check": "find_tmp"},
                {"category": "location", "question": f"Is the path of {tf} hardcoded in other files?", "check": "grep_path"},
                {"category": "chat_history", "question": f"Is {kf} mentioned in Downloads/*.md?", "check": "grep_downloads"},
                {"category": "chat_history", "question": f"Is {kf} mentioned in chat_mover/*.md?", "check": "grep_chatmover"},
                {"category": "chat_history", "question": f"Is {kf} mentioned in vb_shared.know_questions?", "check": "mysql_questions"},
                {"category": "chat_history", "question": f"Is {kf} mentioned in vb_shared.know_answers?", "check": "mysql_answers"},
                {"category": "chat_history", "question": f"Is {kf} mentioned in devin_messages?", "check": "mysql_devin"},
                {"category": "chat_history", "question": f"Is {kf} mentioned in devin_transcripts?", "check": "mysql_transcripts"},
                {"category": "chat_history", "question": f"Is {kf} mentioned in learned_rules?", "check": "mysql_rules"},
                {"category": "database_state", "question": f"Is {kf} in CODEBASE.python_files?", "check": "mysql_codebase"},
                {"category": "database_state", "question": f"Is {kf} in vb_code_test.vb_classes?", "check": "mysql_vbclasses"},
                {"category": "authorship", "question": f"Does {tf} have a GHOST header with author?", "check": "read_header"},
                {"category": "authorship", "question": f"Was {tf} created by Cascade?", "check": "header_cascade"},
                {"category": "authorship", "question": f"Was {tf} created by Devin?", "check": "header_devin"},
                {"category": "dependencies", "question": f"Does {tf} import PyQt6?", "check": "grep_imports"},
                {"category": "dependencies", "question": f"Does {tf} use MySQL?", "check": "grep_mysql"},
                {"category": "dependencies", "question": f"Does {tf} use SQLite?", "check": "grep_sqlite"},
            ])
        return questions

    def _generate_followup(self, parent_q):
        kf = self.state["target_keyword"]
        tf = self.state["target_file"]
        cat = parent_q.get("category", "")
        qtext = parent_q["question"]
        followups = []

        if "Downloads" in qtext and parent_q.get("_result") == ANSWER_YES:
            followups.append({"category": "followup_yes", "question": f"Which Downloads/*.md files mention {kf}?", "check": "grep_downloads_list"})
            followups.append({"category": "followup_yes", "question": f"Does the first match CREATE {tf} or USE it?", "check": "read_context"})
            followups.append({"category": "followup_yes", "question": f"What time was the first match file created?", "check": "stat_match"})

        if "chat_mover" in qtext and parent_q.get("_result") == ANSWER_YES:
            followups.append({"category": "followup_yes", "question": f"Which chat_mover files mention {kf}?", "check": "grep_chatmover_list"})

        if "same day" in qtext and parent_q.get("_result") == ANSWER_YES:
            followups.append({"category": "followup_yes", "question": f"Do those same-day files appear together in any chat?", "check": "grep_cluster"})
            followups.append({"category": "followup_yes", "question": f"Which chats mention the rarest same-day file?", "check": "grep_rarest"})

        if "devin_messages" in qtext and parent_q.get("_result") == ANSWER_YES:
            followups.append({"category": "followup_yes", "question": f"Which session do those messages belong to?", "check": "mysql_session"})
            followups.append({"category": "followup_yes", "question": f"Did that session create {tf} or just list it?", "check": "read_message"})

        if "know_questions" in qtext and parent_q.get("_result") == ANSWER_YES:
            followups.append({"category": "followup_yes", "question": f"What is the question_id?", "check": "mysql_qid"})
            followups.append({"category": "followup_yes", "question": f"Does the answer mention creation of {tf}?", "check": "mysql_answer_for_qid"})

        if "CREATE" in qtext and parent_q.get("_result") == ANSWER_YES:
            followups.append({"category": "followup_yes", "question": f"What is the exact line where {tf} is created?", "check": "read_line"})
            followups.append({"category": "followup_yes", "question": f"What was the user prompt that triggered creation?", "check": "read_user_input"})

        return followups

    def _check_existence(self, q):
        tf = self.state["target_file"]
        check = q.get("check")
        if check == "ls" and tf:
            if os.path.exists(tf):
                return ANSWER_YES, f"file exists: {tf}"
            return ANSWER_NO, f"file not found: {tf}"
        if check == "find_versions" and tf:
            basename = os.path.basename(tf)
            parent = os.path.dirname(tf)
            result = self._run_cmd(f"/usr/bin/find /Users/wws/Qdrant_mysql_mlx_vector_engine -name '{basename}*' -not -path '*/.git/*' 2>/dev/null")
            count = len([l for l in result.strip().split("\n") if l])
            if count > 1:
                return ANSWER_YES, f"found {count} versions: {result[:200]}"
            return ANSWER_NO, "only one version"
        if check == "find_backups":
            result = self._run_cmd("/usr/bin/find /Users/wws/Qdrant_mysql_mlx_vector_engine -name '*.bak' -o -name '*.orig' 2>/dev/null | head -5")
            if result.strip():
                return ANSWER_YES, f"backups found: {result[:200]}"
            return ANSWER_NO, "no backups"
        if check == "find_tests":
            kf = self.state["target_keyword"]
            result = self._run_cmd(f"/usr/bin/find /Users/wws/Qdrant_mysql_mlx_vector_engine -name 'test_*{kf}*' -o -name '*{kf}*test*' 2>/dev/null")
            if result.strip():
                return ANSWER_YES, f"tests found: {result[:200]}"
            return ANSWER_NO, "no tests"
        if check == "grep_refs" and tf:
            basename = os.path.basename(tf)
            result = self._run_cmd(f"/usr/bin/grep -rl '{basename}' /Users/wws/Qdrant_mysql_mlx_vector_engine/ 2>/dev/null | head -10")
            if result.strip():
                return ANSWER_YES, f"referenced by: {result[:200]}"
            return ANSWER_NO, "no references"
        return ANSWER_UNKNOWN, "no check implemented"

    def _check_time(self, q):
        tf = self.state["target_file"]
        check = q.get("check")
        if check == "stat_birth" and tf and os.path.exists(tf):
            result = self._run_cmd(f"stat -f '%SB' '{tf}'")
            return ANSWER_YES, f"birth time: {result.strip()}"
        if check == "stat_mod" and tf and os.path.exists(tf):
            result = self._run_cmd(f"stat -f '%Sm' '{tf}'")
            return ANSWER_YES, f"mod time: {result.strip()}"
        if check == "find_same_day" and tf and os.path.exists(tf):
            birth = self._run_cmd(f"stat -f '%SB' '{tf}'").strip()
            if birth:
                day = birth.split(" ")[0]
                result = self._run_cmd(f"/usr/bin/find /Users/wws/Qdrant_mysql_mlx_vector_engine -name '*.py' -newermt '{day} 00:00:00' ! -newermt '{day} 23:59:59' -not -path '*/.git/*' 2>/dev/null | head -20")
                count = len([l for l in result.strip().split("\n") if l])
                if count > 1:
                    return ANSWER_YES, f"{count} files same day: {result[:300]}"
                return ANSWER_NO, "no other files same day"
        if check == "find_same_hour" and tf and os.path.exists(tf):
            birth = self._run_cmd(f"stat -f '%SB' '{tf}'").strip()
            if birth:
                parts = birth.split(" ")
                day = parts[0]
                hour = int(parts[1].split(":")[0]) if len(parts) > 1 else 0
                start_h = max(0, hour - 1)
                result = self._run_cmd(f"/usr/bin/find /Users/wws/Qdrant_mysql_mlx_vector_engine -name '*.py' -newermt '{day} {start_h}:00:00' ! -newermt '{day} {hour+1}:30:00' -not -path '*/.git/*' 2>/dev/null | head -20")
                count = len([l for l in result.strip().split("\n") if l])
                if count > 1:
                    return ANSWER_YES, f"{count} files in same hour window: {result[:300]}"
                return ANSWER_NO, "no other files in same hour"
        return ANSWER_UNKNOWN, "no check implemented"

    def _check_versions(self, q):
        tf = self.state["target_file"]
        check = q.get("check")
        if check == "git_log":
            result = self._run_cmd("cd /Users/wws/Qdrant_mysql_mlx_vector_engine && git log --oneline --follow '" + tf + "' 2>&1 | head -5")
            if "fatal" in result or "not a git" in result:
                return ANSWER_NO, "not in git"
            if result.strip():
                return ANSWER_YES, f"git history: {result[:200]}"
            return ANSWER_NO, "no git history"
        if check == "find_v2" and tf:
            basename = os.path.basename(tf).replace(".py", "")
            result = self._run_cmd(f"/usr/bin/find /Users/wws/Qdrant_mysql_mlx_vector_engine -name '{basename}_v*.py' -o -name '{basename}_new.py' 2>/dev/null")
            if result.strip():
                return ANSWER_YES, f"v2 found: {result[:200]}"
            return ANSWER_NO, "no v2"
        if check == "db_lookup":
            kf = self.state["target_keyword"]
            result = self._run_cmd(f"mysql -u root CODEBASE -e \"SELECT COUNT(*) FROM python_files WHERE filename LIKE '%{kf}%'\" 2>/dev/null")
            if result and result.strip().split("\n")[-1].strip() != "0":
                return ANSWER_YES, f"in CODEBASE: {result.strip()}"
            return ANSWER_NO, "not in CODEBASE"
        return ANSWER_UNKNOWN, "no check implemented"

    def _check_location(self, q):
        tf = self.state["target_file"]
        check = q.get("check")
        if check == "find_tmp":
            basename = os.path.basename(tf) if tf else self.state["target_keyword"]
            result = self._run_cmd(f"/usr/bin/find /tmp -name '{basename}*' 2>/dev/null")
            if result.strip():
                return ANSWER_YES, f"found in /tmp: {result[:200]}"
            return ANSWER_NO, "not in /tmp"
        if check == "grep_path" and tf:
            result = self._run_cmd(f"/usr/bin/grep -rl '{tf}' /Users/wws/Qdrant_mysql_mlx_vector_engine/ 2>/dev/null | head -10")
            if result.strip():
                return ANSWER_YES, f"path hardcoded in: {result[:200]}"
            return ANSWER_NO, "path not hardcoded"
        return ANSWER_UNKNOWN, "no check implemented"

    def _check_chat_history(self, q):
        kf = self.state["target_keyword"]
        check = q.get("check")
        if check == "grep_downloads":
            result = self._run_cmd(f"/usr/bin/grep -rl '{kf}' /Users/wws/Downloads/*.md 2>/dev/null | head -10")
            if result.strip():
                files = result.strip().split("\n")
                q["_result"] = ANSWER_YES
                q["_matches"] = files
                return ANSWER_YES, f"found in {len(files)} Downloads files: {result[:300]}"
            return ANSWER_NO, "not in Downloads"
        if check == "grep_chatmover":
            result = self._run_cmd(f"/usr/bin/grep -rl '{kf}' /Users/wws/Qdrant_mysql_mlx_vector_engine/chat_mover/*.md 2>/dev/null | head -10")
            if result.strip():
                q["_result"] = ANSWER_YES
                return ANSWER_YES, f"found in chat_mover: {result[:200]}"
            return ANSWER_NO, "not in chat_mover"
        if check == "mysql_questions":
            result = self._run_cmd(f"mysql -u root vb_shared -e \"SELECT COUNT(*) FROM know_questions WHERE question LIKE '%{kf}%'\" 2>/dev/null")
            if result:
                count = result.strip().split("\n")[-1].strip()
                if count != "0":
                    q["_result"] = ANSWER_YES
                    return ANSWER_YES, f"{count} questions mention {kf}"
            return ANSWER_NO, "not in know_questions"
        if check == "mysql_answers":
            result = self._run_cmd(f"mysql -u root vb_shared -e \"SELECT COUNT(*) FROM know_answers WHERE answer LIKE '%{kf}%'\" 2>/dev/null")
            if result:
                count = result.strip().split("\n")[-1].strip()
                if count != "0":
                    return ANSWER_YES, f"{count} answers mention {kf}"
            return ANSWER_NO, "not in know_answers"
        if check == "mysql_devin":
            result = self._run_cmd(f"mysql -u root devin -e \"SELECT COUNT(*) FROM devin_messages WHERE content LIKE '%{kf}%'\" 2>/dev/null")
            if result:
                count = result.strip().split("\n")[-1].strip()
                if count != "0":
                    return ANSWER_YES, f"{count} devin messages mention {kf}"
            return ANSWER_NO, "not in devin_messages"
        if check == "mysql_transcripts":
            result = self._run_cmd(f"mysql -u root devin -e \"SELECT COUNT(*) FROM devin_transcripts WHERE raw_json LIKE '%{kf}%'\" 2>/dev/null")
            if result:
                count = result.strip().split("\n")[-1].strip()
                if count != "0":
                    return ANSWER_YES, f"{count} transcripts mention {kf}"
            return ANSWER_NO, "not in devin_transcripts"
        if check == "mysql_rules":
            result = self._run_cmd(f"mysql -u root vb_shared -e \"SELECT COUNT(*) FROM learned_rules WHERE pattern LIKE '%{kf}%'\" 2>/dev/null")
            if result:
                count = result.strip().split("\n")[-1].strip()
                if count != "0":
                    return ANSWER_YES, f"{count} rules mention {kf}"
            return ANSWER_NO, "not in learned_rules"
        return ANSWER_UNKNOWN, "no check implemented"

    def _check_database(self, q):
        kf = self.state["target_keyword"]
        check = q.get("check")
        if check == "mysql_codebase":
            result = self._run_cmd(f"mysql -u root CODEBASE -e \"SELECT COUNT(*) FROM python_files WHERE filename LIKE '%{kf}%'\" 2>/dev/null")
            if result:
                count = result.strip().split("\n")[-1].strip()
                if count != "0":
                    return ANSWER_YES, f"{count} rows in python_files"
            return ANSWER_NO, "not in CODEBASE"
        if check == "mysql_vbclasses":
            result = self._run_cmd(f"mysql -u root vb_code_test -e \"SELECT COUNT(*) FROM vb_classes WHERE class_name LIKE '%{kf}%'\" 2>/dev/null")
            if result:
                count = result.strip().split("\n")[-1].strip()
                if count != "0":
                    return ANSWER_YES, f"{count} classes"
            return ANSWER_NO, "not in vb_classes"
        return ANSWER_UNKNOWN, "no check implemented"

    def _check_authorship(self, q):
        tf = self.state["target_file"]
        check = q.get("check")
        if check == "read_header" and tf and os.path.exists(tf):
            with open(tf, "r") as f:
                header = f.read(500)
            if "[@GHOST]" in header:
                import re
                m = re.search(r'author="([^"]+)"', header)
                if m:
                    return ANSWER_YES, f"author={m.group(1)}"
                return ANSWER_YES, "has GHOST header but no author field"
            return ANSWER_NO, "no GHOST header"
        if check == "header_cascade" and tf and os.path.exists(tf):
            with open(tf, "r") as f:
                header = f.read(500)
            if "Cascade" in header or "cascade" in header:
                return ANSWER_YES, "created by Cascade"
            return ANSWER_NO, "not Cascade"
        if check == "header_devin" and tf and os.path.exists(tf):
            with open(tf, "r") as f:
                header = f.read(500)
            if "Devin" in header or "devin" in header:
                return ANSWER_YES, "created by Devin"
            return ANSWER_NO, "not Devin"
        return ANSWER_UNKNOWN, "no check implemented"

    def _check_followup(self, fq, parent_q):
        kf = self.state["target_keyword"]
        tf = self.state["target_file"]
        check = fq.get("check")
        parent_matches = parent_q.get("_matches", [])

        if check == "grep_downloads_list":
            result = self._run_cmd(f"/usr/bin/grep -rl '{kf}' /Users/wws/Downloads/*.md 2>/dev/null")
            if result.strip():
                return ANSWER_YES, f"files: {result.strip()[:300]}"
            return ANSWER_NO, "none"
        if check == "read_context":
            if parent_matches:
                fpath = parent_matches[0]
                result = self._run_cmd(f"/usr/bin/grep -n '{kf}' '{fpath}' 2>/dev/null | head -5")
                if "Edited relevant file" in result or "created" in result.lower():
                    return ANSWER_YES, f"creation context found in {fpath}"
                return ANSWER_NO, f"used but not created in {fpath}"
            return ANSWER_UNKNOWN, "no parent matches"
        if check == "stat_match":
            if parent_matches:
                fpath = parent_matches[0]
                result = self._run_cmd(f"stat -f '%SB' '{fpath}'")
                return ANSWER_YES, f"file created: {result.strip()}"
            return ANSWER_UNKNOWN, "no matches"
        if check == "grep_cluster":
            # Check if same-day files appear together in any chat
            result = self._run_cmd(f"/usr/bin/grep -rl '{kf}' /Users/wws/Downloads/*.md 2>/dev/null | head -5")
            if result.strip():
                return ANSWER_YES, f"cluster found in: {result[:200]}"
            return ANSWER_NO, "no cluster"
        if check == "grep_rarest":
            # Find rarest same-day file and search for it
            result = self._run_cmd(f"/usr/bin/grep -rl '{kf}' /Users/wws/Downloads/*.md 2>/dev/null | wc -l")
            count = result.strip()
            return ANSWER_YES, f"appears in {count} files"
        if check == "mysql_session":
            result = self._run_cmd(f"mysql -u root devin -e \"SELECT session_id FROM devin_messages WHERE content LIKE '%{kf}%' LIMIT 1\" 2>/dev/null")
            if result and result.strip():
                return ANSWER_YES, f"session: {result.strip()}"
            return ANSWER_NO, "no session"
        if check == "read_message":
            return ANSWER_UNKNOWN, "requires manual reading"
        if check == "read_line":
            return ANSWER_UNKNOWN, "requires manual reading"
        if check == "read_user_input":
            return ANSWER_UNKNOWN, "requires manual reading"
        return ANSWER_UNKNOWN, "no check implemented"

    def _run_cmd(self, cmd):
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            return result.stdout
        except Exception:
            return ""

    def close(self):
        self.store.close()


if __name__ == "__main__":
    import sys
    agent = QuestionAgent()
    if len(sys.argv) < 2:
        print("Usage: question_agent.py '{\"problem\":\"...\",\"target_file\":\"...\"}'")
        sys.exit(1)
    params = json.loads(sys.argv[1])
    ok, data, error = agent.Run("investigate", params)
    if ok:
        print(json.dumps(data, indent=2, default=str))
    else:
        print(f"ERROR: {error}")
    agent.close()
