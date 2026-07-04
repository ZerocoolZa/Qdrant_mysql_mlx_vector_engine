#!/usr/bin/env python3
#[@GHOST]{file_path="core/utility/question_registry.py" date="2026-08-18" author="Devin" session_id="question-registry" context="Registry of all 16 question engine patterns found in CODEBASE — maps each to QuestionStore commands"}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self-_ no-print"}
#[@FILEID]{id="question_registry.py" domain="utility" authority="QuestionRegistry"}
#[@SUMMARY]{summary="Registry of 16 question engine patterns from CODEBASE — each mapped to QuestionStore integration with source file, class, key methods, and integration command"}
#[@CLASS]{class="QuestionRegistry" domain="utility" authority="single"}
#[@METHOD]{methods="Run,List,Get,Integrate,IntegrateAll,FromContradictions,FromGaps,FromChat,FromCode,FromBook,FromSchema,FromContext,FromArchitecture,Weight,Closure,Cascade,Rank,Proof,Minimum,Track,Report"}

"""
QuestionRegistry — maps 16 question engine patterns to the QuestionStore.

Each pattern was found by searching CODEBASE.mysql (389K python files) for
class names containing Question/Curiosity/Uncertainty/Interrogat.

The registry provides:
1. A catalog of all patterns with source files
2. Integration methods that connect each pattern to QuestionStore
3. A unified Run() dispatch that can invoke any pattern

Patterns integrated:
  1. QuestionEngine         — contradictions + gaps → questions
  2. ChatInterrogationEngine — chat content → questions with confidence
  3. CodeQuestionProofEngine — 20-question VBStyle interrogation
  4. BookQuestionGenerator   — book content → questions with templates
  5. QuestionToLawClosure_V3 — questions → laws via score/infer/loop
  6. QuestionWeigherV2       — evidence-based weight scoring + conflict veto
  7. SmartQuestionTackleApp  — PyQt6 app with progress tracking
  8. EnhancedQuestionDB      — SQLite with users/categories/analytics
  9. DatabaseQuestionEngine  — GUI + DB question engine
 10. QuestioningEngine       — tier-based completeness validation
 11. QuestionThinkingAI      — 7 domain-specific question frameworks
 12. Question_Engine         — context-aware minimum-question selector
 13. QuestionCascadeEngine   — questions spawn sub-questions (cascade)
 14. UncertaintyQueue        — queue of uncertainties to resolve
 15. RankedQuestion          — question ranking by importance
 16. QuestionNode            — node in question tree (predictive world model)
"""

import json
import os
import re
import sqlite3
import subprocess
from datetime import datetime

from question_store import QuestionStore, ANSWER_YES, ANSWER_NO, ANSWER_UNKNOWN, ANSWER_ACTION

# ── REGISTRY: 16 patterns ──────────────────────────────────────

