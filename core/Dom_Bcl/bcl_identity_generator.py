#!/usr/bin/env python3
"""
BCL Identity Generator
======================
Generates BCL self-description tokens for every entity in the v20 database.

Each entity (domain, class, method, computational unit) gets a BCL token
that describes itself — like a nametag or self-introduction:

    [@DomAi]{
        ("identity";"AI domain")
        ("purpose";"text classification, generation, memory, reasoning, scoring")
        ("capabilities";"classify,complete,embed,forget,generate,learn,plan,prompt")
        ("used_in";"efl_brain pipeline")
        ("closure";"100%")
        ("violations";"0")
        (92)
    }

When you ask "How does DomAi work?", the interrogator retrieves this BCL token.
The LLM reads it and formats it as natural speech.

BCL = Bracket Command Language — the universal token format.
    [@name]{(key;value)(key;value)(weight)}

Levels of identity:
    1. DOMAIN   — "I am the ai domain. I do X. My classes are Y."
    2. CLASS    — "I am DomAi. I am the ai domain. I can classify, generate, ..."
    3. METHOD   — "I am the compress method. I belong to DomCompression. I take (data, algorithm)."
    4. CU       — "I am CU_Bootstrap. I am Init + load knowledge + load embedder."
"""

import sqlite3
import os
import sys
import json
from datetime import datetime

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "code_store_variations", "v20_hybrid_best.db"
)


def bcl_escape(text):
    """Escape text for BCL format — no semicolons or parens inside values."""
    if not text:
        return ""
    return str(text).replace(";", ",").replace("(", "[").replace(")", "]").replace('"', "'").strip()


def bcl_tuple(key, value, weight=None):
    """Generate a BCL tuple: ("key";"value") or ("key";"value";weight)"""
    k = bcl_escape(key)
    v = bcl_escape(value)
    if weight is not None:
        return f'("{k}";"{v}";{weight})'
    return f'("{k}";"{v}")'


def bcl_token(name, tuples, weight=92):
    """Generate a full BCL token: [@name]{(t1)(t2)...(weight)}"""
    body = "".join(tuples) + f"({weight})"
    safe_name = bcl_escape(name).replace(" ", "_")
    return f"[@{safe_name}]{{{body}}}"


# ════════════════════════════════════════════════════════════════════════
# DOMAIN-LEVEL BCL IDENTITY
# ════════════════════════════════════════════════════════════════════════

