#!/usr/bin/env python3
#[@GHOST]{[@file<bcl_pattern_collector.py>][@state<active>][@date<2026-07-01>][@ver<2.0.0>][@auth<devin>]}
#[@VBSTYLE]{[@auth<devin>][@role<bcl_pattern_collector>][@return<Tuple3>][@orch<Dom_Db>][@no<decorators|print|hardcoded>]}

import os
import re
import difflib
from collections import defaultdict, namedtuple


class BclPatternCollector:
    """Scan, classify, detect canonical, repair, and report BCL bracket patterns.

    Domain: BCL pattern collection and canonical format repair.
    Authority: owns pattern scanning, classification, canonical detection, repair.
    """

    DEFAULT_ROOT_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine"
    SKIP_DIRS = (
        ".git", "__pycache__", ".devin", ".windsurf", ".codeium",
        ".cursor", "node_modules", ".tasks", "treasure_trove_backup",
        "snapshots", "logs",
    )
    FILE_EXTENSIONS = (".py", ".md", ".sql", ".sh", ".c", ".json", ".yaml", ".txt")
    MAX_EXAMPLES_PER_PATTERN = 50
    CONTEXT_LINES_AHEAD = 5

    BCL_TAG_RE = re.compile(r'\[@(\w+)\]')
    HEADER_BCL_RE = re.compile(r'^#\s*\[@(\w+)\]')
    BODY_BCL_RE = re.compile(r'^\s*\[@(\w+)\]')
    GHOST_HEADER_RE = re.compile(r'^#\[@GHOST\]\{')
    VBSTYLE_HEADER_RE = re.compile(r'^#\[@VBSTYLE\]\{')
    WCL_WIDGET_RE = re.compile(r'#\s*\[@WIDGET\]\{')
    KV_ANGLE_RE = re.compile(r'\[@(\w+)<([^>]*)>\]')
    KV_QUOTED_RE = re.compile(r'(\w+)="([^"]*)"')
    SEMICOLON_QUOTED_RE = re.compile(r'"([^"]*)"\s*;\s*"([^"]*)"')

    Example = namedtuple("Example", ["file", "line", "text", "commented"])

    ClassificationRule = namedtuple("ClassificationRule", ["name", "predicate"])

    HEADER_RULES = [
        ClassificationRule("ghost_header", lambda s, ctx: BclPatternCollector.GHOST_HEADER_RE.match(s)),
        ClassificationRule("vbstyle_header", lambda s, ctx: BclPatternCollector.VBSTYLE_HEADER_RE.match(s)),
        ClassificationRule("wcl_widget", lambda s, ctx: BclPatternCollector.WCL_WIDGET_RE.search(s)),
        ClassificationRule("header_keyvalue", lambda s, ctx: re.search(r'\w+="[^"]*"', s)),
        ClassificationRule("header_angle", lambda s, ctx: re.search(r'\[@\w+<', s)),
        ClassificationRule("header_semicolon", lambda s, ctx: ';' in s and '"' in s),
        ClassificationRule("header_other", lambda s, ctx: True),
    ]

    CONTENT_RULES = [
        ClassificationRule("content_quoted_semicolon", lambda s, ctx: s.endswith('";')),
        ClassificationRule("content_quoted_nosemicolon", lambda s, ctx: s.endswith('"')),
        ClassificationRule("content_quoted_trailing_quote", lambda s, ctx: s.endswith('";"')),
        ClassificationRule("content_quoted_other", lambda s, ctx: True),
    ]

    LIST_RULES = [
        ClassificationRule("list_paren_semicolon_empty", lambda s, ctx: '";"' in s and s.endswith(';\"\"")')),
        ClassificationRule("list_paren_semicolon_noempty", lambda s, ctx: '";"' in s),
        ClassificationRule("list_paren_comma", lambda s, ctx: '","' in s),
        ClassificationRule("list_paren_doubled_quote", lambda s, ctx: '"";' in s),
        ClassificationRule("list_paren_other", lambda s, ctx: True),
    ]

    KEYVALUE_RULES = [
        ClassificationRule("keyvalue_quoted_semicolon", lambda s, ctx: s.endswith('";')),
        ClassificationRule("keyvalue_quoted_nosemicolon", lambda s, ctx: s.endswith('"')),
        ClassificationRule("keyvalue_quoted_trailing_quote", lambda s, ctx: s.endswith('";"')),
        ClassificationRule("keyvalue_quoted_other", lambda s, ctx: True),
    ]

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "root_path": self.DEFAULT_ROOT_PATH,
                "skip_dirs": list(self.SKIP_DIRS),
                "file_extensions": list(self.FILE_EXTENSIONS),
                "max_examples": self.MAX_EXAMPLES_PER_PATTERN,
            },
            "patterns": {},
            "canonical": None,
            "results": {},
        }

    def _p(self, params, key, default=None):
        if params is None:
            return default
        return params.get(key, default)

    def read_state(self):
        return {
            "config": dict(self.state["config"]),
            "canonical": self.state["canonical"],
            "pattern_count": len(self.state["patterns"]),
        }

    def set_config(self, config):
        if config is None:
            return (0, None, ("CFG_NULL", "config is None", 0))
        for key, value in config.items():
            self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def Run(self, command, params=None):
        dispatch = {
            "scan": self.Scan,
            "detect_canonical": self.DetectCanonical,
            "repair": self.Repair,
            "report": self.Report,
            "diff": self.Diff,
            "read_state": lambda p: (1, self.read_state(), None),
            "set_config": lambda p: self.set_config(p),
            "close": lambda p: self.Close(),
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_CMD", "unknown command: " + str(command), 0))
        return handler(params)

    def Close(self):
        """Close any open resources. Returns Tuple3."""
        return (1, {"closed": True}, None)

    def ClassifyFormat(self, line, context_lines=None):
        """Classify the BCL format of a line into a list of pattern signatures.

        Returns (patterns, is_commented). Uses rules tables for data-driven dispatch.
        """
        stripped = line.strip()
        patterns = []
        is_commented = stripped.startswith("#")
        ctx = context_lines or []

        if is_commented and self.BCL_TAG_RE.search(stripped):
            patterns.append(self._match_rules(self.HEADER_RULES, stripped, ctx))
            return patterns, is_commented

        if self.BODY_BCL_RE.match(stripped):
            patterns.extend(self._classify_body(stripped, ctx))
            return patterns, is_commented

        if stripped.startswith('"'):
            if re.match(r'^"[\w]+":\s*"', stripped):
                patterns.append(self._match_rules(self.KEYVALUE_RULES, stripped, ctx))
            else:
                patterns.append(self._match_rules(self.CONTENT_RULES, stripped, ctx))
            return patterns, is_commented

        if stripped.startswith("(") and stripped.endswith(")"):
            patterns.append(self._match_rules(self.LIST_RULES, stripped, ctx))
            return patterns, is_commented

        return patterns, is_commented

    def _match_rules(self, rules, stripped, ctx):
        """Return the first matching rule name from a rules table."""
        for rule in rules:
            if rule.predicate(stripped, ctx):
                return rule.name
        return "unknown"

    def _classify_body(self, stripped, ctx):
        """Classify body-style BCL blocks (inline vs multiline)."""
        patterns = ["body_multiline"]
        has_brace_same_line = stripped.endswith("{") or re.search(r'\[@\w+\]\{', stripped)

        if has_brace_same_line:
            patterns = []
            if re.search(r'\[@\w+\]\{.*\)', stripped):
                inner = re.search(r'\((.*)\)', stripped)
                content = inner.group(1) if inner else ""
                if '";"' in content:
                    patterns.append("body_inline_paren_semicolon")
                elif '","' in content:
                    patterns.append("body_inline_paren_comma")
                elif ";" in content and '"' in content:
                    patterns.append("body_inline_paren_mixed")
                else:
                    patterns.append("body_inline_paren_other")
            elif re.search(r'\[@\w+\]\{.*"', stripped):
                patterns.append("body_inline_quoted_semicolon" if ';' in stripped else "body_inline_quoted")
            else:
                patterns.append("body_inline_other")
            return patterns

        for cl in ctx[:self.CONTEXT_LINES_AHEAD]:
            cs = cl.strip()
            if cs.startswith("(") and cs.endswith(")"):
                if '";"' in cs:
                    patterns.append("body_multiline_paren_semicolon")
                elif '","' in cs:
                    patterns.append("body_multiline_paren_comma")
                else:
                    patterns.append("body_multiline_paren_other")
            elif cs.startswith('"') and cs.endswith('";'):
                patterns.append("body_multiline_quoted_semicolon")
            elif cs.startswith('"') and cs.endswith('"'):
                patterns.append("body_multiline_quoted_nosemicolon")
            elif cs == "}":
                break
        return patterns

    def Scan(self, params=None):
        """Scan the codebase for BCL bracket patterns across all file types."""
        root_path = self.state["config"].get("root_path", self.DEFAULT_ROOT_PATH)
        skip_dirs = set(self.state["config"].get("skip_dirs", list(self.SKIP_DIRS)))
        extensions = tuple(self.state["config"].get("file_extensions", list(self.FILE_EXTENSIONS)))
        max_examples = self.state["config"].get("max_examples", self.MAX_EXAMPLES_PER_PATTERN)

        if not os.path.isdir(root_path):
            return (0, None, ("ROOT_MISSING", "root_path does not exist: " + str(root_path), 0))

        pattern_examples = defaultdict(list)

        for root, dirs, files in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for fname in files:
                if not fname.endswith(extensions):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", errors="replace") as f:
                        lines = f.readlines()
                except Exception:
                    continue

                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if not stripped:
                        continue
                    if "[@" not in stripped and not stripped.startswith('"') and not stripped.startswith("("):
                        continue
                    if self.BCL_TAG_RE.search(stripped) or stripped.startswith('"') or stripped.startswith("("):
                        context = lines[i + 1:i + 1 + self.CONTEXT_LINES_AHEAD] if i + 1 < len(lines) else []
                        detected, is_commented = self.ClassifyFormat(line, context)
                        rel_path = os.path.relpath(fpath, root_path)
                        for p in detected:
                            ex = self.Example(file=rel_path, line=i + 1, text=stripped[:120], commented=is_commented)
                            if len(pattern_examples[p]) < max_examples:
                                pattern_examples[p].append(ex)

        self.state["patterns"] = dict(pattern_examples)
        return (1, dict(pattern_examples), None)

    def DetectCanonical(self, params=None):
        """Detect the canonical pattern by frequency and file coverage."""
        patterns = self.state.get("patterns", {})
        if not patterns:
            return (0, None, ("NO_PATTERNS", "no patterns scanned; run scan first", 0))

        def score(pname):
            examples = patterns[pname]
            return (len(examples), len(set(ex.file for ex in examples)))

        best = max(patterns.keys(), key=score)
        self.state["canonical"] = best
        return (1, best, None)

    def _build_conversions(self):
        """Build the conversion registry."""
        return {
            ("header_keyvalue", "header_angle"): self.ConvertKeyvalueToAngle,
            ("header_angle", "header_keyvalue"): self.ConvertAngleToKeyvalue,
        }

    def Repair(self, params=None):
        """Repair non-canonical patterns to match the canonical format."""
        dry_run = self._p(params, "dry_run", True)
        files_filter = self._p(params, "files", None)
        patterns_filter = self._p(params, "patterns", None)
        canonical = self.state.get("canonical")
        if not canonical:
            return (0, None, ("NO_CANONICAL", "no canonical set; run detect_canonical first", 0))

        patterns = self.state.get("patterns", {})
        if not patterns:
            return (0, None, ("NO_PATTERNS", "no patterns scanned; run scan first", 0))

        root_path = self.state["config"].get("root_path", self.DEFAULT_ROOT_PATH)
        target_files = self._collect_target_files(patterns, canonical, patterns_filter, files_filter)
        conversions = self._build_conversions()

        changes = []
        for rel_file in sorted(target_files):
            abs_path = os.path.join(root_path, rel_file)
            if not os.path.isfile(abs_path):
                continue
            new_lines, file_changes = self._scan_and_convert(abs_path, rel_file, canonical, conversions)
            if file_changes:
                changes.extend(file_changes)
                if not dry_run:
                    try:
                        with open(abs_path, "w") as f:
                            f.writelines(new_lines)
                    except Exception as exc:
                        return (0, None, ("WRITE_FAIL", str(exc), 0))

        return (1, changes, None)

    def _collect_target_files(self, patterns, canonical, patterns_filter, files_filter):
        """Collect the set of files that contain non-canonical patterns."""
        target_files = set()
        for pname, examples in patterns.items():
            if pname == canonical:
                continue
            if patterns_filter is not None and pname not in patterns_filter:
                continue
            for ex in examples:
                if files_filter is not None and ex.file not in files_filter:
                    continue
                target_files.add(ex.file)
        return target_files

    def _scan_and_convert(self, abs_path, rel_file, canonical, conversions):
        """Shared logic: read file, classify each line, convert non-canonical.

        Returns (new_lines, file_changes).
        """
        try:
            with open(abs_path, "r", errors="replace") as f:
                lines = f.readlines()
        except Exception:
            return [], []

        new_lines = list(lines)
        file_changes = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            context = lines[i + 1:i + 1 + self.CONTEXT_LINES_AHEAD] if i + 1 < len(lines) else []
            detected, _ = self.ClassifyFormat(line, context)
            if not detected or all(p == canonical for p in detected):
                continue
            converted = self._convert_with_registry(line, detected, canonical, conversions)
            if converted is not None and converted != line:
                file_changes.append({
                    "file": rel_file,
                    "line": i + 1,
                    "before": stripped,
                    "after": converted.strip(),
                })
                new_lines[i] = converted
        return new_lines, file_changes

    def _convert_with_registry(self, line, detected, canonical, conversions):
        """Look up conversion function from registry; return converted line or None."""
        for source_pattern in detected:
            key = (source_pattern, canonical)
            converter = conversions.get(key)
            if converter is not None:
                return converter(line)
        return None

    def ConvertKeyvalueToAngle(self, line):
        """Convert key="value" pairs inside a header BCL to [@key<value>] format."""
        match = re.match(r'^(\s*#\s*\[@\w+\]\{)(.*)(\}\s*)$', line.rstrip("\n"))
        if not match:
            return None
        prefix, body, suffix = match.group(1), match.group(2), match.group(3)
        kvs = self.KV_QUOTED_RE.findall(body)
        if not kvs:
            return None
        new_body = "".join("[@%s<%s>]" % (k, v) for k, v in kvs)
        return prefix + new_body + suffix + "\n"

    def ConvertAngleToKeyvalue(self, line):
        """Convert [@key<value>] pairs inside a header BCL to key="value" format."""
        match = re.match(r'^(\s*#\s*\[@\w+\]\{)(.*)(\}\s*)$', line.rstrip("\n"))
        if not match:
            return None
        prefix, body, suffix = match.group(1), match.group(2), match.group(3)
        kvs = self.KV_ANGLE_RE.findall(body)
        if not kvs:
            return None
        new_body = ";".join('%s="%s"' % (k, v) for k, v in kvs)
        return prefix + new_body + suffix + "\n"

    REPORT_TEMPLATE = (
        "BCL Pattern Collector Report\n"
        "={sep}\n"
        "Total patterns detected: {count}\n"
        "Canonical format: {canonical}\n\n"
        "{pattern_details}\n"
        "{repair_section}"
    )

    def Report(self, params=None):
        """Generate a text report of all patterns, counts, files, canonical, repair targets."""
        patterns = self.state.get("patterns", {})
        canonical = self.state.get("canonical")
        if not patterns:
            return (1, "No patterns scanned. Run scan first.", None)

        pattern_lines = []
        for pname in sorted(patterns.keys()):
            examples = patterns[pname]
            files = set(ex.file for ex in examples)
            marker = " [CANONICAL]" if pname == canonical else ""
            pattern_lines.append("  %s:%s" % (pname, marker))
            pattern_lines.append("    Examples: %d, Files: %d" % (len(examples), len(files)))
            for ex in examples[:3]:
                pattern_lines.append("      L%d %s: %s" % (ex.line, ex.file, ex.text[:80]))
            pattern_lines.append("")

        if canonical:
            repair_targets = [p for p in patterns if p != canonical]
            repair_section = "Repair targets (%d):\n" % len(repair_targets)
            repair_section += "\n".join("  - %s" % p for p in repair_targets)
        else:
            repair_section = "Repair targets: (run detect_canonical first)"

        report = self.REPORT_TEMPLATE.format(
            sep="=" * 40,
            count=len(patterns),
            canonical=canonical or "(not set)",
            pattern_details="\n".join(pattern_lines),
            repair_section=repair_section,
        )
        return (1, report, None)

    def Diff(self, params=None):
        """Generate a unified diff showing what repair would do to a single file."""
        file_rel = self._p(params, "file")
        if not file_rel:
            return (0, None, ("NO_FILE", "file param required", 0))

        canonical = self.state.get("canonical")
        if not canonical:
            return (0, None, ("NO_CANONICAL", "no canonical set; run detect_canonical first", 0))

        root_path = self.state["config"].get("root_path", self.DEFAULT_ROOT_PATH)
        abs_path = os.path.join(root_path, file_rel)
        if not os.path.isfile(abs_path):
            return (0, None, ("FILE_MISSING", "file not found: " + str(abs_path), 0))

        try:
            with open(abs_path, "r", errors="replace") as f:
                original_lines = f.readlines()
        except Exception as exc:
            return (0, None, ("READ_FAIL", str(exc), 0))

        conversions = self._build_conversions()
        new_lines, _ = self._scan_and_convert(abs_path, file_rel, canonical, conversions)

        diff = difflib.unified_diff(
            original_lines, new_lines,
            fromfile="a/" + file_rel,
            tofile="b/" + file_rel,
            lineterm="",
        )
        return (1, "\n".join(diff), None)