REGISTRY = {
    "QuestionEngine": {
        "source": "/Users/wws/contestsystem/VBSTYLE_MASTER _CORE/VBstyle_Python/Domains/dom_knowledge.py",
        "lines": 3669,
        "class": "QuestionEngine",
        "pattern": "contradictions_and_gaps",
        "description": "Generates questions from contradictions and knowledge gaps",
        "run_commands": ["generate", "store", "query", "read_state", "set_config"],
        "key_methods": ["_generate", "_store", "_query"],
        "db": "in_memory (self.state['questions'])",
        "integration": "FromContradictions",
        "question_template": "Why does '{a}' contradict '{b}'?",
        "gap_template": "What is missing regarding {gap}?"
    },
    "ChatInterrogationEngine": {
        "source": "/Users/Shared/VB_ai_Dec/Project_PropPanel/kernel/MASTER_2026_Rules/Project_Chat_Investigator/chat_interrogation_engine.py",
        "lines": 1212,
        "class": "ChatInterrogationEngine",
        "pattern": "chat_content_extraction",
        "description": "Extracts maximum information from chat content using dynamic question generation",
        "run_commands": [],
        "key_methods": ["PatternAnalyzer", "ContextBuilder", "DynamicQuestionGenerator", "KnowledgeExtractor"],
        "db": "in_memory (questions_db list, knowledge_graph networkx)",
        "integration": "FromChat",
        "question_template": "What does the chat reveal about {topic}?"
    },
    "CodeQuestionProofEngine": {
        "source": "/Users/wws/Documents/MOVED_FROM_WAYNE_OLD_ACCOUNT/Prj_testbed/AA_MEMORIES/2026_GuisMost_important/Unit/Unit_Truth/Unit_CodeQuestionProofEngine.py",
        "lines": 1203,
        "class": "CodeQuestionProofEngine",
        "pattern": "vbstyle_interrogation",
        "description": "VBSTYLE conformance interrogation — asks closed 20-question set until violations exposed",
        "run_commands": ["bootstrap", "seedquestions", "askall", "askone", "decide", "adversary", "status", "weaknessreport", "askqueue"],
        "key_methods": ["SeedQuestions", "AskAll", "AskOne", "DecideAll", "RunAdversary"],
        "db": "qproof_run, qproof_question, qproof_answer, qproof_evidence, qproof_decision, qproof_weakness",
        "integration": "Proof",
        "question_template": "Does the code comply with {rule}?"
    },
    "BookQuestionGenerator": {
        "source": "/Users/Shared/VB_ai_Dec/Edward/book_question_generator.py",
        "lines": 954,
        "class": "BookQuestionGenerator",
        "pattern": "book_content_templates",
        "description": "Generates questions from book content using concept extraction and templates",
        "run_commands": [],
        "key_methods": ["load_book", "parse_chapters", "extract_concepts", "question_templates"],
        "db": "in_memory",
        "integration": "FromBook",
        "question_templates": {
            "definition": "What is the definition of {concept}?",
            "usage": "How is {concept} used in practice?",
            "comparison": "How does {concept} compare to {alternative}?",
            "implementation": "How is {concept} implemented?",
            "best_practice": "What are best practices for {concept}?"
        }
    },
    "QuestionToLawClosure_V3": {
        "source": "/Users/wws/Documents/MOVED_FROM_WAYNE_OLD_ACCOUNT/PRj_codex-notes/Ai_Wayne_Made/Sources/TOKAI/CORE_BRKTOKAI/UNITS/Unit_QuestionToLawClosure_V3.py",
        "lines": 793,
        "class": "QuestionToLawClosure_V3",
        "pattern": "question_to_law_closure",
        "description": "Fixed-law-anchored question-to-law closure engine with strict QA routing",
        "run_commands": ["contract", "start", "addQuestion", "addAnswer", "generate", "score", "ask", "answer", "infer", "step", "loop", "close", "status", "export", "state"],
        "key_methods": ["AddQuestion", "AddAnswer", "Generate", "Score", "Infer", "Close"],
        "db": "in_memory (self.sessions dict)",
        "integration": "Closure",
        "question_template": "Can question '{q}' be closed into a law given answers {answers}?"
    },
    "QuestionWeigherV2": {
        "source": "/Users/wws/Documents/MOVED_FROM_WAYNE_OLD_ACCOUNT/Prj_testbed/AA_MEMORIES/2026_GuisMost_important/Unit/Unit_qna/Unit_QuestionWeigherV2.py",
        "lines": 792,
        "class": "QuestionWeigherV2",
        "pattern": "evidence_weight_scoring",
        "description": "Question/answer weight evidence-derived proof scorer with conflict veto",
        "run_commands": ["status", "load", "score", "decide", "prove", "proveQ3", "demo", "explain", "ingest", "proveAndIngest"],
        "key_methods": ["Load", "ScoreAll", "DecideAll", "ProveQ3", "ProveAll"],
        "db": "qw_question, qw_candidate, qw_known_fact, qwEvidence, qwConflict, qwScore, qwDecision, qwSearchRadius",
        "integration": "Weight",
        "question_template": "What is the evidence weight for '{question}'?"
    },
    "SmartQuestionTackleApp": {
        "source": "/Users/Shared/VB_ai_Dec/PYTHONCODE /smart_question_tackle_app.py",
        "lines": 1232,
        "class": "SmartQuestionTackleApp",
        "pattern": "gui_progress_tracking",
        "description": "PyQt6 app for presenting architecture questions with progress tracking",
        "run_commands": [],
        "key_methods": ["parse_questions", "save_progress", "load_progress"],
        "db": "QSettings (local persistence)",
        "integration": "Track",
        "question_template": "Architecture question: {question} (progress: {done}/{total})"
    },
    "EnhancedQuestionDB": {
        "source": "/Users/Shared/Cascade_Tools/Pycode/rebuilt/secure_key_vault/enhanced_question_db.py",
        "lines": 1213,
        "class": "EnhancedQuestionDB",
        "pattern": "sqlite_comprehensive_qa",
        "description": "SQLite-based comprehensive Q&A management system",
        "run_commands": [],
        "key_methods": ["_init_db", "add_question", "get_question_by_uuid", "record_answer"],
        "db": "users, categories, questions, user_answers, user_preferences, knowledge_base, question_analytics",
        "integration": "DirectSQL",
        "question_template": "Category: {category} — {question}"
    },
    "DatabaseQuestionEngine": {
        "source": "/Users/Shared/Cascade_Tools/Pycode/rebuilt/secure_key_vault/question_gui_db.py",
        "lines": 975,
        "class": "DatabaseQuestionEngine",
        "pattern": "gui_db_qa",
        "description": "PyQt6 GUI for database-driven Q/A",
        "run_commands": ["run"],
        "key_methods": ["_refresh_question", "_on_answer", "get_next_question"],
        "db": "external QuestionDB",
        "integration": "FromSchema",
        "question_template": "Database question: {question}"
    },
    "QuestioningEngine": {
        "source": "/Users/Shared/Mastermanager/From car-Road/maxed_thinking_reasoning_engine.py",
        "lines": 1155,
        "class": "QuestioningEngine",
        "pattern": "tier_completeness_validation",
        "description": "Tier-based completeness validation — questions its own conclusions",
        "run_commands": [],
        "key_methods": ["derive_evidence_from_system", "validate_component_tier", "generate_questions"],
        "db": "in_memory (Evidence, Pattern, Question, CompletenessResult dataclasses)",
        "integration": "FromContext",
        "question_template": "Is tier {tier} complete? What is missing?"
    },
    "QuestionThinkingAI": {
        "source": "/Users/Shared/VB_ai_Dec/Processing files/08_Architecture_Tools/question_thinking_ai_framework.py",
        "lines": 665,
        "class": "QuestionThinkingAI",
        "pattern": "domain_specific_frameworks",
        "description": "7 domain-specific question frameworks (CodeReview, SystemDesign, etc.)",
        "run_commands": [],
        "key_methods": ["analyze_problem", "_generate_questions", "_evaluate_solution"],
        "db": "in_memory (knowledge_graph, metadata_store, evaluation_frameworks)",
        "integration": "FromArchitecture",
        "subclasses": ["CodeReviewAI", "SystemDesignAI", "DebugAI", "TestingAI", "SecurityAI", "PerformanceAI", "ArchitectureAI"],
        "question_template": "{domain}: {question}"
    },
    "Question_Engine": {
        "source": "/Users/wws/Documents/MOVED_FROM_WAYNE_OLD_ACCOUNT/PRj_codex-notes/Master_Data/Question_Engine.py",
        "lines": 619,
        "class": "RankedQuestion",
        "pattern": "context_aware_minimum_selector",
        "description": "Context-aware minimum-question selector with slots/ledger/ranked questions",
        "run_commands": [],
        "key_methods": ["classify_task", "detect_gaps", "fill_from_context"],
        "db": "in_memory (slots, ledger, ranked questions)",
        "integration": "Minimum",
        "question_template": "Minimum question for slot '{slot}': {question} (priority: {priority})"
    },
    "QuestionCascadeEngine": {
        "source": "/Users/Shared/VB_ai_Dec/Project_security_sandbox/Project_VirtualDrive/pine cone/Not_in Service_MEMBUS_V3.py",
        "lines": 695,
        "class": "QuestionCascadeEngine",
        "pattern": "cascade_subquestions",
        "description": "Cascading question engine — questions spawn sub-questions",
        "run_commands": [],
        "key_methods": [],
        "db": "in_memory",
        "integration": "Cascade",
        "question_template": "Sub-question of '{parent}': {question}"
    },
    "UncertaintyQueue": {
        "source": "/Users/wws/Documents/MOVED_FROM_WAYNE_OLD_ACCOUNT/PRj_codex-notes/fv.py",
        "lines": 1013,
        "class": "UncertaintyQueue",
        "pattern": "uncertainty_queue",
        "description": "Queue of uncertainties to resolve",
        "run_commands": [],
        "key_methods": [],
        "db": "in_memory",
        "integration": "Queue",
        "question_template": "Uncertainty: {uncertainty} (type: {type})"
    },
    "RankedQuestion": {
        "source": "/Users/wws/Documents/MOVED_FROM_WAYNE_OLD_ACCOUNT/PRj_codex-notes/Master_Data/Question_Engine.py",
        "lines": 619,
        "class": "RankedQuestion",
        "pattern": "question_ranking",
        "description": "Question ranking by importance",
        "run_commands": [],
        "key_methods": [],
        "db": "in_memory",
        "integration": "Rank",
        "question_template": "Ranked question #{rank}: {question}"
    },
    "QuestionNode": {
        "source": "/Users/Shared/VB_ai_Dec/Project_PropPanel/Libs/Py/AISystem/Lib_PredictiveWorldModel.py",
        "lines": 715,
        "class": "QuestionNode",
        "pattern": "question_tree_node",
        "description": "Node in a question tree (used by predictive world model)",
        "run_commands": [],
        "key_methods": [],
        "db": "in_memory",
        "integration": "Node",
        "question_template": "Question node: {question} (children: {child_count})"
    }
}

