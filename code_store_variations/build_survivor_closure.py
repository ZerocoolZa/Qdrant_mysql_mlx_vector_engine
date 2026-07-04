#!/usr/bin/env python3
"""
Level 3: Survivor Closure Generator

Combines:
  - 52 normalized domains (from normalize_closure.py)
  - 168 behavior clusters (from cluster_behaviors.py)

Produces a proof-ranked closure with:
  TIER 0 — Universal primitives (>=15 domains) — the true core
  TIER 1 — Common primitives (>=10 domains)
  TIER 2 — Shared primitives (>=5 domains)
  TIER 3 — Moderate behaviors (>=3 domains)
  TIER 4 — Domain-specific (2 domains)
  TIER 5 — Singleton behaviors (1 domain only)

Output: survivor_closure.py (importable)
"""
import os, json, importlib.util
from collections import defaultdict

# Load normalized domains
spec1 = importlib.util.spec_from_file_location("ndc",
    os.path.join(os.path.dirname(__file__), "normalized_domain_closure.py"))
mod1 = importlib.util.module_from_spec(spec1)
spec1.loader.exec_module(mod1)
NORMALIZED_DOMAINS = mod1.NORMALIZED_DOMAINS

# Load behavior clusters
with open(os.path.join(os.path.dirname(__file__), "behavior_clusters.json")) as f:
    CLUSTER_DATA = json.load(f)

# ============================================================
# 1. Build cluster lookup: method_name -> cluster info
# ============================================================
method_to_cluster = {}
for cluster in CLUSTER_DATA["clusters"]:
    for member in cluster["members"]:
        method_to_cluster[member] = cluster

# ============================================================
# 2. Build domain -> behaviors map
#    For each domain, list which behavior clusters it uses
# ============================================================
domain_behaviors = defaultdict(set)  # domain -> set of cluster ranks
behavior_domains = defaultdict(set)  # cluster rank -> set of domains

for domain, info in NORMALIZED_DOMAINS.items():
    for layer in ("core", "extended", "control", "edge"):
        for m in info[layer]:
            name = m["name"]
            if name in method_to_cluster:
                rank = method_to_cluster[name]["rank"]
                domain_behaviors[domain].add(rank)
                behavior_domains[rank].add(domain)

# ============================================================
# 3. Classify behaviors into tiers
# ============================================================
TIER_THRESHOLDS = [
    (0, 15, "Universal"),    # >= 15 domains
    (1, 10, "Common"),       # >= 10 domains
    (2, 5, "Shared"),        # >= 5 domains
    (3, 3, "Moderate"),      # >= 3 domains
    (4, 2, "Paired"),        # >= 2 domains
    (5, 1, "Singleton"),     # 1 domain
]

def classify_tier(domain_count):
    for tier, threshold, label in TIER_THRESHOLDS:
        if domain_count >= threshold:
            return tier, label
    return 5, "Singleton"

# ============================================================
# 4. Build tier-ranked behavior list
# ============================================================
tiered_behaviors = defaultdict(list)  # tier -> list of behavior dicts

for cluster in CLUSTER_DATA["clusters"]:
    rank = cluster["rank"]
    domain_count = cluster["domain_count"]
    method_count = cluster["method_count"]
    canonical = cluster["canonical"]
    members = cluster["members"]
    domains = cluster["domains"]

    tier, label = classify_tier(domain_count)

    tiered_behaviors[tier].append({
        "rank": rank,
        "canonical": canonical,
        "tier": tier,
        "tier_label": label,
        "domain_count": domain_count,
        "method_count": method_count,
        "members": members,
        "domains": domains,
    })

# Sort each tier by domain_count descending
for tier in tiered_behaviors:
    tiered_behaviors[tier].sort(key=lambda x: x["domain_count"], reverse=True)

# ============================================================
# 5. Build domain -> tier usage map
#     Which tiers does each domain draw from?
# ============================================================
domain_tier_usage = {}
for domain in NORMALIZED_DOMAINS:
    usage = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for rank in domain_behaviors[domain]:
        cluster = CLUSTER_DATA["clusters"][rank]
        tier, _ = classify_tier(cluster["domain_count"])
        usage[tier] += 1
    domain_tier_usage[domain] = usage

