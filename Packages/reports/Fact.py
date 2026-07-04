#!/usr/bin/env python3
# [@GHOST]{[@file<Fact.py>][@domain<Dom_Report>][@role<atom>][@auth<devin>][@date<2026-07-02>][@ver<3.0.0>][@session<report-domain>]}
# [@VBSTYLE]{[@auth<devin>][@role<data_type>][@return<tuple3>][@orch<Report>][@no<decorators|print|hardcoded|tabs|self_underscore>]}
# [@SUMMARY]{Fact — the one universal data type. Carries one piece of runtime information: kind, name, value + metadata (timestamp, source).}
# [@CLASS]{Fact}
# [@METHOD]{Run,read_state,set_config}
# [@FILEID]{core/Dom_Report/Fact.py

import datetime

from . import Config


class Fact:
    """The universal atom of runtime information.

    CONTENT (provided by the emitter):
        state['kind']:      one of FACT_KINDS — what type of information
        state['name']:      what this fact is about
        state['value']:     the actual data
        state['severity']:  sub-classification for issues (error/warning/info)
        state['unit']:      optional unit for measurements
        state['detail']:    optional extended explanation

    METADATA (stamped by the collector, not the emitter):
        state['timestamp']: when the fact was received
        state['source']:    who produced it (class.method)
        state['file']:      optional source file
        state['line']:      optional source line
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "kind": "message",
            "name": "",
            "value": None,
            "severity": "",
            "unit": "",
            "detail": "",
            "timestamp": "",
            "source": "",
            "file": "",
            "line": 0,
        }
        if param:
            self.set_config(param)

    def Run(self, command, params=None):
        dispatch = {
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", command, 0))
        return handler(params or {})

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        for key, val in params.items():
            if key in self.state:
                self.state[key] = val
        if self.state["kind"] not in Config.FACT_KINDS and self.state["kind"] != "summary":
            self.state["kind"] = "message"
        return (1, dict(self.state), None)