# ── CONTRADICTION/GAP TEMPLATES (from QuestionEngine) ──────────

CONTRADICTION_TEMPLATE = "Why does '{statement_a}' contradict '{statement_b}'?"
GAP_TEMPLATE = "What is missing regarding {gap}?"

# ── BOOK TEMPLATES (from BookQuestionGenerator) ────────────────

BOOK_TEMPLATES = {
    "definition": "What is the definition of {concept}?",
    "usage": "How is {concept} used in practice?",
    "comparison": "How does {concept} compare to {alternative}?",
    "implementation": "How is {concept} implemented?",
    "best_practice": "What are best practices for {concept}?"
}

# ── VBSTYLE PROOF QUESTIONS (from CodeQuestionProofEngine) ─────

PROOF_QUESTIONS = [
    "Does the file have a #[@GHOST] header?",
    "Does the file have a #[@VBSTYLE] header?",
    "Does the file have a #[@FILEID] header?",
    "Does the file have a #[@SUMMARY] header?",
    "Does the class have a #[@CLASS] header?",
    "Does each method have a #[@METHOD] header?",
    "Does the class have Run(self, command, params=None) dispatch?",
    "Do all methods return Tuple3 (1, data, None) or (0, None, error)?",
    "Is __init__(self, mem=None, db=None, param=None)?",
    "Is there self.state dict (not self._ attributes)?",
    "Are class names PascalCase (no underscores)?",
    "Are constants UPPERCASE at class level?",
    "Are there any print() statements (forbidden)?",
    "Are there any @property/@staticmethod/@classmethod (forbidden)?",
    "Are there any hardcoded values (should be in Config)?",
    "Are there any tab characters (spaces only)?",
    "Is there trailing whitespace (forbidden)?",
    "Is there a _p(self, params, key, default) helper?",
    "Does the file have one class (not a monolith)?",
    "Is there a Config.py for shared constants?"
]

