#!/usr/bin/env python3
# [@GHOST]{file_path="Dom_Graph/dom_graph_bridge.py"
# date="2026-06-28" author="Devin" session_id="domgraph-phase4"
# context="ContextRAM bridge — Swift ctx binary calls this via subprocess"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase Tuple3 JSON stdout"}
# [@FILEID]{id="dom_graph_bridge.py" domain="unified_graph" authority="bridge"}
# [@SUMMARY]{summary="Subprocess bridge between ContextRAM Swift ctx binary and DomGraphEngine. Called via: python3 dom_graph_bridge.py <command> --domain codefix --query '...' --file '...' --limit 10. Returns JSON to stdout: {ok, data, error}."}
# [@METHOD]{method="main" type="entry"}
# [@METHOD]{method="parse_argv" type="helper"}
# [@METHOD]{method="to_context_assembly" type="converter"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<warn>][@notes<Subprocess bridge between ContextRAM Swift ctx binary and DomGraphEngine. Has GHOST/VBSTYLE/FILEID/SUMMARY/METHOD headers but NO @CLASS header -- uses module-level functions (parse_argv, to_context_assembly, main) instead of a class. No Run() dispatch. No Tuple3 returns (returns JSON dict). No print/decorators/self._. No hardcoded paths (uses os.path.dirname). Not VBStyle compliant -- bridge/CLI entry point.>][@todos<1. Add @CLASS header or document as non-class entry point. 2. Consider wrapping in a class with Run() dispatch for VBStyle compliance. 3. Add Tuple3 return pattern if feasible.>]}
"""
dom_graph_bridge.py — ContextRAM ↔ DomGraphEngine bridge.

Called by Swift ctx binary via subprocess:
    python3 dom_graph_bridge.py decide --domain codefix --query "fix import error" --file gui.py
    python3 dom_graph_bridge.py get_candidates --domain codefix --query "NameError"
    python3 dom_graph_bridge.py trace
    python3 dom_graph_bridge.py stats

Returns JSON to stdout:
    {"ok": 1, "data": {...}, "error": null}
    {"ok": 0, "data": null, "error": {"code": "...", "desc": "..."}}

ContextRAM integration:
    Swift AutoContextRetriever.smartAssemble() calls this bridge,
    parses JSON, and merges results into ContextAssembly:
      - decisions[]  ← DomGraphEngine decide output (chosen fix)
      - facts[]      ← DomGraphEngine candidates (knowledge nodes)
      - rules[]      ← DomGraphEngine when_rules (triggered rules)
      - memories[]   ← DomGraphEngine past decisions
      - reason_trace ← DomGraphEngine trace steps
"""
import json
import os
import sys

ENGINE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "DomGraphEngine.py")


def parse_argv(argv):
    """Parse command-line args into (command, params dict).
    Format: python3 bridge.py <command> --key value --key2 value2
    Boolean flags: --persist (no value → True)
    """
    if len(argv) < 2:
        return None, {}
    command = argv[1]
    params = {}
    i = 2
    while i < len(argv):
        arg = argv[i]
        if arg.startswith("--"):
            key = arg[2:]
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                params[key] = argv[i + 1]
                i += 2
            else:
                params[key] = True
                i += 1
        else:
            i += 1
    # Type conversions
    if "limit" in params:
        try:
            params["limit"] = int(params["limit"])
        except (ValueError, TypeError):
            pass
    if "persist" in params:
        val = params["persist"]
        if isinstance(val, str):
            params["persist"] = val.lower() in ("true", "1", "yes")
    return command, params


def to_context_assembly(decide_result, trace_result, candidates_result):
    """Convert DomGraphEngine outputs into ContextRAM ContextAssembly shape.
    ContextAssembly has: query, goals, tasks, facts, rules, memories,
                         decisions, hypotheses, openQuestions
    """
    assembly = {
        "query": None,
        "goals": [],
        "tasks": [],
        "facts": [],
        "rules": [],
        "memories": [],
        "decisions": [],
        "hypotheses": [],
        "openQuestions": [],
        "reason_trace": [],
    }
    # From decide result
    if decide_result and decide_result.get("ok") == 1:
        data = decide_result["data"]
        assembly["query"] = data.get("query")
        chosen = data.get("chosen")
        if chosen:
            assembly["decisions"].append(_node_to_context_node(chosen, "decision"))
        for candidate in data.get("evaluated", []):
            assembly["facts"].append(_node_to_context_node(candidate, "fact"))
        assembly["reason_trace"] = data.get("reason_trace", [])
    # From candidates result (if decide didn't produce enough)
    if candidates_result and candidates_result.get("ok") == 1 and not assembly["facts"]:
        for candidate in candidates_result["data"].get("candidates", []):
            assembly["facts"].append(_node_to_context_node(candidate, "fact"))
    # From trace result
    if trace_result and trace_result.get("ok") == 1:
        if not assembly["reason_trace"]:
            assembly["reason_trace"] = trace_result["data"].get("reason_trace", [])
    return assembly


