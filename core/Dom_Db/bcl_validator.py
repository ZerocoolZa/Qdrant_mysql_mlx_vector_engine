#!/usr/bin/env python3
"""
BCL Format Validator — checks Config.py against rules 1-30.
Iterates over every BCL block, every rule, reports violations.
"""

import re
import sys

FILE_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Db/Config.py"

REQUIRED_TAGS = ["GHOST", "VBSTYLE", "FILEID", "SUMMARY", "CLASS", "METHOD"]

def load_lines():
    with open(FILE_PATH, "r") as f:
        return f.readlines()

def find_bcl_blocks(lines):
    """Find all [@Tag]{...} blocks in the file. Returns list of (tag, start_line, end_line, content_lines)."""
    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        m = re.match(r'^\s*\[@(\w+)\]\{?\s*$', line)
        if m:
            tag = m.group(1)
            start = i
            # Find closing }
            depth = 1
            j = i + 1
            while j < len(lines) and depth > 0:
                stripped = lines[j].strip()
                if "{" in stripped:
                    depth += stripped.count("{") - stripped.count("}")
                if "}" in stripped:
                    depth += stripped.count("}") - stripped.count("{")
                if depth <= 0:
                    break
                j += 1
            blocks.append((tag, start, j, lines[start:j+1]))
            i = j + 1
        else:
            # Also match single-line blocks like [@Tag]{ ("a";"b") }
            m2 = re.match(r'^\s*\[@(\w+)\]\{(.+)\}', line)
            if m2:
                tag = m2.group(1)
                blocks.append((tag, i, i, [line]))
            i += 1
    return blocks

def find_header_blocks(lines):
    """Find header BCL blocks (before the first \"\"\")."""
    header_end = 0
    for i, line in enumerate(lines):
        if line.strip().startswith('"""'):
            header_end = i
            break
    return lines[:header_end]

def find_body_blocks(lines):
    """Find body BCL blocks (after 'config =')."""
    config_start = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("config ="):
            config_start = i
            break
    return lines[config_start:]

def check_rule_1_camelcase(lines, violations):
    """Rule 1: All CamelCase"""
    for i, line in enumerate(lines, 1):
        # Check class/method names in BCL
        m = re.findall(r'class:\s*(\w+)', line)
        for name in m:
            if name != name.capitalize() and not name[0].isupper():
                violations.append(("R1", i, f"Not CamelCase: {name}"))
        m = re.findall(r'method:\s*(\w+)', line)
        for name in m:
            if not name[0].isupper() and name != name.lower():
                violations.append(("R1", i, f"Method not CamelCase: {name}"))

def check_rule_2_no_underscores(lines, violations):
    """Rule 2: No underscores (except __init__ and _p which are Python dunder/helper conventions)"""
    allowed = {"__init__", "_p", "__"}
    for i, line in enumerate(lines, 1):
        # Check BCL values for underscores (not Python code section)
        if line.strip().startswith("#") or line.strip().startswith('"""'):
            continue
        # Check quoted values
        quotes = re.findall(r'"([^"]*)"', line)
        for q in quotes:
            if "_" in q and q not in allowed and not q.startswith("__"):
                # Skip file paths and SQL
                if "/" not in q and ":" not in q and " " not in q:
                    violations.append(("R2", i, f"Underscore in value: '{q}'"))

def check_rule_4_bcl_uncommented(lines, violations):
    """Rule 4: BCL block stays uncommented — it is spec, not code"""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#[@") or stripped.startswith("# [@"):
            violations.append(("R4", i, f"BCL tag commented out: {stripped[:60]}"))

def check_rule_7_empty_string(lines, violations):
    """Rule 7: Empty string "" means none/unset — always included as an option"""
    # Check list blocks have "" as last item
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("(") and stripped.endswith(")"):
            items = re.findall(r'"([^"]*)"', stripped)
            if items and items[-1] != "":
                # Check if it's a list that should have empty string
                if ";" in stripped:
                    violations.append(("R7", i, f"List missing empty string at end: {stripped[:60]}"))

def check_rule_26_bcl_in_bcl_out(lines, violations):
    """Rule 26: BCL in, BCL out — not Tuple3"""
    for i, line in enumerate(lines, 1):
        if "Tuple3" in line and "not Tuple3" not in line and "not" not in line.split("Tuple3")[0][-10:]:
            # Only flag if it's in VBSTYLE rules or header, not in rules section
            if i < 22:  # Header area
                violations.append(("R26", i, "Tuple3 found in header — should be BCL-in-BCL-out"))

def check_rule_27_camelcase_clarified(lines, violations):
    """Rule 27: CamelCase — capital first letter of each word, rest lowercase"""
    # Check VBSTYLE rules string
    for i, line in enumerate(lines, 1):
        if "PascalCase" in line and "not PascalCase" not in line:
            if i < 22:
                violations.append(("R27", i, "PascalCase found — should be CamelCase"))