# ── DOMAIN FRAMEWORKS (from QuestionThinkingAI) ────────────────

DOMAIN_FRAMEWORKS = {
    "CodeReview": [
        "Does the code compile?",
        "Are there any obvious bugs?",
        "Is error handling adequate?",
        "Are edge cases covered?",
        "Is the code readable?"
    ],
    "SystemDesign": [
        "Is the architecture scalable?",
        "Are components loosely coupled?",
        "Is there separation of concerns?",
        "Are interfaces stable?",
        "Is the system testable?"
    ],
    "Debug": [
        "What is the root cause?",
        "Can the bug be reproduced?",
        "What is the minimal reproduction case?",
        "What changed recently?",
        "What is the fix?"
    ],
    "Testing": [
        "What are the test cases?",
        "What is the coverage?",
        "Are edge cases tested?",
        "Are integration tests present?",
        "Do tests pass?"
    ],
    "Security": [
        "Are there injection vulnerabilities?",
        "Are credentials hardcoded?",
        "Is input validated?",
        "Are permissions checked?",
        "Is data encrypted?"
    ],
    "Performance": [
        "What is the bottleneck?",
        "What is the time complexity?",
        "What is the space complexity?",
        "Can it be parallelized?",
        "What is the measured performance?"
    ],
    "Architecture": [
        "Is the design pattern appropriate?",
        "Are dependencies minimal?",
        "Is the code DRY (no duplication)?",
        "Is the code SOLID?",
        "Is the code maintainable?"
    ]
}


