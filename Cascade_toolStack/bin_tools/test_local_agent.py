import json, subprocess, requests, time

SERVER = "http://127.0.0.1:8765"
MODEL = "mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit"
MSEARCH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack/Built_tools/msearch"

def call_msearch(query):
    result = subprocess.run([MSEARCH, query], capture_output=True, text=True, timeout=10)
    output = result.stdout.strip()
    if len(output) > 2000:
        output = output[:2000] + "\n... (truncated)"
    return output

messages = [
    {"role": "system", "content": "You are a helpful assistant with access to a local search tool called msearch. Call msearch ONCE to find information, then answer the user's question based on the results. Do NOT call msearch more than once."},
    {"role": "user", "content": "What is MemUnit? Search my local database and tell me."},
]

tools = [
    {
        "type": "function",
        "function": {
            "name": "msearch",
            "description": "Search the local knowledge base for information",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"],
            },
        },
    }
]

start = time.time()

for step in range(3):
    resp = requests.post(
        f"{SERVER}/v1/chat/completions",
        json={"model": MODEL, "messages": messages, "tools": tools, "tool_choice": "auto", "max_tokens": 200},
    )
    data = resp.json()
    msg = data["choices"][0]["message"]

    if msg.get("tool_calls"):
        for tc in msg["tool_calls"]:
            func_name = tc["function"]["name"]
            args = json.loads(tc["function"]["arguments"])
            print(f"[TOOL CALL] {func_name}({args})")

            if func_name == "msearch":
                result = call_msearch(args.get("query", ""))
                print(f"[TOOL RESULT] {len(result)} chars")
                messages.append({"role": "assistant", "content": "", "tool_calls": [tc]})
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
    else:
        elapsed = time.time() - start
        print(f"\n[FINAL ANSWER] ({elapsed:.1f}s)")
        print(msg.get("content", ""))
        break