def generate_domain_bcl(conn, domain_name):
    """Generate BCL token for a domain.

    [@DomAi]{
        ("identity";"ai domain")
        ("purpose";"text classification, generation, memory, reasoning, scoring")
        ("classes";"DomAi")
        ("capabilities";"classify,complete,embed,forget,generate,learn,plan,prompt")
        ("method_count";"16")
        ("used_in_pipelines";"efl_brain")
        ("used_in_plans";"efl_brain_repair_loop")
        ("closure";"100%")
        ("violations";"0")
        (92)
    }
    """
    c = conn.cursor()

    # Get all classes in this domain
    c.execute("""
        SELECT id, class_name, description FROM classes
        WHERE is_vbstyle=1 AND domain=? ORDER BY class_name
    """, (domain_name,))
    classes = c.fetchall()
    if not classes:
        return None

    class_names = [r[1] for r in classes]
    class_ids = [r[0] for r in classes]
    descriptions = [r[2] for r in classes if r[2]]

    # Get all methods across all classes in this domain (with signatures for HOW)
    placeholders = ",".join("?" * len(class_ids))
    c.execute(f"""
        SELECT method_name, params, returns_tuple3 FROM methods
        WHERE class_id IN ({placeholders}) AND method_name NOT LIKE '\\_%'
        ORDER BY method_name
    """, class_ids)
    method_rows = c.fetchall()
    methods = [r[0] for r in method_rows]
    # Build signature list: "compress(data, algorithm)→Tuple3"
    signatures = [f"{r[0]}({r[1] or 'self'}){'→Tuple3' if r[2] else ''}" for r in method_rows[:15]]

    # Get orchestration usage
    c.execute(f"""
        SELECT DISTINCT pipeline, role FROM orchestration
        WHERE class_id IN ({placeholders})
    """, class_ids)
    pipeline_rows = c.fetchall()
    pipelines = [r[0] for r in pipeline_rows]
    roles = list(set(r[1] for r in pipeline_rows if r[1]))

    # Get plan usage
    c.execute(f"""
        SELECT DISTINCT p.name FROM plan_steps ps
        JOIN plans p ON ps.plan_id = p.id
        WHERE ps.class_id IN ({placeholders})
    """, class_ids)
    plans = [r[0] for r in c.fetchall()]

    # Get plan ingredients (what plans need me as an ingredient)
    c.execute(f"""
        SELECT DISTINCT p.name FROM plan_ingredients pi
        JOIN plans p ON pi.plan_id = p.id
        WHERE pi.class_id IN ({placeholders})
    """, class_ids)
    ingredients = [r[0] for r in c.fetchall()]

    # Get closure
    c.execute("SELECT closure_pct, status FROM closure_status WHERE domain=?", (domain_name,))
    closure = c.fetchone()

    # Get violations
    c.execute(f"""
        SELECT COUNT(*) FROM violations v
        JOIN methods m ON v.method_id = m.id
        WHERE m.class_id IN ({placeholders})
    """, class_ids)
    violations = c.fetchone()[0]

    # WHAT_IF: What other domains are used alongside me in pipelines?
    c.execute(f"""
        SELECT DISTINCT cl.domain FROM orchestration o
        JOIN classes cl ON o.class_id = cl.id
        WHERE o.pipeline IN (SELECT DISTINCT pipeline FROM orchestration WHERE class_id IN ({placeholders}))
        AND cl.id NOT IN ({placeholders})
    """, class_ids + class_ids)
    coworkers = [r[0] for r in c.fetchall()]

    # WHAT_IF: What domains do I depend on (appear before me in pipelines)?
    c.execute(f"""
        SELECT DISTINCT cl2.domain FROM orchestration o1
        JOIN orchestration o2 ON o1.pipeline = o2.pipeline AND o2.sequence < o1.sequence
        JOIN classes cl2 ON o2.class_id = cl2.id
        WHERE o1.class_id IN ({placeholders})
    """, class_ids)
    depends_on = [r[0] for r in c.fetchall()]

    # WHAT_IF: What domains depend on ME (appear after me in pipelines)?
    c.execute(f"""
        SELECT DISTINCT cl2.domain FROM orchestration o1
        JOIN orchestration o2 ON o1.pipeline = o2.pipeline AND o2.sequence > o1.sequence
        JOIN classes cl2 ON o2.class_id = cl2.id
        WHERE o1.class_id IN ({placeholders})
    """, class_ids)
    depended_by = [r[0] for r in c.fetchall()]

    # Build BCL token
    # Use the primary class name (first one) as the token name
    primary_class = class_names[0]
    tuples = []

    # ── (A) IDENTITY LAYER — WHO ──
    tuples.append(bcl_tuple("identity", f"{domain_name} domain"))
    tuples.append(bcl_tuple("class", primary_class))
    tuples.append(bcl_tuple("domain", domain_name))

    # ── (B) CAPABILITY LAYER — WHAT ──
    if descriptions:
        tuples.append(bcl_tuple("purpose", descriptions[0]))
    tuples.append(bcl_tuple("classes", ", ".join(class_names)))
    tuples.append(bcl_tuple("capabilities", ", ".join(methods[:20])))
    tuples.append(bcl_tuple("method_count", str(len(methods))))

    # ── (C) HOW LAYER — signatures ──
    tuples.append(bcl_tuple("signatures", "; ".join(signatures)))

    # ── (D) RELATIONSHIP LAYER — WHERE + WHAT_IF ──
    if pipelines:
        tuples.append(bcl_tuple("used_in_pipelines", ", ".join(pipelines)))
    else:
        tuples.append(bcl_tuple("used_in_pipelines", "none"))
    if roles:
        tuples.append(bcl_tuple("roles", ", ".join(roles)))
    if plans:
        tuples.append(bcl_tuple("used_in_plans", ", ".join(plans)))
    else:
        tuples.append(bcl_tuple("used_in_plans", "none"))
    if ingredients:
        tuples.append(bcl_tuple("ingredient_of", ", ".join(ingredients)))
    if coworkers:
        tuples.append(bcl_tuple("coworkers", ", ".join(coworkers)))
    if depends_on:
        tuples.append(bcl_tuple("depends_on", ", ".join(depends_on)))
    else:
        tuples.append(bcl_tuple("depends_on", "none"))
    if depended_by:
        tuples.append(bcl_tuple("depended_by", ", ".join(depended_by)))
    else:
        tuples.append(bcl_tuple("depended_by", "none"))

    # ── (E) ROLE LAYER — WHY + WHEN ──
    if closure:
        tuples.append(bcl_tuple("closure", f"{closure[0]}% ({closure[1]})"))
    else:
        tuples.append(bcl_tuple("closure", "not tracked"))
    tuples.append(bcl_tuple("violations", str(violations)))

    # Self-narrative — includes all 7 W-questions
    narrative = f"I am the {domain_name} domain. "
    if descriptions:
        narrative += f"I do {descriptions[0].lower()}. "
    narrative += f"I have {len(methods)} methods: {', '.join(methods[:8])}. "
    if pipelines:
        narrative += f"I am used in the {', '.join(pipelines)} pipeline as {', '.join(roles) if roles else 'a component'}. "
    else:
        narrative += "I am not used in any pipeline yet. "
    if depends_on:
        narrative += f"I depend on {', '.join(depends_on)}. "
    if depended_by:
        narrative += f"{', '.join(depended_by)} depend on me. "
    if closure and closure[0] == 100.0:
        narrative += "I am fully closed. "
    if violations == 0:
        narrative += "I have no violations."
    else:
        narrative += f"I have {violations} violation(s)."
    tuples.append(bcl_tuple("self_narrative", narrative))

    return bcl_token(primary_class, tuples)


