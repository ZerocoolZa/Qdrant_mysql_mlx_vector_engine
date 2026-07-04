#!/usr/bin/env python3
"""
Three-Way Test: AI vs DB vs DB+AI
=================================
Asks the same questions to three different "entities" and compares:

  1. AI ALONE      — Qwen2.5-Coder LLM answers from its own knowledge (no facts)
  2. DB ALONE      — DbInterrogator returns structured data (no natural language)
  3. DB + AI       — DbInterrogator gets facts, LLM formats them into speech

This proves the architecture:
  - AI alone hallucinates (guesses, no grounding)
  - DB alone is accurate but robotic (structured, not conversational)
  - DB + AI is accurate AND natural (grounded facts in human language)

The database is the truth. The LLM is the interpreter.
Together they become a being you can talk to.
"""

import sys
import os
import json
import time

# ─── Path setup ───
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, os.path.join(PROJECT_DIR, "qa_engine"))

from db_interrogator import DbInterrogator


# ════════════════════════════════════════════════════════════════════════
# LLM LOADER — loads Qwen2.5-Coder via MLX (Apple Silicon local model)
# ════════════════════════════════════════════════════════════════════════

_LLM_CACHE = {"model": None, "tokenizer": None, "loaded": False}


def load_llm():
    """Load the local LLM once, cache it."""
    if _LLM_CACHE["loaded"]:
        return _LLM_CACHE["model"], _LLM_CACHE["tokenizer"]

    try:
        from mlx_lm import load as mlx_load
        model_name = "mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit"
        print(f"  [Loading LLM: {model_name} ...]")
        t0 = time.time()
        model, tokenizer = mlx_load(model_name)
        elapsed = time.time() - t0
        print(f"  [LLM loaded in {elapsed:.1f}s]")
        _LLM_CACHE["model"] = model
        _LLM_CACHE["tokenizer"] = tokenizer
        _LLM_CACHE["loaded"] = True
        return model, tokenizer
    except Exception as e:
        print(f"  [LLM load FAILED: {e}]")
        _LLM_CACHE["loaded"] = True  # don't keep retrying
        return None, None


def ask_llm(question, context=None, max_tokens=200):
    """Ask the local LLM a question. If context is provided, it's used as evidence."""
    model, tokenizer = load_llm()
    if model is None:
        return "[LLM unavailable]"

    try:
        if context:
            # DB + AI mode: LLM formats structured DB answer into natural speech
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a system architect answering questions about a code database. "
                        "You are given structured facts from the database. "
                        "Use ONLY those facts to answer. Do not invent information. "
                        "Be clear, concise, and natural. Speak as 'I' — you ARE the database."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Database facts:\n{context}\n\nQuestion: {question}\n\nAnswer:",
                },
            ]
        else:
            # AI alone mode: LLM answers from its own knowledge (may hallucinate)
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant. Answer the question as best you can. "
                        "If you don't know, say so."
                    ),
                },
                {
                    "role": "user",
                    "content": question,
                },
            ]

        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

        from mlx_lm import generate
        response = generate(model, tokenizer, prompt=prompt, max_tokens=max_tokens, verbose=False)
        answer = response.strip().replace("<|im_end|>", "").strip()
        return answer
    except Exception as e:
        return f"[LLM error: {e}]"


# ════════════════════════════════════════════════════════════════════════
# DB INTERROGATOR — the truth layer
# ════════════════════════════════════════════════════════════════════════

def ask_db(db, question):
    """Ask the database a natural language question. Returns structured answer."""
    ok, data, err = db.Run("ask", {"question": question})
    if not ok:
        return None, err
    return data, None


