#!/usr/bin/env python3
# [@GHOST]{[@file<demo_bcl_stress.py>][@domain<Dom_Bcl>][@role<demo>][@auth<devin>][@date<2026-07-02>][@ver<3.0.0>][@session<bcl-stress>]}
# [@VBSTYLE]{[@auth<devin>][@role<demo>][@return<tuple3>][@orch<BCLParser>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{BCL Stress Suite — proves the bracket grammar is universal across 7 domains. Same 4 symbols: [@]container {}hands ()pots ;separator. Every domain parses with the same BCLParser.}
# [@FILEID]{core/Dom_Bcl/demo_bcl_stress.py

import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from bcl_lexer import BCLTokenizer
from bcl_parser import BCLParser


# ════════════════════════════════════════════════════════════════
# BCL GRAMMAR — The 4 Symbols
# ════════════════════════════════════════════════════════════════
#
# [@NAME]  = The Container — the thing that owns everything inside it
#      {}  = The Hands — gathers related items together
#      ()  = The Pots — holds individual values
#       ;  = The Separator — separates values within a pot
#
# Hierarchy:
#   Container → Hands → Pots → Values
#   Container → Container → Container → ... (recursive)
#
# ════════════════════════════════════════════════════════════════

DOMAINS = {}


# ────────────────────────────────────────────────────────────────
# 1. REPORT — incidents, errors, questions, fixes, evidence
# ────────────────────────────────────────────────────────────────
DOMAINS["report"] = """
[@REPORT]
{
    ("title";"ReadFile failure report")
    ("incident";8)

    [@ERRORS]
    {
        (91;94;97)
    }

    [@PROBLEMS]
    {
        (17)
    }

    [@CAUSES]
    {
        (4;7)
    }

    [@FIXES]
    {
        (1;7;13)
    }

    [@FACTS]
    {
        (9;10;11;12)
    }

    [@ANSWERS]
    {
        (1;7;9;32)
    }

    [@EVIDENCE]
    {
        (4;5;22)
    }

    [@RULES]
    {
        (3;84)
    }
}
"""


# ────────────────────────────────────────────────────────────────
# 2. MATHEMATICS — expressions, functions, variables, results
# ────────────────────────────────────────────────────────────────
DOMAINS["math"] = """
[@EQUATION]
{
    ("name";"quadratic_formula")
    ("description";"Solve ax^2 + bx + c = 0")

    [@VARIABLES]
    {
        [@VAR]
        {
            ("name";"a")
            ("value";2)
            ("type";"coefficient")
        }
        [@VAR]
        {
            ("name";"b")
            ("value";-7)
            ("type";"coefficient")
        }
        [@VAR]
        {
            ("name";"c")
            ("value";3)
            ("type";"coefficient")
        }
    }

    [@DISCRIMINANT]
    {
        ("formula";"b^2 - 4ac")
        ("value";25)
        ("positive";"yes")
    }

    [@ROOTS]
    {
        [@ROOT]
        {
            ("formula";"(-b + sqrt(discriminant)) / 2a")
            ("value";3)
        }
        [@ROOT]
        {
            ("formula";"(-b - sqrt(discriminant)) / 2a")
            ("value";0.5)
        }
    }

    [@RESULT]
    {
        ("x1";3)
        ("x2";0.5)
        ("verified";"yes")
    }
}
"""


# ────────────────────────────────────────────────────────────────
# 3. TREE STRUCTURE — parent, child, grandchild (recursion proof)
# ────────────────────────────────────────────────────────────────
DOMAINS["tree"] = """
[@NODE]
{
    ("name";"root")
    ("depth";0)

    [@CHILDREN]
    {
        [@NODE]
        {
            ("name";"alpha")
            ("depth";1)

            [@CHILDREN]
            {
                [@NODE]
                {
                    ("name";"alpha_1")
                    ("depth";2)

                    [@CHILDREN]
                    {
                        [@NODE]
                        {
                            ("name";"alpha_1_a")
                            ("depth";3)
                        }
                        [@NODE]
                        {
                            ("name";"alpha_1_b")
                            ("depth";3)
                        }
                    }
                }
                [@NODE]
                {
                    ("name";"alpha_2")
                    ("depth";2)
                }
            }
        }
        [@NODE]
        {
            ("name";"beta")
            ("depth";1)
        }
    }
}
"""


