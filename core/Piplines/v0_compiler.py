#!/usr/bin/env python3
"""
v0 Knowledge Compiler — MINIMAL
Input: 292 messages from SQLite
Output: nodes (claims), edges (relations), failure map
No BCL, no layers, no ontology. Just extraction + graph + failure.
"""
import sqlite3
import re
import json
from collections import defaultdict

DB = "/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Report/saved_sessions/Devin_Moseimport.db"

# ─── 5 NODE TYPES ───
NODE_TYPES = {"Claim", "Decision", "Question", "Fact", "Concept"}

# ─── 5 EDGE TYPES ───
EDGE_TYPES = {"SUPPORTS", "CONTRADICTS", "DERIVES_FROM", "RESPONDS_TO", "EVOLVES_TO"}

# ─── EXTRACTION PATTERNS (naive, deliberately simple) ───
DECISION_PATTERNS = [
    r"\b(?:I|we)\s+(?:should|will|decided to|need to|must)\b",
    r"\b(?:created|dropped|migrated|removed|added|built)\b",
    r"\bSTOP\b",
    r"\b(?:decision|decided)\b",
    r"\b(?:use|using|adopted|chose)\b.*(?:instead of|rather than)",
]
QUESTION_PATTERNS = [
    r"\?",
    r"\b(?:what is|what are|how do|why did|should we|is it)\b",
    r"\b(?:question|unclear|unresolved|open question)\b",
]
FACT_PATTERNS = [
    r"\b(?:fact|law|principle|rule)\b",
    r"\bLAW\d\b",
    r"\b(?:every|always|never|must|required)\b",
    r"\b(?:architecture|concept|model)\b.*(?:is|are|means)",
]
CONCEPT_PATTERNS = [
    r"\b(?:Entity|Authority|Relation|Type|BCL|compiler|pipeline|atom|claim)\b",
    r"\b(?:knowledge compiler|reasoning graph|conversation pair)\b",
]
CONTRADICTION_PATTERNS = [
    r"\b(?:wrong|incorrect|violate|violated|contradict|conflict|overlap)\b",
    r"\b(?:not a|should not|don't|do not|never)\b",
    r"\b(?:reversed|replaced|superseded)\b",
]

def classify_message(text):
    """Return list of (node_type, content_snippet) for one message."""
    if not text or len(text.strip()) < 10:
        return []
    text_lower = text.lower()
    nodes = []
    # Split into sentences (rough)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    for sent in sentences:
        if len(sent) < 15:
            continue
        sent_lower = sent.lower()
        # Check decision
        for pat in DECISION_PATTERNS:
            if re.search(pat, sent, re.IGNORECASE):
                nodes.append(("Decision", sent[:200]))
                break
        else:
            # Check question
            for pat in QUESTION_PATTERNS:
                if re.search(pat, sent, re.IGNORECASE):
                    nodes.append(("Question", sent[:200]))
                    break
            else:
                # Check contradiction
                for pat in CONTRADICTION_PATTERNS:
                    if re.search(pat, sent, re.IGNORECASE):
                        nodes.append(("Claim", sent[:200]))  # contradiction = claim
                        break
                else:
                    # Check fact
                    for pat in FACT_PATTERNS:
                        if re.search(pat, sent, re.IGNORECASE):
                            nodes.append(("Fact", sent[:200]))
                            break
                    else:
                        # Check concept
                        for pat in CONCEPT_PATTERNS:
                            if re.search(pat, sent, re.IGNORECASE):
                                nodes.append(("Concept", sent[:200]))
                                break
    return nodes

