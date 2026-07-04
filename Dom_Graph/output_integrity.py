#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/Dom_Graph/output_integrity.py"
# date="2026-06-26" author="Devin" session_id="phase7-meta"
# context="Project Digital Twin Phase 7 Section 74 Output Integrity"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="output_integrity.py" domain="twin_integrity" authority="OutputIntegrity"}
# [@SUMMARY]{summary="Output integrity authority that validates blocks, checks completeness, verifies schemas and runs final aggregated validation."}
# [@CLASS]{class="OutputIntegrity" domain="integrity" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="validate_block" type="command"}
# [@METHOD]{method="check_completeness" type="command"}
# [@METHOD]{method="check_schema" type="command"}
# [@METHOD]{method="block_boundary_enforcement" type="command"}
# [@METHOD]{method="encoding_consistency" type="command"}
# [@METHOD]{method="structural_completeness" type="command"}
# [@METHOD]{method="missing_section_detection" type="command"}
# [@METHOD]{method="schema_lock" type="command"}
# [@METHOD]{method="corruption_detection" type="command"}
# [@METHOD]{method="final_validate" type="command"}
# [@METHOD]{method="final_render_validate" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<pass>][@notes<OutputIntegrity: validates blocks checks completeness verifies schemas runs final aggregated validation. Full VBStyle headers. Run() dispatch with Tuple3. self.state dict _p helper read_state set_config. No print no decorators no self._ violations.>][@todos<none>]}
"""
OutputIntegrity -- authority for output block validation and schema integrity.
Implements Section 74 of DEVIN_SPEC_DOMAIN_TWIN.md.
Commands: validate_block, check_completeness, check_schema, final_validate.
"""
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone

DEFAULT_DB_NAME = "dom_graph_work.db"
DEFAULT_LIMIT = 50
BLOCK_START = "```"
BLOCK_END = "```"