# ════════════════════════════════════════════════════════════════════════
# CLASS-LEVEL BCL IDENTITY
# ════════════════════════════════════════════════════════════════════════

def generate_class_bcl(conn, class_id, class_name, domain, description):
    """Generate BCL token for a class.

    [@DomCompression]{
        ("identity";"DomCompression")
        ("domain";"compression")
        ("purpose";"zlib, gzip, lzma, streaming, benchmarking")
        ("capabilities";"compress,decompress,benchmark,stream_compress,stream_decompress")
        ("method_count";"13")
        ("vbstyle";"yes")
        ("has_run";"yes")
        ("closure";"100%")
        (92)
    }
    """
    c = conn.cursor()

    # Get methods (with signatures for HOW)
    c.execute("""
        SELECT method_name, params, returns_tuple3 FROM methods
        WHERE class_id=? AND method_name NOT LIKE '\\_%'
        ORDER BY method_name
    """, (class_id,))
    methods = c.fetchall()
    method_names = [r[0] for r in methods]
    signatures = [f"{r[0]}({r[1] or 'self'}){'→Tuple3' if r[2] else ''}" for r in methods[:15]]

    # Get VBStyle compliance
    c.execute("SELECT has_run_method, has_tuple3, is_vbstyle FROM classes WHERE id=?", (class_id,))
    vb = c.fetchone()

    # Get closure
    c.execute("SELECT closure_pct, status FROM closure_status WHERE domain=?", (domain,))
    closure = c.fetchone()

    # Get orchestration (with roles)
    c.execute("SELECT DISTINCT pipeline, role FROM orchestration WHERE class_id=?", (class_id,))
    orch_rows = c.fetchall()
    pipelines = [r[0] for r in orch_rows]
    roles = list(set(r[1] for r in orch_rows if r[1]))

    # Get plan usage
    c.execute("SELECT DISTINCT p.name FROM plan_steps ps JOIN plans p ON ps.plan_id = p.id WHERE ps.class_id=?", (class_id,))
    plans = [r[0] for r in c.fetchall()]

    # WHAT_IF: depends_on (domains before me in pipeline)
    c.execute("""
        SELECT DISTINCT cl2.domain FROM orchestration o1
        JOIN orchestration o2 ON o1.pipeline = o2.pipeline AND o2.sequence < o1.sequence
        JOIN classes cl2 ON o2.class_id = cl2.id
        WHERE o1.class_id=?
    """, (class_id,))
    depends_on = [r[0] for r in c.fetchall()]

    # WHAT_IF: depended_by (domains after me in pipeline)
    c.execute("""
        SELECT DISTINCT cl2.domain FROM orchestration o1
        JOIN orchestration o2 ON o1.pipeline = o2.pipeline AND o2.sequence > o1.sequence
        JOIN classes cl2 ON o2.class_id = cl2.id
        WHERE o1.class_id=?
    """, (class_id,))
    depended_by = [r[0] for r in c.fetchall()]

    # WHAT_IF: coworkers (other domains in same pipelines)
    c.execute("""
        SELECT DISTINCT cl.domain FROM orchestration o
        JOIN classes cl ON o.class_id = cl.id
        WHERE o.pipeline IN (SELECT DISTINCT pipeline FROM orchestration WHERE class_id=?)
        AND cl.id != ?
    """, (class_id, class_id))
    coworkers = [r[0] for r in c.fetchall()]

    tuples = []

    # ── (A) IDENTITY LAYER — WHO ──
    tuples.append(bcl_tuple("identity", class_name))
    tuples.append(bcl_tuple("domain", domain))
    tuples.append(bcl_tuple("extends", f"domain:{domain}"))

    # ── (B) CAPABILITY LAYER — WHAT ──
    if description:
        tuples.append(bcl_tuple("purpose", description))
    tuples.append(bcl_tuple("capabilities", ", ".join(method_names[:20])))
    tuples.append(bcl_tuple("method_count", str(len(methods))))

    # ── (C) HOW LAYER — signatures ──
    tuples.append(bcl_tuple("signatures", "; ".join(signatures)))
    tuples.append(bcl_tuple("vbstyle", "yes" if vb and vb[2] else "no"))
    tuples.append(bcl_tuple("has_run", "yes" if vb and vb[0] else "no"))
    tuples.append(bcl_tuple("has_tuple3", "yes" if vb and vb[1] else "no"))

    # ── (D) RELATIONSHIP LAYER — WHERE + WHAT_IF ──
    if pipelines:
        tuples.append(bcl_tuple("used_in_pipelines", ", ".join(pipelines)))
    else:
        tuples.append(bcl_tuple("used_in_pipelines", "none"))
    if roles:
        tuples.append(bcl_tuple("roles", ", ".join(roles)))
    if plans:
        tuples.append(bcl_tuple("used_in_plans", ", ".join(plans)))
    else:
        tuples.append(bcl_tuple("used_in_plans", "none"))
    if coworkers:
        tuples.append(bcl_tuple("coworkers", ", ".join(coworkers)))
    tuples.append(bcl_tuple("depends_on", ", ".join(depends_on) if depends_on else "none"))
    tuples.append(bcl_tuple("depended_by", ", ".join(depended_by) if depended_by else "none"))

    # ── (E) ROLE LAYER — WHY + WHEN ──
    if closure:
        tuples.append(bcl_tuple("closure", f"{closure[0]}%"))

    # Self-narrative — all 7 W-questions
    narrative = f"I am {class_name}, the {domain} domain. "
    if description:
        narrative += f"I {description.lower()}. "
    narrative += f"I can {', '.join(method_names[:10])}. "
    if pipelines:
        narrative += f"I am used in {', '.join(pipelines)}"
        if roles:
            narrative += f" as {', '.join(roles)}"
        narrative += ". "
    else:
        narrative += "I am not used in any pipeline. "
    if depends_on:
        narrative += f"I depend on {', '.join(depends_on)}. "
    if depended_by:
        narrative += f"{', '.join(depended_by)} depend on me. "
    if closure and closure[0] == 100.0:
        narrative += "I am fully closed."
    tuples.append(bcl_tuple("self_narrative", narrative))

    return bcl_token(class_name, tuples)


