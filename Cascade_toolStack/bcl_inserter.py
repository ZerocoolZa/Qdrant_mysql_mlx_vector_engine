#!/usr/bin/env python3
"""
BCL Chunked Inserter — Marker-based code insertion tool

Solves the "large file write gets stuck" problem by:
1. Writing a small skeleton file with # [SECTION:NAME] markers
2. Inserting implementations one marker at a time (small edits, never stuck)

Usage:
  bcl_inserter.py init --skeleton FILE --output FILE    Create skeleton from spec
  bcl_inserter.py insert --file FILE --section NAME --impl TEXT  Insert one section
  bcl_inserter.py insert-all --file FILE --impls DIR     Insert all from snippet files
  bcl_inserter.py status --file FILE                     Show unfilled sections
  bcl_inserter.py fill --file FILE --from FILE           Insert all from a Python impl file
"""
import os
import re
import sys
import json
import argparse
from datetime import datetime

SECTION_RE = re.compile(r'# \[SECTION:(\w+)\]')
SECTION_PASS_RE = re.compile(r'(\s*)# \[SECTION:(\w+)\]\n\s*pass\s+# \[SECTION:\2\]')


def find_sections(filepath):
    """Find all section markers in a file. Returns list of (name, line_num, filled).
    Each section has two markers (comment + pass). Only count the first one."""
    with open(filepath, "r") as f:
        lines = f.readlines()

    sections = []
    seen = set()
    for i, line in enumerate(lines):
        m = SECTION_RE.search(line)
        if m:
            name = m.group(1)
            if name in seen:
                continue
            seen.add(name)
            # Check if next line is "pass  # [SECTION:NAME]" (unfilled)
            next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
            is_pass = next_line.startswith("pass")
            sections.append({"name": name, "line": i + 1, "filled": not is_pass})
    return sections


def show_status(filepath):
    """Show which sections are filled vs unfilled."""
    sections = find_sections(filepath)
    if not sections:
        print("No section markers found.")
        return 0

    filled = [s for s in sections if s["filled"]]
    unfilled = [s for s in sections if not s["filled"]]

    print(f"File: {filepath}")
    print(f"Sections: {len(sections)} total | {len(filled)} filled | {len(unfilled)} unfilled")
    print("")

    if unfilled:
        print("UNFILLED:")
        for s in unfilled:
            print(f"  - [{s['name']}] at line {s['line']}")
        print("")

    if filled:
        print("FILLED:")
        for s in filled:
            print(f"  - [{s['name']}] at line {s['line']}")

    return 0 if not unfilled else 1


def insert_section(filepath, section_name, impl_text):
    """Insert implementation text at a specific section marker.
    Replaces 'pass  # [SECTION:NAME]' with the implementation."""
    with open(filepath, "r") as f:
        content = f.read()

    # Find the marker pattern: # [SECTION:NAME]\n        pass  # [SECTION:NAME]
    pattern = re.compile(
        r'(\s*)# \[SECTION:' + re.escape(section_name) + r'\]\n\s*pass\s+# \[SECTION:' + re.escape(section_name) + r'\]'
    )

    m = pattern.search(content)
    if not m:
        # Check if section exists but is already filled
        if f"# [SECTION:{section_name}]" in content:
            print(f"Section [{section_name}] already filled or not a pass-placeholder.")
            return 1
        print(f"Section [{section_name}] not found in {filepath}")
        return 1

    indent = m.group(1)
    # Indent the implementation text to match
    impl_lines = impl_text.rstrip().split("\n")
    indented = "\n".join(indent + line if line.strip() else line for line in impl_lines)

    # Replace: keep the section comment, replace pass with impl
    replacement = f"{indent}# [SECTION:{section_name}]\n{indented}"
    new_content = content[:m.start()] + replacement + content[m.end():]

    with open(filepath, "w") as f:
        f.write(new_content)

    print(f"Inserted [{section_name}] — {len(impl_lines)} lines")
    return 0


def insert_all_from_dir(filepath, impls_dir):
    """Insert all implementations from snippet files in a directory.
    Each file named SECTION_NAME.py contains the implementation text."""
    sections = find_sections(filepath)
    unfilled = [s for s in sections if not s["filled"]]

    if not unfilled:
        print("All sections already filled.")
        return 0

    inserted = 0
    failed = 0

    for s in unfilled:
        snippet_path = os.path.join(impls_dir, f"{s['name']}.py")
        if os.path.exists(snippet_path):
            with open(snippet_path, "r") as f:
                impl = f.read()
            result = insert_section(filepath, s["name"], impl)
            if result == 0:
                inserted += 1
            else:
                failed += 1
        else:
            print(f"SKIP [{s['name']}] — no snippet at {snippet_path}")
            failed += 1

    print(f"\nDone: {inserted} inserted, {failed} skipped/failed")
    return 0 if failed == 0 else 1


