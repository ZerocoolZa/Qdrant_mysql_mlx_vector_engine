import os, struct, subprocess

CORETOTCH = "./coretotch"
DN = ["vscode", "browser", "dashboard", "mobile", "tablet"]
vf = [0.8,0.6,0.9,0.7,0.5,0.1,0.4,0.36,0.3,0.4,0.3,0.2,0.1,0.05,0.64,0.5,0.1,0.09,0.2,0.1,0.0,0.0,0.0,0.0,0.0,0.05,0.1,0.02,0.05,0.1,0.05,0.05,0.15,0.56,0.48,0.1,0.18,0.6,0.8,0.6]

def ri(w, f):
    if not os.path.exists(w):
        return None
    with open("/tmp/ai.bin", "wb") as fh:
        for v in f:
            fh.write(struct.pack("<f", v))
    p = subprocess.run([CORETOTCH, "select", w, "/tmp/ai.bin"], capture_output=True, text=True, timeout=5)
    for l in (p.stderr + p.stdout).split("\n"):
        if "output:" in l:
            return [float(x) for x in l.split("output:")[1].strip().split()]
    return None

print("=== AST LAYER EXPERTS (vscode input) ===")
for layer in ["grammar", "idiom", "library", "style"]:
    w = "experts/ast_" + layer + "_vscode.weights.bin"
    o = ri(w, vf)
    if o:
        i = o.index(max(o))
        tag = "OK" if DN[i] == "vscode" else "WRONG"
        print("  ast_" + layer + "_vscode: pred=" + DN[i] + " conf=" + str(round(max(o), 4)) + " [" + tag + "]")
    else:
        print("  ast_" + layer + "_vscode: NONE")

print()
print("=== TRANSFORM EXPERT (vscode input) ===")
w = "experts/transform_transform_vscode.weights.bin"
o = ri(w, vf)
if o:
    print("  transform_vscode: pred_transform=" + str(o.index(max(o))) + " conf=" + str(round(max(o), 4)))
else:
    print("  transform_vscode: NONE")

print()
print("=== INVARIANT EXPERT (vscode input) ===")
w = "experts/transform_invariant_vscode.weights.bin"
o = ri(w, vf)
if o:
    print("  invariant_vscode: pred=" + str(o.index(max(o))) + " conf=" + str(round(max(o), 4)))
    if o[0] > o[1]:
        print("    -> SAFE")
    else:
        print("    -> UNSAFE")
else:
    print("  invariant_vscode: NONE")

print()
print("=== ADAPTIVE RULE EXPERTS (vscode input) ===")
for r in [0, 1, 2, 3]:
    w = "experts/adaptive_rule_" + str(r) + "_vscode.weights.bin"
    o = ri(w, vf)
    if o:
        print("  adapt_rule_" + str(r) + ": pred=" + str(o.index(max(o))) + " conf=" + str(round(max(o), 4)))
    else:
        print("  adapt_rule_" + str(r) + ": NONE")

print()
print("=== CROSS-DOMAIN TEST (browser input -> vscode expert) ===")
bf = [0.6,0.7,0.7,0.6,0.6,0.1,0.3,0.27,0.2,0.5,0.1,0.3,0.0,0.0,0.48,0.5,0.1,0.03,0.15,0.1,0.0,0.0,0.0,0.0,0.0,0.05,0.1,0.02,0.05,0.1,0.05,0.05,0.15,0.42,0.56,0.1,0.18,0.6,0.8,0.7]
for layer in ["grammar", "idiom", "library", "style"]:
    w = "experts/ast_" + layer + "_vscode.weights.bin"
    o = ri(w, bf)
    if o:
        i = o.index(max(o))
        tag = "OK" if DN[i] == "browser" else "WRONG"
        print("  ast_" + layer + "_vscode on browser input: pred=" + DN[i] + " conf=" + str(round(max(o), 4)) + " [" + tag + "]")
    else:
        print("  ast_" + layer + "_vscode on browser input: NONE")