# ════════════════════════════════════════════════════════════════════════
# METHOD-LEVEL BCL IDENTITY
# ════════════════════════════════════════════════════════════════════════

def generate_method_bcl(conn, method_id, class_id, method_name, params, returns_tuple3):
    """Generate BCL token for a method.

    [@compress]{
        ("identity";"compress")
        ("class";"DomCompression")
        ("domain";"compression")
        ("signature";"self, params")
        ("returns_tuple3";"yes")
        ("vbstyle";"yes")
        (92)
    }
    """
    c = conn.cursor()

    # Get class info
    c.execute("SELECT class_name, domain FROM classes WHERE id=?", (class_id,))
    class_row = c.fetchone()
    if not class_row:
        return None
    class_name, domain = class_row

    tuples = []
    tuples.append(bcl_tuple("identity", method_name))
    tuples.append(bcl_tuple("class", class_name))
    tuples.append(bcl_tuple("domain", domain))
    tuples.append(bcl_tuple("extends", f"class:{class_name}"))
    tuples.append(bcl_tuple("signature", params or "self"))
    tuples.append(bcl_tuple("returns_tuple3", "yes" if returns_tuple3 else "no"))

    # Self-narrative
    narrative = f"I am the {method_name} method of {class_name} ({domain} domain). "
    narrative += f"I take ({params}). "
    narrative += f"I return {'Tuple3' if returns_tuple3 else 'a value'}."
    tuples.append(bcl_tuple("self_narrative", narrative))

    # Use class_name_method_name as token name to avoid collisions
    token_name = f"{class_name}_{method_name}"
    return bcl_token(token_name, tuples)


