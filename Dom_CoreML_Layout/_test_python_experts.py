import struct, os, sys, subprocess
sys.path.insert(0, ".")
from CoreMLPythonTrainer import CoreMLPythonTrainer

pt = CoreMLPythonTrainer()
root = "/Users/wws/Qdrant_mysql_mlx_vector_engine"

files = {
    "main.py": "Dom_CoreML_Layout/main.py",
    "CoreMLRouter.py": "Dom_CoreML_Layout/CoreMLRouter.py",
    "GraphPhysics.py": "Dom_Graph/GraphPhysics.py",
    "GraphSignalMatrix.py": "Dom_Graph/GraphSignalMatrix.py",
    "GhostQAEngine.py": "Dom_qa_engine/GhostQAEngine.py",
    "Efi_agent_brain.py": "efl_brain/Efi_agent_brain.py",
    "wizard_mockup.py": "Dom_svg_engine/wizard_mockup.py",
    "wizard_animation_engine.py": "Dom_svg_engine/wizard_animation_engine.py",
    "GapGraph.py": "Dom_Graph/GapGraph.py",
    "OrchGraph.py": "Dom_Graph/OrchGraph.py",
}

domainIndices = {"vscode": 0, "browser": 1, "dashboard": 2, "mobile": 3, "tablet": 4}
domains = ["vscode", "browser", "dashboard", "mobile", "tablet"]

print("=== PYTHON CODE CLASSIFICATION TEST ===")
print("Each file is classified by all 5 experts.")
print()

for label, relPath in files.items():
    fpath = os.path.join(root, relPath)
    if not os.path.exists(fpath):
        print(label + " -> NOT FOUND")
        continue
    feats = pt.extractFeatures(fpath)
    with open("tmp_runtime/test_state.bin", "wb") as f:
        for v in feats:
            f.write(struct.pack("<f", v))
    votes = {}
    for domain in domains:
        wpath = "experts/" + domain + "_python.weights.bin"
        proc = subprocess.run(
            ["./coretotch", "select", wpath, "tmp_runtime/test_state.bin"],
            capture_output=True, text=True
        )
        for line in (proc.stderr + proc.stdout).split("\n"):
            if "output:" in line:
                vals = [float(x) for x in line.split("output:")[1].strip().split()]
                idx = domainIndices[domain]
                votes[domain] = vals[idx]
                break
    winner = max(votes, key=votes.get)
    print(label + " -> WINNER: " + winner + " (score=" + str(round(votes[winner], 4)) + ")")
    for d in domains:
        bar = "#" * int(votes[d] * 20)
        print("  " + d + ": " + str(round(votes[d], 4)) + " " + bar)
    print()