def extract_edges(nodes, msg_map):
    """Naive edge extraction: look at node pairs in same or adjacent messages."""
    edges = []
    node_list = nodes  # already (node_id, type, content, source_msg)
    for i in range(len(node_list)):
        id_i, type_i, content_i, msg_i = node_list[i]
        for j in range(i + 1, len(node_list)):
            id_j, type_j, content_j, msg_j = node_list[j]
            if i >= j:
                continue
            # Same message or adjacent
            if abs(msg_i - msg_j) > 3:
                continue
            # CONTRADICTS: contradiction words in either
            ci = content_i.lower()
            cj = content_j.lower()
            if any(w in ci + " " + cj for w in ["wrong", "violate", "incorrect", "contradict", "overlap", "reversed", "replaced"]):
                edges.append((id_i, id_j, "CONTRADICTS", 0.5))
                continue
            # EVOLVES_TO: one mentions replacement
            if any(w in ci + " " + cj for w in ["replaced", "superseded", "corrected", "dropped", "removed"]):
                edges.append((id_i, id_j, "EVOLVES_TO", 0.5))
                continue
            # SUPPORTS: one mentions law, evidence, because
            if any(w in ci + " " + cj for w in ["law", "evidence", "because", "supports", "reason"]):
                edges.append((id_i, id_j, "SUPPORTS", 0.4))
                continue
            # RESPONDS_TO: question + answer in adjacent messages
            if type_i == "Question" and type_j != "Question" and abs(msg_i - msg_j) <= 2:
                edges.append((id_i, id_j, "RESPONDS_TO", 0.5))
                continue
            # DERIVES_FROM: concept + something else
            if type_i == "Concept" and type_j != "Concept":
                edges.append((id_i, id_j, "DERIVES_FROM", 0.3))
    return edges