def _node_to_context_node(node, node_type):
    """Convert a DomGraphEngine node to ContextRAM ContextNode shape."""
    props = node.get("properties", {})
    if isinstance(props, str):
        try:
            props = json.loads(props)
        except (json.JSONDecodeError, TypeError):
            props = {}
    return {
        "nodeID": str(node.get("node_id", "")),
        "type": node_type,
        "value": node.get("description") or node.get("name", ""),
        "status": node.get("status", "active"),
        "authority": "model",
        "score": node.get("decision_score", node.get("confidence", 0)),
        "tags": [node.get("domain_tags", "")] if node.get("domain_tags") else [],
        "source": "DomGraphEngine",
        "properties": props,
    }


def main():
    command, params = parse_argv(sys.argv)
    if not command:
        result = {
            "ok": 0,
            "data": None,
            "error": {"code": "NO_COMMAND", "desc": "Usage: dom_graph_bridge.py <command> [--key value ...]"},
        }
        print(json.dumps(result))
        sys.exit(1)

    # Import DomGraphEngine
    if not os.path.isfile(ENGINE_PATH):
        result = {
            "ok": 0,
            "data": None,
            "error": {"code": "ENGINE_NOT_FOUND", "desc": "DomGraphEngine.py not found at " + ENGINE_PATH},
        }
        print(json.dumps(result))
        sys.exit(1)

    sys.path.insert(0, os.path.dirname(ENGINE_PATH))
    import importlib.util
    spec = importlib.util.spec_from_file_location("DomGraphEngine", ENGINE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    engine = mod.DomGraphEngine()

    # Handle special "to_context_assembly" meta-command
    if command == "to_context_assembly":
        domain = params.get("domain", "codefix")
        query = params.get("query", "")
        limit = params.get("limit", 10)
        file_path = params.get("file")
        # Run decide pipeline
        decide_params = {"domain": domain, "query": query, "limit": limit, "persist": False}
        if file_path:
            decide_params["file"] = file_path
        decide_ok, decide_data, decide_err = engine.Run("decide", decide_params)
        decide_result = {"ok": decide_ok, "data": decide_data, "error": decide_err}
        # Get candidates separately for facts
        cand_ok, cand_data, cand_err = engine.Run("get_candidates", {"domain": domain, "query": query, "limit": limit})
        cand_result = {"ok": cand_ok, "data": cand_data, "error": cand_err}
        # Get trace
        trace_ok, trace_data, trace_err = engine.Run("trace", {})
        trace_result = {"ok": trace_ok, "data": trace_data, "error": trace_err}
        # Convert to ContextAssembly shape
        assembly = to_context_assembly(decide_result, trace_result, cand_result)
        result = {"ok": 1, "data": assembly, "error": None}
        print(json.dumps(result, default=str))
        sys.exit(0)

    # Standard command dispatch — wrap in try/except so unexpected
    # crashes (e.g. missing DB rows, import errors) return proper JSON
    # instead of a traceback to stderr and a non-zero exit code.
    try:
        ok, data, err = engine.Run(command, params)
    except Exception as exc:
        result = {
            "ok": 0,
            "data": None,
            "error": {"code": "BRIDGE_EXCEPTION", "desc": str(exc)},
        }
        print(json.dumps(result, default=str))
        sys.exit(0)

    if err and isinstance(err, (list, tuple)) and len(err) >= 2:
        error_obj = {"code": str(err[0]), "desc": str(err[1])}
    elif err:
        error_obj = {"code": "UNKNOWN", "desc": str(err)}
    else:
        error_obj = None
    result = {"ok": ok, "data": data, "error": error_obj}
    print(json.dumps(result, default=str))
    # Always exit 0 when we produced valid JSON — the caller (Go side)
    # inspects the "ok" field to determine success/failure.  A non-zero
    # exit code causes the Go subprocess wrapper to treat the entire
    # output as an error, discarding the structured JSON payload.
    sys.exit(0)


if __name__ == "__main__":
    main()
