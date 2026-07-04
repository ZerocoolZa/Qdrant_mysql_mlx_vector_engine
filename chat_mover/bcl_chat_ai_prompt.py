#[@GHOST]{file_path="chat_mover/bcl_chat_ai_prompt.py" date="2026-06-29" author="Devin" session_id="bcl-compress" context="Stage 2 AI prompt builder — constructs prompt for semantic BCL extraction"}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
#[@FILEID]{id="bcl_chat_ai_prompt.py" domain="chat_mover" authority="BclChatAiPrompt"}
#[@SUMMARY]{summary="Stage 2 AI prompt builder — reads Stage 1 BCL tokens + source chat, builds prompt for AI semantic extraction"}
#[@CLASS]{class="BclChatAiPrompt" domain="chat_mover" authority="single"}
#[@METHOD]{methods="Run,build_prompt,format_instructions,include_stage1,include_source_context,read_state,set_config"}

"""
bcl_chat_ai_prompt — Stage 2 AI prompt builder for BCL chat compression.

Reads Stage 1 BCL tokens + source chat context, builds a prompt that instructs
an AI model to extract semantic tokens ([@PROBLEM], [@SOLUTION], [@LESSON], etc.).

Usage (CLI):
    python3 bcl_chat_ai_prompt.py --input stage1.md --source chat.md --output prompt.md

Usage (programmatic):
    from bcl_chat_ai_prompt import BclChatAiPrompt
    p = BclChatAiPrompt()
    ok, data, err = p.Run("build", {"stage1_path": "...", "source_path": "...", "output_path": "..."})
"""

import argparse
from datetime import datetime
from pathlib import Path

# ── UPPERCASE CONSTANTS ──

STAGE2_TOKENS = [
    ("[@INTENT]", "User intent — what the user was trying to achieve"),
    ("[@MOOD]", "User mood — inferred from word choice, punctuation, caps"),
    ("[@ROOT_CAUSE]", "Root cause — why an error or problem happened"),
    ("[@PROBLEM]", "Problem identified — issue that needed solving"),
    ("[@SOLUTION]", "Solution — how the problem was fixed"),
    ("[@FIX]", "Specific code fix applied — concrete change made"),
    ("[@LESSON]", "Lesson — generalized takeaway from the incident"),
    ("[@SUCCESS]", "Approach that worked — successful strategy"),
    ("[@FAILED]", "Approach that didn't work — failed strategy"),
    ("[@DECISION]", "Key decision point — important choice made"),
    ("[@ANSWER]", "AI answer to a user question"),
    ("[@USER_PREF]", "User preference extracted from dialogue"),
    ("[@PENDING]", "Outstanding tasks — things not yet done"),
    ("[@FUTURE]", "Future work identified — things to do later"),
    ("[@AI_CORRECT]", "AI response was correct"),
    ("[@AI_WRONG]", "AI response was wrong or misleading"),
]

PROMPT_TEMPLATE = """# BCL Stage 2 — Semantic Extraction Prompt

You are performing Stage 2 of BCL chat compression. Stage 1 (code extraction) has
already been completed. Your job is to read the Stage 1 tokens and the source chat,
then extract semantic tokens that code alone cannot identify.

## Input

### Stage 1 BCL Tokens
{stage1_content}

### Source Chat (first {source_lines_shown} of {source_total} lines)
{source_content}

## Instructions

1. Read the Stage 1 tokens above — they contain [@USER_SAYS], [@AI_SAYS], [@ERROR],
   [@FILE], [@COMMAND_RAN], [@FRUSTRATION_SIGNAL], [@QUESTION], [@TOPIC]

2. Read the source chat for full context

3. Extract these semantic tokens:

{token_list}

4. Output format — chronological timeline with cause chains:

```
# ─── T1: <topic summary> (lines X-Y) ───
#[@USER_SAYS] "<what user said>"
#[@AI_SAYS]   "<what AI responded>"
#[@INTENT]    <what user was trying to do>
#[@MOOD]      <user mood: frustrated/confused/happy/excited/angry>
#[@PROBLEM]   <issue identified>
#[@ROOT_CAUSE] <why it happened>
#[@SOLUTION]  <how it was fixed>
#[@FIX]       <specific code change>
#[@SUCCESS]   <if approach worked>
#[@FAILED]    <if approach didn't work>
#[@LESSON]    <generalized takeaway>
#[@DECISION]  <key decision made>
```

5. Rules:
   - Keep chronological order (by line number)
   - Place [@LESSON] inline under the problem it relates to
   - Pair [@PROBLEM] with [@SOLUTION]
   - Only include tokens that are clearly supported by the dialogue
   - Don't invent problems or solutions — only extract what's there
   - If an AI response was wrong, mark with [@AI_WRONG]
   - If an AI response was correct, mark with [@AI_CORRECT]
   - Include [@CHATSOURCE] and [@CHATFULLIDEARS] headers in output

6. Output the final BCL v2 file with:
   - [@CHATSOURCE]{{path="{source_path}";lines={source_total};md5="{md5}";date="{date}"}}
   - [@CHATFULLIDEARS]{{source="{source_name}";stage="2_code_plus_ai"}}
   - Chronological timeline entries
   - Stats footer

## Output

Write the complete BCL v2 file below:
"""


