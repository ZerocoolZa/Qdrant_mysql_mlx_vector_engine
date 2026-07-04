#[@GHOST]{file_path="core/Dom_Benchmark/Scoring.py" date="2026-07-04" author="Devin" session_id="benchmark-framework" context="Scoring engine for benchmark framework. Scores fix candidates based on correctness, conservatism, speed, self-validation, false-positive detection, and penalty weights."}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
#[@FILEID]{id="Scoring.py" domain="dom_benchmark" authority="Scoring"}
#[@SUMMARY]{summary="Scoring engine — scores fix candidates. Base score + fix bonus - remaining errors - changed lines - attempts + clean bonus + conservative bonus + fast bonus + self-validating bonus - false positive penalty - syntax error penalty - timeout penalty - crash penalty."}
#[@CLASS]{class="Scoring" domain="dom_benchmark" authority="scorer"}
#[@METHOD]{method="score_candidate" type="scorer"}
#[@METHOD]{method="score_batch" type="scorer"}
#[@METHOD]{method="rank" type="ranker"}
#[@METHOD]{method="confidence_adjust" type="adjuster"}
#[@METHOD]{method="promote_demote" type="adjuster"}

"""Scoring — Scores fix candidates for the benchmark framework.

Scoring formula:
  score = BASE
        + fixes * PER_FIX
        - remaining_errors * PER_REMAINING_ERROR
        - changed_lines * PER_CHANGED_LINE
        - attempts * PER_ATTEMPT
        - passes * PER_PASS
        + (clean ? BONUS_CLEAN : 0)
        + (conservative ? BONUS_CONSERVATIVE : 0)
        + (fast ? BONUS_FAST : 0)
        + (self_validating ? BONUS_SELF_VALIDATING : 0)
        - (false_positive ? PENALTY_FALSE_POSITIVE : 0)
        - (syntax_error ? PENALTY_SYNTAX_ERROR : 0)
        - (timeout ? PENALTY_TIMEOUT : 0)
        - (crash ? PENALTY_CRASH : 0)
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

try:
    import Config
    from ErrorModel import FixCandidate, ValidationResult
except ImportError:
    from . import Config
    from .ErrorModel import FixCandidate, ValidationResult


class Scoring:
    """Scoring engine for fix candidates.

    Methods:
        score_candidate: score a single fix candidate
        score_batch: score a list of candidates
        rank: rank candidates by score
        confidence_adjust: adjust confidence based on results
        promote_demote: determine if a case should be promoted/demoted
    """

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param or {}
        self.state = {
            "class": "Scoring",
            "total_scored": 0,
            "total_promoted": 0,
            "total_demoted": 0,
            "avg_score": 0.0,
            "best_score": 0,
            "worst_score": 0,
        }

    def _p(self, label, value):
        """Helper to log state transitions."""
        self.state["last_" + label] = value

    def Run(self, command, params=None):
        """Dispatch a command. Returns Tuple3."""
        dispatch = {
            "score_candidate": self.cmd_score_candidate,
            "score_batch": self.cmd_score_batch,
            "rank": self.cmd_rank,
            "confidence_adjust": self.cmd_confidence_adjust,
            "promote_demote": self.cmd_promote_demote,
            "read_state": self.cmd_read_state,
            "set_config": self.cmd_set_config,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, ("SCORING_UNKNOWN_COMMAND", command, 0))
        return handler(params or {})

    def cmd_read_state(self, params):
        return (1, dict(self.state), None)

    def cmd_set_config(self, params):
        for key, value in params.items():
            self.state[key] = value
        return (1, {"updated": len(params)}, None)

    def cmd_score_candidate(self, params):
        candidate = params.get("candidate")
        validation = params.get("validation")
        original_code = params.get("original_code", "")
        if not candidate:
            return (0, None, ("SCORING_NO_CANDIDATE", "no candidate provided", 0))
        if isinstance(candidate, dict):
            candidate = FixCandidate.from_dict(candidate)
        if validation and isinstance(validation, dict):
            validation = ValidationResult.from_dict(validation)
        score = self.score_candidate(candidate, validation, original_code)
        return (1, {"score": score, "candidate": candidate.to_dict()}, None)

    def cmd_score_batch(self, params):
        candidates = params.get("candidates", [])
        validation = params.get("validation")
        original_code = params.get("original_code", "")
        if not candidates:
            return (0, None, ("SCORING_NO_CANDIDATES", "no candidates provided", 0))
        results = []
        for c in candidates:
            cand = FixCandidate.from_dict(c) if isinstance(c, dict) else c
            val = ValidationResult.from_dict(validation) if isinstance(validation, dict) else validation
            score = self.score_candidate(cand, val, original_code)
            results.append({"strategy": cand.strategy, "score": score, "passed": cand.passed})
        ranked = sorted(results, key=lambda r: r["score"], reverse=True)
        return (1, {"results": ranked, "best": ranked[0] if ranked else None}, None)

    def cmd_rank(self, params):
        candidates = params.get("candidates", [])
        if not candidates:
            return (0, None, ("SCORING_NO_CANDIDATES", "no candidates to rank", 0))
        ranked = self.rank(candidates)
        return (1, {"ranked": ranked, "best": ranked[0] if ranked else None}, None)

    def cmd_confidence_adjust(self, params):
        current_confidence = params.get("confidence", Config.INITIAL_CONFIDENCE)
        success = params.get("success", False)
        new_confidence = self.confidence_adjust(current_confidence, success)
        return (1, {"old": current_confidence, "new": new_confidence, "success": success}, None)

    def cmd_promote_demote(self, params):
        confidence = params.get("confidence", Config.INITIAL_CONFIDENCE)
        pass_count = params.get("pass_count", 0)
        run_count = params.get("run_count", 0)
        action = self.promote_demote(confidence, pass_count, run_count)
        return (1, {"action": action, "confidence": confidence, "pass_count": pass_count, "run_count": run_count}, None)

    def score_candidate(
        self,
        candidate: FixCandidate,
        validation: Optional[ValidationResult] = None,
        original_code: str = "",
    ) -> int:
        """Score a single fix candidate.

        Args:
            candidate: the FixCandidate to score
            validation: optional ValidationResult for additional penalties/bonuses
            original_code: the original broken code (for change counting)

        Returns:
            integer score (higher is better)
        """
        score = Config.SCORE_BASE

        # Positive: fixes applied
        score += candidate.changes * Config.SCORE_PER_FIX

        # Negative: remaining errors
        score -= candidate.remaining_errors * Config.SCORE_PER_REMAINING_ERROR

        # Negative: changed lines (prefer minimal changes)
        score -= candidate.changes * Config.SCORE_PER_CHANGED_LINE

        # Negative: attempts (prefer fewer attempts)
        score -= candidate.attempts * Config.SCORE_PER_ATTEMPT

        # Bonus: clean (no remaining errors)
        if candidate.remaining_errors == 0:
            score += Config.SCORE_BONUS_CLEAN

        # Bonus: conservative strategy
        if candidate.strategy.lower().startswith("conservative"):
            score += Config.SCORE_BONUS_CONSERVATIVE

        # Bonus: fast execution
        if candidate.timing_ms > 0 and candidate.timing_ms < 100:
            score += Config.SCORE_BONUS_FAST

        # Bonus: self-validating
        if candidate.self_validating:
            score += Config.SCORE_BONUS_SELF_VALIDATING

        # Validation-based adjustments
        if validation:
            # Penalty: false positive
            if validation.false_positive:
                score += Config.SCORE_PENALTY_FALSE_POSITIVE

            # Penalty: syntax error in fixed code
            if validation.syntax_error:
                score += Config.SCORE_PENALTY_SYNTAX_ERROR

            # Penalty: runtime error on re-run
            if validation.runtime_error and not validation.re_run_passed:
                score += Config.SCORE_PENALTY_CRASH

            # Bonus: all validation checks passed
            if (validation.py_compile_passed and
                    validation.ast_parse_passed and
                    validation.re_run_passed and
                    validation.self_validating_passed):
                score += Config.SCORE_BONUS_CLEAN

        # Update candidate score
        candidate.score = score

        # Update state
        self.state["total_scored"] += 1
        if score > self.state["best_score"]:
            self.state["best_score"] = score
        if self.state["worst_score"] == 0 or score < self.state["worst_score"]:
            self.state["worst_score"] = score
        total = self.state["total_scored"]
        current_avg = self.state["avg_score"]
        self.state["avg_score"] = ((current_avg * (total - 1)) + score) / total

        self._p("score", score)
        return score

    def rank(self, candidates: List[Any]) -> List[Dict[str, Any]]:
        """Rank candidates by score (highest first).

        Args:
            candidates: list of FixCandidate objects or dicts

        Returns:
            list of dicts with strategy, score, passed, sorted by score desc
        """
        results = []
        for c in candidates:
            if isinstance(c, FixCandidate):
                results.append({
                    "strategy": c.strategy,
                    "score": c.score,
                    "passed": c.passed,
                    "changes": c.changes,
                    "remaining": c.remaining_errors,
                })
            elif isinstance(c, dict):
                results.append({
                    "strategy": c.get("strategy", ""),
                    "score": c.get("score", 0),
                    "passed": c.get("passed", False),
                    "changes": c.get("changes", 0),
                    "remaining": c.get("remaining_errors", 0),
                })
        return sorted(results, key=lambda r: (r["score"], -r["remaining"]), reverse=True)

    def confidence_adjust(self, current: float, success: bool) -> float:
        """Adjust confidence based on success/failure.

        Args:
            current: current confidence (0.0-1.0)
            success: whether the fix was successful

        Returns:
            new confidence (0.0-1.0)
        """
        if success:
            new_val = current * Config.CONFIDENCE_BOOST
            return min(new_val, Config.MAX_CONFIDENCE)
        else:
            new_val = current * Config.CONFIDENCE_DECAY
            return max(new_val, Config.MIN_CONFIDENCE)

    def promote_demote(self, confidence: float, pass_count: int, run_count: int) -> str:
        """Determine if a case should be promoted, demoted, or kept.

        Args:
            confidence: current confidence
            pass_count: number of successful fixes
            run_count: total number of runs

        Returns:
            "promote", "demote", or "keep"
        """
        if confidence >= Config.PROMOTE_THRESHOLD and pass_count >= 2:
            self.state["total_promoted"] += 1
            return "promote"
        if confidence <= Config.DEMOTE_THRESHOLD and run_count >= 3:
            self.state["total_demoted"] += 1
            return "demote"
        return "keep"

    def merge_duplicates(self, cases: List[Any]) -> List[Any]:
        """Merge duplicate patterns (same fingerprint).

        Args:
            cases: list of ErrorModel objects

        Returns:
            deduplicated list with merged stats
        """
        seen = {}
        merged = []
        for case in cases:
            fp = case.traceback_fingerprint or case.fingerprint()
            if fp in seen:
                existing = seen[fp]
                existing.run_count += case.run_count
                existing.pass_count += case.pass_count
                existing.fail_count += case.fail_count
                if case.best_score > existing.best_score:
                    existing.best_score = case.best_score
                    existing.best_strategy = case.best_strategy
                existing.confidence = max(existing.confidence, case.confidence)
            else:
                if not case.traceback_fingerprint:
                    case.traceback_fingerprint = fp
                seen[fp] = case
                merged.append(case)
        return merged

    def detect_false_positive(
        self,
        candidate: FixCandidate,
        validation: ValidationResult,
        original_code: str,
    ) -> bool:
        """Detect if a fix is a false positive.

        A false positive is when:
        - The fix "passes" but doesn't actually change the code
        - The fix passes but the original code also passes (no error to fix)
        - The fix introduces a new error that masks the original

        Args:
            candidate: the fix candidate
            validation: validation results
            original_code: the original broken code

        Returns:
            True if false positive detected
        """
        # Fix didn't change anything
        if candidate.fixed_code.strip() == original_code.strip():
            return True

        # Fix passes but has syntax error
        if candidate.passed and validation.syntax_error:
            return True

        # Fix passes but py_compile fails
        if candidate.passed and not validation.py_compile_passed:
            return True

        # Fix passes but AST parse fails
        if candidate.passed and not validation.ast_parse_passed:
            return True

        return False
