#[@GHOST]{file_path="chat_mover/bcl_chat_compressor.py" date="2026-06-29" author="Devin" session_id="bcl-compress" context="Stage 1 BCL chat compression — extract tokens from chat files"}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch self.state no-self._ no-print"}
#[@FILEID]{id="bcl_chat_compressor.py" domain="chat_mover" authority="BclChatCompressor"}
#[@SUMMARY]{summary="Stage 1 BCL compressor — extracts [@USER_SAYS] [@AI_SAYS] [@ERROR] [@FILE] [@COMMAND_RAN] [@FRUSTRATION_SIGNAL] [@QUESTION] [@TOPIC] tokens from chat files"}
#[@CLASS]{class="BclChatCompressor" domain="chat_mover" authority="single"}
#[@METHOD]{methods="Run,compress,extract_dialogue,extract_errors,extract_files,extract_commands,extract_frustration,extract_questions,extract_topics,format_output,write_stats,read_state,set_config"}

"""
bcl_chat_compressor — Stage 1 BCL chat compression.

Extracts BCL tokens from chat files (markdown exports or .pb via pb_reader).
Produces a compressed .md file with [@CHATSOURCE] linking back to source.

Usage (CLI):
    python3 bcl_chat_compressor.py --input "chat.md" --output "chat_BCL.md"
    python3 bcl_chat_compressor.py --input "chat.md" --dry-run

Usage (programmatic):
    from bcl_chat_compressor import BclChatCompressor
    c = BclChatCompressor()
    ok, data, err = c.Run("compress", {"input_path": "...", "output_path": "..."})
"""

import re
import hashlib
import argparse
from datetime import datetime
from pathlib import Path

# ── UPPERCASE CONSTANTS ──

FRUSTRATION_KEYWORDS = [
    "stuck", "frozen", "why", "weird", "shit", "hell", "damn",
    "broke", "broken", "crash", "hang", "hangs", "failed", "fail",
    "problem", "wrong", "error", "bug", "issue", "not working",
    "give up", "doesn't work", "dont work", "not working",
]

ERROR_PATTERNS = [
    (r"Traceback \(most recent call last\)", "python_traceback"),
    (r"\bError\b", "generic_error"),
    (r"\bTypeError\b", "type_error"),
    (r"\bValueError\b", "value_error"),
    (r"\bKeyError\b", "key_error"),
    (r"\bIndexError\b", "index_error"),
    (r"\bAttributeError\b", "attribute_error"),
    (r"\bModuleNotFoundError\b", "module_not_found"),
    (r"\bImportError\b", "import_error"),
    (r"\bFileNotFoundError\b", "file_not_found"),
    (r"\bNameError\b", "name_error"),
    (r"\bSyntaxError\b", "syntax_error"),
    (r"\bRuntimeError\b", "runtime_error"),
    (r"\bFAILED\b", "failed_marker"),
    (r"\bError:\s", "error_marker"),
    (r"exit code [1-9]", "exit_code_error"),
    (r"command not found", "not_found_error"),
    (r"permission denied", "permission_error"),
    (r"no such file or directory", "not_found_error"),
]

FILE_PATTERN = re.compile(r'[\w/.\-]+\.(py|c|h|md|sql|sh|json|yaml|yml|txt|js|ts|tsx|jsx|rb|go|rs|java|cpp|cc|hh)')
QUESTION_PATTERN = re.compile(r'\?')
USER_INPUT_HEADER = re.compile(r'^###\s*User Input', re.MULTILINE)
PLANNER_HEADER = re.compile(r'^###\s*Planner Response', re.MULTILINE)
COMMAND_ACCEPTED = re.compile(r'\*User accepted command\*')
COMMAND_REJECTED = re.compile(r'\*User rejected command\*')
CODE_BLOCK = re.compile(r'```(\w*)\n(.*?)```', re.DOTALL)

STAGE2_TOKENS = "[@PROBLEM] [@SOLUTION] [@ROOT_CAUSE] [@LESSON] [@SUCCESS] [@FAILED] [@DECISION] [@USER_PREF] [@MOOD] [@INTENT] [@AI_CORRECT] [@AI_WRONG]"


