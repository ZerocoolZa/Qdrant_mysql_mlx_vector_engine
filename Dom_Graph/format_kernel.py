#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/format_kernel.py"
# date="2026-06-26" author="Devin" session_id="phase7-meta"
# context="Project Digital Twin Phase 7 Section 71 Format Kernel"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="format_kernel.py" domain="twin_format" authority="FormatKernel"}
# [@SUMMARY]{summary="Format authority that controls output mode, validates output against schemas and enforces output block boundaries."}
# [@CLASS]{class="FormatKernel" domain="format" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="set_mode" type="command"}
# [@METHOD]{method="strict_output_mode" type="command"}
# [@METHOD]{method="single_block_enforcement" type="command"}
# [@METHOD]{method="no_commentary" type="command"}
# [@METHOD]{method="raw_structure_output" type="command"}
# [@METHOD]{method="validate_output" type="command"}
# [@METHOD]{method="format_compliance_validator" type="command"}
# [@METHOD]{method="enforce_boundaries" type="command"}
# [@METHOD]{method="block_boundary_enforcement" type="command"}
# [@METHOD]{method="encoding_consistency" type="command"}
# [@METHOD]{method="structural_completeness" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<FormatKernel: controls output mode, validates output against schemas, enforces output block boundaries. Full VBStyle headers, Run dispatch, Tuple3 returns, single class, _p helper. No print/decorators/self._/hardcoded paths.>][@todos<none>]}
"""
FormatKernel -- authority for output formatting control and validation.
Implements Section 71 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: set_mode, validate_output, enforce_boundaries.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50
VALID_MODES = ("strict", "json", "raw")
BLOCK_START = "```"
BLOCK_END = "```"


class FormatKernel:
    """Authority for output formatting control and structured output validation."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "default_limit": DEFAULT_LIMIT,
                "mode": "strict",
                "valid_modes": list(VALID_MODES),
            },
            "catalog": [],
            "results": [],
            "memunit": mem,
            "db_manager": db,
            "db_conn": None,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "set_mode":
            return self.SetMode(params)
        elif command == "strict_output_mode":
            return self.StrictOutputMode(params)
        elif command == "single_block_enforcement":
            return self.SingleBlockEnforcement(params)
        elif command == "no_commentary":
            return self.NoCommentary(params)
        elif command == "raw_structure_output":
            return self.RawStructureOutput(params)
        elif command == "validate_output":
            return self.ValidateOutput(params)
        elif command == "format_compliance_validator":
            return self.FormatComplianceValidator(params)
        elif command == "enforce_boundaries":
            return self.EnforceBoundaries(params)
        elif command == "block_boundary_enforcement":
            return self.BlockBoundaryEnforcement(params)
        elif command == "encoding_consistency":
            return self.EncodingConsistency(params)
        elif command == "structural_completeness":
            return self.StructuralCompleteness(params)
        elif command == "read_state":
            return self.read_state(params)
        elif command == "set_config":
            return self.set_config(params)
        return (0, None, ("UNKNOWN_COMMAND", "Unknown command: " + str(command), 0))

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        params = params or {}
        for key, value in params.items():
            self.state["config"][key] = value
        return (1, dict(self.state["config"]), None)

    def Connect(self):
        if self.state["db_conn"] is None:
            self.state["db_conn"] = sqlite3.connect(self.state["config"]["db_path"])
        return self.state["db_conn"]

    def SetMode(self, params):
        mode = self._p(params, "mode")
        if not mode:
            return (0, None, ("MISSING_PARAM", "mode required", 0))
        if mode not in VALID_MODES:
            return (0, None, ("INVALID_MODE",
                              "mode must be one of " + str(VALID_MODES), 0))
        self.state["config"]["mode"] = mode
        return (1, {"mode": mode, "confirmed": True}, None)

    def ValidateOutput(self, params):
        output = self._p(params, "output")
        expected_schema = self._p(params, "expected_schema")
        if output is None:
            return (0, None, ("MISSING_PARAM", "output required", 0))
        if not isinstance(output, dict):
            return (0, None, ("INVALID_OUTPUT", "output must be a dict", 0))
        if expected_schema is None:
            return (0, None, ("MISSING_PARAM", "expected_schema required", 0))
        if not isinstance(expected_schema, (list, dict)):
            return (0, None, ("INVALID_SCHEMA",
                              "expected_schema must be list or dict", 0))
        if isinstance(expected_schema, dict):
            required_fields = list(expected_schema.keys())
        else:
            required_fields = list(expected_schema)
        output_keys = list(output.keys())
        missing_fields = [f for f in required_fields if f not in output_keys]
        extra_fields = [k for k in output_keys if k not in required_fields]
        valid = (len(missing_fields) == 0)
        result = {
            "valid": valid,
            "missing_fields": missing_fields,
            "extra_fields": extra_fields,
        }
        self.state["results"] = result
        return (1, result, None)

    def EnforceBoundaries(self, params):
        output = self._p(params, "output")
        if output is None:
            return (0, None, ("MISSING_PARAM", "output required", 0))
        if not isinstance(output, str):
            return (0, None, ("INVALID_OUTPUT", "output must be a string", 0))
        violations = []
        start_count = output.count(BLOCK_START)
        end_count = output.count(BLOCK_END)
        if start_count == 0:
            violations.append("no_output_block")
        if start_count > 1:
            violations.append("multiple_output_blocks")
        if end_count != start_count:
            violations.append("unbalanced_block_markers")
        first_start = output.find(BLOCK_START)
        last_end = output.rfind(BLOCK_END)
        if first_start > 0:
            before = output[:first_start].strip()
            if before:
                violations.append("text_before_block")
        if last_end >= 0 and last_end + len(BLOCK_END) < len(output):
            after = output[last_end + len(BLOCK_END):].strip()
            if after:
                violations.append("text_after_block")
        valid = (len(violations) == 0)
        result = {"valid": valid, "violations": violations}
        self.state["results"] = result
        return (1, result, None)

    def StrictOutputMode(self, params):
        self.state["config"]["mode"] = "strict"
        output = self._p(params, "output")
        if output is None:
            return (1, {"mode": "strict", "confirmed": True}, None)
        if not isinstance(output, (dict, list, str)):
            return (0, None, ("INVALID_OUTPUT",
                              "output must be dict, list, or str", 0))
        if isinstance(output, str):
            try:
                json.loads(output)
            except (ValueError, TypeError):
                return (0, None, ("NOT_STRUCTURED",
                                  "strict mode requires JSON-serializable output", 0))
        return (1, {"mode": "strict", "confirmed": True,
                    "output_is_structured": True}, None)

    def SingleBlockEnforcement(self, params):
        output = self._p(params, "output")
        if output is None:
            return (0, None, ("MISSING_PARAM", "output required", 0))
        if not isinstance(output, str):
            return (0, None, ("INVALID_OUTPUT", "output must be a string", 0))
        violations = []
        start_count = output.count(BLOCK_START)
        if start_count > 1:
            violations.append("multiple_blocks_detected")
        if start_count == 0:
            violations.append("no_block_found")
        valid = (len(violations) == 0)
        return (1, {"valid": valid, "block_count": start_count,
                    "violations": violations}, None)

    def NoCommentary(self, params):
        output = self._p(params, "output")
        if output is None:
            return (0, None, ("MISSING_PARAM", "output required", 0))
        if not isinstance(output, str):
            return (0, None, ("INVALID_OUTPUT", "output must be a string", 0))
        commentary_markers = ["here's what", "i found", "let me", "as you can see",
                              "note that", "interestingly", "furthermore"]
        found = []
        lower = output.lower()
        for marker in commentary_markers:
            if marker in lower:
                found.append(marker)
        valid = (len(found) == 0)
        return (1, {"valid": valid, "commentary_found": found}, None)

    def RawStructureOutput(self, params):
        output = self._p(params, "output")
        if output is None:
            return (0, None, ("MISSING_PARAM", "output required", 0))
        if isinstance(output, (dict, list)):
            return (1, {"is_raw_structure": True,
                        "type": type(output).__name__}, None)
        if isinstance(output, str):
            try:
                json.loads(output)
                return (1, {"is_raw_structure": True,
                            "type": "json_string"}, None)
            except (ValueError, TypeError):
                return (0, None, ("NOT_RAW_STRUCTURE",
                                  "output is not structured data", 0))
        return (0, None, ("INVALID_OUTPUT",
                          "output must be dict, list, or JSON string", 0))

    def FormatComplianceValidator(self, params):
        output = self._p(params, "output")
        expected_format = self._p(params, "expected_format", "json")
        if output is None:
            return (0, None, ("MISSING_PARAM", "output required", 0))
        violations = []
        if expected_format == "json":
            if isinstance(output, str):
                try:
                    json.loads(output)
                except (ValueError, TypeError):
                    violations.append("not_valid_json")
            elif not isinstance(output, (dict, list)):
                violations.append("not_json_type")
        block_res = self.BlockBoundaryEnforcement(params)
        if block_res[0] == 1 and not block_res[1].get("valid", False):
            violations.extend(block_res[1].get("violations", []))
        enc_res = self.EncodingConsistency(params)
        if enc_res[0] == 1 and not enc_res[1].get("valid", False):
            violations.extend(enc_res[1].get("violations", []))
        struct_res = self.StructuralCompleteness(params)
        if struct_res[0] == 1 and not struct_res[1].get("valid", False):
            violations.extend(struct_res[1].get("violations", []))
        valid = (len(violations) == 0)
        result = {"valid": valid, "violations": violations,
                  "expected_format": expected_format}
        self.state["results"] = result
        return (1, result, None)

    def BlockBoundaryEnforcement(self, params):
        output = self._p(params, "output")
        if output is None:
            return (0, None, ("MISSING_PARAM", "output required", 0))
        if not isinstance(output, str):
            return (0, None, ("INVALID_OUTPUT", "output must be a string", 0))
        violations = []
        start_count = output.count(BLOCK_START)
        end_count = output.count(BLOCK_END)
        if start_count != end_count:
            violations.append("unbalanced_markers")
        if start_count == 0:
            violations.append("no_block_markers")
        if start_count > 1:
            violations.append("multiple_blocks")
        first_start = output.find(BLOCK_START)
        last_end = output.rfind(BLOCK_END)
        if first_start >= 0 and last_end >= 0:
            if first_start > last_end:
                violations.append("end_before_start")
        valid = (len(violations) == 0)
        return (1, {"valid": valid, "violations": violations,
                    "start_count": start_count, "end_count": end_count}, None)

    def EncodingConsistency(self, params):
        output = self._p(params, "output")
        if output is None:
            return (0, None, ("MISSING_PARAM", "output required", 0))
        violations = []
        if isinstance(output, str):
            try:
                output.encode("utf-8")
            except UnicodeEncodeError as exc:
                violations.append("encoding_error: " + str(exc)[:100])
            for char in output:
                if ord(char) > 0x10FFFF:
                    violations.append("invalid_unicode_char")
                    break
        elif isinstance(output, bytes):
            try:
                output.decode("utf-8")
            except UnicodeDecodeError as exc:
                violations.append("bytes_not_utf8: " + str(exc)[:100])
        else:
            try:
                json.dumps(output, ensure_ascii=False)
            except (TypeError, ValueError) as exc:
                violations.append("not_json_serializable: " + str(exc)[:100])
        valid = (len(violations) == 0)
        return (1, {"valid": valid, "encoding": "utf-8",
                    "violations": violations}, None)

    def StructuralCompleteness(self, params):
        output = self._p(params, "output")
        required_fields = self._p(params, "required_fields")
        if output is None:
            return (0, None, ("MISSING_PARAM", "output required", 0))
        if required_fields is None:
            return (0, None, ("MISSING_PARAM", "required_fields required", 0))
        if not isinstance(output, dict):
            return (0, None, ("INVALID_OUTPUT", "output must be a dict", 0))
        if not isinstance(required_fields, (list, dict)):
            return (0, None, ("INVALID_FIELDS",
                              "required_fields must be list or dict", 0))
        if isinstance(required_fields, dict):
            required = list(required_fields.keys())
        else:
            required = list(required_fields)
        missing = [f for f in required if f not in output]
        null_fields = [f for f in required if f in output and output[f] is None]
        valid = (len(missing) == 0 and len(null_fields) == 0)
        return (1, {"valid": valid, "missing": missing,
                    "null_fields": null_fields,
                    "total_required": len(required)}, None)