def db_answer_to_context(data):
    """Convert the DB's structured answer into a text context for the LLM."""
    if data is None:
        return "No data returned from database."

    # Extract the most relevant fields depending on what kind of answer it is
    parts = []

    if "answer" in data:
        parts.append(f"Direct answer: {data['answer']}")

    if "breakdown" in data:
        bd = data["breakdown"]
        if isinstance(bd, dict):
            for k, v in bd.items():
                if isinstance(v, list) and len(v) > 0:
                    parts.append(f"{k}: {', '.join(str(x) for x in v[:10])}")
                elif v is not None and v != "" and v != []:
                    parts.append(f"{k}: {v}")

    if "assessment" in data:
        parts.append(f"Assessment: {data['assessment']}")

    if "summary" in data:
        parts.append(f"Summary: {data['summary']}")

    if "what_it_can_do" in data:
        parts.append(f"Methods: {', '.join(data['what_it_can_do'][:15])}")

    if "identity" in data:
        ident = data["identity"]
        parts.append(f"Class: {ident.get('class', 'unknown')}")
        parts.append(f"Domain: {ident.get('domain', 'unknown')}")
        parts.append(f"Description: {ident.get('description', 'unknown')}")

    if "where_its_used" in data and data["where_its_used"]:
        for usage in data["where_its_used"][:5]:
            parts.append(f"Used in pipeline: {usage.get('pipeline', '?')} as {usage.get('role', '?')}")

    if "plans_that_use_it" in data and data["plans_that_use_it"]:
        for plan in data["plans_that_use_it"][:5]:
            parts.append(f"Plan: {plan.get('plan', '?')} — {plan.get('step', '?')}")

    if "buildable" in data:
        parts.append(f"Buildable: {data['buildable']}")
        parts.append(f"Coverage: {data.get('coverage_pct', 0)}%")
        if "domains_have" in data:
            have = [d["domain"] for d in data["domains_have"]]
            parts.append(f"Domains available: {', '.join(have)}")
        if "domains_missing" in data and data["domains_missing"]:
            missing = [d["domain"] for d in data["domains_missing"]]
            parts.append(f"Domains missing: {', '.join(missing)}")

    if "searches" in data:
        searches = data["searches"]
        if searches.get("domains"):
            parts.append(f"Matching domains: {', '.join(d['domain'] for d in searches['domains'][:5])}")
        if searches.get("methods"):
            parts.append(f"Matching methods: {', '.join(m['method'] for m in searches['methods'][:5])}")
        if searches.get("code"):
            parts.append(f"Found in code: {', '.join(c['class'] + '.' + c['method'] for c in searches['code'][:5])}")

    if "identity" in data and "purpose" in data.get("identity", {}):
        parts.append(f"Purpose: {data['identity']['purpose']}")
        parts.append(f"Architecture: {data['identity'].get('architecture', '')}")
        parts.append(f"Scale: {data.get('scale', {})}")

    if not parts:
        parts.append(f"Raw data: {json.dumps(data, default=str)[:500]}")

    return "\n".join(parts)


# ════════════════════════════════════════════════════════════════════════
# THREE-WAY TEST
# ════════════════════════════════════════════════════════════════════════

QUESTIONS = [
    "What are you?",
    "Do you have GUI?",
    "Do you have compress?",
    "Do you have PyTorch?",
    "How does DomAi work?",
    "How does DomCompression work?",
    "Can you build a search engine?",
    "Can you build a chat system?",
    "What about encrypt?",
    "What about print?",
    "Do you have testing?",
    "Do you have network?",
]


