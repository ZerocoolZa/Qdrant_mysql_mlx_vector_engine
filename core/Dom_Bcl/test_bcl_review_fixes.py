#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Bcl/test_bcl_review_fixes.py"
# date="2026-06-28" author="Devin" session_id="bcl-review-fixes"
# context="Tests for the 13 BCL review findings. Each test verifies a specific fix."}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="test_bcl_review_fixes.py" domain="BCL" authority="test"}
# [@SUMMARY]{summary="Verification tests for BCL review fixes #1-#13."}

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bcl_lexer import BCLTokenizer
from bcl_parser import BCLParser, BCLNode
from bcl_validator import BCLValidator, IRValidator, LOWERCASE_EXEMPT
from bcl_decision_walker import BCLDecisionWalker

CANONICAL_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "Sql_Schema_Config", "Database_Schema_config_v2.bcl"
)

PASS = 0
FAIL = 0


def Check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print("  PASS %s" % name)
    else:
        FAIL += 1
        print("  FAIL %s -- %s" % (name, detail))


def TestData():
    return (
        '[@no_column_spread]{[@is_audit_column]{[@Pass]{("-- acceptable";100)}'
        '[@Fail]{[@same_name_diff_meaning]{[@Pass]{("ALTER TABLE {table} RENAME COLUMN {column} TO {table}_{column}";90)}'
        '[@Fail]{("-- flag for human review";50)}}}}}'
    )


def TestFix1ValidatorNoCrash():
    print("[Fix #1] validator no longer crashes on out-of-range int weight")
    root = BCLNode("root")
    parent = BCLNode("Foo", parent=root)
    root.state["children"].append(parent)
    parent.state["tuples"].append(["x", 150])
    v = BCLValidator()
    r = v.Run("validate", {"root": root})
    inner = r[1] if r[0] == 1 else None
    data = inner[1] if (inner and inner[0] == 1) else None
    Check("no crash", r[0] == 1, str(r[2]) if r[0] == 0 else "")
    Check("status FAIL", data is not None and data.get("status") == "FAIL", str(data))


def TestFix2LexerMultiDot():
    print("[Fix #2] lexer rejects malformed multi-dot floats")
    lex = BCLTokenizer()
    r = lex.Run("tokenize", {"text": '[@Foo]{("x";3.5.6)'})
    Check("rejected", r[0] == 0, str(r[2]) if r[0] == 1 else "accepted bad input")
    Check("error code", r[0] == 0 and r[2][0] == "LEX_NUMBER_INVALID", str(r[2]) if r[0] == 0 else "")


def TestFix3CrudQuarantined():
    print("[Fix #3] bcl_crud.py quarantined")
    here = os.path.dirname(os.path.abspath(__file__))
    Check("bcl_crud.py removed", not os.path.exists(os.path.join(here, "bcl_crud.py")), "still present")
    Check("bcl_crud.py.dead exists", os.path.exists(os.path.join(here, "bcl_crud.py.dead")), "missing .dead")


def TestFix4LowercaseExempt():
    print("[Fix #4] schema-lint lowercase names exempt from rule 24")
    root = BCLNode("root")
    good = BCLNode("must_have_pk", parent=root)
    root.state["children"].append(good)
    v = BCLValidator()
    r = v.Run("validate", {"root": root})
    data = r[1][1]
    exempt_flagged = [x for x in data["violations"] if "must_have_pk" in x.get("message", "") and "capital" in x.get("message", "")]
    Check("exempt not flagged", not exempt_flagged, str(exempt_flagged))
    root2 = BCLNode("root")
    bad = BCLNode("badname", parent=root2)
    root2.state["children"].append(bad)
    r2 = v.Run("validate", {"root": root2})
    data2 = r2[1][1]
    flagged = [x for x in data2["violations"] if "badname" in x.get("message", "")]
    Check("non-exempt still flagged", len(flagged) > 0, "not flagged")
    Check("exempt set non-empty", len(LOWERCASE_EXEMPT) > 30, "too small")