# ────────────────────────────────────────────────────────────────
# 4. FILESYSTEM — folders, files, metadata
# ────────────────────────────────────────────────────────────────
DOMAINS["filesystem"] = """
[@FOLDER]
{
    ("name";"core")
    ("path";"/project/core")

    [@FOLDERS]
    {
        [@FOLDER]
        {
            ("name";"Dom_Report")
            ("path";"/project/core/Dom_Report")

            [@FILES]
            {
                [@FILE]
                {
                    ("name";"Report.py")
                    ("size";4592)
                    ("type";"python")
                    ("lines";120)
                }
                [@FILE]
                {
                    ("name";"Fact.py")
                    ("size");2890)
                    ("type";"python")
                    ("lines";85)
                }
            }
        }
        [@FOLDER]
        {
            ("name";"Dom_Bcl")
            ("path";"/project/core/Dom_Bcl")

            [@FILES]
            {
                [@FILE]
                {
                    ("name";"bcl_parser.py")
                    ("size";12000)
                    ("type";"python")
                    ("lines";320)
                }
            }
        }
    }

    [@FILES]
    {
        [@FILE]
        {
            ("name";"__init__.py")
            ("size";76)
            ("type";"python")
            ("lines";3)
        }
    }
}
"""


# ────────────────────────────────────────────────────────────────
# 5. GUI — window, controls, properties, events
# ────────────────────────────────────────────────────────────────
DOMAINS["gui"] = """
[@WINDOW]
{
    ("title";"BCL Studio")
    ("width";1920)
    ("height";1080)
    ("resizable";"yes")

    [@TOOLBAR]
    {
        ("name";"main_toolbar")
        ("position";"top")

        [@BUTTON]
        {
            ("name";"file")
            ("label";"File")
            ("enabled";"yes")

            [@MENU]
            {
                [@ITEM]
                {
                    ("label";"Open")
                    ("shortcut";"Ctrl+O")
                    ("action";"open_file")
                }
                [@ITEM]
                {
                    ("label";"Save")
                    ("shortcut";"Ctrl+S")
                    ("action";"save_file")
                }
                [@ITEM]
                {
                    ("label";"Exit")
                    ("shortcut";"Ctrl+Q")
                    ("action";"quit")
                }
            }
        }
        [@BUTTON]
        {
            ("name";"build")
            ("label";"Build")
            ("enabled";"yes")
        }
    }

    [@PANEL]
    {
        ("name";"editor")
        ("position";"center")
        ("background";"#1e1e1e")
    }

    [@STATUSBAR]
    {
        ("name";"status")
        ("position";"bottom")
        ("text";"Ready")
    }
}
"""


# ────────────────────────────────────────────────────────────────
# 6. KNOWLEDGE GRAPH — problem, cause, solution, rule, fact
# ────────────────────────────────────────────────────────────────
DOMAINS["knowledge"] = """
[@KNOWLEDGE]
{
    ("domain";"diagnostic")
    ("version";"3.0")

    [@PROBLEM]
    {
        ("id";17)
        ("name";"FileNotFoundError on read")
        ("occurrences";10)

        [@CAUSE]
        {
            ("id";4)
            ("type";"root")
            ("text";"File does not exist on disk")
            ("severity";4)
        }

        [@SOLUTION]
        {
            ("id";23)
            ("text";"Check file exists before reading")
            ("confidence";0.85)
        }

        [@FIX]
        {
            ("id";11)
            ("type";"recommended")
            ("action";"Add os.path.exists() guard")
            ("result";"untried")
        }

        [@PREVENTION]
        {
            ("id";1)
            ("type";"guard")
            ("rule";"Validate file path before read_file")
        }

        [@RULE]
        {
            ("id";3)
            ("pattern";"read_file without exists check")
            ("fix_action";"Add os.path.exists() guard")
            ("confidence";0.90)
        }

        [@FACTS]
        {
            ("id";9)
            ("id";10)
            ("id";11)
            ("id";12)
        }

        [@EVIDENCE]
        {
            ("id";4)
            ("id";5)
        }
    }
}
"""


