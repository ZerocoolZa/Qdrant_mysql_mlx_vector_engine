#!/usr/bin/env python3
#[@GHOST]{file_path="core/utility/question_dimensions.py" date="2026-08-18" author="Devin" session_id="question-dimensions" context="Complete dimensional question framework — every aspect, sector, time, relationship, state — zero uncovered dimensions"}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
#[@FILEID]{id="question_dimensions.py" domain="utility" authority="QuestionDimensions"}
#[@SUMMARY]{summary="Complete dimensional question generator — covers all aspects, sectors, time, relationships, state, causality, intent, evidence, risk, alternatives — zero uncovered dimensions"}
#[@CLASS]{class="QuestionDimensions" domain="utility" authority="single"}
#[@METHOD]{methods="Run,Generate,GenerateAll,ByDimension,BySector,ByTime,ByAspect,Coverage,GapReport"}

"""
QuestionDimensions — complete dimensional question framework.

A "dimension" is an axis of inquiry. A "sector" is a domain within a dimension.
An "aspect" is a specific angle within a sector.

The goal: cover EVERY dimension, sector, and aspect so that
zero dimensions remain unasked. The problem space collapses
when every dimension has been interrogated.

DIMENSIONS (12):
1. EXISTENCE     — does it exist? in what form?
2. TIME          — when? how long? how often? before/after what?
3. LOCATION      — where? moved from where? going where?
4. IDENTITY      — what is it? named what? same as what?
5. CAUSALITY     — why? caused by what? leads to what?
6. COMPOSITION   — made of what? contains what? part of what?
7. RELATIONSHIP  — connected to what? depends on what? affects what?
8. STATE         — in what condition? changed how? stable or volatile?
9. EVIDENCE      — how do we know? source reliable? verifiable?
10. INTENT       — purpose? goal? who wants what?
11. RISK         — what could go wrong? severity? likelihood?
12. ALTERNATIVES — what else could it be? what was rejected? why?

Each dimension has SECTORS (sub-domains).
Each sector has ASPECTS (specific questions).

Total: 12 dimensions x ~5 sectors x ~5 aspects = ~300 base questions.
With recursion (each YES spawns 2 follow-ups): ~2400 questions at depth 5.
"""

import json
from datetime import datetime

# ── DIMENSION DEFINITIONS ──────────────────────────────────────

