# [@GHOST]{[@file<spec_graph_runner.py>][@domain<Dom_Unified>][@role<spec_graph_engine>][@auth<cascade>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<spec_graph_engine>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{Spec graph runner — loads questions from MySQL graph_config, asks the spec file, extracts answers. BCL tag aware.}
# [@CLASS]{SpecGraphRunner}
# [@METHOD]{Run,AskAll,AskOne,ExtractAnswer,LoadSpec,LoadQuestions}

import re
from Config import UnifiedConfig
from DatabaseManager import DatabaseManager


class SpecGraphRunner:

    TAG_HINTS = {
        "[@what]": ["is", "are", "uses", "builds", "creates", "runs", "files", "tables", "classes"],
        "[@how]": ["flow", "step", "stage", "dump", "load", "thread", "batch", "unwind", "staging"],
        "[@why]": ["because", "faster", "domain", "authority", "one class", "batch", "thread"],
        "[@when]": ["when", "stage", "created", "destroyed", "runs", "process", "exit"],
        "[@where]": ["mysql", "sqlite", "neo4j", "ram", "disk", "memory", "permanent", "temporary"],
        "[@who]": ["neo4jgraph", "databasemanager", "config", "calls", "creates", "runs"],
        "[@how_many]": ["count", "rows", "nodes", "edges", "batches", "threads"],
        "[@which]": ["which", "class", "method", "table", "bottleneck", "hub"],
    }

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "spec_path": None,
                "questions_db": "vb_shared",
                "questions_table": "graph_config",
                "questions_domain": "dom_graph",
            },
            "results": {
                "total_questions": 0,
                "total_answered": 0,
                "total_no_match": 0,
                "answers": {},
            },
            "spec_text": "",
            "sections": {},
        }
        cfg = UnifiedConfig()
        ok, cfg_state, err = cfg.read_state()
        if ok:
            c = cfg_state["config"]
            self.state["config"]["questions_db"] = c.get("graph_questions_db", "vb_shared")
            self.state["config"]["questions_table"] = c.get("graph_questions_table", "graph_config")
            self.state["config"]["questions_domain"] = c.get("graph_questions_domain", "dom_graph")
        if param:
            self.state["config"].update(param)

    def _p(self, params, key, default=None):
        if not params or not isinstance(params, dict):
            return default
        val = params.get(key, default)
        return val if val is not None else default

    def Run(self, command, params=None):
        dispatch = {
            "ask_all": self._cmd_ask_all,
            "ask_one": self._cmd_ask_one,
            "load_spec": self._cmd_load_spec,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", "unknown command: " + str(command), 0))
        return handler(params)

    def _cmd_load_spec(self, params):
        spec_path = self._p(params, "spec_path", self.state["config"]["spec_path"])
        if not spec_path:
            return (0, None, ("ERR_NO_PATH", "spec_path required", 0))
        try:
            with open(spec_path, "r") as f:
                self.state["spec_text"] = f.read()
        except Exception as e:
            return (0, None, ("ERR_READ", str(e), 0))
        self._parse_sections()
        self.state["config"]["spec_path"] = spec_path
        return (1, {"sections": len(self.state["sections"]), "chars": len(self.state["spec_text"])}, None)

    def _parse_sections(self):
        sections = {}
        current_section = "0"
        current_content = []
        for line in self.state["spec_text"].split("\n"):
            m = re.match(r"^## (\d+)\.", line)
            if m:
                sections[current_section] = "\n".join(current_content)
                current_section = m.group(1)
                current_content = [line]
            else:
                current_content.append(line)
        sections[current_section] = "\n".join(current_content)
        self.state["sections"] = sections

    def _load_questions(self):
        c = self.state["config"]
        db = DatabaseManager(param={
            "db_type": "mysql",
            "db_host": "localhost",
            "db_user": "root",
            "db_name": c["questions_db"],
        })
        ok, rows, err = db.Run("query", {
            "sql": "SELECT section, question_key, bcl_tag, question_text, spec_section FROM " + c["questions_table"] + " WHERE domain = %s ORDER BY section, sort_order",
            "args": [c["questions_domain"]],
        })
        if not ok:
            return (0, None, err)
        return (1, rows, None)

    def _extract_answer(self, question_text, bcl_tag, section_content, full_spec):
        keywords = [w.lower() for w in question_text.split() if len(w) > 3]
        if not keywords:
            keywords = [w.lower() for w in question_text.split() if len(w) > 2]
        hint_words = self.TAG_HINTS.get(bcl_tag, [])

        def ScoreLine(line):
            line_stripped = line.strip()
            if len(line_stripped) < 10:
                return 0
            if line_stripped.startswith("|--") or line_stripped.startswith("```"):
                return 0
            line_lower = line_stripped.lower()
            kw_score = sum(2 for kw in keywords if kw in line_lower)
            hint_score = sum(1 for hw in hint_words if hw in line_lower)
            return kw_score + hint_score

        lines = section_content.split("\n")
        scored = [(ScoreLine(l), l.strip()) for l in lines]
        scored = [(s, l) for s, l in scored if s > 0]
        scored.sort(key=lambda x: -x[0])

        # Fallback: only search full spec if target section has NO matches at all
        if not scored:
            full_lines = full_spec.split("\n")
            full_scored = [(ScoreLine(l), l.strip()) for l in full_lines]
            full_scored = [(s, l) for s, l in full_scored if s > 0]
            full_scored.sort(key=lambda x: -x[0])
            scored = full_scored

        if not scored:
            return ["(no match found)"]
        return [s[1][:160] for s in scored[:3]]

    def _cmd_ask_all(self, params):
        spec_path = self._p(params, "spec_path", self.state["config"]["spec_path"])
        if not self.state["spec_text"] and spec_path:
            ok, data, err = self._cmd_load_spec({"spec_path": spec_path})
            if not ok:
                return (0, None, err)
        if not self.state["spec_text"]:
            return (0, None, ("ERR_NO_SPEC", "load spec first", 0))

        ok, questions, err = self._load_questions()
        if not ok:
            return (0, None, err)

        answers = {}
        total_answered = 0
        total_no_match = 0
        current_graph = ""

        for q in questions:
            section = q["section"]
            if section not in answers:
                answers[section] = []

            full_q = q["bcl_tag"] + " " + q["question_text"]
            spec_sec = q["spec_section"]
            if spec_sec == "all":
                content = self.state["spec_text"]
            else:
                content = self.state["sections"].get(spec_sec, "")

            result_lines = self._extract_answer(q["question_text"], q["bcl_tag"], content, self.state["spec_text"])
            is_match = result_lines[0] != "(no match found)"
            if is_match:
                total_answered += 1
            else:
                total_no_match += 1

            answers[section].append({
                "question": full_q,
                "bcl_tag": q["bcl_tag"],
                "spec_section": spec_sec,
                "answers": result_lines,
                "matched": is_match,
            })

        self.state["results"]["total_questions"] = len(questions)
        self.state["results"]["total_answered"] = total_answered
        self.state["results"]["total_no_match"] = total_no_match
        self.state["results"]["answers"] = answers

        return (1, {
            "total_questions": len(questions),
            "total_answered": total_answered,
            "total_no_match": total_no_match,
            "answers": answers,
        }, None)

    def _cmd_ask_one(self, params):
        section = self._p(params, "section")
        question_key = self._p(params, "question_key")
        if not section or not question_key:
            return (0, None, ("ERR_PARAMS", "section and question_key required", 0))
        if not self.state["spec_text"]:
            return (0, None, ("ERR_NO_SPEC", "load spec first", 0))

        ok, questions, err = self._load_questions()
        if not ok:
            return (0, None, err)

        for q in questions:
            if q["section"] == section and q["question_key"] == question_key:
                spec_sec = q["spec_section"]
                content = self.state["spec_text"] if spec_sec == "all" else self.state["sections"].get(spec_sec, "")
                result = self._extract_answer(q["question_text"], q["bcl_tag"], content, self.state["spec_text"])
                return (1, {
                    "question": q["bcl_tag"] + " " + q["question_text"],
                    "answers": result,
                    "spec_section": spec_sec,
                }, None)

        return (0, None, ("ERR_NOT_FOUND", "question not found", 0))

    def read_state(self, params=None):
        return (1, {
            "config": dict(self.state["config"]),
            "results": {k: v for k, v in self.state["results"].items() if k != "answers"},
        }, None)

    def set_config(self, params):
        if not params or not isinstance(params, dict):
            return (0, None, ("ERR_PARAMS", "config dict required", 0))
        self.state["config"].update(params)
        return (1, {"updated": list(params.keys())}, None)


if __name__ == "__main__":
    runner = SpecGraphRunner()
    ok, data, err = runner.Run("ask_all", {"spec_path": "NEO4J_PIPELINE.md"})
    if ok:
        print("=== SPEC GRAPH RUNNER ===")
        print("Questions: " + str(data["total_questions"]))
        print("Answered:  " + str(data["total_answered"]))
        print("No match:  " + str(data["total_no_match"]))
        print()
        for section, qs in data["answers"].items():
            print("--- " + section.upper() + " ---")
            for q in qs:
                print("Q: " + q["question"])
                for a in q["answers"]:
                    print("A: " + a)
                print()
    else:
        print("ERROR: " + str(err))
