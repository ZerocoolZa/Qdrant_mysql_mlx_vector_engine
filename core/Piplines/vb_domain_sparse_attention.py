#!/usr/bin/env python3
#[@GHOST]{file_path="core/Piplines/vb_domain_sparse_attention.py" date="2026-07-04" author="Cascade" session_id="domain-sparse-attn" context="DomainSparseAttention — 75 domains as block-sparse attention clusters for BCL Transformer. Same-domain dense, cross-domain sparse."}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE spaces only Tuple3 no_print no_decorator no_self_underscore"}
#[@FILEID]{id="vb_domain_sparse_attention.py" domain="Piplines" authority="DomainSparseAttention"}
#[@SUMMARY]{summary="DomainSparseAttention loads 75 domains from MySQL vb_shared.domains, routes tokens to domains via vb_code_test.vb_classes lookup + BCL container name matching, builds block-sparse attention mask (dense intra-domain blocks + sparse cross-domain links), converts to dense numpy for Metal kernel. Config: n_domains=75, cross_attention_density=1, d_model=384, n_heads=6."}
#[@CLASS]{DomainSparseAttention}
#[@METHOD]{Run LoadDomains BuildMask ToDense Info RouteToken BuildBlockSparse CrossDomainLinks _p read_state SetConfig}

"""
DomainSparseAttention — Block-Sparse Domain Attention for BCL Transformer

Vision component #6 (Config_BclTransformer.py BUILD_ORDER).
75 domains in MySQL vb_shared.domains → sparse attention clusters.

Mask structure:
  - Tokens in the SAME domain attend to each other fully (dense block)
  - Tokens in DIFFERENT domains attend sparsely (cross_attention_density random links per token)
  - Result: 75 dense blocks + sparse cross-links, stored as block-sparse (not dense O(N^2))

Commands (Run dispatch):
  load_domains  — query MySQL, cache domain list + class→domain map
  build_mask    — takes list of (token, class_name) pairs, returns block-sparse mask
  to_dense      — converts block-sparse mask to dense numpy array (seq_len, seq_len)
  info          — return config + cache stats
"""

import os
import sys
import random
import numpy as np
import pymysql
from typing import Optional
from typing import Tuple
from typing import Dict
from typing import Any
from typing import List

MYSQL_HOST = "localhost"
MYSQL_PORT = 3306
MYSQL_USER = "root"
MYSQL_PASSWORD = ""
DOMAINS_DB = "vb_shared"
CLASSES_DB = "vb_code_test"

N_DOMAINS = 75
CROSS_ATTENTION_DENSITY = 1
D_MODEL = 384
N_HEADS = 6
UNKNOWN_DOMAIN = "unknown"


