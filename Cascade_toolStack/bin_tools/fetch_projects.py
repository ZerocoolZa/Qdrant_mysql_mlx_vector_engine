import sqlite3, json, subprocess, time

DB_PATH = "/Users/wws/Qdrant_mysql_mlx_vector_engine/Cascade_toolStack/bin_tools/online_projects.db"

db = sqlite3.connect(DB_PATH)
db.execute("""CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    full_name TEXT,
    github_url TEXT,
    stars INTEGER,
    language TEXT,
    description TEXT,
    topics TEXT,
    clone_url TEXT,
    default_branch TEXT,
    created_at TEXT,
    updated_at TEXT,
    fetched_at TEXT
)""")

repos = [
    "raullenchai/Rapid-MLX",
    "anemll/anemll",
    "StarTrail-org/LEANN",
]

for repo in repos:
    info = subprocess.check_output(["curl", "-s", f"https://api.github.com/repos/{repo}"], text=True)
    d = json.loads(info)
    db.execute(
        "INSERT INTO projects (name, full_name, github_url, stars, language, description, topics, clone_url, default_branch, created_at, updated_at, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            d["name"],
            d["full_name"],
            d["html_url"],
            d["stargazers_count"],
            d["language"],
            d["description"],
            json.dumps(d.get("topics", [])),
            d["clone_url"],
            d["default_branch"],
            d["created_at"],
            d["updated_at"],
            time.strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    print(f"Saved: {d['full_name']} | {d['stargazers_count']} stars | {d['language']}")

db.commit()

rows = db.execute("SELECT name, stars, language, github_url FROM projects").fetchall()
print()
print("=== SAVED TO online_projects.db ===")
for r in rows:
    print(f"  {r[0]} | {r[1]} stars | {r[2]} | {r[3]}")

db.close()