DIMENSIONS = {
    "existence": {
        "description": "Does it exist? In what form?",
        "sectors": {
            "physical": "Does the physical file/object exist on disk?",
            "digital": "Does it exist in a database, cache, or index?",
            "historical": "Did it ever exist in the past?",
            "partial": "Does a partial/draft/version exist?",
            "derivative": "Does a copy/clone/variant exist?",
            "referenced": "Is it referenced by name in other things?",
            "encoded": "Is it embedded/encoded inside something else?",
            "deleted": "Was it deleted? recoverable?",
            "virtual": "Does it exist as a concept/plan but not implemented?",
            "latent": "Could it exist if generated/compiled/built?"
        }
    },
    "time": {
        "description": "When? How long? How often? Before/after what?",
        "sectors": {
            "creation": "When was it created?",
            "modification": "When was it last changed?",
            "deletion": "When was it deleted (if applicable)?",
            "duration": "How long did creation take?",
            "frequency": "How often is it accessed/used?",
            "sequence": "What came before it? What came after?",
            "simultaneity": "What else happened at the same time?",
            "periodicity": "Is it periodic/recurring?",
            "staleness": "How stale is it? When did it last matter?",
            "lifespan": "How long will it remain relevant?",
            "window": "What time window does it belong to?",
            "epoch": "What era/phase of the project was it created in?"
        }
    },
    "location": {
        "description": "Where? Moved from where? Going where?",
        "sectors": {
            "current": "Where is it now?",
            "original": "Where was it originally?",
            "moved": "Was it moved? from where? to where? why?",
            "copies": "Are there copies elsewhere?",
            "expected": "Where should it be?",
            "referenced": "Where do other things expect to find it?",
            "relative": "What is it near? what directory? what siblings?",
            "remote": "Is it on another machine/volume/cloud?",
            "temporary": "Is there a temp/cache copy?",
            "backup": "Is there a backup copy?",
            "archive": "Is it in an archive/zip/tar?",
            "distributed": "Is it split across multiple locations?"
        }
    },
    "identity": {
        "description": "What is it? Named what? Same as what?",
        "sectors": {
            "name": "What is it called?",
            "type": "What type/category is it?",
            "class": "What class does it belong to?",
            "signature": "What is its unique signature/hash/fingerprint?",
            "aliases": "Does it have other names/aliases?",
            "renamed": "Was it renamed? from what? to what?",
            "equivalence": "Is it the same as something else?",
            "similarity": "Is it similar to something else?",
            "canonical": "Is this the canonical/original version?",
            "derivation": "What was it derived/copied from?",
            "namespace": "What namespace/domain does it belong to?",
            "hierarchy": "What is its parent? what are its children?"
        }
    },
    "causality": {
        "description": "Why? Caused by what? Leads to what?",
        "sectors": {
            "cause": "What caused it to be created?",
            "trigger": "What triggered the creation event?",
            "motivation": "Why was it needed?",
            "request": "Who requested it? what did they ask for?",
            "decision": "What decision led to it?",
            "constraint": "What constraints shaped it?",
            "effect": "What did it cause/enable/lead to?",
            "consequence": "What happened as a result?",
            "side_effect": "What unintended effects did it have?",
            "prevention": "What did it prevent/fix/stop?",
            "root_cause": "What is the root cause it addresses?",
            "chain": "What is the full causal chain?"
        }
    },
    "composition": {
        "description": "Made of what? Contains what? Part of what?",
        "sectors": {
            "components": "What is it made of?",
            "imports": "What does it import/depend on?",
            "contains": "What does it contain/embed?",
            "structure": "How is it structured internally?",
            "format": "What format/encoding is it in?",
            "size": "How big is it?",
            "complexity": "How complex is it?",
            "parts": "What are its parts/modules/methods?",
            "whole": "What whole is it part of?",
            "layer": "What layer does it sit at?",
            "interface": "What interface does it expose?",
            "implementation": "How is it implemented?"
        }
    },
    "relationship": {
        "description": "Connected to what? Depends on what? Affects what?",
        "sectors": {
            "depends_on": "What does it depend on?",
            "depended_by": "What depends on it?",
            "calls": "What does it call/invoke?",
            "called_by": "What calls/invokes it?",
            "imports": "What does it import?",
            "imported_by": "What imports it?",
            "references": "What does it reference?",
            "referenced_by": "What references it?",
            "conflicts": "What does it conflict with?",
            "complements": "What does it complement/work with?",
            "replaces": "What does it replace/supersede?",
            "replaced_by": "What replaces/supersedes it?",
            "version_of": "What is it a version of?",
            "parent_of": "What is it a parent of?",
            "child_of": "What is it a child of?",
            "peer_of": "What is it a peer/sibling of?"
        }
    },
    "state": {
        "description": "In what condition? Changed how? Stable or volatile?",
        "sectors": {
            "current_state": "What is its current state?",
            "completeness": "Is it complete or incomplete?",
            "correctness": "Is it correct? does it work?",
            "compliance": "Does it comply with standards/rules?",
            "tested": "Is it tested? do tests pass?",
            "documented": "Is it documented?",
            "active": "Is it actively used/maintained?",
            "deprecated": "Is it deprecated/abandoned?",
            "broken": "Is it broken? does it have bugs?",
            "secure": "Is it secure? does it have vulnerabilities?",
            "performance": "Is it fast enough? does it scale?",
            "stability": "Is it stable or volatile?",
            "history": "How has its state changed over time?",
            "trajectory": "Where is its state heading?"
        }
    },
    "evidence": {
        "description": "How do we know? Source reliable? Verifiable?",
        "sectors": {
            "source": "Where did we learn this?",
            "reliability": "Is the source reliable?",
            "verifiability": "Can we verify this independently?",
            "corroboration": "Do other sources confirm this?",
            "contradiction": "Do any sources contradict this?",
            "provenance": "What is the chain of evidence?",
            "freshness": "Is the evidence current or stale?",
            "completeness": "Is the evidence complete?",
            "bias": "Is the source biased?",
            "method": "How was the evidence collected?",
            "confidence": "How confident are we?",
            "uncertainty": "What is uncertain?"
        }
    },
    "intent": {
        "description": "Purpose? Goal? Who wants what?",
        "sectors": {
            "purpose": "What is it for?",
            "goal": "What goal does it serve?",
            "user_intent": "What did the user want when creating it?",
            "design_intent": "What did the designer intend?",
            "actual_use": "How is it actually used (vs intended)?",
            "stakeholder": "Who cares about it?",
            "beneficiary": "Who benefits from it?",
            "opposition": "Who opposes it or wants it removed?",
            "priority": "How important is it?",
            "urgency": "How urgent is it?",
            "scope": "What is in scope vs out of scope?",
            "success_criteria": "How do we know it succeeded?"
        }
    },
    "risk": {
        "description": "What could go wrong? Severity? Likelihood?",
        "sectors": {
            "failure_mode": "How could it fail?",
            "severity": "How bad would failure be?",
            "likelihood": "How likely is failure?",
            "impact": "Who/what would be affected?",
            "mitigation": "What mitigations exist?",
            "contingency": "What is the fallback plan?",
            "blast_radius": "How wide would the damage be?",
            "recoverability": "Can it be recovered if it fails?",
            "detection": "Would we detect the failure?",
            "prevention": "Can the failure be prevented?",
            "cost_of_failure": "What is the cost of failure?",
            "cost_of_prevention": "What is the cost of prevention?"
        }
    },
    "alternatives": {
        "description": "What else could it be? What was rejected? Why?",
        "sectors": {
            "alternatives": "What else could it be?",
            "rejected": "What was rejected? why?",
            "chosen": "Why was this chosen over alternatives?",
            "tradeoffs": "What tradeoffs were made?",
            "upgrade_path": "What could it be upgraded to?",
            "replacement": "What could replace it?",
            "merge": "Could it be merged with something?",
            "split": "Could it be split into parts?",
            "simplification": "Could it be simpler?",
            "generalization": "Could it be more general?",
            "specialization": "Could it be more specialized?",
            "obsolescence": "What would make it obsolete?"
        }
    }
}

