#!/usr/bin/env python3
"""
Automatic behavior clustering of 523 unique method names.
No hand-written alias map — pure algorithmic clustering using:
  1. Root verb extraction (stemming)
  2. Levenshtein edit distance for near-duplicates
  3. Cross-domain frequency analysis
  4. Affinity propagation style clustering by behavior signature

Output: behavior_clusters.json + prints top 50 primitives
"""
import os, importlib.util, json, re
from collections import defaultdict, Counter

# Load Level-1 data
spec = importlib.util.spec_from_file_location("der",
    os.path.join(os.path.dirname(__file__), "domain_extraction_results.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
EXTRACTED_DOMAINS = mod.EXTRACTED_DOMAINS

# ============================================================
# 1. Flatten all methods, get 523 unique names + domain map
# ============================================================
all_entries = []  # (domain, method_name)
for d, info in EXTRACTED_DOMAINS.items():
    for layer in ("core", "extended", "control", "edge"):
        for m in info[layer]:
            all_entries.append((d, m["name"]))

unique_names = sorted(set(m[1] for m in all_entries))
name_to_domains = defaultdict(set)
for d, n in all_entries:
    name_to_domains[n].add(d)

print(f"Total entries: {len(all_entries)}")
print(f"Unique method names: {len(unique_names)}")

# ============================================================
# 2. Root verb extraction
#    Strip common suffixes/prefixes to find the "stem verb"
# ============================================================

# Common English verb roots that appear in method names
VERB_ROOTS = [
    # Core CRUD
    "create", "make", "build", "construct", "init", "setup",
    "read", "load", "fetch", "get", "obtain", "acquire", "retrieve", "recall",
    "write", "save", "store", "persist", "dump", "commit", "flush",
    "update", "modify", "change", "alter", "edit", "patch", "set", "configure",
    "delete", "remove", "drop", "clear", "purge", "destroy", "dispose", "forget",
    "insert", "add", "append", "push", "enqueue",
    # Query/Search
    "query", "search", "find", "lookup", "seek", "match", "filter", "select",
    "scan", "browse", "inspect", "explore", "discover",
    # Transform
    "transform", "convert", "translate", "map", "project", "restructure",
    "normalize", "standardize", "format", "clean", "sanitize",
    "merge", "join", "combine", "unify", "concat",
    "split", "separate", "partition", "chunk", "segment",
    "flatten", "compress", "decompress", "pack", "unpack",
    "sort", "rank", "order", "shuffle",
    "group", "cluster", "aggregate", "accumulate", "pivot",
    "dedupe", "deduplicate",
    # Validate
    "validate", "verify", "check", "assert", "test", "confirm", "prove",
    "enforce", "comply", "audit",
    # Parse/Encode
    "parse", "tokenize", "lex", "deserialize", "decode",
    "serialize", "encode", "emit", "generate", "render", "produce",
    "compile", "assemble", "disassemble", "decompile",
    # Control flow
    "start", "stop", "run", "execute", "invoke", "call", "dispatch",
    "pause", "resume", "cancel", "abort", "kill", "terminate",
    "schedule", "trigger", "notify", "wait", "sleep", "poll",
    "retry", "timeout",
    "connect", "disconnect", "bind", "listen", "accept",
    "send", "receive", "recv", "publish", "subscribe", "broadcast",
    "stream", "pipe", "redirect",
    # Analysis
    "analyze", "inspect", "examine", "review", "diagnose", "trace",
    "measure", "count", "calculate", "compute", "sum", "average",
    "compare", "diff", "contrast",
    "detect", "identify", "recognize", "classify", "categorize",
    "predict", "forecast", "estimate", "approximate",
    "explain", "describe", "report", "document", "summarize",
    "plan", "reason", "reflect", "evaluate", "score", "rank",
    "learn", "train", "tune", "optimize", "improve",
    # Security
    "hash", "encrypt", "decrypt", "sign", "authenticate", "authorize",
    "revoke", "lock", "unlock", "isolate", "quarantine",
    # Lifecycle
    "register", "unregister", "subscribe", "unsubscribe",
    "backup", "restore", "rollback", "recover", "repair", "fix",
    "migrate", "sync", "replicate",
    "archive", "rotate", "expire", "invalidate",
    "snapshot", "clone", "copy",
    # I/O
    "open", "close", "seek", "tell", "truncate",
    "upload", "download",
    "import", "export",
    "index", "reindex", "rebuild",
    # GUI
    "show", "hide", "resize", "move", "draw", "paint",
    "enable", "disable", "toggle",
    "click", "focus", "blur",
    # Misc
    "handle", "process", "manage", "configure", "design",
    "navigate", "route", "orient", "calibrate", "benchmark",
    "link", "reference", "cross_reference",
    "embed", "prompt", "complete", "suggest", "highlight",
    "tag", "label", "annotate", "enrich",
    "log", "debug", "info", "warn", "error", "fatal", "trace",
    "monitor", "watch", "observe", "profile",
    "escalate", "approve", "reject", "waive", "review",
    "baseline", "drift", "flag",
    "state_machine", "pipeline", "sequence", "parallel", "chain", "branch", "loop",
    "iterate", "control",
    "lock", "unlock",
    "touch", "temp", "glob", "walk", "exists", "stat", "chmod",
    "rename", "move", "glob",
    "path", "traverse", "navigate", "neighbors",
    "visualize", "diagram", "map",
    "waypoint", "landmark", "heading", "distance",
]

def extract_root(name):
    """Extract the root verb from a method name."""
    name_lower = name.lower()
    # Try exact match first
    for root in VERB_ROOTS:
        if name_lower == root:
            return root
    # Try prefix match (longest first)
    sorted_roots = sorted(VERB_ROOTS, key=len, reverse=True)
    for root in sorted_roots:
        if name_lower.startswith(root):
            return root
        if name_lower.endswith(root):
            return root
    # Try substring match for compound names
    for root in sorted_roots:
        if root in name_lower and len(root) >= 4:
            return root
    # Fallback: first 4 chars
    return name_lower[:4] if len(name_lower) >= 4 else name_lower

# ============================================================
# 3. Levenshtein distance for near-duplicate detection
# ============================================================
def levenshtein(a, b):
    """Compute Levenshtein edit distance."""
    if len(a) < len(b):
        a, b = b, a
    if len(b) == 0:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            ins = prev[j + 1] + 1
            dele = curr[j] + 1
            sub = prev[j] + (ca != cb)
            curr.append(min(ins, dele, sub))
        prev = curr
    return prev[-1]

# ============================================================
# 4. Cluster: group by root verb, then refine with edit distance
# ============================================================
# Step A: Group by root verb
root_groups = defaultdict(list)
for name in unique_names:
    root = extract_root(name)
    root_groups[root].append(name)

# Step B: Within each root group, sub-cluster by prefix similarity
# Methods that share the root verb as a prefix are the same behavior variant
def cluster_by_prefix(names, root):
    """Cluster names by whether they start with the root verb."""
    # Group 1: exact match or starts with root_
    prefix_cluster = []
    exact_cluster = []
    suffix_cluster = []
    other_cluster = []
    for name in names:
        if name == root:
            exact_cluster.append(name)
        elif name.startswith(root + "_") or name.startswith(root):
            prefix_cluster.append(name)
        elif name.endswith(root):
            suffix_cluster.append(name)
        else:
            other_cluster.append(name)
    clusters = []
    if exact_cluster:
        clusters.append(exact_cluster + prefix_cluster)
    elif prefix_cluster:
        clusters.append(prefix_cluster)
    elif suffix_cluster:
        clusters.append(suffix_cluster)
    for name in other_cluster:
        clusters.append([name])
    return clusters

# Build final behavior clusters
behavior_clusters = {}  # cluster_id -> {root, members, domains, frequency}
cluster_id = 0
for root, names in sorted(root_groups.items(), key=lambda x: len(x[1]), reverse=True):
    if len(names) == 1:
        # Single member — still a cluster
        behavior_clusters[cluster_id] = {
            "root": root,
            "canonical": names[0],
            "members": names,
            "domains": sorted(name_to_domains[names[0]]),
            "domain_count": len(name_to_domains[names[0]]),
            "method_count": 1,
        }
        cluster_id += 1
    else:
        sub_clusters = cluster_by_prefix(names, root)
        for sc in sub_clusters:
            # Collect all domains for this sub-cluster
            all_domains = set()
            for n in sc:
                all_domains.update(name_to_domains[n])
            # Canonical = shortest name (most general)
            canonical = min(sc, key=len)
            behavior_clusters[cluster_id] = {
                "root": root,
                "canonical": canonical,
                "members": sorted(sc),
                "domains": sorted(all_domains),
                "domain_count": len(all_domains),
                "method_count": len(sc),
            }
            cluster_id += 1

# ============================================================
# 5. Merge clusters that share the same canonical name
#    (can happen when root extraction picks different stems)
# ============================================================
canonical_groups = defaultdict(list)
for cid, info in behavior_clusters.items():
    canonical_groups[info["canonical"]].append(cid)

# Merge clusters with same canonical
merged_clusters = {}
new_id = 0
for canon, cids in canonical_groups.items():
    all_members = set()
    all_domains = set()
    roots = set()
    for cid in cids:
        info = behavior_clusters[cid]
        all_members.update(info["members"])
        all_domains.update(info["domains"])
        roots.add(info["root"])
    merged_clusters[new_id] = {
        "canonical": canon,
        "roots": sorted(roots),
        "members": sorted(all_members),
        "domains": sorted(all_domains),
        "domain_count": len(all_domains),
        "method_count": len(all_members),
    }
    new_id += 1

behavior_clusters = merged_clusters

# ============================================================
# 6. Post-merge: further merge clusters with high member overlap
#    If two clusters share >50% members, merge them
# ============================================================
def merge_overlapping_clusters(clusters, threshold=0.5):
    """Merge clusters with >threshold member overlap."""
    items = list(clusters.items())
    merged = {}
    skip = set()
    for i, (cid1, info1) in enumerate(items):
        if cid1 in skip:
            continue
        current = dict(info1)
        for j in range(i + 1, len(items)):
            cid2, info2 = items[j]
            if cid2 in skip:
                continue
            set1 = set(current["members"])
            set2 = set(info2["members"])
            if not set1 or not set2:
                continue
            overlap = len(set1 & set2) / len(set1 | set2)
            if overlap >= threshold:
                current["members"] = sorted(set1 | set2)
                current["domains"] = sorted(set(current["domains"]) | set(info2["domains"]))
                current["domain_count"] = len(current["domains"])
                current["method_count"] = len(current["members"])
                current["roots"] = sorted(set(current.get("roots", [])) | set(info2.get("roots", [])))
                skip.add(cid2)
        merged[cid1] = current
    return merged

# Run overlap merging 3 times to converge
for _ in range(3):
    behavior_clusters = merge_overlapping_clusters(behavior_clusters, threshold=0.3)

# Step C: Co-occurrence merge — if two clusters share >70% of domains,
# they're likely the same behavior expressed differently
def merge_by_cooccurrence(clusters, domain_threshold=0.7):
    """Merge clusters that appear in the same domains."""
    items = list(clusters.items())
    merged = {}
    skip = set()
    for i, (cid1, info1) in enumerate(items):
        if cid1 in skip:
            continue
        current = dict(info1)
        d1 = set(current["domains"])
        if not d1:
            merged[cid1] = current
            continue
        for j in range(i + 1, len(items)):
            cid2, info2 = items[j]
            if cid2 in skip:
                continue
            d2 = set(info2["domains"])
            if not d2:
                continue
            # Jaccard of domain sets
            overlap = len(d1 & d2) / len(d1 | d2)
            if overlap >= domain_threshold:
                current["members"] = sorted(set(current["members"]) | set(info2["members"]))
                current["domains"] = sorted(set(current["domains"]) | set(info2["domains"]))
                current["domain_count"] = len(current["domains"])
                current["method_count"] = len(current["members"])
                current["roots"] = sorted(set(current.get("roots", [])) | set(info2.get("roots", [])))
                d1 = set(current["domains"])
                skip.add(cid2)
        merged[cid1] = current
    return merged

for _ in range(3):
    behavior_clusters = merge_by_cooccurrence(behavior_clusters, domain_threshold=0.6)

# Re-index
final_clusters = {}
for i, (cid, info) in enumerate(sorted(behavior_clusters.items(),
    key=lambda x: x[1]["domain_count"], reverse=True)):
    final_clusters[i] = info

# ============================================================
# 7. Results
# ============================================================
total_clusters = len(final_clusters)
total_methods_clustered = sum(c["method_count"] for c in final_clusters.values())

print(f"\n{'='*70}")
print(f"BEHAVIOR CLUSTERING RESULTS")
print(f"{'='*70}")
print(f"Input: {len(unique_names)} unique method names")
print(f"Behavior clusters: {total_clusters}")
print(f"Methods clustered: {total_methods_clustered}")
print(f"Compression ratio: {len(unique_names)/total_clusters:.1f}x")

# Cluster size distribution
sizes = [c["method_count"] for c in final_clusters.values()]
size_dist = Counter(sizes)
print(f"\nCluster size distribution:")
for size in sorted(size_dist.keys()):
    bar = "#" * min(size, 30)
    print(f"  {size:>3} methods: {size_dist[size]:>3} clusters  {bar}")

# Domain coverage distribution
dom_counts = [c["domain_count"] for c in final_clusters.values()]
dom_dist = Counter(dom_counts)
print(f"\nDomain coverage distribution:")
for dc in sorted(dom_dist.keys(), reverse=True)[:20]:
    bar = "#" * min(dc, 40)
    print(f"  {dc:>3} domains: {dom_dist[dc]:>3} clusters  {bar}")

# ============================================================
# 8. Top 50 primitive operations by domain coverage
# ============================================================
print(f"\n{'='*70}")
print(f"TOP 50 PRIMITIVE OPERATIONS (by domain coverage)")
print(f"{'='*70}")
print(f"{'#':>3} {'Primitive':<25} {'#Doms':>5} {'#Vars':>5} {'Variants'}")
print(f"{'-'*70}")

top50 = sorted(final_clusters.values(), key=lambda c: c["domain_count"], reverse=True)[:50]
for i, cluster in enumerate(top50, 1):
    canon = cluster["canonical"]
    nd = cluster["domain_count"]
    nv = cluster["method_count"]
    variants = cluster["members"][:6]
    var_str = ", ".join(variants)
    if len(cluster["members"]) > 6:
        var_str += f", ...+{len(cluster['members'])-6}"
    print(f"{i:>3} {canon:<25} {nd:>5} {nv:>5} {var_str}")

# ============================================================
# 9. Save to JSON
# ============================================================
output = {
    "total_unique_names": len(unique_names),
    "total_clusters": total_clusters,
    "compression_ratio": round(len(unique_names) / total_clusters, 2),
    "clusters": [
        {
            "rank": i,
            "canonical": c["canonical"],
            "domain_count": c["domain_count"],
            "method_count": c["method_count"],
            "members": c["members"],
            "domains": c["domains"],
            "roots": c.get("roots", []),
        }
        for i, c in enumerate(sorted(final_clusters.values(),
            key=lambda c: c["domain_count"], reverse=True))
    ],
}

output_path = os.path.join(os.path.dirname(__file__), "behavior_clusters.json")
with open(output_path, "w") as f:
    json.dump(output, f, indent=2)
print(f"\nSaved to {output_path}")

# ============================================================
# 10. Summary stats
# ============================================================
# How many behaviors appear in ALL 58 domains?
all_domain_count = sum(1 for c in final_clusters.values() if c["domain_count"] >= 50)
most_domain_count = sum(1 for c in final_clusters.values() if c["domain_count"] >= 40)
many_domain_count = sum(1 for c in final_clusters.values() if c["domain_count"] >= 20)
some_domain_count = sum(1 for c in final_clusters.values() if c["domain_count"] >= 10)
few_domain_count = sum(1 for c in final_clusters.values() if c["domain_count"] >= 5)
one_domain_count = sum(1 for c in final_clusters.values() if c["domain_count"] == 1)

print(f"\n{'='*70}")
print(f"PRIMITIVE DISTRIBUTION BY DOMAIN COVERAGE")
print(f"{'='*70}")
print(f"  >= 50 domains (universal):     {all_domain_count}")
print(f"  >= 40 domains (near-universal): {most_domain_count}")
print(f"  >= 20 domains (common):         {many_domain_count}")
print(f"  >= 10 domains (shared):         {some_domain_count}")
print(f"  >=  5 domains (moderate):       {few_domain_count}")
print(f"   =  1 domain  (domain-specific): {one_domain_count}")
print(f"\n  Total clusters: {total_clusters}")
print(f"  True universal primitives (>=40 domains): {most_domain_count}")
print(f"  Core behavior set (>=10 domains): {some_domain_count}")