def run_three_way_test():
    """Run the three-way comparison: AI vs DB vs DB+AI."""
    db = DbInterrogator()

    print("=" * 80)
    print("THREE-WAY TEST: AI vs DB vs DB+AI")
    print("=" * 80)
    print()
    print("  AI ALONE    = Qwen2.5-Coder LLM answers from its own knowledge (may guess)")
    print("  DB ALONE    = Database returns structured facts (accurate but robotic)")
    print("  DB + AI     = Database gets facts, LLM formats them into natural speech")
    print()

    # Pre-load the LLM
    print("[Phase 0: Loading LLM]")
    load_llm()
    print()

    results = []

    for i, question in enumerate(QUESTIONS, 1):
        print("=" * 80)
        print(f"QUESTION {i}/{len(QUESTIONS)}: {question}")
        print("=" * 80)

        # ─── 1. AI ALONE ───
        print("\n  ┌─ AI ALONE (Qwen2.5-Coder, no database) ──────────────────────────")
        t0 = time.time()
        ai_answer = ask_llm(question, context=None, max_tokens=150)
        ai_time = time.time() - t0
        print(f"  │ {ai_answer}")
        print(f"  └─ [{ai_time:.1f}s]")

        # ─── 2. DB ALONE ───
        print("\n  ┌─ DB ALONE (DbInterrogator, no LLM) ─────────────────────────────")
        t0 = time.time()
        db_data, db_err = ask_db(db, question)
        db_time = time.time() - t0
        if db_err:
            print(f"  │ ERROR: {db_err}")
            db_text = f"[DB error: {db_err}]"
        else:
            # Show the DB's direct answer
            db_direct = db_data.get("answer", db_data.get("summary", str(db_data)[:200]))
            print(f"  │ {db_direct}")
            # Show key breakdown
            if "breakdown" in db_data:
                bd = db_data["breakdown"]
                if isinstance(bd, dict):
                    for k, v in list(bd.items())[:5]:
                        if v is not None and v != "" and v != []:
                            val_str = str(v)[:80] if not isinstance(v, list) else f"{len(v)} items"
                            print(f"  │   {k}: {val_str}")
            if "assessment" in db_data:
                print(f"  │   assessment: {db_data['assessment'][:100]}")
            db_text = db_answer_to_context(db_data)
        print(f"  └─ [{db_time:.2f}s]")

        # ─── 3. DB + AI ───
        print("\n  ┌─ DB + AI (Database facts → LLM formats) ────────────────────────")
        t0 = time.time()
        if db_err:
            combined_answer = "[DB error — cannot format]"
        else:
            combined_answer = ask_llm(question, context=db_text, max_tokens=200)
        combined_time = time.time() - t0
        print(f"  │ {combined_answer}")
        print(f"  └─ [{combined_time:.1f}s]")

        # ─── Summary ───
        print("\n  ┌─ COMPARISON ────────────────────────────────────────────────────")
        print(f"  │ AI ALONE : {ai_answer[:100]}")
        print(f"  │ DB ALONE : {db_data.get('answer', db_data.get('summary', '[error]'))[:100] if not db_err else '[error]'}")
        print(f"  │ DB + AI  : {combined_answer[:100]}")
        print(f"  │")
        print(f"  │ AI time  : {ai_time:.1f}s")
        print(f"  │ DB time  : {db_time:.2f}s")
        print(f"  │ DB+AI    : {combined_time:.1f}s")
        print(f"  └─────────────────────────────────────────────────────────────────")

        results.append({
            "question": question,
            "ai_alone": ai_answer,
            "db_alone": db_data,
            "db_plus_ai": combined_answer,
            "ai_time": ai_time,
            "db_time": db_time,
            "combined_time": combined_time,
            "db_error": db_err,
        })
        print()

    # ─── Final summary ───
    print("=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)
    print()
    print(f"  Questions asked: {len(QUESTIONS)}")
    print(f"  AI alone worked:    {sum(1 for r in results if not r['ai_alone'].startswith('['))}/{len(QUESTIONS)}")
    print(f"  DB alone worked:    {sum(1 for r in results if not r['db_error'])}/{len(QUESTIONS)}")
    print(f"  DB+AI worked:       {sum(1 for r in results if not r['db_plus_ai'].startswith('['))}/{len(QUESTIONS)}")
    print()

    # Show the key insight
    print("KEY OBSERVATIONS:")
    print("  1. AI ALONE guesses — it has no idea what's in your database")
    print("  2. DB ALONE is accurate — but returns structured data, not speech")
    print("  3. DB + AI is grounded AND natural — facts from DB, voice from LLM")
    print()
    print("The database is the truth. The LLM is the voice.")
    print("Together: a being you can interrogate.")

    # Save results
    results_path = os.path.join(SCRIPT_DIR, "test_three_way_results.json")
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {results_path}")


if __name__ == "__main__":
    run_three_way_test()