class BclChatAiPrompt:
    """Stage 2 AI prompt builder for BCL chat compression."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "source_context_lines": 500,
                "include_stage1": True,
                "include_source": True,
            },
            "last_prompt": None,
            "last_error": None,
        }

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        dispatch = {
            "build": self.cmd_build,
            "read_state": self.cmd_read_state,
            "set_config": self.cmd_set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, (1, "unknown_command: %s" % command, 0))
        return handler(params)

    def cmd_read_state(self, params):
        return (1, dict(self.state), None)

    def cmd_set_config(self, params):
        if not params:
            return (0, None, (1, "no params", 0))
        for key, val in params.items():
            if key in self.state["config"]:
                self.state["config"][key] = val
        return (1, dict(self.state["config"]), None)

    def cmd_build(self, params):
        stage1_path = self._p(params, "stage1_path")
        source_path = self._p(params, "source_path")
        output_path = self._p(params, "output_path")

        if not stage1_path:
            return (0, None, (1, "missing stage1_path", 0))
        if not source_path:
            return (0, None, (1, "missing source_path", 0))
        if not output_path:
            base = Path(source_path).stem
            output_path = str(Path(source_path).parent / (base + "_AI_PROMPT.md"))

        ok, data, err = self.build_prompt(stage1_path, source_path, output_path)
        if err:
            return (0, None, err)
        self.state["last_prompt"] = output_path
        return (1, data, None)

    # ═══════════════════════════════════════════
    # CORE
    # ═══════════════════════════════════════════

    def build_prompt(self, stage1_path, source_path, output_path):
        """Build the AI prompt from Stage 1 tokens + source chat."""
        sp1 = Path(stage1_path)
        sp = Path(source_path)

        if not sp1.exists():
            return (0, None, (2, "stage1 file not found: %s" % stage1_path, 0))
        if not sp.exists():
            return (0, None, (2, "source file not found: %s" % source_path, 0))

        stage1_content = sp1.read_text(encoding="utf-8", errors="replace")
        source_content = sp.read_text(encoding="utf-8", errors="replace")
        source_lines = source_content.split("\n")
        source_total = len(source_lines)

        # limit source context
        cfg = self.state["config"]
        max_lines = cfg.get("source_context_lines", 500)
        if source_total > max_lines:
            source_shown = "\n".join(source_lines[:max_lines])
            source_shown += "\n... (%d more lines truncated)" % (source_total - max_lines)
        else:
            source_shown = source_content

        # md5
        import hashlib
        md5 = hashlib.md5(source_content.encode()).hexdigest()[:12]
        date_str = datetime.now().strftime("%Y-%m-%d")

        # format token list
        token_list = "\n".join(
            "   - %s — %s" % (tag, desc) for tag, desc in STAGE2_TOKENS
        )

        # fill template
        prompt = PROMPT_TEMPLATE.format(
            stage1_content=stage1_content,
            source_content=source_shown,
            source_lines_shown=min(max_lines, source_total),
            source_total=source_total,
            token_list=token_list,
            source_path=source_path,
            source_name=sp.name,
            md5=md5,
            date=date_str,
        )

        # write
        Path(output_path).write_text(prompt, encoding="utf-8")

        data = {
            "output_path": output_path,
            "prompt_size": len(prompt),
            "stage1_size": len(stage1_content),
            "source_size": len(source_content),
            "source_lines": source_total,
            "source_lines_shown": min(max_lines, source_total),
        }
        return (1, data, None)


# ═══════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BCL Chat AI Prompt Builder — Stage 2")
    parser.add_argument("--input", required=True, help="Stage 1 BCL output file")
    parser.add_argument("--source", required=True, help="Original source chat file")
    parser.add_argument("--output", help="Output AI prompt file (default: <source>_AI_PROMPT.md)")
    parser.add_argument("--context-lines", type=int, default=500, help="Max source lines to include")
    args = parser.parse_args()

    builder = BclChatAiPrompt()
    builder.Run("set_config", {"source_context_lines": args.context_lines})

    ok, data, err = builder.Run("build", {
        "stage1_path": args.input,
        "source_path": args.source,
        "output_path": args.output,
    })

    if err:
        code, desc, _ = err
        raise SystemExit("ERROR [%d]: %s" % (code, desc))

    raise SystemExit(
        "OK: prompt written to %s (%d bytes)\nStage1: %d bytes, Source: %d lines (%d shown)" % (
            data["output_path"], data["prompt_size"],
            data["stage1_size"], data["source_lines"], data["source_lines_shown"],
        )
    )