# ============================================================
# 6. Compute closure graph edges
#    Two domains are connected if they share >= 3 behaviors
# ============================================================
edges = []
doms = list(NORMALIZED_DOMAINS.keys())
for i in range(len(doms)):
    for j in range(i + 1, len(doms)):
        shared = domain_behaviors[doms[i]] & domain_behaviors[doms[j]]
        if len(shared) >= 3:
            edges.append((doms[i], doms[j], len(shared)))

edges.sort(key=lambda x: x[2], reverse=True)

# ============================================================
# 7. Generate output file
# ============================================================
output_path = os.path.join(os.path.dirname(__file__), "survivor_closure.py")

lines = [
    '"""Survivor Closure — Level 3.',
    '',
    'Proof-ranked closure generated from:',
    f'  - {len(NORMALIZED_DOMAINS)} normalized domains',
    f'  - {CLUSTER_DATA["total_clusters"]} behavior clusters',
    f'  - {CLUSTER_DATA["total_unique_names"]} unique method names (original: 873)',
    '',
    'Tier system:',
    '  TIER 0 — Universal  (>=15 domains) — true core primitives',
    '  TIER 1 — Common     (>=10 domains)',
    '  TIER 2 — Shared     (>=5 domains)',
    '  TIER 3 — Moderate   (>=3 domains)',
    '  TIER 4 — Paired     (>=2 domains)',
    '  TIER 5 — Singleton  (1 domain only)',
    '',
    f'Total unique behaviors: {CLUSTER_DATA["total_clusters"]}',
    '"""',
    '',
    'SURVIVOR_CLOSURE = {',
]

# Add tiered behaviors
for tier in range(6):
    label = TIER_THRESHOLDS[tier][2]
    behaviors = tiered_behaviors.get(tier, [])
    lines.append(f'    "tier_{tier}_{label.lower()}": [')
    for b in behaviors:
        lines.append(f'        {{"rank": {b["rank"]}, "canonical": "{b["canonical"]}", '
                     f'"domain_count": {b["domain_count"]}, "method_count": {b["method_count"]}, '
                     f'"members": {b["members"]!r}, "domains": {b["domains"]!r}}},')
    lines.append('    ],')

# Add domain tier usage
lines.append('    "domain_tier_usage": {')
for domain in sorted(NORMALIZED_DOMAINS):
    usage = domain_tier_usage[domain]
    lines.append(f'        "{domain}": {{"tier0": {usage[0]}, "tier1": {usage[1]}, '
                 f'"tier2": {usage[2]}, "tier3": {usage[3]}, "tier4": {usage[4]}, "tier5": {usage[5]}}},')
lines.append('    },')

# Add closure graph edges
lines.append(f'    "closure_graph_edges": [')
for a, b, w in edges[:100]:  # Top 100 edges
    lines.append(f'        ("{a}", "{b}", {w}),')
lines.append('    ],')

# Add summary stats
total_behaviors = CLUSTER_DATA["total_clusters"]
tier_counts = {tier: len(tiered_behaviors.get(tier, [])) for tier in range(6)}
lines.append(f'    "summary": {{')
lines.append(f'        "total_behaviors": {total_behaviors},')
lines.append(f'        "total_domains": {len(NORMALIZED_DOMAINS)},')
lines.append(f'        "total_edges": {len(edges)},')
for tier in range(6):
    label = TIER_THRESHOLDS[tier][2]
    lines.append(f'        "tier_{tier}_{label.lower()}_count": {tier_counts[tier]},')
lines.append(f'        "original_method_entries": 873,')
lines.append(f'        "unique_method_names": {CLUSTER_DATA["total_unique_names"]},')
lines.append(f'        "behavior_clusters": {total_behaviors},')
lines.append(f'        "compression_ratio": {CLUSTER_DATA["compression_ratio"]},')
lines.append(f'    }},')

lines.append('}')
lines.append('')

with open(output_path, "w") as f:
    f.write("\n".join(lines))

# ============================================================
# 8. Print summary
# ============================================================
print(f"Generated {output_path}")
print(f"\n{'='*70}")
print(f"SURVIVOR CLOSURE — LEVEL 3")
print(f"{'='*70}")
print(f"Original method entries:     873")
print(f"Unique method names:         {CLUSTER_DATA['total_unique_names']}")
print(f"Behavior clusters:           {total_behaviors}")
print(f"Compression ratio:           {CLUSTER_DATA['compression_ratio']}x")
print(f"Domains:                     {len(NORMALIZED_DOMAINS)}")
print(f"Closure graph edges (>=3):   {len(edges)}")
print()