def TestFix5DecisionWalker():
    print("[Fix #5] decision-tree walker executes Pass/Fail/Unsure")
    lex = BCLTokenizer()
    par = BCLParser()
    lr = lex.Run("tokenize", {"text": TestData()})
    pr = par.Run("parse", {"tokens": lr[1]["tokens"]})
    root = pr[1]["root"]
    w = BCLDecisionWalker()
    c1 = {"is_audit_column": lambda m: "Pass", "same_name_diff_meaning": lambda m: "Pass"}
    r1 = w.Run("walk", {"root": root, "rule_id": "no_column_spread", "check_functions": c1, "schema_meta": {"table": "users", "column": "created"}})
    Check("Pass branch", r1[0] == 1 and r1[1]["fix_sql"].startswith("-- acceptable"), str(r1))
    c2 = {"is_audit_column": lambda m: "Fail", "same_name_diff_meaning": lambda m: "Pass"}
    r2 = w.Run("walk", {"root": root, "rule_id": "no_column_spread", "check_functions": c2, "schema_meta": {"table": "users", "column": "name"}})
    Check("nested Pass with placeholder", r2[1]["fix_sql"] == "ALTER TABLE users RENAME COLUMN name TO users_name", str(r2[1]))
    c3 = {"is_audit_column": lambda m: "Fail", "same_name_diff_meaning": lambda m: "Fail"}
    r3 = w.Run("walk", {"root": root, "rule_id": "no_column_spread", "check_functions": c3, "schema_meta": {}})
    Check("Fail fallback tuple", r3[1]["fix_sql"] == "-- flag for human review", str(r3[1]))
    r4 = w.Run("walk", {"root": root, "rule_id": "nonexistent", "check_functions": {}, "schema_meta": {}})
    Check("missing rule error", r4[0] == 0 and r4[2][0] == "RULE_NOT_FOUND", str(r4))


def TestFix6BclAllQuarantined():
    print("[Fix #6] bcl_all.py monolith quarantined")
    here = os.path.dirname(os.path.abspath(__file__))
    Check("bcl_all.py removed", not os.path.exists(os.path.join(here, "bcl_all.py")), "still present")
    Check("bcl_all.py.dead exists", os.path.exists(os.path.join(here, "bcl_all.py.dead")), "missing .dead")


def TestFix7DuplicatesQuarantined():
    print("[Fix #7] stale duplicate modules quarantined")
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    Check("BclGenerator.py v1 removed", not os.path.exists(os.path.join(root, "core", "Dom_Bcl", "BclGenerator.py")), "still present")
    Check("bin_tools/bcl_parser.py removed", not os.path.exists(os.path.join(root, "Cascade_toolStack", "bin_tools", "bcl_parser.py")), "still present")
    Check("BclGenerator_v2.py kept", os.path.exists(os.path.join(root, "core", "Dom_Bcl", "BclGenerator_v2.py")), "v2 missing")


def TestFix8GetAmbiguity():
    print("[Fix #8] BCLNode.Get disambiguates property vs weighted")
    n = BCLNode("Test")
    n.state["tuples"].append(["text", 92])
    r = n.Run("get", {"key": "text"})
    Check("weighted 2-tuple -> dict", isinstance(r[1], dict) and r[1].get("weight") == 92, str(r[1]))
    n.state["tuples"].append(["version", "2.1"])
    r2 = n.Run("get", {"key": "version"})
    Check("property 2-tuple -> value", r2[1] == "2.1", str(r2[1]))


def TestFix9GetWeightAllTuples():
    print("[Fix #9] BCLNode.GetWeight scans all tuples")
    n = BCLNode("Branch")
    n.state["tuples"].append(["first", 50])
    n.state["tuples"].append(["second", 92])
    r = n.Run("get_weight", {})
    Check("returns max weight", r[1] == 92, str(r[1]))


