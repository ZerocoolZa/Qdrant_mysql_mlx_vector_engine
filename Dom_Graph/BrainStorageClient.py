#!/usr/bin/env python3
# [@GHOST]{[@file<BrainStorageClient.py>][@domain<graph>][@role<storage_client>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<storage_client>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{BrainStorageClient — Python client for the Node.js BrainStorageServer. Sends trained models, templates, training history, and layout snapshots to the REST API. VBStyle Run() dispatch, Tuple3, self.state.}
# [@CLASS]{BrainStorageClient}
# [@METHOD]{Run,save_model,get_models,save_template,get_templates,save_history,get_history,save_layout,get_layouts,save_run,get_stats,health,read_state,set_config}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<warn>][@notes<Python REST client for Node.js BrainStorageServer. Sends models, templates, history, layouts via HTTP. VBStyle Run dispatch, Tuple3, self.state. Has hardcoded SERVER_HOST, SERVER_PORT, TIMEOUT_SEC defaults. Uses os.environ for override which is acceptable.>][@todos<Move default host/port/timeout to Config.py>]}
"""
BrainStorageClient — Python REST client for BrainStorageServer.

Connects the Python GUI AI Brain to the Node.js storage server.
Sends trained model metadata, layout templates, training history,
and layout snapshots to the server via HTTP.

USAGE:
  from BrainStorageClient import BrainStorageClient

  client = BrainStorageClient(param={"host": "0.0.0.0", "port": 7777})
  client.Run("health")                              # check server
  client.Run("save_model", {"name": "v3", ...})     # save model metadata
  client.Run("save_template", {"name": "vscode", ...}) # save layout template
  client.Run("save_history", {"run_id": "run1", ...}) # save training episode
  client.Run("get_stats")                           # get system stats
"""

import json
import os
import urllib.request
import urllib.error