# ════════════════════════════════════════════════════════════════════════
# COMPUTATIONAL UNIT-LEVEL BCL IDENTITY
# ════════════════════════════════════════════════════════════════════════

def generate_cu_bcl(conn, cu_id, unit_name, unit_type, class_id, method_id, description):
    """Generate BCL token for a computational unit.

    [@CU_Bootstrap]{
        ("identity";"CU_Bootstrap")
        ("type";"class")
        ("description";"Init + load knowledge + load embedder + load LLM")
        ("class";"DatabaseBrain")
        ("domain";"knowledge")
        (92)
    }
    """
    c = conn.cursor()

    class_name = ""
    domain = ""
    if class_id:
        c.execute("SELECT class_name, domain FROM classes WHERE id=?", (class_id,))
        row = c.fetchone()
        if row:
            class_name, domain = row

    method_name = ""
    if method_id:
        c.execute("SELECT method_name FROM methods WHERE id=?", (method_id,))
        row = c.fetchone()
        if row:
            method_name = row[0]

    tuples = []
    tuples.append(bcl_tuple("identity", unit_name))
    tuples.append(bcl_tuple("type", unit_type or "unit"))
    if class_name:
        tuples.append(bcl_tuple("extends", f"class:{class_name}"))
    if description:
        tuples.append(bcl_tuple("description", description))
    if class_name:
        tuples.append(bcl_tuple("class", class_name))
    if domain:
        tuples.append(bcl_tuple("domain", domain))
    if method_name:
        tuples.append(bcl_tuple("method", method_name))

    # Self-narrative
    narrative = f"I am {unit_name}. "
    if description:
        narrative += f"I do {description.lower()}. "
    if class_name:
        narrative += f"I belong to {class_name}"
        if domain:
            narrative += f" ({domain} domain)"
        narrative += "."
    tuples.append(bcl_tuple("self_narrative", narrative))

    return bcl_token(unit_name, tuples)