def TestFix10ToBclEscaping():
    print("[Fix #10] ToBcl escapes special chars and round-trips")
    n = BCLNode("Esc")
    n.state["tuples"].append(["val", 'has "quote" and ;semi'])
    rt = n.Run("to_bcl", {})
    lex = BCLTokenizer()
    par = BCLParser()
    lr = lex.Run("tokenize", {"text": rt[1]})
    pr = par.Run("parse", {"tokens": lr[1]["tokens"]})
    reparsed = pr[1]["root"].state["children"][0]
    rv = reparsed.Run("get", {"key": "val"})
    Check("round-trip preserves value", rv[1] == 'has "quote" and ;semi', repr(rv[1]))


def TestFix11ValidateIrUsesLexer():
    print("[Fix #11] IRValidator uses real lexer, not string scraping")
    v = IRValidator()
    ir1 = '[@IRNODE]  type=method id=abc123 parent=def456\n("name";"foo")\n[@ENDNODE]'
    ir2 = '[@IRNODE]  type=class id=def456\n[@ENDNODE]'
    r = v.Run("validate_ir", {"results": [{"bcl": ir1, "filepath": "a"}, {"bcl": ir2, "filepath": "b"}]})
    Check("valid IR ok", r[1]["ok"], str(r[1]))
    r2 = v.Run("validate_ir", {"results": [{"bcl": '[@IRNODE]  id=dup\n[@ENDNODE]', "filepath": "x"}, {"bcl": '[@IRNODE]  id=dup\n[@ENDNODE]', "filepath": "y"}]})
    Check("dup detected", any("DUPLICATE" in i for i in r2[1]["issues"]), str(r2[1]))
    r3 = v.Run("validate_ir", {"results": [{"bcl": '[@IRNODE]  id=n1 parent=ghost\n[@ENDNODE]', "filepath": "z"}]})
    Check("orphan detected", any("ORPHAN" in i for i in r3[1]["issues"]), str(r3[1]))


def TestFix12StringWeights():
    print("[Fix #12] string weights flagged (3-tuple)")
    root = BCLNode("root")
    bad = BCLNode("Bad", parent=root)
    root.state["children"].append(bad)
    bad.state["tuples"].append(["text", "fix", "100"])
    v = BCLValidator()
    r = v.Run("validate", {"root": root})
    data = r[1][1]
    str_violations = [x for x in data["violations"] if "string" in x.get("message", "")]
    Check("string weight flagged", len(str_violations) > 0, "not flagged")
    root2 = BCLNode("root")
    ok = BCLNode("Ok", parent=root2)
    root2.state["children"].append(ok)
    ok.state["tuples"].append(["version", "2.1"])
    r2 = v.Run("validate", {"root": root2})
    data2 = r2[1][1]
    false_pos = [x for x in data2["violations"] if "string" in x.get("message", "")]
    Check("2-tuple property value not flagged", not false_pos, str(false_pos))


def TestFix13StrayBracket():
    print("[Fix #13] lexer rejects stray ] outside container")
    lex = BCLTokenizer()
    r = lex.Run("tokenize", {"text": '[@Foo]{("x";1)} ]'})
    Check("rejected", r[0] == 0, "accepted stray ]")
    Check("error code", r[0] == 0 and r[2][0] == "STRAY_CLOSE_BRACKET", str(r[2]) if r[0] == 0 else "")


def TestGap12FloatStringWeight():
    print("[Gap #12] float-string weights flagged (3-tuple, unambiguous weight)")
    root = BCLNode("root")
    bad = BCLNode("Bad", parent=root)
    root.state["children"].append(bad)
    bad.state["tuples"].append(["text", "fix_sql", "100.5"])
    v = BCLValidator()
    r = v.Run("validate", {"root": root})
    data = r[1][1]
    float_str = [x for x in data["violations"] if "100.5" in x.get("message", "")]
    Check("float-string weight flagged", len(float_str) > 0, "silently accepted")