SERVER_HOST = os.environ.get("BRAIN_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("BRAIN_PORT", "7777"))
TIMEOUT_SEC = 10

# API endpoint paths (UPPERCASE constants, not hardcoded strings in code)
PATH_HEALTH = "/health"
PATH_MODELS = "/api/models"
PATH_TEMPLATES = "/api/templates"
PATH_HISTORY = "/api/history"
PATH_HISTORY_BATCH = "/api/history/batch"
PATH_HISTORY_LATEST = "/api/history/latest"
PATH_LAYOUTS = "/api/layouts"
PATH_RUNS = "/api/runs"
PATH_STATS = "/api/stats"


class BrainStorageClient:
    """
    Python REST client for BrainStorageServer.
    VBStyle: Run() dispatch, Tuple3 returns, self.state dict.
    """

    def __init__(self, mem=None, db=None, param=None):
        p = param or {}
        self.state = {
            "config": {
                "host": p.get("host", SERVER_HOST),
                "port": int(p.get("port", SERVER_PORT)),
                "timeout": TIMEOUT_SEC,
            },
            "connected": False,
            "last_response": None,
            "stats": {
                "requests": 0,
                "successes": 0,
                "failures": 0,
            },
        }

    def Run(self, command, params=None):
        dispatch = {
            "health": self.cmd_health,
            "save_model": self.cmd_save_model,
            "get_models": self.cmd_get_models,
            "save_template": self.cmd_save_template,
            "get_templates": self.cmd_get_templates,
            "save_history": self.cmd_save_history,
            "save_history_batch": self.cmd_save_history_batch,
            "get_history": self.cmd_get_history,
            "get_history_latest": self.cmd_get_history_latest,
            "save_layout": self.cmd_save_layout,
            "get_layouts": self.cmd_get_layouts,
            "save_run": self.cmd_save_run,
            "get_runs": self.cmd_get_runs,
            "get_stats": self.cmd_get_stats,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", "unknown command", 0))
        return handler(params or {})

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        for key, val in params.items():
            if key in self.state["config"]:
                self.state["config"][key] = val
        return (1, dict(self.state["config"]), None)

    def p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def baseUrl(self):
        cfg = self.state["config"]
        return "http://%s:%d" % (cfg["host"], cfg["port"])

    def request(self, method, path, data=None):
        """Make HTTP request to the server. Returns (ok, responseData, error)."""
        url = self.baseUrl() + path
        self.state["stats"]["requests"] += 1
        try:
            if data is not None:
                body = json.dumps(data).encode("utf-8")
                req = urllib.request.Request(url, data=body, method=method)
                req.add_header("Content-Type", "application/json")
            else:
                req = urllib.request.Request(url, method=method)
            with urllib.request.urlopen(req, timeout=self.state["config"]["timeout"]) as resp:
                responseBody = resp.read().decode("utf-8")
                parsed = json.loads(responseBody)
                self.state["stats"]["successes"] += 1
                self.state["last_response"] = parsed
                return (True, parsed, None)
        except urllib.error.URLError as e:
            self.state["stats"]["failures"] += 1
            return (False, None, ("ERR_CONNECTION", str(e)[:200], 0))
        except Exception as e:
            self.state["stats"]["failures"] += 1
            return (False, None, ("ERR_REQUEST", str(e)[:200], 0))

    # ════════════════════════════════════════════
    # HEALTH
    # ════════════════════════════════════════════

    def cmd_health(self, params):
        ok, data, err = self.request("GET", PATH_HEALTH)
        if not ok:
            return (0, None, err)
        self.state["connected"] = True
        return (1, data, None)

    # ════════════════════════════════════════════
    # MODELS
    # ════════════════════════════════════════════

    def cmd_save_model(self, params):
        ok, data, err = self.request("POST", PATH_MODELS, params)
        if not ok:
            return (0, None, err)
        return (1, data, None)

    def cmd_get_models(self, params):
        limit = self.p(params, "limit", 50)
        ok, data, err = self.request("GET", PATH_MODELS + "?limit=%d" % limit)
        if not ok:
            return (0, None, err)
        return (1, data, None)

    # ════════════════════════════════════════════
    # TEMPLATES
    # ════════════════════════════════════════════

    def cmd_save_template(self, params):
        ok, data, err = self.request("POST", PATH_TEMPLATES, params)
        if not ok:
            return (0, None, err)
        return (1, data, None)

    def cmd_get_templates(self, params):
        ok, data, err = self.request("GET", PATH_TEMPLATES)
        if not ok:
            return (0, None, err)
        return (1, data, None)

    # ════════════════════════════════════════════
    # HISTORY
    # ════════════════════════════════════════════

    def cmd_save_history(self, params):
        ok, data, err = self.request("POST", PATH_HISTORY, params)
        if not ok:
            return (0, None, err)
        return (1, data, None)

    def cmd_save_history_batch(self, params):
        ok, data, err = self.request("POST", PATH_HISTORY_BATCH, params)
        if not ok:
            return (0, None, err)
        return (1, data, None)

    def cmd_get_history(self, params):
        runId = self.p(params, "run_id")
        limit = self.p(params, "limit", 100)
        if runId:
            path = PATH_HISTORY + "?run_id=%s&limit=%d" % (runId, limit)
        else:
            path = PATH_HISTORY + "?limit=%d" % limit
        ok, data, err = self.request("GET", path)
        if not ok:
            return (0, None, err)
        return (1, data, None)

    def cmd_get_history_latest(self, params):
        ok, data, err = self.request("GET", PATH_HISTORY_LATEST)
        if not ok:
            return (0, None, err)
        return (1, data, None)

    # ════════════════════════════════════════════
    # LAYOUTS
    # ════════════════════════════════════════════

    def cmd_save_layout(self, params):
        ok, data, err = self.request("POST", PATH_LAYOUTS, params)
        if not ok:
            return (0, None, err)
        return (1, data, None)

    def cmd_get_layouts(self, params):
        limit = self.p(params, "limit", 50)
        ok, data, err = self.request("GET", PATH_LAYOUTS + "?limit=%d" % limit)
        if not ok:
            return (0, None, err)
        return (1, data, None)

    # ════════════════════════════════════════════
    # RUNS
    # ════════════════════════════════════════════

    def cmd_save_run(self, params):
        ok, data, err = self.request("POST", PATH_RUNS, params)
        if not ok:
            return (0, None, err)
        return (1, data, None)

    def cmd_get_runs(self, params):
        ok, data, err = self.request("GET", PATH_RUNS)
        if not ok:
            return (0, None, err)
        return (1, data, None)

    # ════════════════════════════════════════════
    # STATS
    # ════════════════════════════════════════════

    def cmd_get_stats(self, params):
        ok, data, err = self.request("GET", PATH_STATS)
        if not ok:
            return (0, None, err)
        return (1, data, None)