def insert_all_from_file(filepath, impl_filepath):
    """Insert all implementations from a single Python file.
    Parses the file for function definitions and maps them to sections by name."""
    with open(impl_filepath, "r") as f:
        impl_content = f.read()

    # Extract function bodies: def function_name(...):\n    body
    func_pattern = re.compile(
        r'^def\s+(\w+)\s*\([^)]*\):\s*\n((?:    .*\n|\n)*)',
        re.MULTILINE
    )

    implementations = {}
    for m in func_pattern.finditer(impl_content):
        name = m.group(1)
        body = m.group(2)
        # Dedent the body (remove leading 4 spaces)
        body_lines = body.split("\n")
        dedented = []
        for line in body_lines:
            if line.startswith("    "):
                dedented.append(line[4:])
            else:
                dedented.append(line)
        implementations[name] = "\n".join(dedented).strip()

    if not implementations:
        print(f"No function definitions found in {impl_filepath}")
        return 1

    sections = find_sections(filepath)
    unfilled = [s for s in sections if not s["filled"]]

    inserted = 0
    skipped = 0

    for s in unfilled:
        if s["name"] in implementations:
            result = insert_section(filepath, s["name"], implementations[s["name"]])
            if result == 0:
                inserted += 1
            else:
                skipped += 1
        else:
            print(f"SKIP [{s['name']}] — no matching function in impl file")
            skipped += 1

    print(f"\nDone: {inserted} inserted, {skipped} skipped")
    return 0 if skipped == 0 else 1


def create_skeleton(spec_path, output_path):
    """Create a skeleton file from a JSON spec with section markers."""
    with open(spec_path, "r") as f:
        spec = json.load(f)

    lines = []
    lines.append(f'"""')
    lines.append(f'{spec.get("module_name", "module")} — {spec.get("description", "")}')
    lines.append(f'Generated: {datetime.now().isoformat()}')
    lines.append(f'"""')
    lines.append("")
    lines.append("# [SECTION:IMPORTS]")
    lines.append("pass  # [SECTION:IMPORTS]")
    lines.append("")

    for cls in spec.get("classes", []):
        lines.append(f'class {cls["name"]}:')
        lines.append(f'    """{cls.get("description", "")}"""')
        lines.append("")

        for method in cls.get("methods", []):
            lines.append(f'    def {method["name"]}{method.get("signature", "(self)")}:')
            lines.append(f'        """{method.get("desc", "")}"""')
            lines.append(f'        # [SECTION:{method["name"].upper()}]')
            lines.append(f'        pass  # [SECTION:{method["name"].upper()}]')
            lines.append("")

        lines.append("")

    lines.append("# [SECTION:ENTRY_POINT]")
    lines.append("pass  # [SECTION:ENTRY_POINT]")
    lines.append("")

    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    sections = find_sections(output_path)
    print(f"Skeleton created: {output_path}")
    print(f"Sections: {len(sections)} markers ready for insertion")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="BCL Chunked Inserter — marker-based code insertion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # init
    p_init = sub.add_parser("init", help="Create skeleton from spec")
    p_init.add_argument("--spec", required=True, help="JSON spec file")
    p_init.add_argument("--output", required=True, help="Output skeleton file")

    # insert
    p_insert = sub.add_parser("insert", help="Insert one section")
    p_insert.add_argument("--file", required=True, help="Target file")
    p_insert.add_argument("--section", required=True, help="Section name")
    p_insert.add_argument("--impl", required=True, help="Implementation text or @file")

    # insert-all from dir
    p_all_dir = sub.add_parser("insert-all", help="Insert all from snippet directory")
    p_all_dir.add_argument("--file", required=True, help="Target file")
    p_all_dir.add_argument("--impls", required=True, help="Directory of SECTION_NAME.py snippets")

    # fill from file
    p_fill = sub.add_parser("fill", help="Insert all from a single impl file")
    p_fill.add_argument("--file", required=True, help="Target skeleton file")
    p_fill.add_argument("--from", required=True, dest="impl", help="Implementation file")

    # status
    p_status = sub.add_parser("status", help="Show filled/unfilled sections")
    p_status.add_argument("--file", required=True, help="Target file")

    args = parser.parse_args()

    if args.command == "init":
        return create_skeleton(args.spec, args.output)

    elif args.command == "insert":
        impl = args.impl
        if impl.startswith("@"):
            with open(impl[1:], "r") as f:
                impl = f.read()
        return insert_section(args.file, args.section, impl)

    elif args.command == "insert-all":
        return insert_all_from_dir(args.file, args.impls)

    elif args.command == "fill":
        return insert_all_from_file(args.file, args.impl)

    elif args.command == "status":
        return show_status(args.file)

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