class OutputIntegrity:
    """Authority for output block validation, completeness and schema integrity."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "db_path": os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), DEFAULT_DB_NAME
                ),
                "default_limit": DEFAULT_LIMIT,
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
        if command == "validate_block":
            return self.ValidateBlock(params)
        elif command == "check_completeness":
            return self.CheckCompleteness(params)
        elif command == "check_schema":
            return self.CheckSchema(params)
        elif command == "block_boundary_enforcement":
            return self.BlockBoundaryEnforcement(params)
        elif command == "encoding_consistency":
            return self.EncodingConsistency(params)
        elif command == "structural_completeness":
            return self.StructuralCompleteness(params)
        elif command == "missing_section_detection":
            return self.MissingSectionDetection(params)
        elif command == "schema_lock":
            return self.SchemaLock(params)
        elif command == "corruption_detection":
            return self.CorruptionDetection(params)
        elif command == "final_validate":
            return self.FinalValidate(params)
        elif command == "final_render_validate":
            return self.FinalRenderValidate(params)
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

    def ValidateBlock(self, params):
        block = self._p(params, "block")
        expected_fields = self._p(params, "expected_fields")
        if block is None:
            return (0, None, ("MISSING_PARAM", "block required", 0))
        if not isinstance(block, dict):
            return (0, None, ("INVALID_BLOCK", "block must be a dict", 0))
        if expected_fields is None:
            return (0, None, ("MISSING_PARAM", "expected_fields required", 0))
        if not isinstance(expected_fields, (list, dict)):
            return (0, None, ("INVALID_FIELDS",
                              "expected_fields must be list or dict", 0))
        if isinstance(expected_fields, dict):
            required = list(expected_fields.keys())
        else:
            required = list(expected_fields)
        block_keys = list(block.keys())
        missing = [f for f in required if f not in block_keys]
        extra = [k for k in block_keys if k not in required]
        valid = (len(missing) == 0 and len(extra) == 0)
        result = {"valid": valid, "missing": missing, "extra": extra}
        return (1, result, None)

    def CheckCompleteness(self, params):
        sections = self._p(params, "sections")
        expected_sections = self._p(params, "expected_sections")
        if sections is None:
            return (0, None, ("MISSING_PARAM", "sections required", 0))
        if not isinstance(sections, (list, dict)):
            return (0, None, ("INVALID_SECTIONS",
                              "sections must be list or dict", 0))
        if expected_sections is None:
            return (0, None, ("MISSING_PARAM", "expected_sections required", 0))
        if not isinstance(expected_sections, (list, dict)):
            return (0, None, ("INVALID_EXPECTED",
                              "expected_sections must be list or dict", 0))
        if isinstance(sections, dict):
            present = list(sections.keys())
        else:
            present = list(sections)
        if isinstance(expected_sections, dict):
            expected = list(expected_sections.keys())
        else:
            expected = list(expected_sections)
        missing_sections = [s for s in expected if s not in present]
        complete = (len(missing_sections) == 0)
        result = {"complete": complete, "missing_sections": missing_sections}
        return (1, result, None)

    def CheckSchema(self, params):
        data = self._p(params, "data")
        schema = self._p(params, "schema")
        if data is None:
            return (0, None, ("MISSING_PARAM", "data required", 0))
        if not isinstance(data, dict):
            return (0, None, ("INVALID_DATA", "data must be a dict", 0))
        if schema is None:
            return (0, None, ("MISSING_PARAM", "schema required", 0))
        if not isinstance(schema, dict):
            return (0, None, ("INVALID_SCHEMA", "schema must be a dict", 0))
        type_mismatches = []
        for key, expected_type in schema.items():
            if key not in data:
                type_mismatches.append({
                    "field": key,
                    "issue": "missing",
                    "expected": str(expected_type),
                })
                continue
            actual_value = data[key]
            actual_type = type(actual_value).__name__
            if isinstance(expected_type, type):
                expected_name = expected_type.__name__
            else:
                expected_name = str(expected_type)
            if isinstance(expected_type, type):
                if not isinstance(actual_value, expected_type):
                    type_mismatches.append({
                        "field": key,
                        "issue": "type_mismatch",
                        "expected": expected_name,
                        "actual": actual_type,
                    })
            else:
                if actual_type != expected_name:
                    type_mismatches.append({
                        "field": key,
                        "issue": "type_mismatch",
                        "expected": expected_name,
                        "actual": actual_type,
                    })
        valid = (len(type_mismatches) == 0)
        result = {"valid": valid, "type_mismatches": type_mismatches}
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
        if first_start >= 0 and last_end >= 0 and first_start > last_end:
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
        data = self._p(params, "data")
        required_fields = self._p(params, "required_fields")
        if data is None:
            return (0, None, ("MISSING_PARAM", "data required", 0))
        if not isinstance(data, dict):
            return (0, None, ("INVALID_DATA", "data must be a dict", 0))
        if required_fields is None:
            return (0, None, ("MISSING_PARAM", "required_fields required", 0))
        if not isinstance(required_fields, (list, dict)):
            return (0, None, ("INVALID_FIELDS",
                              "required_fields must be list or dict", 0))
        if isinstance(required_fields, dict):
            required = list(required_fields.keys())
        else:
            required = list(required_fields)
        missing = [f for f in required if f not in data]
        null_fields = [f for f in required if f in data and data[f] is None]
        valid = (len(missing) == 0 and len(null_fields) == 0)
        return (1, {"valid": valid, "missing": missing,
                    "null_fields": null_fields,
                    "total_required": len(required)}, None)

    def MissingSectionDetection(self, params):
        sections = self._p(params, "sections")
        expected_count = self._p(params, "expected_count")
        if sections is None:
            return (0, None, ("MISSING_PARAM", "sections required", 0))
        if not isinstance(sections, (list, dict)):
            return (0, None, ("INVALID_SECTIONS",
                              "sections must be list or dict", 0))
        if isinstance(sections, dict):
            present_indices = sorted(sections.keys())
        else:
            present_indices = list(sections)
        if expected_count is None:
            return (0, None, ("MISSING_PARAM", "expected_count required", 0))
        if not isinstance(expected_count, int) or expected_count < 0:
            return (0, None, ("INVALID_COUNT",
                              "expected_count must be non-negative int", 0))
        expected_indices = list(range(expected_count))
        missing = [i for i in expected_indices if str(i) not in [str(x) for x in present_indices]]
        gaps = []
        for i in range(1, len(expected_indices)):
            if i not in [int(x) for x in present_indices if str(x).isdigit()]:
                gaps.append(i)
        return (1, {"missing_sections": missing, "gaps": gaps,
                    "expected_count": expected_count,
                    "present_count": len(present_indices)}, None)

    def SchemaLock(self, params):
        schema = self._p(params, "schema")
        if schema is None:
            return (0, None, ("MISSING_PARAM", "schema required", 0))
        if not isinstance(schema, dict):
            return (0, None, ("INVALID_SCHEMA", "schema must be a dict", 0))
        schema_hash = hashlib.sha256(json.dumps(schema, sort_keys=True).encode("utf-8")).hexdigest()
        if "locked_schema_hash" in self.state:
            if self.state["locked_schema_hash"] != schema_hash:
                return (0, None, ("SCHEMA_CHANGED",
                                  "schema differs from locked version", 0))
            return (1, {"locked": True, "schema_hash": schema_hash,
                        "matches": True}, None)
        self.state["locked_schema_hash"] = schema_hash
        self.state["locked_schema"] = schema
        return (1, {"locked": True, "schema_hash": schema_hash,
                    "matches": True}, None)

    def CorruptionDetection(self, params):
        data = self._p(params, "data")
        expected_hash = self._p(params, "expected_hash")
        if data is None:
            return (0, None, ("MISSING_PARAM", "data required", 0))
        if expected_hash is None:
            return (0, None, ("MISSING_PARAM", "expected_hash required", 0))
        if isinstance(data, str):
            encoded = data.encode("utf-8")
        elif isinstance(data, bytes):
            encoded = data
        else:
            try:
                encoded = json.dumps(data, sort_keys=True).encode("utf-8")
            except (TypeError, ValueError):
                return (0, None, ("NOT_SERIALIZABLE",
                                  "data cannot be serialized for hashing", 0))
        actual_hash = hashlib.sha256(encoded).hexdigest()
        is_corrupt = (actual_hash != expected_hash)
        return (1, {"is_corrupt": is_corrupt, "actual_hash": actual_hash,
                    "expected_hash": expected_hash,
                    "matches": not is_corrupt}, None)

    def FinalValidate(self, params):
        block_result = self.ValidateBlock(params)
        if block_result[0] != 1:
            return (0, None, ("BLOCK_VALIDATION_FAILED",
                              "validate_block failed", 0))
        block_data = block_result[1]
        if not block_data.get("valid", False):
            return (0, None, ("BLOCK_INVALID",
                              "block has missing or extra fields", 0))
        completeness_result = self.CheckCompleteness(params)
        if completeness_result[0] != 1:
            return (0, None, ("COMPLETENESS_CHECK_FAILED",
                              "check_completeness failed", 0))
        completeness_data = completeness_result[1]
        if not completeness_data.get("complete", False):
            return (0, None, ("INCOMPLETE_SECTIONS",
                              "missing sections detected", 0))
        schema_result = self.CheckSchema(params)
        if schema_result[0] != 1:
            return (0, None, ("SCHEMA_CHECK_FAILED",
                              "check_schema failed", 0))
        schema_data = schema_result[1]
        if not schema_data.get("valid", False):
            return (0, None, ("SCHEMA_INVALID",
                              "schema type mismatches detected", 0))
        aggregated = {
            "valid": True,
            "block": block_data,
            "completeness": completeness_data,
            "schema": schema_data,
        }
        self.state["results"] = aggregated
        return (1, aggregated, None)

    def FinalRenderValidate(self, params):
        checks = {}
        overall_valid = True
        block_res = self.BlockBoundaryEnforcement(params)
        if block_res[0] == 1:
            checks["block_boundary"] = block_res[1]
            if not block_res[1].get("valid", False):
                overall_valid = False
        else:
            checks["block_boundary"] = {"error": block_res[2]}
            overall_valid = False
        enc_res = self.EncodingConsistency(params)
        if enc_res[0] == 1:
            checks["encoding"] = enc_res[1]
            if not enc_res[1].get("valid", False):
                overall_valid = False
        else:
            checks["encoding"] = {"error": enc_res[2]}
            overall_valid = False
        struct_res = self.StructuralCompleteness(params)
        if struct_res[0] == 1:
            checks["structural"] = struct_res[1]
            if not struct_res[1].get("valid", False):
                overall_valid = False
        else:
            checks["structural"] = {"error": struct_res[2]}
            overall_valid = False
        missing_res = self.MissingSectionDetection(params)
        if missing_res[0] == 1:
            checks["missing_sections"] = missing_res[1]
            if len(missing_res[1].get("missing_sections", [])) > 0:
                overall_valid = False
        else:
            checks["missing_sections"] = {"error": missing_res[2]}
            overall_valid = False
        result = {
            "valid": overall_valid,
            "checks": checks,
            "render_ready": overall_valid,
        }
        self.state["results"] = result
        return (1, result, None)
