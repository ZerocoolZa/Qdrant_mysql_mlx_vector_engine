#!/usr/bin/env python3
#[@GHOST]
#[@VBSTYLE]
#[@FILEID] agent_mcp_server.py
#[@SUMMARY] Minimal MCP server exposing agent invocation as MCP tools over stdio JSON-RPC
#[@CLASS] AgentMcpServer
#[@METHOD] Run
import sys
import json
import subprocess
import os
import shutil

DEVIN_CLI = "/Users/wws/.local/bin/devin"
CWD = "/Users/wws/Qdrant_mysql_mlx_vector_engine"

TOOLS = [
    {
        "name": "invoke_devin",
        "description": "Invoke Devin Local agent with a prompt. Devin can read files, edit code, run shell commands. Returns Devin's full output as text.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The task/prompt to send to Devin"
                },
                "permission_mode": {
                    "type": "string",
                    "description": "Permission mode: auto, accept-edits, smart, or dangerous",
                    "default": "auto"
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory for Devin",
                    "default": "/Users/wws/Qdrant_mysql_mlx_vector_engine"
                }
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "list_agents",
        "description": "List all available agent backends and their status (installed, path, version).",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "invoke_shell",
        "description": "Invoke a shell command and return stdout+stderr. Simple passthrough for agent orchestration.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute"
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory",
                    "default": "/Users/wws/Qdrant_mysql_mlx_vector_engine"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds",
                    "default": 120
                }
            },
            "required": ["command"]
        }
    }
]


def handle_invoke_devin(args):
    prompt = args.get("prompt", "")
    mode = args.get("permission_mode", "auto")
    work_dir = args.get("cwd", CWD)
    if not prompt:
        return {"content": [{"type": "text", "text": "Error: prompt is required"}], "isError": True}
    if not os.path.exists(DEVIN_CLI):
        return {"content": [{"type": "text", "text": "Error: Devin CLI not found at " + DEVIN_CLI}], "isError": True}
    cmd = [DEVIN_CLI, "--print", "--permission-mode", mode, "--", prompt]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=work_dir
        )
        output = result.stdout
        if result.stderr:
            output = output + "\n--- STDERR ---\n" + result.stderr
        if result.returncode != 0:
            output = output + "\n--- EXIT CODE: " + str(result.returncode) + " ---"
        return {"content": [{"type": "text", "text": output}]}
    except subprocess.TimeoutExpired:
        return {"content": [{"type": "text", "text": "Error: Devin timed out after 300s"}], "isError": True}
    except Exception as e:
        return {"content": [{"type": "text", "text": "Error: " + str(e)}], "isError": True}


def handle_list_agents(args):
    agents = []
    devin_path = DEVIN_CLI
    devin_installed = os.path.exists(devin_path)
    devin_version = ""
    if devin_installed:
        try:
            vresult = subprocess.run([devin_path, "version"], capture_output=True, text=True, timeout=10)
            devin_version = vresult.stdout.strip()
        except Exception:
            devin_version = "unknown"
    agents.append({
        "name": "Devin Local",
        "installed": devin_installed,
        "path": devin_path,
        "version": devin_version,
        "invocation": "devin --print --permission-mode auto -- '<prompt>'"
    })
    agents.append({
        "name": "GLM Agent",
        "installed": False,
        "path": "ACP agent — select from Windsurf agent dropdown",
        "version": "glm-5.1, glm-5-turbo, glm-4.7, glm-4.5-air",
        "invocation": "UI only — no CLI"
    })
    agents.append({
        "name": "Devin Cloud",
        "installed": devin_installed,
        "path": devin_path + " cloud",
        "version": devin_version,
        "invocation": "devin cloud <subcommand>"
    })
    lines = []
    for a in agents:
        lines.append("Agent: " + a["name"])
        lines.append("  Installed: " + str(a["installed"]))
        lines.append("  Path: " + a["path"])
        lines.append("  Version: " + a["version"])
        lines.append("  Invocation: " + a["invocation"])
        lines.append("")
    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


def handle_invoke_shell(args):
    command = args.get("command", "")
    work_dir = args.get("cwd", CWD)
    timeout = args.get("timeout", 120)
    if not command:
        return {"content": [{"type": "text", "text": "Error: command is required"}], "isError": True}
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=work_dir
        )
        output = result.stdout
        if result.stderr:
            output = output + "\n--- STDERR ---\n" + result.stderr
        return {"content": [{"type": "text", "text": output}]}
    except subprocess.TimeoutExpired:
        return {"content": [{"type": "text", "text": "Error: command timed out after " + str(timeout) + "s"}], "isError": True}
    except Exception as e:
        return {"content": [{"type": "text", "text": "Error: " + str(e)}], "isError": True}


def process_message(msg):
    method = msg.get("method", "")
    params = msg.get("params", {})
    msg_id = msg.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "agent-mcp-server",
                    "version": "1.0.0"
                }
            }
        }

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": TOOLS
            }
        }

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        if tool_name == "invoke_devin":
            result = handle_invoke_devin(tool_args)
        elif tool_name == "list_agents":
            result = handle_list_agents(tool_args)
        elif tool_name == "invoke_shell":
            result = handle_invoke_shell(tool_args)
        else:
            result = {"content": [{"type": "text", "text": "Unknown tool: " + tool_name}], "isError": True}
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": result
        }

    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {
            "code": -32601,
            "message": "Method not found: " + method
        }
    }


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = process_message(msg)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