# Tier table
print(f"{'='*70}")
print(f"TIER DISTRIBUTION")
print(f"{'='*70}")
print(f"{'Tier':<6} {'Label':<12} {'Threshold':>10} {'Count':>6} {'%':>6}")
print(f"{'-'*70}")
for tier in range(6):
    label = TIER_THRESHOLDS[tier][2]
    threshold = TIER_THRESHOLDS[tier][1]
    count = tier_counts[tier]
    pct = count / total_behaviors * 100
    print(f"  {tier:<4} {label:<12} {('>='+str(threshold)+' doms'):>10} {count:>6} {pct:>5.1f}%")
print(f"{'-'*70}")
print(f"  {'TOTAL':<16} {'':>10} {total_behaviors:>6} {'100.0%':>6}")
print()

# Tier 0 + Tier 1 primitives (the true core)
print(f"{'='*70}")
print(f"TIER 0 — UNIVERSAL PRIMITIVES (>=15 domains)")
print(f"{'='*70}")
print(f"{'#':>3} {'Primitive':<20} {'#Doms':>5} {'#Vars':>5}")
for i, b in enumerate(tiered_behaviors.get(0, []), 1):
    print(f"{i:>3} {b['canonical']:<20} {b['domain_count']:>5} {b['method_count']:>5}")

print(f"\n{'='*70}")
print(f"TIER 1 — COMMON PRIMITIVES (>=10 domains)")
print(f"{'='*70}")
print(f"{'#':>3} {'Primitive':<20} {'#Doms':>5} {'#Vars':>5}")
for i, b in enumerate(tiered_behaviors.get(1, []), 1):
    print(f"{i:>3} {b['canonical']:<20} {b['domain_count']:>5} {b['method_count']:>5}")

print(f"\n{'='*70}")
print(f"TIER 2 — SHARED PRIMITIVES (>=5 domains)")
print(f"{'='*70}")
print(f"{'#':>3} {'Primitive':<20} {'#Doms':>5} {'#Vars':>5}")
for i, b in enumerate(tiered_behaviors.get(2, []), 1):
    print(f"{i:>3} {b['canonical']:<20} {b['domain_count']:>5} {b['method_count']:>5}")

# Domain tier usage
print(f"\n{'='*70}")
print(f"DOMAIN TIER USAGE (how many behaviors each domain draws from each tier)")
print(f"{'='*70}")
print(f"{'Domain':<20} {'T0':>3} {'T1':>3} {'T2':>3} {'T3':>3} {'T4':>3} {'T5':>3} {'Total':>5}")
print(f"{'-'*70}")
for domain in sorted(NORMALIZED_DOMAINS, key=lambda d: sum(domain_tier_usage[d].values()), reverse=True):
    u = domain_tier_usage[domain]
    total = sum(u.values())
    print(f"{domain:<20} {u[0]:>3} {u[1]:>3} {u[2]:>3} {u[3]:>3} {u[4]:>3} {u[5]:>3} {total:>5}")

# Top closure graph edges
print(f"\n{'='*70}")
print(f"TOP 20 CLOSURE GRAPH EDGES (domains sharing most behaviors)")
print(f"{'='*70}")
print(f"{'#':>3} {'Domain A':<15} {'Domain B':<15} {'#Shared':>7}")
for i, (a, b, w) in enumerate(edges[:20], 1):
    print(f"{i:>3} {a:<15} {b:<15} {w:>7}")

# Final number
print(f"\n{'='*70}")
print(f"FINAL NUMBER")
print(f"{'='*70}")
print(f"  873 documented method entries")
print(f"  523 unique method names")
print(f"  {total_behaviors} behavior clusters (true unique behaviors)")
print(f"  {tier_counts[0]+tier_counts[1]} core primitives (Tier 0+1)")
print(f"  {tier_counts[5]} singleton behaviors (domain-specific)")
print(f"  {len(edges)} closure graph edges (domains connected by shared behaviors)")
