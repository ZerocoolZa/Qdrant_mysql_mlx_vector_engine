import subprocess
import sys
import os

# -----------------------------
# Provider Layer
# -----------------------------

def run_msearch(query: str):
    cmd = [
        "/Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack/Built_tools/msearch",
        query
    ]
    return subprocess.check_output(cmd, text=True)

def run_local_echo(query: str):
    return f"[LOCAL_ECHO] {query}"

def run_gemini(query: str):
    """Chat with Gemini via browser automation (no API key)."""
    script = os.path.join(os.path.dirname(__file__), "gemini_cli.py")
    result = subprocess.run(
        [sys.executable, script, query],
        capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        return f"[GEMINI ERROR] {result.stderr.strip() or result.stdout.strip()}"
    return result.stdout.strip()

def run_web_stub(query: str):
    """Placeholder for future web scraping providers."""
    return f"[WEB_STUB] would search: {query}"

# -----------------------------
# Router Layer
# -----------------------------

PROVIDERS = {
    "local": run_local_echo,
    "msearch": run_msearch,
    "gemini": run_gemini,
    "web": run_web_stub,
}

def route(provider: str, query: str):
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}")
    return PROVIDERS[provider](query)

# -----------------------------
# CLI Entry
# -----------------------------

def main():
    if len(sys.argv) < 3:
        print("Usage: python router_cli.py <provider> <query>")
        print("Providers: local | msearch | gemini | web")
        sys.exit(1)
    provider = sys.argv[1]
    query = " ".join(sys.argv[2:])
    result = route(provider, query)
    print(result)

if __name__ == "__main__":
    main()