def TestGap5MissingCheckFnStrict():
    print("[Gap #5] missing check function errors in strict mode")
    lex = BCLTokenizer()
    par = BCLParser()
    tree = '[@rule]{[@check_a]{[@Pass]{("fix_a";90)}[@Fail]{("fallback";50)}}}'
    pr = par.Run("parse", {"tokens": lex.Run("tokenize", {"text": tree})[1]["tokens"]})
    w = BCLDecisionWalker()
    r1 = w.Run("walk", {"root": pr[1]["root"], "rule_id": "rule", "check_functions": {}, "schema_meta": {}, "strict_checks": False})
    Check("lenient: silent None", r1[0] == 1 and r1[1] is None, str(r1))
    r2 = w.Run("walk", {"root": pr[1]["root"], "rule_id": "rule", "check_functions": {}, "schema_meta": {}, "strict_checks": True})
    Check("strict: errors", r2[0] == 0 and r2[2][0] == "CHECK_NOT_FOUND", str(r2[2]) if r2[0] == 0 else str(r2))


def TestGap10TabEscaping():
    print("[Gap #10] ToBcl escapes tab characters")
    n = BCLNode("T")
    n.state["tuples"].append(["v", "has\ttab"])
    rt = n.Run("to_bcl", {})
    has_raw_tab = "\t" in rt[1].split('"')[1] if '"' in rt[1] else False
    Check("no raw tab in output", not has_raw_tab, "raw tab present")
    lex = BCLTokenizer()
    par = BCLParser()
    lr = lex.Run("tokenize", {"text": rt[1]})
    pr = par.Run("parse", {"tokens": lr[1]["tokens"]})
    rv = pr[1]["root"].state["children"][0].Run("get", {"key": "v"})
    Check("tab round-trips", rv[1] == "has\ttab", repr(rv[1]))


def TestCanonicalFileValidates():
    print("[Regression] canonical schema file validates without crash")
    if not os.path.exists(CANONICAL_FILE):
        Check("file exists", False, CANONICAL_FILE)
        return
    text = open(CANONICAL_FILE).read()
    lex = BCLTokenizer()
    par = BCLParser()
    v = BCLValidator()
    lr = lex.Run("tokenize", {"text": text})
    Check("lex ok", lr[0] == 1, str(lr[2]) if lr[0] == 0 else "")
    pr = par.Run("parse", {"tokens": lr[1]["tokens"]})
    Check("parse ok", pr[0] == 1, str(pr[2]) if pr[0] == 0 else "")
    vr = v.Run("validate", {"root": pr[1]["root"]})
    Check("validate no crash", vr[0] == 1, str(vr[2]) if vr[0] == 0 else "")
    data = vr[1][1]
    r24 = [x for x in data["violations"] if "capital" in x.get("message", "")]
    Check("no false rule-24 capital violations", len(r24) == 0, "%d false positives" % len(r24))


def main():
    print("=" * 70)
    print("BCL Review Fixes — Verification Tests")
    print("=" * 70)
    tests = [
        TestFix1ValidatorNoCrash, TestFix2LexerMultiDot, TestFix3CrudQuarantined,
        TestFix4LowercaseExempt, TestFix5DecisionWalker, TestFix6BclAllQuarantined,
        TestFix7DuplicatesQuarantined, TestFix8GetAmbiguity, TestFix9GetWeightAllTuples,
        TestFix10ToBclEscaping, TestFix11ValidateIrUsesLexer, TestFix12StringWeights,
        TestFix13StrayBracket,
        TestGap12FloatStringWeight, TestGap5MissingCheckFnStrict, TestGap10TabEscaping,
        TestCanonicalFileValidates,
    ]
    for t in tests:
        print()
        t()
    print()
    print("=" * 70)
    print("RESULT: %d passed, %d failed" % (PASS, FAIL))
    print("=" * 70)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