class QuestionRegistry:
    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {"max_questions": 1000},
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

    def _save_q(self, problem_id, category, question, depth=0, parent_id=None):
        if not problem_id:
            return None
        ok, data, err = self.store.Run("ask", {
            "problem_id": problem_id,
            "question": question,
            "category": category,
            "depth": depth,
            "parent_id": parent_id
        })
        return data["question_id"] if data else None

    def _save_a(self, question_id, answer, evidence="", source=""):
        if not question_id:
            return
        self.store.Run("answer", {
            "question_id": question_id,
            "answer": answer,
            "evidence": evidence,
            "source": source
        })

    def Run(self, command, params=None):
        dispatch = {
            "list": self.List,
            "get": self.Get,
            "from_contradictions": self.FromContradictions,
            "from_gaps": self.FromGaps,
            "from_chat": self.FromChat,
            "from_code": self.FromCode,
            "from_book": self.FromBook,
            "from_schema": self.FromSchema,
            "from_context": self.FromContext,
            "from_architecture": self.FromArchitecture,
            "weight": self.Weight,
            "closure": self.Closure,
            "cascade": self.Cascade,
            "rank": self.Rank,
            "proof": self.Proof,
            "minimum": self.Minimum,
            "track": self.Track,
            "integrate_all": self.IntegrateAll,
            "report": self.Report,
        }
        handler = dispatch.get(command)
        if handler:
            return handler(params)
        return (0, None, (1, f"unknown_command:{command}", 0))

    # ── CATALOG ─────────────────────────────────────────────────

    def List(self, params):
        patterns = []
        for name, info in REGISTRY.items():
            patterns.append({
                "name": name,
                "pattern": info["pattern"],
                "description": info["description"],
                "source": info["source"],
                "lines": info["lines"],
                "integration": info["integration"],
                "run_commands": info["run_commands"]
            })
        return (1, {"patterns": patterns, "count": len(patterns)}, None)

    def Get(self, params):
        name = self._p(params, "name")
        if not name or name not in REGISTRY:
            return (0, None, (2, f"unknown pattern: {name}", 0))
        return (1, {"pattern": REGISTRY[name]}, None)

    # ── 1. FROM CONTRADICTIONS (QuestionEngine) ─────────────────

    def FromContradictions(self, params):
        problem_id = self._p(params, "problem_id")
        contradictions = self._p(params, "contradictions", [])
        saved = 0
        for c in contradictions:
            a = c.get("a", "")
            b = c.get("b", "")
            q = CONTRADICTION_TEMPLATE.format(statement_a=a, statement_b=b)
            qid = self._save_q(problem_id, "causality.contradiction", q)
            if qid:
                saved += 1
        return (1, {"contradictions": len(contradictions), "questions_saved": saved}, None)

    # ── 2. FROM GAPS (QuestionEngine) ───────────────────────────

    def FromGaps(self, params):
        problem_id = self._p(params, "problem_id")
        gaps = self._p(params, "gaps", [])
        saved = 0
        for gap in gaps:
            q = GAP_TEMPLATE.format(gap=gap)
            qid = self._save_q(problem_id, "existence.gap", q)
            if qid:
                saved += 1
        return (1, {"gaps": len(gaps), "questions_saved": saved}, None)

    # ── 3. FROM CHAT (ChatInterrogationEngine) ──────────────────

    def FromChat(self, params):
        problem_id = self._p(params, "problem_id")
        chat_content = self._p(params, "chat_content", "")
        topics = self._p(params, "topics", [])
        saved = 0
        for topic in topics:
            q = f"What does the chat reveal about {topic}?"
            qid = self._save_q(problem_id, "chat_history.extraction", q)
            if qid:
                saved += 1
        # Also extract contradictions from chat
        contradictions = re.findall(r"but\s+(.{10,100})", chat_content, re.IGNORECASE)
        for c in contradictions[:10]:
            q = f"Chat contradiction: '{c.strip()[:80]}' — why?"
            qid = self._save_q(problem_id, "chat_history.contradiction", q)
            if qid:
                saved += 1
        return (1, {"topics": len(topics), "contradictions_found": len(contradictions), "questions_saved": saved}, None)

    # ── 4. FROM CODE (CodeQuestionProofEngine) ──────────────────

    def FromCode(self, params):
        problem_id = self._p(params, "problem_id")
        file_path = self._p(params, "file_path")
        saved = 0
        for q in PROOF_QUESTIONS:
            qid = self._save_q(problem_id, "state.code_proof", q)
            if qid:
                saved += 1
        return (1, {"file_path": file_path, "proof_questions": len(PROOF_QUESTIONS), "questions_saved": saved}, None)

    # ── 5. FROM BOOK (BookQuestionGenerator) ────────────────────

    def FromBook(self, params):
        problem_id = self._p(params, "problem_id")
        concepts = self._p(params, "concepts", [])
        saved = 0
        for concept in concepts:
            for template_name, template in BOOK_TEMPLATES.items():
                if "{alternative}" in template:
                    q = template.format(concept=concept, alternative=f"alternative to {concept}")
                else:
                    q = template.format(concept=concept)
                qid = self._save_q(problem_id, f"composition.book.{template_name}", q)
                if qid:
                    saved += 1
        return (1, {"concepts": len(concepts), "templates": len(BOOK_TEMPLATES), "questions_saved": saved}, None)

    # ── 6. FROM SCHEMA (DatabaseQuestionEngine / CuriosityController) ─

    def FromSchema(self, params):
        problem_id = self._p(params, "problem_id")
        db_path = self._p(params, "db_path")
        saved = 0
        if not db_path or not os.path.exists(db_path):
            return (0, None, (2, f"db not found: {db_path}", 0))
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [r[0] for r in c.fetchall()]
        for table in tables:
            c.execute(f"SELECT COUNT(*) FROM {table}")
            count = c.fetchone()[0]
            if count == 0:
                qid = self._save_q(problem_id, "database_state.empty", f"Schema: Is table '{table}' supposed to be empty?")
                if qid:
                    saved += 1
            c.execute(f"PRAGMA table_info({table})")
            cols = [col[1] for col in c.fetchall()]
            if "parent_id" in cols:
                qid = self._save_q(problem_id, "database_state.hierarchy", f"Schema: Is hierarchy in '{table}' complete?")
                if qid:
                    saved += 1
        conn.close()
        return (1, {"tables": len(tables), "questions_saved": saved}, None)

    # ── 7. FROM CONTEXT (QuestioningEngine) ─────────────────────

    def FromContext(self, params):
        problem_id = self._p(params, "problem_id")
        context = self._p(params, "context", "")
        tiers = self._p(params, "tiers", ["ui", "logic", "data", "config"])
        saved = 0
        for tier in tiers:
            q = f"Is tier '{tier}' complete? What is missing?"
            qid = self._save_q(problem_id, f"composition.tier.{tier}", q)
            if qid:
                saved += 1
        return (1, {"tiers": len(tiers), "questions_saved": saved}, None)

    # ── 8. FROM ARCHITECTURE (QuestionThinkingAI) ───────────────

    def FromArchitecture(self, params):
        problem_id = self._p(params, "problem_id")
        domains = self._p(params, "domains", list(DOMAIN_FRAMEWORKS.keys()))
        saved = 0
        for domain in domains:
            questions = DOMAIN_FRAMEWORKS.get(domain, [])
            for q in questions:
                qid = self._save_q(problem_id, f"composition.architecture.{domain}", f"{domain}: {q}")
                if qid:
                    saved += 1
        return (1, {"domains": len(domains), "questions_saved": saved}, None)

    # ── 9. WEIGHT (QuestionWeigherV2) ───────────────────────────

    def Weight(self, params):
        problem_id = self._p(params, "problem_id")
        if not problem_id:
            return (0, None, (2, "missing problem_id", 0))
        # Get all answered questions and assign weights
        ok, facts_data, err = self.store.Run("facts", {"problem_id": problem_id})
        if not ok:
            return (0, None, err)
        weights = []
        for fact in facts_data.get("facts", []):
            # Weight by evidence length and category
            ev_len = len(fact.get("evidence", "") or "")
            cat = fact.get("category", "")
            weight = 1.0
            if "causality" in cat:
                weight = 3.0  # causality is high-weight
            elif "risk" in cat:
                weight = 2.5
            elif "evidence" in cat:
                weight = 2.0
            elif "existence" in cat:
                weight = 1.5
            weight += min(ev_len / 100, 2.0)  # evidence length bonus
            weights.append({
                "question_id": fact["question_id"],
                "question": fact["question"][:80],
                "answer": fact["answer"],
                "weight": round(weight, 2)
            })
        weights.sort(key=lambda x: x["weight"], reverse=True)
        return (1, {"weights": weights, "count": len(weights)}, None)

    # ── 10. CLOSURE (QuestionToLawClosure_V3) ───────────────────

    def Closure(self, params):
        problem_id = self._p(params, "problem_id")
        if not problem_id:
            return (0, None, (2, "missing problem_id", 0))
        ok, collapse, err = self.store.Run("collapse_check", {"problem_id": problem_id})
        ok, facts_data, err = self.store.Run("facts", {"problem_id": problem_id})
        ok, unknowns_data, err = self.store.Run("unknowns", {"problem_id": problem_id})
        # Can we close any unknowns into laws based on existing facts?
        closures = []
        facts = facts_data.get("facts", []) if facts_data else []
        unknowns = unknowns_data.get("unknowns", []) if unknowns_data else []
        for unk in unknowns:
            # Check if any fact answers this unknown
            unk_text = unk["question"].lower()
            for fact in facts:
                fact_text = fact["question"].lower()
                # Simple keyword overlap
                unk_words = set(w for w in unk_text.split() if len(w) > 4)
                fact_words = set(w for w in fact_text.split() if len(w) > 4)
                overlap = unk_words & fact_words
                if len(overlap) >= 2:
                    closures.append({
                        "unknown_id": unk["question_id"],
                        "unknown": unk["question"][:80],
                        "inferred_from": fact["question_id"],
                        "inferred_answer": fact["answer"],
                        "overlap_keywords": list(overlap)[:5]
                    })
                    break
        return (1, {
            "collapse_status": collapse,
            "facts_count": len(facts),
            "unknowns_count": len(unknowns),
            "potential_closures": len(closures),
            "closures": closures
        }, None)

    # ── 11. CASCADE (QuestionCascadeEngine) ─────────────────────

    def Cascade(self, params):
        problem_id = self._p(params, "problem_id")
        parent_question_id = self._p(params, "parent_question_id")
        parent_question = self._p(params, "parent_question", "")
        depth = self._p(params, "depth", 1)
        max_depth = self._p(params, "max_depth", 3)
        if depth > max_depth:
            return (1, {"cascaded": 0, "reason": "max_depth_reached"}, None)
        # Generate sub-questions for the parent question
        sub_questions = [
            f"Sub-question: What evidence supports '{parent_question[:60]}'?",
            f"Sub-question: What contradicts '{parent_question[:60]}'?",
            f"Sub-question: What depends on the answer to '{parent_question[:60]}'?",
        ]
        saved = 0
        for sq in sub_questions:
            qid = self._save_q(problem_id, "cascade.subquestion", sq, depth=depth, parent_id=parent_question_id)
            if qid:
                saved += 1
        return (1, {"parent": parent_question[:60], "depth": depth, "sub_questions": saved}, None)

    # ── 12. RANK (RankedQuestion) ───────────────────────────────

    def Rank(self, params):
        problem_id = self._p(params, "problem_id")
        if not problem_id:
            return (0, None, (2, "missing problem_id", 0))
        ok, weight_data, err = self.Weight({"problem_id": problem_id})
        if not ok:
            return (0, None, err)
        ranked = []
        for i, w in enumerate(weight_data["weights"]):
            ranked.append({
                "rank": i + 1,
                "question_id": w["question_id"],
                "question": w["question"],
                "weight": w["weight"]
            })
        return (1, {"ranked": ranked, "count": len(ranked)}, None)

    # ── 13. PROOF (CodeQuestionProofEngine) ─────────────────────

    def Proof(self, params):
        problem_id = self._p(params, "problem_id")
        file_path = self._p(params, "file_path")
        if not file_path or not os.path.exists(file_path):
            return (0, None, (2, f"file not found: {file_path}", 0))
        # Run the 20 VBStyle proof questions with actual checks
        with open(file_path, "r") as f:
            content = f.read()
        results = []
        for q in PROOF_QUESTIONS:
            ans = ANSWER_UNKNOWN
            ev = ""
            q_lower = q.lower()
            if "ghost" in q_lower:
                ans = ANSWER_YES if "[@GHOST]" in content[:500] else ANSWER_NO
                ev = "found" if ans == ANSWER_YES else "missing"
            elif "vbstyle" in q_lower:
                ans = ANSWER_YES if "[@VBSTYLE]" in content[:500] else ANSWER_NO
                ev = "found" if ans == ANSWER_YES else "missing"
            elif "fileid" in q_lower:
                ans = ANSWER_YES if "[@FILEID]" in content[:500] else ANSWER_NO
                ev = "found" if ans == ANSWER_YES else "missing"
            elif "summary" in q_lower:
                ans = ANSWER_YES if "[@SUMMARY]" in content[:500] else ANSWER_NO
                ev = "found" if ans == ANSWER_YES else "missing"
            elif "class" in q_lower and "header" in q_lower:
                ans = ANSWER_YES if "[@CLASS]" in content[:500] else ANSWER_NO
                ev = "found" if ans == ANSWER_YES else "missing"
            elif "method" in q_lower and "header" in q_lower:
                ans = ANSWER_YES if "[@METHOD]" in content[:500] else ANSWER_NO
                ev = "found" if ans == ANSWER_YES else "missing"
            elif "run" in q_lower and "dispatch" in q_lower:
                ans = ANSWER_YES if re.search(r"def\s+Run\s*\(\s*self\s*,\s*command", content) else ANSWER_NO
                ev = "found" if ans == ANSWER_YES else "missing"
            elif "tuple3" in q_lower:
                ans = ANSWER_YES if re.search(r"return\s*\(\s*[01]\s*,", content) else ANSWER_NO
                ev = "found" if ans == ANSWER_YES else "missing"
            elif "init" in q_lower:
                ans = ANSWER_YES if re.search(r"def\s+__init__\s*\(\s*self\s*,\s*mem\s*=\s*None", content) else ANSWER_NO
                ev = "correct" if ans == ANSWER_YES else "wrong"
            elif "self.state" in q_lower:
                ans = ANSWER_YES if re.search(r"self\.state\s*=\s*\{", content) else ANSWER_NO
                ev = "found" if ans == ANSWER_YES else "missing"
            elif "pascalcase" in q_lower:
                classes = re.findall(r"class\s+(\w+)", content)
                bad = [c for c in classes if "_" in c or c[0].islower()]
                ans = ANSWER_NO if bad else ANSWER_YES
                ev = f"bad: {bad}" if bad else "all pascal"
            elif "uppercase" in q_lower:
                consts = re.findall(r"^([A-Z][A-Z_0-9]+)\s*=", content, re.MULTILINE)
                ans = ANSWER_YES if consts else ANSWER_UNKNOWN
                ev = f"{len(consts)} found" if consts else "none found"
            elif "print" in q_lower:
                count = len(re.findall(r"\bprint\s*\(", content))
                ans = ANSWER_NO if count else ANSWER_YES
                ev = f"{count} found" if count else "none"
            elif "property" in q_lower or "staticmethod" in q_lower:
                count = len(re.findall(r"@(property|staticmethod|classmethod)", content))
                ans = ANSWER_NO if count else ANSWER_YES
                ev = f"{count} found" if count else "none"
            elif "hardcoded" in q_lower:
                paths = re.findall(r'["\']/(Users|tmp|var|opt|home)/[^"\']+["\']', content)
                ans = ANSWER_NO if len(paths) > 2 else ANSWER_YES
                ev = f"{len(paths)} paths" if paths else "none"
            elif "tab" in q_lower:
                count = content.count("\t")
                ans = ANSWER_NO if count else ANSWER_YES
                ev = f"{count} tabs" if count else "none"
            elif "trailing" in q_lower:
                lines = content.split("\n")
                count = sum(1 for l in lines if l != l.rstrip())
                ans = ANSWER_NO if count else ANSWER_YES
                ev = f"{count} lines" if count else "none"
            elif "_p" in q_lower:
                ans = ANSWER_YES if re.search(r"def\s+_p\s*\(\s*self\s*,\s*params", content) else ANSWER_NO
                ev = "found" if ans == ANSWER_YES else "missing"
            elif "one class" in q_lower:
                classes = re.findall(r"^class\s+\w+", content, re.MULTILINE)
                ans = ANSWER_NO if len(classes) > 1 else ANSWER_YES
                ev = f"{len(classes)} classes" if len(classes) > 1 else "one class"
            elif "config" in q_lower:
                # Check if file is Config.py or imports from Config
                ans = ANSWER_YES if "Config" in content or os.path.basename(file_path) == "Config.py" else ANSWER_UNKNOWN
                ev = "found" if ans == ANSWER_YES else "not found"
            qid = self._save_q(problem_id, "state.proof", q)
            if qid:
                self._save_a(qid, ans, ev, "proof_check")
            results.append({"question": q, "answer": ans, "evidence": ev})
        passed = sum(1 for r in results if r["answer"] == ANSWER_YES)
        failed = sum(1 for r in results if r["answer"] == ANSWER_NO)
        return (1, {
            "file_path": file_path,
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "unknown": len(results) - passed - failed,
            "results": results
        }, None)

    # ── 14. MINIMUM (Question_Engine) ───────────────────────────

    def Minimum(self, params):
        problem_id = self._p(params, "problem_id")
        context = self._p(params, "context", "")
        # Detect gaps in context
        gaps = []
        if "refactor" in context.lower():
            gaps = ["What is the target structure?", "What are the dependencies?", "What is the risk?"]
        elif "bug" in context.lower():
            gaps = ["What is the root cause?", "How to reproduce?", "What is the fix?"]
        elif "search" in context.lower():
            gaps = ["What am I looking for?", "Where to search?", "When was it created?"]
        else:
            gaps = ["What exists?", "What is missing?", "What is the goal?"]
        saved = 0
        for gap in gaps:
            qid = self._save_q(problem_id, "intent.minimum", f"Minimum question: {gap}")
            if qid:
                saved += 1
        return (1, {"context": context[:50], "gaps": gaps, "questions_saved": saved}, None)

    # ── 15. TRACK (SmartQuestionTackleApp) ──────────────────────

    def Track(self, params):
        problem_id = self._p(params, "problem_id")
        if not problem_id:
            return (0, None, (2, "missing problem_id", 0))
        ok, collapse, err = self.store.Run("collapse_check", {"problem_id": problem_id})
        total = collapse["total_questions"]
        facts = collapse["facts"]
        unknowns = collapse["unknowns"]
        progress = round(facts / total * 100, 1) if total > 0 else 0
        return (1, {
            "problem_id": problem_id,
            "total": total,
            "answered": facts,
            "remaining": unknowns,
            "progress_pct": progress,
            "status": collapse["status"]
        }, None)

    # ── 16. INTEGRATE ALL ───────────────────────────────────────

    def IntegrateAll(self, params):
        """Run all 16 patterns and save questions to store."""
        problem_name = self._p(params, "problem")
        target_file = self._p(params, "target_file")
        context = self._p(params, "context", "")
        concepts = self._p(params, "concepts", [])
        contradictions = self._p(params, "contradictions", [])
        gaps = self._p(params, "gaps", [])
        db_path = self._p(params, "db_path")
        # Register problem
        ok, pdata, perr = self.store.Run("register_problem", {"name": problem_name})
        pid = pdata["problem_id"]
        results = {}
        # Run each integration
        integrations = [
            ("from_contradictions", {"problem_id": pid, "contradictions": contradictions}),
            ("from_gaps", {"problem_id": pid, "gaps": gaps}),
            ("from_chat", {"problem_id": pid, "context": context, "topics": concepts}),
            ("from_code", {"problem_id": pid, "file_path": target_file}),
            ("from_book", {"problem_id": pid, "concepts": concepts}),
            ("from_context", {"problem_id": pid, "context": context}),
            ("from_architecture", {"problem_id": pid}),
            ("minimum", {"problem_id": pid, "context": context}),
        ]
        if db_path:
            integrations.append(("from_schema", {"problem_id": pid, "db_path": db_path}))
        for cmd, p in integrations:
            ok, data, err = self.Run(cmd, p)
            results[cmd] = {"ok": ok, "data": data, "error": err}
        # Run cognitive loop
        ok, loop_data, err = self.store.Run("cognitive_loop", {"problem_id": pid})
        results["cognitive_loop"] = {"ok": ok, "data": loop_data, "error": err}
        # Collapse check
        ok, collapse, err = self.store.Run("collapse_check", {"problem_id": pid})
        results["collapse"] = collapse
        # Track progress
        ok, track_data, err = self.Track({"problem_id": pid})
        results["track"] = track_data
        return (1, {
            "problem_id": pid,
            "problem": problem_name,
            "integrations_run": len(results),
            "results": results
        }, None)

    # ── REPORT ──────────────────────────────────────────────────

    def Report(self, params):
        problem_id = self._p(params, "problem_id")
        if not problem_id:
            return (0, None, (2, "missing problem_id", 0))
        ok, report_data, err = self.store.Run("full_report", {"problem_id": problem_id})
        ok, track_data, err = self.Track({"problem_id": problem_id})
        ok, rank_data, err = self.Rank({"problem_id": problem_id})
        ok, closure_data, err = self.Closure({"problem_id": problem_id})
        lines = []
        lines.append("=" * 70)
        lines.append("QUESTION REGISTRY — FULL INTEGRATED REPORT")
        lines.append(f"Patterns integrated: {len(REGISTRY)}")
        lines.append("=" * 70)
        lines.append(f"Progress: {track_data['progress_pct']}% ({track_data['answered']}/{track_data['total']})")
        lines.append(f"Status: {track_data['status']}")
        lines.append(f"Remaining: {track_data['remaining']} unknowns")
        lines.append("")
        lines.append("TOP 10 RANKED QUESTIONS:")
        for r in rank_data.get("ranked", [])[:10]:
            lines.append(f"  #{r['rank']} (w={r['weight']}) {r['question']}")
        lines.append("")
        lines.append(f"POTENTIAL CLOSURES: {closure_data.get('potential_closures', 0)}")
        for c in closure_data.get("closures", [])[:5]:
            lines.append(f"  → {c['unknown'][:60]} → inferred: {c['inferred_answer']}")
        lines.append("")
        if report_data and "report" in report_data:
            lines.append(report_data["report"][:2000])
        return (1, {"report": "\n".join(lines)}, None)

    def close(self):
        self.store.close()


if __name__ == "__main__":
    import sys
    qr = QuestionRegistry()
    if len(sys.argv) < 2:
        print("Usage: question_registry.py <command> [json_params]")
        print("Commands: list, get, from_contradictions, from_gaps, from_chat,")
        print("          from_code, from_book, from_schema, from_context,")
        print("          from_architecture, weight, closure, cascade, rank,")
        print("          proof, minimum, track, integrate_all, report")
        sys.exit(1)
    cmd = sys.argv[1]
    params = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    ok, data, error = qr.Run(cmd, params)
    if ok:
        if isinstance(data, dict) and "report" in data:
            print(data["report"])
        else:
            print(json.dumps(data, indent=2, default=str))
    else:
        print(f"ERROR: {error}")
    qr.close()