class BclChatCompressor:
    """Stage 1 BCL chat compressor — code-based token extraction."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "min_lines": 500,
                "chronological": True,
                "inline_lessons": True,
                "extract_errors": True,
                "extract_files": True,
                "extract_commands": True,
                "extract_frustration": True,
                "extract_questions": True,
                "extract_topics": True,
                "extract_dialogue": True,
            },
            "last_input": None,
            "last_output": None,
            "last_stats": None,
            "last_error": None,
        }

    def _p(self, params, key, default=None):
        """Extract param from dict safely."""
        if not params:
            return default
        return params.get(key, default)

    def Run(self, command, params=None):
        """Dispatch commands."""
        dispatch = {
            "compress": self.cmd_compress,
            "dry_run": self.cmd_dry_run,
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

    def cmd_compress(self, params):
        input_path = self._p(params, "input_path")
        output_path = self._p(params, "output_path")
        if not input_path:
            return (0, None, (1, "missing input_path", 0))
        if not output_path:
            base = Path(input_path).stem
            output_path = str(Path(input_path).parent / (base + "_BCL_stage1.md"))

        ok, data, err = self.compress_file(input_path, output_path)
        if err:
            return (0, None, err)
        self.state["last_input"] = input_path
        self.state["last_output"] = output_path
        self.state["last_stats"] = data.get("stats", {})
        return (1, data, None)

    def cmd_dry_run(self, params):
        input_path = self._p(params, "input_path")
        if not input_path:
            return (0, None, (1, "missing input_path", 0))
        ok, data, err = self.compress_file(input_path, None)
        if err:
            return (0, None, err)
        return (1, data, None)

    # ═══════════════════════════════════════════
    # CORE COMPRESSION
    # ═══════════════════════════════════════════

    def compress_file(self, input_path, output_path):
        """Read file, extract tokens, write output."""
        p = Path(input_path)
        if not p.exists():
            return (0, None, (2, "file not found: %s" % input_path, 0))

        content = p.read_text(encoding="utf-8", errors="replace")
        lines = content.split("\n")
        line_count = len(lines)

        # compute md5
        md5 = hashlib.md5(content.encode()).hexdigest()[:12]
        date_str = datetime.now().strftime("%Y-%m-%d")

        # extract tokens
        tokens = []
        cfg = self.state["config"]

        if cfg.get("extract_dialogue", True):
            tokens.extend(self.extract_dialogue(lines))
        if cfg.get("extract_errors", True):
            tokens.extend(self.extract_errors(lines))
        if cfg.get("extract_files", True):
            tokens.extend(self.extract_files(lines))
        if cfg.get("extract_commands", True):
            tokens.extend(self.extract_commands(lines))
        if cfg.get("extract_frustration", True):
            tokens.extend(self.extract_frustration(lines))
        if cfg.get("extract_questions", True):
            tokens.extend(self.extract_questions(lines))
        if cfg.get("extract_topics", True):
            tokens.extend(self.extract_topics(lines))

        # sort by line number (chronological)
        tokens.sort(key=lambda t: t.get("line", 0))

        # stats
        stats = self.compute_stats(tokens, line_count)

        # format output
        output_text = self.format_output(
            tokens, stats, input_path, line_count, md5, date_str
        )

        data = {
            "output_path": output_path,
            "tokens": tokens,
            "stats": stats,
            "token_count": len(tokens),
            "line_count": line_count,
            "md5": md5,
        }

        if output_path:
            Path(output_path).write_text(output_text, encoding="utf-8")
            data["output_path"] = output_path
        else:
            data["output_text"] = output_text

        return (1, data, None)

    # ═══════════════════════════════════════════
    # EXTRACTION METHODS
    # ═══════════════════════════════════════════

    def extract_dialogue(self, lines):
        """Extract [@USER_SAYS] and [@AI_SAYS] tokens."""
        tokens = []
        current_section = None
        current_text = []
        current_line = 0

        for i, line in enumerate(lines):
            line_num = i + 1

            if USER_INPUT_HEADER.match(line):
                if current_section and current_text:
                    tokens.append(self.make_dialogue_token(
                        current_section, current_line, "\n".join(current_text)
                    ))
                current_section = "user"
                current_text = []
                current_line = line_num
                continue

            if PLANNER_HEADER.match(line):
                if current_section and current_text:
                    tokens.append(self.make_dialogue_token(
                        current_section, current_line, "\n".join(current_text)
                    ))
                current_section = "ai"
                current_text = []
                current_line = line_num
                continue

            if current_section:
                stripped = line.strip()
                if stripped and not stripped.startswith("###"):
                    current_text.append(stripped)

        # flush last
        if current_section and current_text:
            tokens.append(self.make_dialogue_token(
                current_section, current_line, "\n".join(current_text)
            ))

        return tokens

    def make_dialogue_token(self, section, line_num, text):
        text_clean = text.strip()[:500]  # truncate
        tag = "USER_SAYS" if section == "user" else "AI_SAYS"
        return {
            "tag": tag,
            "line": line_num,
            "text": text_clean,
            "type": "dialogue",
        }

    def extract_errors(self, lines):
        """Extract [@ERROR] tokens using regex patterns."""
        tokens = []
        for i, line in enumerate(lines):
            line_num = i + 1
            for pattern, error_type in ERROR_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    text = line.strip()[:300]
                    tokens.append({
                        "tag": "ERROR",
                        "line": line_num,
                        "text": text,
                        "error_type": error_type,
                        "type": "error",
                    })
                    break  # one error type per line
        return tokens

    def extract_files(self, lines):
        """Extract [@FILE] tokens — file paths mentioned."""
        tokens = []
        seen = set()
        for i, line in enumerate(lines):
            line_num = i + 1
            for match in FILE_PATTERN.finditer(line):
                path = match.group(0)
                if len(path) < 5 or path.startswith("http"):
                    continue
                key = (path, line_num)
                if key not in seen:
                    seen.add(key)
                    tokens.append({
                        "tag": "FILE",
                        "line": line_num,
                        "text": path,
                        "type": "file",
                    })
        return tokens

    def extract_commands(self, lines):
        """Extract [@COMMAND_RAN] tokens."""
        tokens = []
        for i, line in enumerate(lines):
            line_num = i + 1
            if COMMAND_ACCEPTED.search(line):
                tokens.append({
                    "tag": "COMMAND_RAN",
                    "line": line_num,
                    "text": "user_accepted",
                    "type": "command",
                })
            elif COMMAND_REJECTED.search(line):
                tokens.append({
                    "tag": "COMMAND_RAN",
                    "line": line_num,
                    "text": "user_rejected",
                    "type": "command",
                })
        return tokens

    def extract_frustration(self, lines):
        """Extract [@FRUSTRATION_SIGNAL] tokens."""
        tokens = []
        for i, line in enumerate(lines):
            line_num = i + 1
            lower = line.lower()
            for kw in FRUSTRATION_KEYWORDS:
                if kw in lower:
                    tokens.append({
                        "tag": "FRUSTRATION_SIGNAL",
                        "line": line_num,
                        "text": "keyword=%s" % kw,
                        "type": "frustration",
                    })
                    break  # one keyword per line
        return tokens

    def extract_questions(self, lines):
        """Extract [@QUESTION] tokens — lines with ?."""
        tokens = []
        for i, line in enumerate(lines):
            line_num = i + 1
            if QUESTION_PATTERN.search(line) and line.strip():
                text = line.strip()[:300]
                tokens.append({
                    "tag": "QUESTION",
                    "line": line_num,
                    "text": text,
                    "type": "question",
                })
        return tokens

    def extract_topics(self, lines):
        """Extract [@TOPIC] tokens — markdown headings."""
        tokens = []
        for i, line in enumerate(lines):
            line_num = i + 1
            stripped = line.strip()
            if stripped.startswith("#") and not stripped.startswith("#[@"):
                topic = stripped.lstrip("#").strip()
                if topic and len(topic) > 2:
                    tokens.append({
                        "tag": "TOPIC",
                        "line": line_num,
                        "text": topic[:200],
                        "type": "topic",
                    })
        return tokens

    # ═══════════════════════════════════════════
    # FORMATTING
    # ═══════════════════════════════════════════

    def compute_stats(self, tokens, line_count):
        """Compute compression statistics."""
        stats = {"source_lines": line_count, "tokens": len(tokens)}
        tag_counts = {}
        for t in tokens:
            tag = t["tag"]
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        stats["tag_counts"] = tag_counts
        if line_count > 0:
            stats["compression_ratio"] = round(line_count / max(len(tokens), 1), 1)
        return stats

    def format_output(self, tokens, stats, source_path, line_count, md5, date_str):
        """Format tokens into BCL output file."""
        source_name = Path(source_path).name
        token_count = len(tokens)
        ratio = stats.get("compression_ratio", 0)

        lines = []

        # header
        lines.append("#[@FILE]      %s path=%s" % (Path(source_path).stem + "_BCL.md", source_path))
        lines.append("#[@FILEID]    md5=%s date=%s source=%s(%d_lines)" % (md5, date_str, source_name, line_count))
        lines.append("#[@SUMMARY]   BCL Stage 1 compression (code extraction). %d lines -> %d tokens." % (line_count, token_count))
        lines.append("#[@METHOD]    parse_structure -> regex_extraction -> dict_matching -> format_output")
        lines.append("#[@TOKENS]    Stage 1 only — AI semantic pass needed for %s" % STAGE2_TOKENS)
        lines.append("")
        lines.append("#[@CHAT]      source=%s lines=%d" % (source_name, line_count))
        lines.append('#[@CHATSOURCE]{path="%s";lines=%d;md5=%s;date="%s"}' % (source_path, line_count, md5, date_str))
        lines.append('#[@CHATFULLIDEARS]{source="%s";compressed_tokens=%d;compression_ratio=%s:1;stage="1_code_only";stage2_needed="%s"}' % (source_name, token_count, ratio, STAGE2_TOKENS))
        lines.append("")

        # body — chronological tokens
        for t in tokens:
            tag = t["tag"]
            line_num = t["line"]
            text = t["text"]

            if tag == "USER_SAYS":
                lines.append("#[@USER_SAYS] L%d: %s" % (line_num, text))
            elif tag == "AI_SAYS":
                lines.append("#[@AI_SAYS]   L%d: %s" % (line_num, text))
            elif tag == "ERROR":
                etype = t.get("error_type", "generic")
                lines.append("#[@ERROR]     L%d [%s] %s" % (line_num, etype, text))
            elif tag == "FILE":
                lines.append("#[@FILE]      L%d %s" % (line_num, text))
            elif tag == "COMMAND_RAN":
                lines.append("#[@COMMAND_RAN] L%d %s" % (line_num, text))
            elif tag == "FRUSTRATION_SIGNAL":
                lines.append("#[@FRUSTRATION_SIGNAL] L%d %s" % (line_num, text))
            elif tag == "QUESTION":
                lines.append("#[@QUESTION]  L%d: %s" % (line_num, text))
            elif tag == "TOPIC":
                lines.append("#[@TOPIC]     L%d: %s" % (line_num, text))

        # footer — stats
        lines.append("")
        lines.append("=" * 60)
        lines.append("# STAGE 1 STATS (code extraction only)")
        lines.append("=" * 60)
        lines.append("#[@STATS]     source_lines=%d -> tokens=%d" % (line_count, token_count))
        tag_counts = stats.get("tag_counts", {})
        for tag in sorted(tag_counts.keys()):
            lines.append("#[@STATS]     %s=%d" % (tag, tag_counts[tag]))

        lines.append("")
        lines.append("=" * 60)
        lines.append("# STAGE 2 NEEDED — AI must extract:")
        lines.append("=" * 60)
        lines.append("#[@NEEDED]    [@PROBLEM] [@SOLUTION] [@ROOT_CAUSE] [@LESSON]")
        lines.append("#[@NEEDED]    [@SUCCESS] [@FAILED] [@DECISION] [@USER_PREF]")
        lines.append("#[@NEEDED]    [@MOOD] [@INTENT] [@AI_CORRECT] [@AI_WRONG]")
        lines.append("#[@NEEDED]    Pair problems with solutions, inline lessons under problems")
        lines.append("#[@NEEDED]    Output in chronological order with cause chain")

        return "\n".join(lines) + "\n"


# ═══════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BCL Chat Compressor — Stage 1")
    parser.add_argument("--input", required=True, help="Source chat .md file")
    parser.add_argument("--output", help="Output BCL .md file (default: <input>_BCL_stage1.md)")
    parser.add_argument("--dry-run", action="store_true", help="Extract without writing file")
    args = parser.parse_args()

    compressor = BclChatCompressor()

    if args.dry_run:
        ok, data, err = compressor.Run("dry_run", {"input_path": args.input})
    else:
        ok, data, err = compressor.Run("compress", {
            "input_path": args.input,
            "output_path": args.output,
        })

    if err:
        code, desc, _ = err
        raise SystemExit("ERROR [%d]: %s" % (code, desc))

    stats = data.get("stats", {})
    token_count = data.get("token_count", 0)
    line_count = data.get("line_count", 0)
    output_path = data.get("output_path", "(dry run)")

    raise SystemExit(
        "OK: %d lines -> %d tokens (ratio %s:1)\nOutput: %s" % (
            line_count, token_count, stats.get("compression_ratio", 0), output_path
        )
    )
