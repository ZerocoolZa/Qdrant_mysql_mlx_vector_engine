import json, subprocess, requests, time

SERVER = "http://127.0.0.1:8765"
MODEL = "mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit"
MSEARCH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack/Built_tools/msearch"

def call_msearch(query):
    result = subprocess.run([MSEARCH, query], capture_output=True, text=True, timeout=10)
    output = result.stdout.strip()
    if len(output) > 3000:
        output = output[:3000] + "\n... (truncated)"
    return output

messages = [
    {"role": "system", "content": "You are a coding assistant with access to msearch, a local knowledge base search tool. Call msearch to find information, then answer the question based on the results. Only call msearch once."},
    {"role": "user", "content": "What is MemUnit? Search the database and tell me."},
]

tools = [
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
print("Sending query to local Qwen model...")

for step in range(4):
    resp = requests.post(
        f"{SERVER}/v1/chat/completions",
        json={"model": MODEL, "messages": messages, "tools": tools, "tool_choice": "auto", "max_tokens": 300},
    )
    data = resp.json()
    msg = data["choices"][0]["message"]

    if msg.get("tool_calls"):
        for tc in msg["tool_calls"]:
            func_name = tc["function"]["name"]
            args = json.loads(tc["function"]["arguments"])
            print(f"\n[STEP {step+1}] Model called {func_name}({args})")

            if func_name == "msearch":
                result = call_msearch(args.get("query", ""))
                print(f"[RESULT] {len(result)} chars from msearch")
                messages.append({"role": "assistant", "content": msg.get("content", ""), "tool_calls": msg["tool_calls"]})
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
            else:
                messages.append({"role": "assistant", "content": msg.get("content", ""), "tool_calls": msg["tool_calls"]})
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": f"Unknown tool: {func_name}"})
    else:
        elapsed = time.time() - start
        print(f"\n[FINAL ANSWER] ({elapsed:.1f}s)")
        print(msg.get("content", "(empty)"))
        break
else:
    print("\n[MAX STEPS REACHED - model kept calling tools]")
