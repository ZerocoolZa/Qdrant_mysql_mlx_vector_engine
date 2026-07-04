import sys
import builtins
builtins.get_ipython = lambda: None

import gradio as gr
import requests
import json

SERVER = "http://localhost:8765"
MODEL = "mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit"

def chat(message, history):
    msgs = []
    for h in history:
        msgs.append({"role": h["role"], "content": h["content"]})
    msgs.append({"role": "user", "content": message})

    resp = requests.post(
        f"{SERVER}/v1/chat/completions",
        json={"model": MODEL, "messages": msgs, "max_tokens": 512, "stream": False},
    )
    data = resp.json()
    return data["choices"][0]["message"]["content"]

demo = gr.ChatInterface(
    fn=chat,
    title="Local Qwen 2.5 Coder — Rapid-MLX",
    description="Running on your Mac. No API key. No internet.",
)

if __name__ == "__main__":
    demo.launch(server_port=7860, server_name="127.0.0.1")