# ────────────────────────────────────────────────────────────────
# 7. CONFIGURATION — settings, sections, values
# ────────────────────────────────────────────────────────────────
DOMAINS["config"] = """
[@CONFIG]
{
    ("app";"diagnostic_kb")
    ("version";"3.0.0")
    ("environment";"production")

    [@DATABASE]
    {
        ("host";"localhost")
        ("port";3306)
        ("user";"root")
        ("password";"")
        ("socket";"/tmp/mysql.sock")
        ("pool_size";10)
        ("timeout";30)
    }

    [@REPORTING]
    {
        ("enabled";"yes")
        ("format";"terminal")
        ("max_facts";100)
        ("max_evidence";50)

        [@SEVERITY_FILTER]
        {
            ("min_level";2)
            ("include_info";"no")
            ("include_debug";"no")
        }
    }

    [@BCL]
    {
        ("parser";"bcl_parser.py")
        ("lexer";"bcl_lexer.py")
        ("max_nesting";32)
        ("auto_fix";"yes")
        ("max_fix_cycles";3)
    }

    [@LOGGING]
    {
        ("level";"info")
        ("file";"/var/log/diagnostic_kb.log")
        ("max_size";10485760)
        ("rotate";"yes")
        ("keep";7)
    }
}
"""


def count_nodes(node):
    """Recursively count all nodes in a BCL AST tree."""
    count = 1
    for child in node.state["children"]:
        count += count_nodes(child)
    return count


def count_tuples(node):
    """Recursively count all tuples in a BCL AST tree."""
    count = len(node.state["tuples"])
    for child in node.state["children"]:
        count += count_tuples(child)
    return count