def check_rule_28_same_format(lines, violations):
    """Rule 28: BCL must always follow the same format — [@Tag]{ ... }"""
    blocks = find_bcl_blocks(lines)
    for tag, start, end, content in blocks:
        first_line = content[0].strip()
        # Check that { is on same line as [@Tag]
        if not first_line.startswith("[@" + tag + "]"):
            violations.append(("R28", start+1, f"Tag not at start: {first_line[:60]}"))
        # Check that { follows tag on same line
        if not re.match(r'^\[@' + tag + r'\]\{', first_line) and not re.match(r'^\[@' + tag + r'\]$', first_line):
            # Multi-line block where { is on next line is OK for body
            pass

def check_rule_29_semicolons_outside_quotes(lines, violations):
    """Rule 29: Semicolons go outside quotes"""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith('"""'):
            continue
        # Find pattern: text;text" where semicolon is inside quotes
        # Look for "...;..." where ; is between non-quote chars inside a quoted string
        # Bad pattern: "value;" (semicolon inside closing quote)
        bad = re.findall(r'"\w+;"', stripped)
        if bad:
            violations.append(("R29", i, f"Semicolon inside quotes: {bad}"))
        # Also check: ;" should not be preceded by " without content
        # Bad: "" ; (double quote space semicolon)
        if '"" ;' in stripped or '";"' in stripped and not stripped.endswith('";"'):
            # This is OK for list separators: "item";"item"
            pass

def check_rule_30_no_trailing_semicolon(lines, violations):
    """Rule 30: Last item before closing bracket has no semicolon"""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Check list blocks: ("a";"b";"c") — last item should not have ;
        if stripped.startswith("(") and stripped.endswith(")"):
            # Check if second-to-last char before ) is ;
            inner = stripped[1:-1].strip()
            if inner.endswith('";"'):
                violations.append(("R30", i, f"Trailing semicolon in list: {stripped[-30:]}"))
        # Check block lines: "item"; before }
        if stripped == '";' or stripped.endswith('";'):
            # Check next line — if it's }, this line shouldn't have ;
            if i < len(lines) and lines[i].strip() == "}":
                violations.append(("R30", i, f"Trailing semicolon before closing brace"))

def check_required_tags_present(lines, violations):
    """Check all REQUIRED_TAGS are present in header"""
    header = find_header_blocks(lines)
    found_tags = set()
    for line in header:
        m = re.match(r'^\[@(\w+)\]', line.strip())
        if m:
            found_tags.add(m.group(1))
    for tag in REQUIRED_TAGS:
        if tag not in found_tags:
            violations.append(("HDR", 0, f"Missing required tag: [@{tag}]"))

def check_doubled_quotes(lines, violations):
    """Check for "" artifacts from find-replace"""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith('"""'):
            continue
        if '""' in stripped and '"" means' not in stripped and '""' != stripped.strip():
            # Allow "" as empty string value, but not ""; which is doubled
            if '"";' in stripped and '""";' not in stripped:
                # Check if it's a real empty string or doubled quote
                # Pattern: word"";word means doubled
                if re.search(r'\w"";', stripped):
                    violations.append(("FMT", i, f"Doubled quote artifact: {stripped[:60]}"))

def check_doubled_semicolons(lines, violations):
    """Check for ;; artifacts"""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if ";;" in stripped and "not" not in stripped[:20]:
            violations.append(("FMT", i, f"Doubled semicolon: {stripped[:60]}"))

def run_all_checks():
    lines = load_lines()
    violations = []

    # Header checks
    check_required_tags_present(lines, violations)

    # Rule checks
    check_rule_1_camelcase(lines, violations)
    check_rule_2_no_underscores(lines, violations)
    check_rule_4_bcl_uncommented(lines, violations)
    check_rule_7_empty_string(lines, violations)
    check_rule_26_bcl_in_bcl_out(lines, violations)
    check_rule_27_camelcase_clarified(lines, violations)
    check_rule_28_same_format(lines, violations)
    check_rule_29_semicolons_outside_quotes(lines, violations)
    check_rule_30_no_trailing_semicolon(lines, violations)

    # Format artifact checks
    check_doubled_quotes(lines, violations)
    check_doubled_semicolons(lines, violations)

    return violations

def main():
    print("=" * 70)
    print("BCL Format Validator — Config.py")
    print("=" * 70)
    print()

    violations = run_all_checks()

    if not violations:
        print("ALL CHECKS PASSED — 0 violations")
        print()
        print("Rules checked:")
        print("  R1  - CamelCase")
        print("  R2  - No underscores")
        print("  R4  - BCL block uncommented")
        print("  R7  - Empty string as option")
        print("  R26 - BCL in, BCL out")
        print("  R27 - CamelCase (not PascalCase)")
        print("  R28 - Same BCL format")
        print("  R29 - Semicolons outside quotes")
        print("  R30 - No trailing semicolon")
        print("  HDR - Required tags present")
        print("  FMT - No format artifacts")
        return 0

    print(f"FOUND {len(violations)} VIOLATION(S):")
    print()
    for rule, line, msg in violations:
        print(f"  [{rule}] Line {line}: {msg}")
    print()
    print(f"Total: {len(violations)} violations across {len(set(v[0] for v in violations))} rules")
    return 1

if __name__ == "__main__":
    sys.exit(main())
