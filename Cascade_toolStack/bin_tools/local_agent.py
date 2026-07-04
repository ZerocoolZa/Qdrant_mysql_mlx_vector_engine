#!/usr/bin/env python3
"""
Minimal local LLM agent — no server, no HTTP, no Gradio.
Direct mlx-lm inference + msearch tool calling.
"""

import json
import subprocess
import sys
import time

from mlx_lm import load, generate

MODEL = "mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit"
MSEARCH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack/Built_tools/msearch"

def call_msearch(query):
    result = subprocess.run([MSEARCH, query], capture_output=True, text=True, timeout=10)
    output = result.stdout.strip()
    if len(output) > 3000:
        output = output[:3000] + "\n... (truncated)"
    return output if output else "No results found."

def main():
    print(f"Loading {MODEL}...")
    model, tokenizer = load(MODEL)
    print("Model loaded.\n")

    user_question = sys.argv[1] if len(sys.argv) > 1 else "What is MemUnit?"

    messages = [
        {"role": "system", "content": "You are a coding assistant. You have access to msearch, a local knowledge base search tool. Call msearch to find information, then answer based on the results. Only call msearch once."},
        {"role": "user", "content": user_question},
    ]

    tools_schema = [
        {
            "type": "function",
            "function": {
                "name": "msearch",
                "description": "Search the local knowledge base (215K+ messages, code, docs). Returns exact matches with context.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "What to search for"}
                    },
                    "required": ["query"],
                },
            },
        }
    ]

    start = time.time()

    for step in range(4):
        prompt = tokenizer.apply_chat_template(
            messages,
            tools=tools_schema,
            add_generation_prompt=True,
            tokenize=False,
        )

        response = generate(
            model=model,
            tokenizer=tokenizer,
            prompt=prompt,
            max_tokens=300,
            verbose=False,
        )

        has_tool_call = False

        if hasattr(tokenizer, "tool_call_start") and tokenizer.tool_call_start in response:
            has_tool_call = True
            start_idx = response.find(tokenizer.tool_call_start) + len(tokenizer.tool_call_start)
            end_idx = response.find(tokenizer.tool_call_end)
            if end_idx == -1:
                end_idx = len(response)
            tool_call_string = response[start_idx:end_idx].strip()
        elif "```json" in response and ("msearch" in response or "name" in response):
            json_start = response.find("```json") + 7
            json_end = response.find("```", json_start)
            if json_end == -1:
                json_end = len(response)
            tool_call_string = response[json_start:json_end].strip()
            has_tool_call = True
        elif response.strip().startswith("{") and "msearch" in response:
            tool_call_string = response.strip()
            has_tool_call = True

        if has_tool_call:
            try:
                tool_call = None
                if hasattr(tokenizer, "tool_parser"):
                    try:
                        tool_call = tokenizer.tool_parser(tool_call_string)
                    except Exception:
                        pass
                if not tool_call:
                    parsed = json.loads(tool_call_string)
                    if isinstance(parsed, list):
                        tool_call = parsed[0]
                    else:
                        tool_call = parsed
                tool_name = tool_call["name"]
                tool_args = tool_call["arguments"]
            except Exception as e:
                print(f"[PARSE ERROR] {e}")
                print(f"[RAW] {response}")
                break

            print(f"[STEP {step+1}] Model called {tool_name}({tool_args})")

            if tool_name == "msearch":
                result = call_msearch(tool_args.get("query", ""))
                print(f"[RESULT] {len(result)} chars from msearch")
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "tool", "content": result})
            else:
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "tool", "content": f"Unknown tool: {tool_name}"})
        else:
            elapsed = time.time() - start
            print(f"\n[FINAL ANSWER] ({elapsed:.1f}s)")
            print(response)
            break
    else:
        print("\n[MAX STEPS REACHED]")

if __name__ == "__main__":
    main()