def main():
    sys.stdout.write("=" * 70 + "\n")
    sys.stdout.write("BCL STRESS SUITE — 7 DOMAINS, SAME GRAMMAR\n")
    sys.stdout.write("=" * 70 + "\n")
    sys.stdout.write("\n")
    sys.stdout.write("The 4 symbols:\n")
    sys.stdout.write("  [@NAME]  = Container — owns everything inside\n")
    sys.stdout.write("      {}  = Hands — gathers related items\n")
    sys.stdout.write("      ()  = Pots — holds individual values\n")
    sys.stdout.write("       ;  = Separator — separates values in a pot\n")
    sys.stdout.write("\n")
    sys.stdout.write("If BCL is universal, the same parser must handle\n")
    sys.stdout.write("all 7 domains without domain-specific logic.\n")
    sys.stdout.write("\n")

    all_pass = True
    total_nodes = 0
    total_tuples = 0
    total_bytes = 0

    for domain_name, bcl_text in DOMAINS.items():
        # Strip leading newline
        bcl_text = bcl_text.strip()

        # ── Lex ──
        lexer = BCLTokenizer()
        lex_result = lexer.Run("tokenize", {"text": bcl_text})
        if lex_result[0] == 0:
            sys.stdout.write("FAIL  %-15s LEX ERROR: %s\n" % (domain_name, lex_result[2]))
            all_pass = False
            continue
        tokens = lex_result[1]["tokens"]
        lex_errors = lex_result[1]["errors"]

        # ── Parse ──
        parser = BCLParser()
        parse_result = parser.Run("parse", {"tokens": tokens})
        if parse_result[0] == 0:
            sys.stdout.write("FAIL  %-15s PARSE ERROR: %s\n" % (domain_name, parse_result[2]))
            all_pass = False
            continue

        root = parse_result[1]["root"]
        children = parse_result[1]["children"]
        parse_errors = parse_result[1]["errors"]

        if parse_errors:
            sys.stdout.write("FAIL  %-15s PARSE ERRORS: %s\n" % (domain_name, parse_errors))
            all_pass = False
            continue

        # ── Count ──
        node_count = 0
        tuple_count = 0
        for child in root.state["children"]:
            node_count += count_nodes(child)
            tuple_count += count_tuples(child)

        byte_count = len(bcl_text.encode())
        total_nodes += node_count
        total_tuples += tuple_count
        total_bytes += byte_count

        # ── Show first container name ──
        first_child = root.state["children"][0] if root.state["children"] else None
        container_name = first_child.state["name"] if first_child else "?"

        sys.stdout.write("PASS  %-15s [%s] %d nodes, %d tuples, %d bytes\n" % (
            domain_name, container_name, node_count, tuple_count, byte_count))

        # ── Show top-level structure ──
        if first_child:
            sys.stdout.write("      container: [@%s]\n" % container_name)
            for tc in first_child.state["children"]:
                sys.stdout.write("      sub-container: [@%s] (%d tuples, %d children)\n" % (
                    tc.state["name"], len(tc.state["tuples"]), len(tc.state["children"])))
            sys.stdout.write("      direct tuples: %d\n" % len(first_child.state["tuples"]))
        sys.stdout.write("\n")

    # ── Summary ──
    sys.stdout.write("=" * 70 + "\n")
    sys.stdout.write("RESULTS\n")
    sys.stdout.write("=" * 70 + "\n")
    sys.stdout.write("  Domains tested:    %d\n" % len(DOMAINS))
    sys.stdout.write("  Domains passed:    %d\n" % (len(DOMAINS) if all_pass else 0))
    sys.stdout.write("  Total nodes:       %d\n" % total_nodes)
    sys.stdout.write("  Total tuples:      %d\n" % total_tuples)
    sys.stdout.write("  Total bytes:       %d\n" % total_bytes)
    sys.stdout.write("  Parser used:       BCLParser (same for all domains)\n")
    sys.stdout.write("  Domain-specific:   NONE\n")
    sys.stdout.write("\n")

    if all_pass:
        sys.stdout.write("VERDICT: BCL is a universal structural language.\n")
        sys.stdout.write("The same 4 symbols ([@] {} () ;) express\n")
        sys.stdout.write("reports, math, trees, filesystems, GUIs,\n")
        sys.stdout.write("knowledge graphs, and configuration.\n")
        sys.stdout.write("No domain-specific logic was needed.\n")
    else:
        sys.stdout.write("VERDICT: SOME DOMAINS FAILED.\n")

    sys.stdout.write("\n")
    sys.stdout.write("=" * 70 + "\n")
    sys.stdout.write("THE 4 SYMBOLS — SEMANTIC ROLES\n")
    sys.stdout.write("=" * 70 + "\n")
    sys.stdout.write("\n")
    sys.stdout.write("  [@NAME]  The Container\n")
    sys.stdout.write("           The thing that owns everything inside it.\n")
    sys.stdout.write("           A report, a window, a folder, an equation.\n")
    sys.stdout.write("           Can contain more containers (recursion).\n")
    sys.stdout.write("\n")
    sys.stdout.write("      {}  The Hands\n")
    sys.stdout.write("           Gathers related items together.\n")
    sys.stdout.write("           Like hands holding a set of pots.\n")
    sys.stdout.write("\n")
    sys.stdout.write("      ()  The Pot\n")
    sys.stdout.write("           Holds individual values.\n")
    sys.stdout.write("           (\"key\";\"value\") or (\"id\";91)\n")
    sys.stdout.write("\n")
    sys.stdout.write("       ;  The Separator\n")
    sys.stdout.write("           Separates values within a pot.\n")
    sys.stdout.write("           (\"name\";\"FileNotFoundError\";\"severity\";4)\n")
    sys.stdout.write("\n")
    sys.stdout.write("Hierarchy:\n")
    sys.stdout.write("  Container → Hands → Pots → Values\n")
    sys.stdout.write("  Container → Container → Container → ... (recursive)\n")
    sys.stdout.write("\n")
    sys.stdout.write("A report contains errors.\n")
    sys.stdout.write("An error contains facts.\n")
    sys.stdout.write("A fact contains evidence.\n")
    sys.stdout.write("Evidence contains measurements.\n")
    sys.stdout.write("Each level is just another container.\n")


if __name__ == "__main__":
    main()