# ════════════════════════════════════════════════════════════════════════
# MAIN — generate and store all BCL identities
# ════════════════════════════════════════════════════════════════════════

def create_bcl_identity_table(conn):
    """Create the bcl_identity table if it doesn't exist."""
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS bcl_identity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            entity_name TEXT NOT NULL,
            domain TEXT,
            bcl_token TEXT NOT NULL,
            self_narrative TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(entity_type, entity_id)
        )
    """)
    # Add FTS5 index for searching BCL tokens
    try:
        c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS bcl_search USING fts5(entity_name, bcl_token, self_narrative, content='bcl_identity', content_rowid='id')")
    except:
        pass  # FTS5 might already exist
    conn.commit()


def store_bcl_identity(conn, entity_type, entity_id, entity_name, domain, bcl, narrative):
    """Store or update a BCL identity token."""
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO bcl_identity (entity_type, entity_id, entity_name, domain, bcl_token, self_narrative)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (entity_type, entity_id, entity_name, domain, bcl, narrative))
    conn.commit()


def extract_narrative(bcl_text):
    """Extract the self_narrative value from a BCL token."""
    try:
        # Find ("self_narrative";"...")
        marker = '("self_narrative";"'
        idx = bcl_text.find(marker)
        if idx == -1:
            return ""
        start = idx + len(marker)
        end = bcl_text.find('"', start)
        if end == -1:
            return ""
        return bcl_text[start:end]
    except:
        return ""


def main():
    print("=" * 70)
    print("BCL IDENTITY GENERATOR")
    print("=" * 70)
    print(f"Database: {DB_PATH}")
    print()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    create_bcl_identity_table(conn)

    # ─── 1. DOMAIN-LEVEL BCL ───
    print("[1/4] Generating DOMAIN-level BCL identities...")
    c = conn.cursor()
    c.execute("SELECT DISTINCT domain FROM classes WHERE is_vbstyle=1 ORDER BY domain")
    domains = [r[0] for r in c.fetchall()]
    domain_count = 0
    for domain in domains:
        bcl = generate_domain_bcl(conn, domain)
        if bcl:
            # Find the primary class for this domain
            c.execute("SELECT id, class_name FROM classes WHERE is_vbstyle=1 AND domain=? ORDER BY id LIMIT 1", (domain,))
            row = c.fetchone()
            if row:
                narrative = extract_narrative(bcl)
                store_bcl_identity(conn, "domain", row[0], row[1], domain, bcl, narrative)
                domain_count += 1
    print(f"  Generated {domain_count} domain BCL tokens")

    # Show a sample
    c.execute("SELECT entity_name, domain, bcl_token FROM bcl_identity WHERE entity_type='domain' LIMIT 3")
    for r in c.fetchall():
        print(f"\n  Sample: [@{r['entity_name']}] ({r['domain']})")
        print(f"  {r['bcl_token'][:200]}...")

    # ─── 2. CLASS-LEVEL BCL ───
    print(f"\n[2/4] Generating CLASS-level BCL identities...")
    c.execute("SELECT id, class_name, domain, description FROM classes WHERE is_vbstyle=1 ORDER BY domain, class_name")
    classes = c.fetchall()
    class_count = 0
    for cls in classes:
        bcl = generate_class_bcl(conn, cls["id"], cls["class_name"], cls["domain"], cls["description"])
        if bcl:
            narrative = extract_narrative(bcl)
            store_bcl_identity(conn, "class", cls["id"], cls["class_name"], cls["domain"], bcl, narrative)
            class_count += 1
    print(f"  Generated {class_count} class BCL tokens")

    # ─── 3. METHOD-LEVEL BCL ───
    print(f"\n[3/4] Generating METHOD-level BCL identities...")
    c.execute("""
        SELECT m.id, m.class_id, m.method_name, m.params, m.returns_tuple3
        FROM methods m
        JOIN classes cl ON m.class_id = cl.id
        WHERE cl.is_vbstyle=1 AND m.method_name NOT LIKE '\\_%'
        ORDER BY cl.domain, cl.class_name, m.method_name
    """)
    methods = c.fetchall()
    method_count = 0
    for m in methods:
        bcl = generate_method_bcl(conn, m["id"], m["class_id"], m["method_name"], m["params"], m["returns_tuple3"])
        if bcl:
            narrative = extract_narrative(bcl)
            # Get domain for this method
            c2 = conn.cursor()
            c2.execute("SELECT domain FROM classes WHERE id=?", (m["class_id"],))
            domain = c2.fetchone()[0]
            store_bcl_identity(conn, "method", m["id"], m["method_name"], domain, bcl, narrative)
            method_count += 1
    print(f"  Generated {method_count} method BCL tokens")

    # ─── 4. COMPUTATIONAL UNIT-LEVEL BCL ───
    print(f"\n[4/4] Generating COMPUTATIONAL UNIT-level BCL identities...")
    c.execute("SELECT id, unit_name, unit_type, class_id, method_id, description FROM computational_units")
    cus = c.fetchall()
    cu_count = 0
    for cu in cus:
        bcl = generate_cu_bcl(conn, cu["id"], cu["unit_name"], cu["unit_type"], cu["class_id"], cu["method_id"], cu["description"])
        if bcl:
            narrative = extract_narrative(bcl)
            # Get domain
            domain = ""
            if cu["class_id"]:
                c2 = conn.cursor()
                c2.execute("SELECT domain FROM classes WHERE id=?", (cu["class_id"],))
                row = c2.fetchone()
                if row:
                    domain = row[0]
            store_bcl_identity(conn, "cu", cu["id"], cu["unit_name"], domain, bcl, narrative)
            cu_count += 1
    print(f"  Generated {cu_count} computational unit BCL tokens")

    # ─── Summary ───
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    c.execute("SELECT entity_type, COUNT(*) as cnt FROM bcl_identity GROUP BY entity_type ORDER BY entity_type")
    for r in c.fetchall():
        print(f"  {r['entity_type']:10}: {r['cnt']} BCL tokens")

    c.execute("SELECT COUNT(*) FROM bcl_identity")
    total = c.fetchone()[0]
    print(f"  {'TOTAL':10}: {total} BCL tokens")

    # Show full sample tokens
    print("\n" + "=" * 70)
    print("SAMPLE BCL IDENTITY TOKENS")
    print("=" * 70)

    for etype in ["domain", "class", "method", "cu"]:
        c.execute("SELECT entity_name, domain, bcl_token, self_narrative FROM bcl_identity WHERE entity_type=? LIMIT 2", (etype,))
        rows = c.fetchall()
        for r in rows:
            print(f"\n  [{etype.upper()}] {r['entity_name']} ({r['domain'] or 'N/A'})")
            print(f"  BCL: {r['bcl_token']}")
            print(f"  Narrative: {r['self_narrative']}")

    # Register in _table_registry
    c.execute("SELECT COUNT(*) FROM _table_registry WHERE table_name='bcl_identity'")
    if c.fetchone()[0] == 0:
        c.execute("""
            INSERT INTO _table_registry (table_name, layer, purpose, key_columns, notes)
            VALUES ('bcl_identity', 'identity', 'BCL self-description tokens for every entity (domain, class, method, CU)', 'entity_type, entity_id, entity_name, domain', 'Each entity carries its own BCL identity. Ask any entity who it is and it answers in BCL.')
        """)
        conn.commit()

    # Register in _db_meta
    c.execute("SELECT COUNT(*) FROM _db_meta WHERE key='bcl_identity'")
    if c.fetchone()[0] == 0:
        c.execute("""
            INSERT INTO _db_meta (key, value) VALUES ('bcl_identity',
            'Every entity in the database has a BCL self-description token. Domains, classes, methods, and computational units can all answer "who are you?" in BCL format. The interrogator retrieves these tokens and the LLM formats them as natural speech.')
        """)
        conn.commit()

    conn.close()
    print(f"\nDone. {total} BCL identity tokens stored in v20_hybrid_best.db")


if __name__ == "__main__":
    main()
