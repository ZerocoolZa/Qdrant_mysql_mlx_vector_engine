#!/usr/bin/env python3
#[@GHOST]{[@file<smart_router.py>][@state<active>][@ver<v1.0>][@auth<Devin>][@date<2026-07-04>]}
#[@VBSTYLE]{[@auth<Devin>][@role<smart_router>][@return<json>][@no<print|hardcoded>]}
#[@FILEID]{smart_router}
#[@SUMMARY]{Mini AI router — uses local MLX Qwen model to pick the best MCP tool for a natural language request. Falls back to keyword matching if model unavailable.}
#[@CLASS]{SmartRouter}
#[@METHOD]{__init__, build_prompt, route_with_llm, route_with_keywords, run}

"""
Smart Router — Mini AI tool dispatcher.

Takes a natural language request like "search for kokoro voice pipeline" and
figures out which MCP tool to call and what parameters to pass.

Two modes:
  1. LLM mode (default): Uses local Qwen2.5-Coder-1.5B-Instruct via mlx_lm
     to classify the intent. Slow (~7s first call, ~2s cached) but smart.
  2. Keyword mode (fallback): Fast keyword matching if MLX unavailable.

Input (stdin): JSON with:
  - query: natural language request
  - tools: list of {name, description, when_to_use, category, params}
  - mode: "llm" or "keyword" (default: llm)

Output (stdout): JSON with:
  - tool: selected tool name
  - params: extracted parameters dict
  - confidence: 0.0-1.0
  - reasoning: why this tool was picked
  - alternatives: list of other candidates
  - mode: which router mode was used
"""

import sys
import json
import re
import os

TOOL_CATALOG = [
    {"name": "cascade_chat_search_sessions", "category": "chat-search",
     "description": "Search which chat sessions discussed a topic",
     "when_to_use": "find sessions about a topic, which chat discussed X, search conversations by keyword",
     "params": {"query": "string: search keywords", "limit": "int: max results"}},
    {"name": "cascade_chat_session_detail", "category": "chat-search",
     "description": "Get full detail of one chat session",
     "when_to_use": "show me session, get details, full conversation, trajectory detail",
     "params": {"trajectory_id": "string: UUID of the session"}},
    {"name": "cascade_chat_search_files", "category": "chat-search",
     "description": "Find which sessions mentioned/created/modified a file",
     "when_to_use": "which sessions touched file X, who created file, file mentions",
     "params": {"query": "string: file path or name"}},
    {"name": "cascade_chat_search", "category": "chat-search",
     "description": "Keyword search across loaded chat content in RAM",
     "when_to_use": "search loaded chats, keyword in messages, RAM search",
     "params": {"query": "string: search keywords"}},
    {"name": "cascade_chat_load_all", "category": "chat-ops",
     "description": "Load all .pb chat files into RAM",
     "when_to_use": "load all chats, load everything, decrypt all pb files",
     "params": {}},
    {"name": "cascade_chat_scan", "category": "chat-ops",
     "description": "Scan disk for .pb chat files",
     "when_to_use": "scan, discover, what files exist, how many pb files",
     "params": {}},
    {"name": "cascade_chat_stats", "category": "chat-ops",
     "description": "Show RAM DB statistics",
     "when_to_use": "stats, statistics, how many loaded, count, summary",
     "params": {}},
    {"name": "cascade_chat_list", "category": "chat-ops",
     "description": "List loaded trajectories in RAM",
     "when_to_use": "list loaded, what loaded, show loaded chats",
     "params": {}},
    {"name": "cascade_chat_read", "category": "chat-ops",
     "description": "Read a single .pb chat as conversation",
     "when_to_use": "read chat, read pb, show conversation, open chat",
     "params": {"file": "string: path to .pb file"}},
    {"name": "cascade_chat_export", "category": "chat-ops",
     "description": "Export a .pb chat to markdown files",
     "when_to_use": "export chat, export to markdown, archive chat",
     "params": {"file": "string: path to .pb file", "outdir": "string: output dir"}},
    {"name": "cascade_chat_export_db", "category": "chat-mysql",
     "description": "Export loaded RAM chats to MySQL",
     "when_to_use": "export to mysql, populate database, sync mysql, transfer to db",
     "params": {}},
    {"name": "cascade_chat_verify_db", "category": "chat-mysql",
     "description": "Verify all .pb files are in MySQL",
     "when_to_use": "verify db, check mysql, all in database, missing from db",
     "params": {}},
    {"name": "cascade_chat_clean", "category": "chat-mysql",
     "description": "Delete .pb files after verifying in MySQL",
     "when_to_use": "clean, delete pb files, remove old chats",
     "params": {"confirm": "bool: must be true"}},
    {"name": "bcl_chat_compress", "category": "bcl",
     "description": "Compress chat markdown to BCL tokens",
     "when_to_use": "compress, bcl, tokenize, extract tokens",
     "params": {"input": "string: input file path"}},
    {"name": "bcl_chat_dry_run", "category": "bcl",
     "description": "Preview BCL token extraction without writing",
     "when_to_use": "dry run, preview bcl, estimate tokens, preview compression",
     "params": {"input": "string: input file path"}},
    {"name": "read_file", "category": "filesystem",
     "description": "Read file contents",
     "when_to_use": "read file, cat file, show file, contents of file",
     "params": {"path": "string: file path"}},
    {"name": "write_file", "category": "filesystem",
     "description": "Write content to a file",
     "when_to_use": "write file, save file, create file",
     "params": {"path": "string: file path", "content": "string: content"}},
    {"name": "list_directory", "category": "filesystem",
     "description": "List directory contents",
     "when_to_use": "list dir, ls, directory contents, what's in folder",
     "params": {"path": "string: directory path"}},
    {"name": "tools_md", "category": "meta",
     "description": "Generate tools documentation",
     "when_to_use": "tools, help, what tools, available tools, document tools",
     "params": {"preview": "bool: preview only"}},
]