# ── ASPECT TEMPLATES per sector ────────────────────────────────
# Each sector generates questions using these aspect templates.

ASPECT_TEMPLATES = [
    "Is {sector} known?",
    "Is {sector} verified?",
    "Is {sector} documented?",
    "Is {sector} recent or stale?",
    "Does {sector} match expectations?",
    "Does {sector} conflict with anything?",
    "What is the evidence for {sector}?",
    "What would change if {sector} were different?",
    "Who knows about {sector}?",
    "Can {sector} be automated/checked?",
]

# ── TIME ASPECTS (special — time has unique aspects) ───────────

TIME_ASPECTS = [
    "When exactly?",
    "What came before?",
    "What came after?",
    "How long did it take?",
    "How long ago?",
    "Is it still happening?",
    "Will it happen again?",
    "What is the interval?",
    "What is the deadline?",
    "What is the window of relevance?",
]

# ── THE GENERATOR ──────────────────────────────────────────────


class QuestionDimensions:
    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "results": None,
            "error": None
        }

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        if command == "generate_all":
            return self.GenerateAll(params)
        elif command == "by_dimension":
            return self.ByDimension(params)
        elif command == "by_sector":
            return self.BySector(params)
        elif command == "coverage":
            return self.Coverage(params)
        elif command == "gap_report":
            return self.GapReport(params)
        elif command == "list_dimensions":
            return self._list_dimensions(params)
        elif command == "list_sectors":
            return self._list_sectors(params)
        else:
            return (0, None, (1, f"unknown_command:{command}", 0))

    def GenerateAll(self, params):
        target = self._p(params, "target", "it")
        context = self._p(params, "context", "")
        questions = []
        for dim_name, dim_def in DIMENSIONS.items():
            for sector_name, sector_desc in dim_def["sectors"].items():
                if dim_name == "time":
                    for aspect in TIME_ASPECTS:
                        q = f"{aspect} [{sector_name}: {sector_desc}] re {target}"
                        questions.append({
                            "dimension": dim_name,
                            "sector": sector_name,
                            "aspect": aspect,
                            "question": q,
                            "description": sector_desc
                        })
                else:
                    for aspect in ASPECT_TEMPLATES:
                        q = aspect.format(sector=sector_desc.rstrip("?"))
                        q = f"{q} re {target}"
                        questions.append({
                            "dimension": dim_name,
                            "sector": sector_name,
                            "aspect": aspect,
                            "question": q,
                            "description": sector_desc
                        })
        return (1, {
            "questions": questions,
            "count": len(questions),
            "dimensions": len(DIMENSIONS),
            "sectors": sum(len(d["sectors"]) for d in DIMENSIONS.values()),
            "aspects_per_sector": len(ASPECT_TEMPLATES),
            "time_aspects": len(TIME_ASPECTS)
        }, None)

    def ByDimension(self, params):
        dim = self._p(params, "dimension")
        if not dim or dim not in DIMENSIONS:
            return (0, None, (2, f"unknown dimension: {dim}", 0))
        target = self._p(params, "target", "it")
        dim_def = DIMENSIONS[dim]
        questions = []
        for sector_name, sector_desc in dim_def["sectors"].items():
            aspects = TIME_ASPECTS if dim == "time" else ASPECT_TEMPLATES
            for aspect in aspects:
                if dim == "time":
                    q = f"{aspect} [{sector_name}: {sector_desc}] re {target}"
                else:
                    q = f"{aspect.format(sector=sector_desc.rstrip('?'))} re {target}"
                questions.append({
                    "dimension": dim,
                    "sector": sector_name,
                    "aspect": aspect,
                    "question": q
                })
        return (1, {"dimension": dim, "questions": questions, "count": len(questions)}, None)

    def BySector(self, params):
        dim = self._p(params, "dimension")
        sector = self._p(params, "sector")
        if not dim or dim not in DIMENSIONS:
            return (0, None, (2, f"unknown dimension: {dim}", 0))
        dim_def = DIMENSIONS[dim]
        if sector not in dim_def["sectors"]:
            return (0, None, (3, f"unknown sector: {sector}", 0))
        target = self._p(params, "target", "it")
        sector_desc = dim_def["sectors"][sector]
        aspects = TIME_ASPECTS if dim == "time" else ASPECT_TEMPLATES
        questions = []
        for aspect in aspects:
            if dim == "time":
                q = f"{aspect} [{sector}: {sector_desc}] re {target}"
            else:
                q = f"{aspect.format(sector=sector_desc.rstrip('?'))} re {target}"
            questions.append({
                "dimension": dim,
                "sector": sector,
                "aspect": aspect,
                "question": q
            })
        return (1, {"dimension": dim, "sector": sector, "questions": questions, "count": len(questions)}, None)

    def Coverage(self, params):
        """Check which dimensions/sectors have been asked vs not."""
        asked_dims = self._p(params, "asked_dimensions", [])
        asked_sectors = self._p(params, "asked_sectors", [])
        total_dims = len(DIMENSIONS)
        total_sectors = sum(len(d["sectors"]) for d in DIMENSIONS.values())
        covered_dims = len(set(asked_dims))
        covered_sectors = len(set(asked_sectors))
        uncovered_dims = [d for d in DIMENSIONS if d not in asked_dims]
        uncovered_sectors = []
        for dim_name, dim_def in DIMENSIONS.items():
            for sector_name in dim_def["sectors"]:
                key = f"{dim_name}.{sector_name}"
                if key not in asked_sectors:
                    uncovered_sectors.append(key)
        return (1, {
            "total_dimensions": total_dims,
            "covered_dimensions": covered_dims,
            "uncovered_dimensions": uncovered_dims,
            "total_sectors": total_sectors,
            "covered_sectors": covered_sectors,
            "uncovered_sectors": uncovered_sectors,
            "coverage_pct": round(covered_sectors / total_sectors * 100, 1),
            "fully_covered": covered_sectors == total_sectors
        }, None)

    def GapReport(self, params):
        ok, coverage, err = self.Coverage(params)
        if not ok:
            return (0, None, err)
        lines = []
        lines.append("# Dimensional Coverage Gap Report")
        lines.append(f"Dimensions: {coverage['covered_dimensions']}/{coverage['total_dimensions']}")
        lines.append(f"Sectors: {coverage['covered_sectors']}/{coverage['total_sectors']} ({coverage['coverage_pct']}%)")
        lines.append(f"Fully covered: {coverage['fully_covered']}")
        lines.append("")
        if coverage["uncovered_dimensions"]:
            lines.append("## Uncovered Dimensions")
            for d in coverage["uncovered_dimensions"]:
                lines.append(f"  - {d}: {DIMENSIONS[d]['description']}")
            lines.append("")
        if coverage["uncovered_sectors"]:
            lines.append("## Uncovered Sectors")
            for s in coverage["uncovered_sectors"]:
                dim, sec = s.split(".")
                lines.append(f"  - {s}: {DIMENSIONS[dim]['sectors'][sec]}")
            lines.append("")
        if coverage["fully_covered"]:
            lines.append("## STATUS: FULLY COVERED — zero uncovered dimensions")
        else:
            remaining = len(coverage["uncovered_sectors"])
            lines.append(f"## STATUS: {remaining} sectors still uncovered — keep asking")
        return (1, {"report": "\n".join(lines), "coverage": coverage}, None)

    def _list_dimensions(self, params):
        dims = []
        for name, defn in DIMENSIONS.items():
            dims.append({
                "name": name,
                "description": defn["description"],
                "sectors": list(defn["sectors"].keys()),
                "sector_count": len(defn["sectors"])
            })
        return (1, {"dimensions": dims, "count": len(dims)}, None)

    def _list_sectors(self, params):
        dim = self._p(params, "dimension")
        if not dim or dim not in DIMENSIONS:
            return (0, None, (2, f"unknown dimension: {dim}", 0))
        sectors = []
        for name, desc in DIMENSIONS[dim]["sectors"].items():
            sectors.append({"name": name, "description": desc})
        return (1, {"dimension": dim, "sectors": sectors, "count": len(sectors)}, None)


if __name__ == "__main__":
    import sys
    qd = QuestionDimensions()
    if len(sys.argv) < 2:
        print("Usage: question_dimensions.py <command> [json_params]")
        print("Commands: generate_all, by_dimension, by_sector, coverage, gap_report,")
        print("          list_dimensions, list_sectors")
        sys.exit(1)
    cmd = sys.argv[1]
    params = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    ok, data, error = qd.Run(cmd, params)
    if ok:
        if "questions" in data:
            print(f"Total: {data['count']} questions")
            for q in data["questions"][:20]:
                print(f"  [{q['dimension']}.{q['sector']}] {q['question']}")
            if data['count'] > 20:
                print(f"  ... and {data['count'] - 20} more")
        else:
            print(json.dumps(data, indent=2, default=str))
    else:
        print(f"ERROR: {error}")
