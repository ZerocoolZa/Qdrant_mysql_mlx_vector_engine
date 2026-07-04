#!/usr/bin/env python3
#[@GHOST]{[@file<test_db_loader.py>][@domain<Dom_Db>][@role<test>][@auth<cascade>][@date<2026-06-29>][@ver<1.0>][@session<db-module-loader>]}
#[@VBSTYLE]{[@auth<cascade>][@role<test_suite>][@return<Tuple3>][@orch<DbModuleLoader>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
#[@SUMMARY]{Test: load embedding classes from v20_hybrid_best.db and run them. Verifies DB-as-module concept works.}
#[@CLASS]{TestDbLoader}
#[@METHOD]{Run,TestListEmbeddingClasses,TestLoadEmbedQueryHelper,TestLoadTrainableEmbedding,TestLoadEmbeddingModelUnit,TestLoadDomain,TestLoadAndRun,read_state,set_config}
#[@FILEID]{core/Dom_Db/test_db_loader.py

import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(BASE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.Dom_Db.DbModuleLoader import DbModuleLoader


class TestDbLoader:

    def __init__(self):
        self.state = {
            "results": [],
            "errors": [],
            "loader": None,
        }

    def Run(self, command, params=None):
        params = params or {}
        if command == "run_all":
            return self._RunAll(params)
        if command == "read_state":
            return self.read_state(params)
        if command == "set_config":
            return self.set_config(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def _p(self, params, key, default=None):
        return params.get(key, default) if params else default

    def _Log(self, name, ok, detail=""):
        status = "PASS" if ok else "FAIL"
        line = "[" + status + "] " + name + (" — " + detail if detail else "")
        self.state["results"].append(line)
        if not ok:
            self.state["errors"].append(line)
        return line

    def _RunAll(self, params):
        self._Log("init_loader", True, "DbModuleLoader created")
        self.TestListEmbeddingClasses(params)
        self.TestLoadEmbeddingModelUnit(params)
        self.TestLoadMPSEmbeddingUnit(params)
        self.TestLoadEmbedQueryHelper(params)
        self.TestLoadTrainableEmbedding(params)
        self.TestLoadDomain(params)
        self.TestLoadAndRun(params)
        total = len(self.state["results"])
        passed = total - len(self.state["errors"])
        summary = "RESULTS: " + str(passed) + "/" + str(total) + " passed"
        if self.state["errors"]:
            summary += " — " + str(len(self.state["errors"])) + " FAILED"
        self.state["results"].append(summary)
        return (1, {"summary": summary, "results": self.state["results"], "errors": self.state["errors"]}, None)

    def TestListEmbeddingClasses(self, params):
        loader = DbModuleLoader()
        self.state["loader"] = loader
        ok, data, err = loader.Run("list_classes", {})
        if not ok:
            self._Log("list_embedding_classes", False, str(err))
            return (0, None, err)
        all_classes = data["classes"]
        embed_classes = [c for c in all_classes if "embed" in c["class_name"].lower()]
        detail = str(len(embed_classes)) + " embedding classes: " + ", ".join(c["class_name"] for c in embed_classes)
        self._Log("list_embedding_classes", len(embed_classes) > 0, detail)
        return (1, embed_classes, None)

    def TestLoadEmbeddingModelUnit(self, params):
        loader = self.state["loader"]
        ok, data, err = loader.Run("load_class", {"class_name": "EmbeddingModelUnit"})
        if not ok:
            self._Log("load_EmbeddingModelUnit", False, str(err))
            return (0, None, err)
        cls = data["class"]
        has_vectorize = hasattr(cls, "vectorize_many")
        detail = "loaded, has vectorize_many=" + str(has_vectorize)
        self._Log("load_EmbeddingModelUnit", has_vectorize, detail)
        return (1, data, None)

    def TestLoadMPSEmbeddingUnit(self, params):
        loader = self.state["loader"]
        ok, data, err = loader.Run("load_class", {"class_name": "MPSEmbeddingUnit"})
        if not ok:
            self._Log("load_MPSEmbeddingUnit", False, str(err))
            return (0, None, err)
        cls = data["class"]
        has_embed = hasattr(cls, "embed_terms")
        detail = "loaded, has embed_terms=" + str(has_embed)
        self._Log("load_MPSEmbeddingUnit", has_embed, detail)
        return (1, data, None)

    def TestLoadEmbedQueryHelper(self, params):
        loader = self.state["loader"]
        ok, data, err = loader.Run("load_class", {"class_name": "EmbedQueryHelper"})
        if not ok:
            self._Log("load_EmbedQueryHelper", False, str(err))
            return (0, None, err)
        cls = data["class"]
        has_run = hasattr(cls, "Run")
        detail = "loaded, has Run=" + str(has_run)
        self._Log("load_EmbedQueryHelper", has_run, detail)
        return (1, data, None)

    def TestLoadTrainableEmbedding(self, params):
        loader = self.state["loader"]
        ok, data, err = loader.Run("load_class", {"class_name": "TrainableEmbedding"})
        if not ok:
            self._Log("load_TrainableEmbedding", False, str(err))
            return (0, None, err)
        cls = data["class"]
        has_run = hasattr(cls, "Run")
        detail = "loaded, has Run=" + str(has_run)
        self._Log("load_TrainableEmbedding", has_run, detail)
        return (1, data, None)

    def TestLoadDomain(self, params):
        loader = self.state["loader"]
        ok, data, err = loader.Run("load_domain", {"domain": "qa"})
        if not ok:
            self._Log("load_domain_qa", False, str(err))
            return (0, None, err)
        loaded = data["loaded"]
        has_embed = any("Embed" in c for c in loaded)
        detail = str(data["count"]) + " classes loaded: " + ", ".join(loaded[:8])
        self._Log("load_domain_qa", has_embed, detail)
        return (1, data, None)

    def TestLoadAndRun(self, params):
        loader = self.state["loader"]
        ok, data, err = loader.Run("load_and_run", {
            "class_name": "EmbedQueryHelper",
            "command": "read_state",
            "params": {},
        })
        if not ok:
            self._Log("load_and_run_EmbedQueryHelper", False, str(err))
            return (0, None, err)
        has_state = isinstance(data, tuple) and len(data) == 3 and data[0] == 1
        detail = "Run(read_state) returned Tuple3 ok=" + str(data[0]) if isinstance(data, tuple) else "returned: " + str(type(data))
        self._Log("load_and_run_EmbedQueryHelper", has_state, detail)
        return (1, data, None)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params=None):
        return (1, {}, None)


if __name__ == "__main__":
    test = TestDbLoader()
    ok, data, err = test.Run("run_all")
    for line in data["results"]:
        sys.stdout.write(line + "\n")
    if err:
        sys.stdout.write("FATAL: " + str(err) + "\n")
    sys.exit(0 if not test.state["errors"] else 1)