class SmartRouter:
    def __init__(self):
        self.model = None
        self.tokenizer = None

    def load_model(self):
        """Lazy-load the MLX model."""
        if self.model is not None:
            return True
        try:
            from mlx_lm import load
            self.model, self.tokenizer = load("Qwen/Qwen2.5-Coder-1.5B-Instruct")
            return True
        except Exception:
            return False

    def build_prompt(self, query, tools):
        """Build the classification prompt for the LLM."""
        tool_list = []
        for i, t in enumerate(tools):
            tool_list.append(
                f"{i+1}. {t['name']} (category: {t['category']}) — {t['description']}. "
                f"USE WHEN: {t['when_to_use']}"
            )
        tools_text = "\n".join(tool_list)

        prompt = (
            f"You are a precise tool router. Pick the ONE best tool for the user's request.\n\n"
            f"Rules:\n"
            f"- If the request mentions 'which sessions' + a file/path → pick cascade_chat_search_files\n"
            f"- If the request mentions 'search for' + topic keywords → pick cascade_chat_search_sessions\n"
            f"- If the request mentions 'show session' + a UUID → pick cascade_chat_session_detail\n"
            f"- If the request mentions 'load' + 'all' → pick cascade_chat_load_all\n"
            f"- If the request mentions 'stats' or 'how many' → pick cascade_chat_stats\n"
            f"- If the request mentions 'export' + 'mysql' → pick cascade_chat_export_db\n"
            f"- If the request mentions 'compress' or 'bcl' → pick bcl_chat_compress\n"
            f"- If the request mentions 'read file' or 'cat file' → pick read_file\n"
            f"- If the request mentions 'tools' or 'help' → pick tools_md\n\n"
            f"Tools:\n{tools_text}\n\n"
            f"User request: \"{query}\"\n\n"
            f"Respond with ONLY a JSON object (no markdown, no backticks):\n"
            f'{{"tool_number": <int>, "search_query": "<search terms or empty>", '
            f'"file_path": "<file path or empty>", '
            f'"trajectory_id": "<UUID or empty>"}}'
        )
        return prompt

    def route_with_llm(self, query, tools):
        """Use local MLX model to pick the tool."""
        if not self.load_model():
            return None

        from mlx_lm import generate

        prompt = self.build_prompt(query, tools)

        # Format as chat
        if hasattr(self.tokenizer, 'apply_chat_template'):
            messages = [{"role": "user", "content": prompt}]
            formatted = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        else:
            formatted = prompt

        response = generate(
            self.model, self.tokenizer,
            prompt=formatted,
            max_tokens=100,
            verbose=False,
        )

        # Parse the JSON response
        # Try to find JSON in the response
        json_match = re.search(r'\{[^}]+\}', response)
        if json_match:
            try:
                result = json.loads(json_match.group())
                tool_num = result.get("tool_number", 0)
                if 1 <= tool_num <= len(tools):
                    tool = tools[tool_num - 1]
                    params = {}
                    sq = result.get("search_query", "")
                    fp = result.get("file_path", "")
                    tid = result.get("trajectory_id", "")

                    # Map extracted values to tool params
                    if "query" in tool.get("params", {}):
                        params["query"] = sq or self._extract_search_terms(query)
                    if "file" in tool.get("params", {}):
                        params["file"] = fp or self._extract_file_path(query)
                    if "path" in tool.get("params", {}):
                        params["path"] = fp or self._extract_file_path(query)
                    if "input" in tool.get("params", {}):
                        params["input"] = fp or self._extract_file_path(query)
                    if "trajectory_id" in tool.get("params", {}):
                        params["trajectory_id"] = tid or self._extract_uuid(query)

                    return {
                        "tool": tool["name"],
                        "params": params,
                        "confidence": 0.8,
                        "reasoning": f"LLM picked tool #{tool_num}: {tool['description']}",
                        "alternatives": [],
                        "mode": "llm",
                        "raw_response": response[:200],
                    }
            except json.JSONDecodeError:
                pass

        # LLM failed to produce valid JSON — fall back
        return None

    def route_with_keywords(self, query, tools):
        """Fast keyword-based routing (fallback)."""
        query_lower = query.lower()
        scored = []

        for t in tools:
            score = 0
            hits = []
            # Check when_to_use keywords
            for kw in t["when_to_use"].split(", "):
                kw = kw.strip().lower()
                if kw and kw in query_lower:
                    score += 2
                    hits.append(kw)
            # Check description words
            for word in t["description"].lower().split():
                if len(word) > 3 and word in query_lower:
                    score += 1
                    hits.append(word)
            # Check category
            if t["category"] in query_lower:
                score += 3
                hits.append(t["category"])

            if score > 0:
                scored.append((score, t, hits))

        scored.sort(key=lambda x: x[0], reverse=True)

        if not scored:
            return {
                "tool": None,
                "params": {},
                "confidence": 0.0,
                "reasoning": "No keyword match found",
                "alternatives": [],
                "mode": "keyword",
            }

        best_score, best_tool, best_hits = scored[0]
        params = {}

        if "query" in best_tool.get("params", {}):
            params["query"] = self._extract_search_terms(query)
        if "file" in best_tool.get("params", {}):
            params["file"] = self._extract_file_path(query)
        if "path" in best_tool.get("params", {}):
            params["path"] = self._extract_file_path(query)
        if "input" in best_tool.get("params", {}):
            params["input"] = self._extract_file_path(query)
        if "trajectory_id" in best_tool.get("params", {}):
            params["trajectory_id"] = self._extract_uuid(query)

        alts = [
            {"tool": s[1]["name"], "score": s[0], "hits": s[2]}
            for s in scored[1:4]
        ]

        return {
            "tool": best_tool["name"],
            "params": params,
            "confidence": min(best_score / 10.0, 1.0),
            "reasoning": f"Keyword match (score={best_score}, hits: {', '.join(best_hits)})",
            "alternatives": alts,
            "mode": "keyword",
        }

    def _extract_search_terms(self, query):
        """Extract search terms from the query."""
        stop = {"search", "for", "find", "show", "me", "get", "the", "a",
                "which", "what", "where", "chats", "sessions", "session",
                "chat", "please", "can", "you", "i", "want", "need", "tell",
                "about", "of", "to", "in", "all", "look", "looking"}
        words = query.split()
        kept = [w for w in words if w.lower() not in stop]
        return " ".join(kept) if kept else query

    def _extract_file_path(self, query):
        """Extract a file path from the query."""
        m = re.search(r'(?:~/[^ ]+|/[^ ]+\.[a-zA-Z]+|[^ /]+\.(?:py|md|pb|txt|go|js|ts|json|yaml|yml|sql|sh|c|h))', query)
        return m.group(0).strip("\"'`,.") if m else ""

    def _extract_uuid(self, query):
        """Extract a UUID from the query."""
        m = re.search(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', query)
        return m.group(0) if m else ""

    def run(self, query, mode="llm"):
        """Route a query to the best tool.

        Modes:
          - llm: Use local MLX model (slow but smart)
          - keyword: Fast keyword matching (instant)
          - hybrid: LLM first, keyword as tiebreaker/override (default)
        """
        tools = TOOL_CATALOG

        if mode == "keyword":
            return self.route_with_keywords(query, tools)

        if mode == "llm":
            result = self.route_with_llm(query, tools)
            if result is not None:
                return result
            result = self.route_with_keywords(query, tools)
            result["reasoning"] += " (LLM unavailable, used keyword fallback)"
            return result

        # hybrid: run both, compare, pick best
        llm_result = self.route_with_llm(query, tools)
        kw_result = self.route_with_keywords(query, tools)

        if llm_result is None:
            kw_result["reasoning"] += " (LLM unavailable, keyword only)"
            return kw_result

        # If keyword score is high AND disagrees with LLM, trust keywords
        kw_conf = kw_result.get("confidence", 0)
        llm_tool = llm_result.get("tool")
        kw_tool = kw_result.get("tool")

        if kw_conf >= 0.5 and kw_tool != llm_tool:
            # Keyword match is strong and disagrees — use keyword
            kw_result["reasoning"] = (
                f"Hybrid: keyword overrode LLM (LLM picked {llm_tool}, "
                f"keyword picked {kw_tool} with confidence {kw_conf:.2f})"
            )
            kw_result["alternatives"].insert(0, {
                "tool": llm_tool,
                "score": 0,
                "hits": ["llm_choice"],
            })
            return kw_result

        # Otherwise trust LLM
        llm_result["reasoning"] += f" (keyword fallback agreed: {kw_tool == llm_tool})"
        if kw_tool != llm_tool:
            llm_result["alternatives"] = kw_result.get("alternatives", [])
        return llm_result


def main():
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        print(json.dumps({"error": "invalid JSON input"}))
        sys.exit(1)

    query = data.get("query", "")
    mode = data.get("mode", "llm")

    if not query:
        print(json.dumps({"error": "no query provided"}))
        sys.exit(1)

    router = SmartRouter()
    result = router.run(query, mode)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