def run_v0():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # Read all messages
    cur.execute("SELECT msg_num, role, content FROM messages ORDER BY msg_num")
    messages = cur.fetchall()

    # ─── PHASE 1: SEGMENTATION + EXTRACTION ───
    nodes = []  # (node_id, type, content, source_msg)
    node_id = 0
    msg_node_count = defaultdict(int)
    empty_msgs = []

    for msg_num, role, content in messages:
        if role in ("System", "Tool"):
            continue
        extracted = classify_message(content or "")
        if not extracted:
            empty_msgs.append(msg_num)
            continue
        for ntype, ncontent in extracted:
            node_id += 1
            nodes.append((node_id, ntype, ncontent, msg_num))
            msg_node_count[msg_num] += 1

    # ─── PHASE 2: NORMALIZATION (skip — v0, no merge) ───

    # ─── PHASE 3: EDGE EXTRACTION ───
    edges = extract_edges(nodes, {})

    # ─── PHASE 4: VALIDATION ───
    # Orphans: nodes with no edges
    node_ids_with_edges = set()
    for src, tgt, etype, conf in edges:
        node_ids_with_edges.add(src)
        node_ids_with_edges.add(tgt)
    orphans = [n[0] for n in nodes if n[0] not in node_ids_with_edges]

    # Over-extraction: messages with > 8 nodes
    over_extraction = {msg: count for msg, count in msg_node_count.items() if count > 8}

    # Conflicts: A SUPPORTS B AND A CONTRADICTS B
    edge_pairs = defaultdict(set)
    for src, tgt, etype, conf in edges:
        edge_pairs[(src, tgt)].add(etype)
    conflicts = [(s, t) for (s, t), types in edge_pairs.items() if "SUPPORTS" in types and "CONTRADICTS" in types]

    # ─── OUTPUT ───
    total_msgs = len([m for m in messages if m[1] not in ("System", "Tool")])
    msgs_with_nodes = len(msg_node_count)
    coverage = (msgs_with_nodes / total_msgs * 100) if total_msgs > 0 else 0
    orphan_rate = (len(orphans) / len(nodes) * 100) if nodes else 0

    print("=" * 70)
    print("v0 COMPILER OUTPUT")
    print("=" * 70)
    print(f"\nINPUT:")
    print(f"  Total messages: {len(messages)}")
    print(f"  User+Assistant messages: {total_msgs}")
    print(f"  Skipped (System/Tool): {len(messages) - total_msgs}")

    print(f"\nOUTPUT:")
    print(f"  Nodes extracted: {len(nodes)}")
    print(f"  Edges extracted: {len(edges)}")
    print(f"  Coverage: {coverage:.1f}% ({msgs_with_nodes}/{total_msgs} msgs produced nodes)")
    print(f"  Orphan rate: {orphan_rate:.1f}% ({len(orphans)}/{len(nodes)} nodes have no edges)")

    print(f"\nNODE TYPES:")
    type_counts = defaultdict(int)
    for _, ntype, _, _ in nodes:
        type_counts[ntype] += 1
    for ntype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {ntype}: {count}")

    print(f"\nEDGE TYPES:")
    edge_counts = defaultdict(int)
    for _, _, etype, _ in edges:
        edge_counts[etype] += 1
    for etype, count in sorted(edge_counts.items(), key=lambda x: -x[1]):
        print(f"  {etype}: {count}")

    print(f"\nVALIDATION:")
    print(f"  Over-extraction zones (>8 nodes/msg): {len(over_extraction)}")
    for msg, count in sorted(over_extraction.items(), key=lambda x: -x[1])[:5]:
        print(f"    msg #{msg}: {count} nodes")
    print(f"  Graph conflicts (SUPPORTS + CONTRADICTS same pair): {len(conflicts)}")
    for s, t in conflicts[:5]:
        print(f"    nodes #{s} <-> #{t}")
    print(f"  Empty messages (no nodes): {len(empty_msgs)}")

    # ─── FAILURE MAP ───
    print(f"\n{'=' * 70}")
    print("FAILURE MAP")
    print(f"{'=' * 70}")
    print(f"\nMessages with NO extraction ({len(empty_msgs)} total):")
    for msg in empty_msgs[:20]:
        print(f"  #{msg}")
    if len(empty_msgs) > 20:
        print(f"  ... and {len(empty_msgs) - 20} more")

    print(f"\nOver-extraction zones:")
    if over_extraction:
        for msg, count in sorted(over_extraction.items(), key=lambda x: -x[1]):
            print(f"  #{msg}: {count} nodes (OVER-EXTRACTION)")
    else:
        print(f"  None")

    print(f"\nOrphan nodes (no edges): {len(orphans)}")
    print(f"  (sample of first 10)")
    for oid in orphans[:10]:
        node = [n for n in nodes if n[0] == oid][0]
        print(f"  #{oid} [{node[1]}] msg#{node[3]}: {node[2][:60]}")

    # ─── COMPARISON WITH MANUAL GRAPH ───
    print(f"\n{'=' * 70}")
    print("COMPARISON: v0 vs MANUAL GRAPH")
    print(f"{'=' * 70}")
    cur.execute("SELECT COUNT(*) FROM atom")
    manual_atoms = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM atom_link")
    manual_links = cur.fetchone()[0]
    print(f"\n  Manual:  {manual_atoms} atoms, {manual_links} links")
    print(f"  v0:      {len(nodes)} nodes,  {len(edges)} edges")
    print(f"  Ratio:   v0 produced {len(nodes)/manual_atoms:.1f}x nodes, {len(edges)/manual_links:.1f}x edges")

    # ─── SAVE TO DB ───
    cur.execute("DROP TABLE IF EXISTS v0_nodes")
    cur.execute("""CREATE TABLE v0_nodes (
        node_id INTEGER PRIMARY KEY,
        type TEXT,
        content TEXT,
        source_msg INTEGER
    )""")
    for nid, ntype, ncontent, smsg in nodes:
        cur.execute("INSERT INTO v0_nodes VALUES (?,?,?,?)", (nid, ntype, ncontent, smsg))

    cur.execute("DROP TABLE IF EXISTS v0_edges")
    cur.execute("""CREATE TABLE v0_edges (
        edge_id INTEGER PRIMARY KEY,
        source_node INTEGER,
        target_node INTEGER,
        edge_type TEXT,
        confidence REAL
    )""")
    for i, (src, tgt, etype, conf) in enumerate(edges, 1):
        cur.execute("INSERT INTO v0_edges VALUES (?,?,?,?,?)", (i, src, tgt, etype, conf))

    conn.commit()
    conn.close()

    print(f"\nSaved to DB: v0_nodes ({len(nodes)} rows), v0_edges ({len(edges)} rows)")
    print(f"\n{'=' * 70}")
    print("VERDICT")
    print(f"{'=' * 70}")
    checks = [
        (">= 70% messages produce nodes", coverage >= 70),
        ("orphan rate < 25%", orphan_rate < 25),
        ("produced nodes", len(nodes) > 0),
        ("produced edges", len(edges) > 0),
    ]
    for label, passed in checks:
        print(f"  {'PASS' if passed else 'FAIL'}: {label}")

if __name__ == "__main__":
    run_v0()