class DomainSparseAttention:
    """Block-sparse domain attention. 75 domains → dense intra-domain blocks + sparse cross-links."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "n_domains": N_DOMAINS,
                "cross_attention_density": CROSS_ATTENTION_DENSITY,
                "d_model": D_MODEL,
                "n_heads": N_HEADS,
                "mysql_host": MYSQL_HOST,
                "mysql_port": MYSQL_PORT,
                "mysql_user": MYSQL_USER,
                "domains_db": DOMAINS_DB,
                "classes_db": CLASSES_DB,
            },
            "domains": [],
            "domain_index": {},
            "class_to_domain": {},
            "block_sparse_mask": None,
            "token_domains": [],
            "seq_len": 0,
            "loaded": False,
            "meta": {"last_command": None, "domain_count": 0, "class_count": 0},
        }

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self) -> Tuple[int, Dict, Optional[Tuple]]:
        return (1, self.state, None)

    def SetConfig(self, params: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:
        if not params:
            return (0, None, (1, "Missing config params", 0))
        self.state["config"].update(params)
        return (1, "Config updated", None)

    def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, Any, Optional[Tuple]]:
        if params is None:
            params = {}
        self.state["meta"]["last_command"] = command
        if command == "load_domains":
            return self.LoadDomains(params)
        elif command == "build_mask":
            return self.BuildMask(params)
        elif command == "to_dense":
            return self.ToDense(params)
        elif command == "info":
            return self.Info(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def LoadDomains(self, params: Optional[dict] = None) -> Tuple[int, Dict, Optional[Tuple]]:
        cfg = self.state["config"]
        n_domains = cfg["n_domains"]
        try:
            conn = pymysql.connect(
                host=cfg["mysql_host"],
                port=cfg["mysql_port"],
                user=cfg["mysql_user"],
                password="",
                database=cfg["domains_db"],
                charset="utf8mb4",
            )
            cur = conn.cursor()
            cur.execute("SELECT id, name FROM domains ORDER BY id ASC LIMIT %s", (n_domains,))
            rows = cur.fetchall()
            cur.close()
            conn.close()
        except Exception as e:
            return (0, None, ("MYSQL_DOMAIN_ERROR", str(e), 0))
        domains = []
        domain_index = {}
        for row in rows:
            did = int(row[0])
            dname = str(row[1]).lower()
            domains.append({"id": did, "name": dname})
            domain_index[dname] = did
        class_to_domain = {}
        try:
            conn2 = pymysql.connect(
                host=cfg["mysql_host"],
                port=cfg["mysql_port"],
                user=cfg["mysql_user"],
                password="",
                database=cfg["classes_db"],
                charset="utf8mb4",
            )
            cur2 = conn2.cursor()
            cur2.execute(
                "SELECT class_name, domain FROM vb_classes "
                "WHERE domain IS NOT NULL AND domain != '' "
                "AND domain NOT LIKE '%%{%%' AND domain NOT LIKE '%%not in%%'"
            )
            for r in cur2.fetchall():
                cname = str(r[0])
                dname = str(r[1]).lower()
                if dname in domain_index:
                    class_to_domain[cname] = dname
                else:
                    matched = None
                    for dn in domain_index:
                        if dn in dname or dname in dn:
                            matched = dn
                            break
                    if matched:
                        class_to_domain[cname] = matched
            cur2.close()
            conn2.close()
        except Exception as e:
            return (0, None, ("MYSQL_CLASS_ERROR", str(e), 0))
        self.state["domains"] = domains
        self.state["domain_index"] = domain_index
        self.state["class_to_domain"] = class_to_domain
        self.state["loaded"] = True
        self.state["meta"]["domain_count"] = len(domains)
        self.state["meta"]["class_count"] = len(class_to_domain)
        return (1, {
            "domains_loaded": len(domains),
            "classes_routed": len(class_to_domain),
            "domain_names": [d["name"] for d in domains[:10]],
        }, None)

    def RouteToken(self, class_name: str) -> Tuple[int, str, Optional[Tuple]]:
        class_to_domain = self.state["class_to_domain"]
        domain_index = self.state["domain_index"]
        if class_name in class_to_domain:
            return (1, class_to_domain[class_name], None)
        lower = class_name.lower()
        for dname in domain_index:
            if dname in lower:
                return (1, dname, None)
        for dname in domain_index:
            if lower in dname:
                return (1, dname, None)
        return (1, UNKNOWN_DOMAIN, None)

    def BuildMask(self, params: Optional[dict] = None) -> Tuple[int, Dict, Optional[Tuple]]:
        if not self.state["loaded"]:
            res = self.LoadDomains(params)
            if res[0] != 1:
                return res
        tokens = self._p(params, "tokens", None)
        if not tokens:
            return (0, None, ("MISSING_TOKENS", "tokens (list of (token, class_name) pairs) required", 0))
        density = self._p(params, "cross_attention_density", self.state["config"]["cross_attention_density"])
        seed = self._p(params, "seed", 42)
        rng = random.Random(seed)
        token_domains = []
        for pair in tokens:
            if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                class_name = str(pair[1])
            else:
                class_name = str(pair)
            rres = self.RouteToken(class_name)
            token_domains.append(rres[1])
        seq_len = len(tokens)
        domain_groups = {}
        for idx, dname in enumerate(token_domains):
            if dname not in domain_groups:
                domain_groups[dname] = []
            domain_groups[dname].append(idx)
        dense_blocks = {}
        for dname, indices in domain_groups.items():
            pairs = []
            for i in indices:
                for j in indices:
                    pairs.append((i, j))
            dense_blocks[dname] = {"indices": indices, "pairs": pairs}
        cross_links = []
        domain_names = list(domain_groups.keys())
        if len(domain_names) > 1:
            for i in range(seq_len):
                src_domain = token_domains[i]
                other_domains = [d for d in domain_names if d != src_domain]
                if not other_domains:
                    continue
                for _ in range(density):
                    tgt_domain = rng.choice(other_domains)
                    tgt_indices = domain_groups[tgt_domain]
                    j = rng.choice(tgt_indices)
                    cross_links.append((i, j))
        block_sparse = {
            "seq_len": seq_len,
            "token_domains": token_domains,
            "domain_groups": domain_groups,
            "dense_blocks": dense_blocks,
            "cross_links": cross_links,
            "cross_attention_density": density,
        }
        self.state["block_sparse_mask"] = block_sparse
        self.state["token_domains"] = token_domains
        self.state["seq_len"] = seq_len
        nnz = sum(len(b["pairs"]) for b in dense_blocks.values()) + len(cross_links)
        dense_nnz = seq_len * seq_len
        sparsity = 1.0 - (nnz / dense_nnz) if dense_nnz > 0 else 0.0
        return (1, {
            "seq_len": seq_len,
            "n_domains_active": len(domain_groups),
            "n_dense_blocks": len(dense_blocks),
            "n_cross_links": len(cross_links),
            "nnz": nnz,
            "sparsity": round(sparsity, 4),
            "token_domains": token_domains,
        }, None)

    def ToDense(self, params: Optional[dict] = None) -> Tuple[int, Any, Optional[Tuple]]:
        bsm = self.state["block_sparse_mask"]
        if bsm is None:
            return (0, None, ("NO_MASK", "No block-sparse mask built. Run build_mask first.", 0))
        seq_len = bsm["seq_len"]
        mask = np.zeros((seq_len, seq_len), dtype=np.float32)
        for dname, block in bsm["dense_blocks"].items():
            for (i, j) in block["pairs"]:
                mask[i, j] = 1.0
        for (i, j) in bsm["cross_links"]:
            mask[i, j] = 1.0
        return (1, mask, None)

    def Info(self, params: Optional[dict] = None) -> Tuple[int, Dict, Optional[Tuple]]:
        cfg = self.state["config"]
        return (1, {
            "config": cfg,
            "loaded": self.state["loaded"],
            "domain_count": self.state["meta"]["domain_count"],
            "class_count": self.state["meta"]["class_count"],
            "has_mask": self.state["block_sparse_mask"] is not None,
            "seq_len": self.state["seq_len"],
        }, None)


def _run_test():
    """Self-test: 10 tokens across 3 domains. No print (writes to stderr via sys.stderr)."""
    dsa = DomainSparseAttention()
    lres = dsa.Run("load_domains")
    if lres[0] != 1:
        sys.stderr.write("[TEST] load_domains FAILED: " + str(lres[2]) + "\n")
        return 1
    sys.stderr.write("[TEST] Domains loaded: " + str(lres[1]["domains_loaded"]) + "\n")
    sys.stderr.write("[TEST] Classes routed: " + str(lres[1]["classes_routed"]) + "\n")
    tokens = [
        ("tok0", "DomSecurity"),
        ("tok1", "DomNetwork"),
        ("tok2", "DomStorage"),
        ("tok3", "DomSecurity"),
        ("tok4", "DomNetwork"),
        ("tok5", "DomStorage"),
        ("tok6", "DomSecurity"),
        ("tok7", "DomNetwork"),
        ("tok8", "DomStorage"),
        ("tok9", "DomSecurity"),
    ]
    bres = dsa.Run("build_mask", {"tokens": tokens})
    if bres[0] != 1:
        sys.stderr.write("[TEST] build_mask FAILED: " + str(bres[2]) + "\n")
        return 1
    info = bres[1]
    sys.stderr.write("[TEST] seq_len=" + str(info["seq_len"]) + "\n")
    sys.stderr.write("[TEST] n_domains_active=" + str(info["n_domains_active"]) + "\n")
    sys.stderr.write("[TEST] n_dense_blocks=" + str(info["n_dense_blocks"]) + "\n")
    sys.stderr.write("[TEST] n_cross_links=" + str(info["n_cross_links"]) + "\n")
    sys.stderr.write("[TEST] nnz=" + str(info["nnz"]) + " sparsity=" + str(info["sparsity"]) + "\n")
    sys.stderr.write("[TEST] token_domains=" + str(info["token_domains"]) + "\n")
    dres = dsa.Run("to_dense")
    if dres[0] != 1:
        sys.stderr.write("[TEST] to_dense FAILED: " + str(dres[2]) + "\n")
        return 1
    dense = dres[1]
    sys.stderr.write("[TEST] dense shape=" + str(dense.shape) + " sum=" + str(float(dense.sum())) + "\n")
    ires = dsa.Run("info")
    if ires[0] == 1:
        sys.stderr.write("[TEST] info: " + str(ires[1]) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(_run_test())
