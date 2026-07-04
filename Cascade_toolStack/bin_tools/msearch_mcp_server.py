#!/usr/bin/env python3
"""
MCP server that exposes msearch as a tool to Rapid-MLX.
When the LLM calls msearch, this server runs the C binary and returns results.
"""

import subprocess
import json
import sys
import os

MSEARCH_BIN = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack/Built_tools/msearch"

def handle_request(req):
    method = req.get("method", "")
    req_id = req.get("id", None)

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "msearch-server", "version": "1.0.0"},
            },
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "msearch",
                        "description": "Search the local knowledge base (MySQL + SQLite, 215K+ messages). Returns exact matches with surrounding context.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "Search query — what to look for in the knowledge base",
                                }
                            },
                            "required": ["query"],
                        },
                    }
                ]
            },
        }

    if method == "tools/call":
        params = req.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if tool_name == "msearch":
            query = arguments.get("query", "")
            try:
                result = subprocess.run(
                    [MSEARCH_BIN, query],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                output = result.stdout.strip()
                if len(output) > 4000:
                    output = output[:4000] + "\n... (truncated)"
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": output if output else "No results found."}]
                    },
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": f"msearch error: {str(e)}"}],
                        "isError": True,
                    },
                }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_request(req)
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except json.JSONDecodeError:
            continue
        except Exception as e:
            sys.stderr.write(f"Error: {e}\n")


if __name__ == "__main__":
    main()
