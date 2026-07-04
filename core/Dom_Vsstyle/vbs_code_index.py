#!/usr/bin/env python3

#[@GHOST]{[@file<vbs_code_index.py>][@domain<Vbs_Code_Verifiation>][@role<storage>][@auth<cascade>][@date<2026-06-26>][@ver<2.0>]}
#[@VBSTYLE]{[@auth<cascade>][@role<storage>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded_paths>]}

"""
CodeIndex: VBStyle code index authority.
Read, write, edit, update code_index entries in MySQL.
Full CRUD on facts, classes, methods, authorities, co-occurrences, identifiers.
"""

import json
import math
from collections import defaultdict, Counter

from . import Config_Vbs_Code_Verifiation as Config

try:
    import mysql.connector as _mysql
    _MYSQL_AVAILABLE = True
except ImportError:
    _MYSQL_AVAILABLE = False


class CodeIndex:
    """VBStyle code index authority — read, write, edit, update MySQL code_index."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param if isinstance(param, dict) else {}
        self.state = {
            "config": self.param.get("config", {}),
            "catalog": [],
            "results": [],
            "conn": None,
            "cur": None,
            "entity_cache": {},
            "co_occurrence": defaultdict(int),
            "identifier_freq": Counter(),
            "identifier_files": defaultdict(set),
        }

    #[@open]{[@params<<params>][@return<Tuple3>][@purpose<open MySQL connection>]}
    def open(self, params=None):
        try:
            if not _MYSQL_AVAILABLE:
                return (0, None, ("MYSQL_NOT_AVAILABLE", "mysql.connector not installed", 0))
            self.state["conn"] = _mysql.connect(**Config.MYSQL_CONFIG)
            self.state["cur"] = self.state["conn"].cursor()
            return (1, {"connected": True}, None)
        except Exception as e:
            return (0, None, ("CONNECT_ERROR", str(e), 0))

    #[@close]{[@params<<params>][@return<Tuple3>][@purpose<close MySQL connection and flush batches>]}
    def close(self, params=None):
        try:
            if self.state["conn"]:
                self.flush_co_occurrence({})
                self.flush_identifier_frequency({})
                self.state["conn"].commit()
                self.state["conn"].close()
            return (1, {
                "entities": len(self.state["entity_cache"]),
                "co_occurrences": len(self.state["co_occurrence"]),
                "identifiers": len(self.state["identifier_freq"]),
            }, None)
        except Exception as e:
            return (0, None, ("CLOSE_ERROR", str(e), 0))

    #[@write_fact]{[@params<<params>][@return<Tuple3>][@purpose<write a canonical fact record into code_index>]}
    def write_fact(self, params):
        try:
            cur = self.state["cur"]
            if not cur:
                return (0, None, ("NO_CURSOR", "Database not open", 0))

            source_table = params.get("source_table", "")
            entity_name = params.get("entity_name", "")
            entity_type = params.get("entity_type", "")
            relationship = params.get("relationship")
            related_entity = params.get("related_entity")
            relationship_type = params.get("relationship_type")
            evidence = params.get("evidence")
            source_row_id = params.get("source_row_id")
            source_file = params.get("source_file")
            source_line = params.get("source_line")
            authority_score = params.get("authority_score", 1.0)
            survival_score = params.get("survival_score", 0.5)
            status = params.get("status", "live")

            cur.execute("""
                INSERT INTO code_index
                    (source_db, source_table, source_row_id, source_file, source_line,
                     entity_name, entity_type, relationship, related_entity,
                     relationship_type, evidence, authority_score, survival_score,
                     status, first_seen, last_seen)
                VALUES ('vb_shared', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """, (source_table, source_row_id, source_file, source_line,
                  entity_name, entity_type, relationship, related_entity,
                  relationship_type, evidence, authority_score, survival_score, status))
            fact_id = cur.lastrowid
            self.state["entity_cache"][entity_name] = fact_id

            self.state["identifier_freq"][entity_name] += 1
            if source_file:
                self.state["identifier_files"][entity_name].add(source_file)

            return (1, {"fact_id": fact_id}, None)
        except Exception as e:
            return (0, None, ("WRITE_FACT_ERROR", str(e), 0))

    #[@read_fact]{[@params<<params>][@return<Tuple3>][@purpose<read a fact from code_index by entity name>]}
    def read_fact(self, params):
        try:
            cur = self.state["cur"]
            if not cur:
                return (0, None, ("NO_CURSOR", "Database not open", 0))
            entity_name = params.get("entity_name", "")
            cur.execute("""
                SELECT fact_id, entity_name, entity_type, relationship, related_entity,
                       evidence, authority_score, survival_score, status
                FROM code_index WHERE entity_name = %s ORDER BY last_seen DESC LIMIT 1
            """, (entity_name,))
            row = cur.fetchone()
            if row:
                return (1, {
                    "fact_id": row[0], "entity_name": row[1], "entity_type": row[2],
                    "relationship": row[3], "related_entity": row[4],
                    "evidence": row[5], "authority_score": row[6],
                    "survival_score": row[7], "status": row[8],
                }, None)
            return (0, None, ("NOT_FOUND", entity_name, 0))
        except Exception as e:
            return (0, None, ("READ_FACT_ERROR", str(e), 0))

    #[@update_fact]{[@params<<params>][@return<Tuple3>][@purpose<update an existing fact in code_index>]}
    def update_fact(self, params):
        try:
            cur = self.state["cur"]
            if not cur:
                return (0, None, ("NO_CURSOR", "Database not open", 0))
            fact_id = params.get("fact_id")
            updates = params.get("updates", {})
            if not fact_id or not updates:
                return (0, None, ("MISSING_PARAMS", "fact_id and updates required", 0))

            set_clauses = []
            values = []
            for k, v in updates.items():
                if k in ("authority_score", "survival_score", "status", "evidence", "relationship"):
                    set_clauses.append("{} = %s".format(k))
                    values.append(v)
            if not set_clauses:
                return (0, None, ("NO_VALID_FIELDS", "No updatable fields", 0))

            set_clauses.append("last_seen = NOW()")
            values.append(fact_id)
            cur.execute("""
                UPDATE code_index SET {} WHERE fact_id = %s
            """.format(", ".join(set_clauses)), tuple(values))
            self.state["conn"].commit()
            return (1, {"updated": fact_id}, None)
        except Exception as e:
            return (0, None, ("UPDATE_FACT_ERROR", str(e), 0))

    #[@edit_fact]{[@params<<params>][@return<Tuple3>][@purpose<edit fields on an existing fact alias for update>]}
    def edit_fact(self, params):
        return self.update_fact(params)

    #[@write_co_occurrence]{[@params<<params>][@return<Tuple3>][@purpose<record two entities appeared together>]}
    def write_co_occurrence(self, params):
        try:
            entity_a = params.get("entity_a", "")
            entity_b = params.get("entity_b", "")
            rel_type = params.get("rel_type", "co_occurs")
            if entity_a > entity_b:
                entity_a, entity_b = entity_b, entity_a
            key = (entity_a, entity_b, rel_type)
            self.state["co_occurrence"][key] += 1
            return (1, {"recorded": True}, None)
        except Exception as e:
            return (0, None, ("CO_OCCURRENCE_ERROR", str(e), 0))

    #[@flush_co_occurrence]{[@params<<params>][@return<Tuple3>][@purpose<batch insert co-occurrence records>]}
    def flush_co_occurrence(self, params):
        try:
            cur = self.state["cur"]
            conn = self.state["conn"]
            if not cur:
                return (1, {"skipped": True}, None)
            for (a, b, rel), count in self.state["co_occurrence"].items():
                cur.execute("""
                    INSERT INTO code_co_occurrence
                        (entity_a, entity_b, co_occurrence_count, relationship_type, weight, source_db, source_table)
                    VALUES (%s, %s, %s, %s, %s, 'vb_shared', 'vbstyle_dom_scanner')
                    ON DUPLICATE KEY UPDATE
                        co_occurrence_count = co_occurrence_count + VALUES(co_occurrence_count),
                        weight = weight + VALUES(weight),
                        last_seen = NOW()
                """, (a, b, count, rel, float(count)))
            conn.commit()
            return (1, {"flushed": len(self.state["co_occurrence"])}, None)
        except Exception as e:
            return (0, None, ("FLUSH_CO_ERROR", str(e), 0))

    #[@flush_identifier_frequency]{[@params<<params>][@return<Tuple3>][@purpose<batch insert identifier frequency records>]}
    def flush_identifier_frequency(self, params):
        try:
            cur = self.state["cur"]
            conn = self.state["conn"]
            if not cur:
                return (1, {"skipped": True}, None)
            for identifier, freq in self.state["identifier_freq"].items():
                file_count = len(self.state["identifier_files"].get(identifier, set()))
                auth = min(10.0, max(1.0, math.log(freq + 1) + 1.0))
                cur.execute("""
                    INSERT INTO code_identifier_frequency
                        (identifier, identifier_type, frequency, file_count, authority_score, last_seen)
                    VALUES (%s, 'class', %s, %s, %s, NOW())
                    ON DUPLICATE KEY UPDATE
                        frequency = frequency + VALUES(frequency),
                        file_count = file_count + VALUES(file_count),
                        authority_score = GREATEST(authority_score, VALUES(authority_score)),
                        last_seen = NOW()
                """, (identifier, freq, file_count, auth))
            conn.commit()
            return (1, {"flushed": len(self.state["identifier_freq"])}, None)
        except Exception as e:
            return (0, None, ("FLUSH_FREQ_ERROR", str(e), 0))

    #[@write_class]{[@params<<params>][@return<Tuple3>][@purpose<write a class entity into code_index>]}
    def write_class(self, params):
        try:
            class_name = params.get("class_name", "")
            access_path = params.get("access_path", "")
            source_file = params.get("source_file", "")
            line_num = params.get("line_num", 0)
            bcl_header = params.get("bcl_header", False)
            vbstyle_compliant = params.get("vbstyle_compliant", False)

            evidence = json.dumps({
                "access_path": access_path,
                "bcl_header": bool(bcl_header),
                "vbstyle_compliant": vbstyle_compliant,
            })
            auth = 5.0 if vbstyle_compliant else 1.0
            survival = 0.8 if vbstyle_compliant else 0.3

            return self.write_fact({
                "source_table": "vbstyle_dom_scanner",
                "entity_name": class_name,
                "entity_type": "class",
                "relationship": "defined_in",
                "related_entity": source_file,
                "relationship_type": "defined_in",
                "evidence": evidence,
                "source_file": source_file,
                "source_line": line_num,
                "authority_score": auth,
                "survival_score": survival,
                "status": "live",
            })
        except Exception as e:
            return (0, None, ("WRITE_CLASS_ERROR", str(e), 0))

    #[@write_method]{[@params<<params>][@return<Tuple3>][@purpose<write a method entity into code_index>]}
    def write_method(self, params):
        try:
            method_name = params.get("method_name", "")
            class_name = params.get("class_name", "")
            method_params = params.get("params", "")
            purpose = params.get("purpose", "")
            source_file = params.get("source_file", "")
            line_num = params.get("line_num", 0)
            is_boilerplate = params.get("is_boilerplate", False)
            has_bcl = params.get("has_bcl", False)
            returns_tuple3 = params.get("returns_tuple3", False)

            evidence = json.dumps({
                "class": class_name,
                "params": method_params,
                "purpose": purpose,
                "is_boilerplate": is_boilerplate,
                "has_bcl": has_bcl,
                "returns_tuple3": returns_tuple3,
            })
            auth = 3.0 if has_bcl else 1.0
            survival = 0.7 if returns_tuple3 else 0.4

            result = self.write_fact({
                "source_table": "vbstyle_dom_scanner",
                "entity_name": "{}.{}".format(class_name, method_name),
                "entity_type": "method",
                "relationship": "contains",
                "related_entity": class_name,
                "relationship_type": "contains",
                "evidence": evidence,
                "source_file": source_file,
                "source_line": line_num,
                "authority_score": auth,
                "survival_score": survival,
                "status": "live",
            })
            if result[0]:
                self.write_co_occurrence({
                    "entity_a": class_name,
                    "entity_b": method_name,
                    "rel_type": "contains",
                })
            return result
        except Exception as e:
            return (0, None, ("WRITE_METHOD_ERROR", str(e), 0))

    #[@write_authority]{[@params<<params>][@return<Tuple3>][@purpose<write a sub-authority nested class into code_index>]}
    def write_authority(self, params):
        try:
            authority_name = params.get("authority_name", "")
            parent_class = params.get("parent_class", "")
            source_file = params.get("source_file", "")

            self.write_fact({
                "source_table": "vbstyle_dom_scanner",
                "entity_name": authority_name,
                "entity_type": "authority",
                "relationship": "nested_in",
                "related_entity": parent_class,
                "relationship_type": "defined_in",
                "evidence": json.dumps({"parent": parent_class}),
                "source_file": source_file,
                "authority_score": 4.0,
                "survival_score": 0.6,
                "status": "live",
            })
            self.write_co_occurrence({
                "entity_a": parent_class,
                "entity_b": authority_name,
                "rel_type": "contains",
            })
            return (1, {"written": authority_name}, None)
        except Exception as e:
            return (0, None, ("WRITE_AUTHORITY_ERROR", str(e), 0))

    #[@read_state]{[@params<<params>][@return<Tuple3>][@purpose<read CodeIndex state>]}
    def read_state(self, params=None):
        return (1, {k: v for k, v in self.state.items() if k not in ("conn", "cur")}, None)

    #[@set_config]{[@params<<params>][@return<Tuple3>][@purpose<set CodeIndex config>]}
    def set_config(self, params):
        try:
            if isinstance(params, dict):
                self.state["config"] = params
            return (1, {"updated": True}, None)
        except Exception as e:
            return (0, None, ("CONFIG_ERROR", str(e), 0))

    #[@Run]{[@params<<command, params>][@return<Tuple3>][@purpose<dispatch CodeIndex commands>]}
    def Run(self, command, params=None):
        if params is None:
            params = {}
        dispatch = {
            "open": self.open,
            "close": self.close,
            "write_fact": self.write_fact,
            "read_fact": self.read_fact,
            "update_fact": self.update_fact,
            "edit_fact": self.edit_fact,
            "write_co_occurrence": self.write_co_occurrence,
            "flush_co_occurrence": self.flush_co_occurrence,
            "flush_identifier_frequency": self.flush_identifier_frequency,
            "write_class": self.write_class,
            "write_method": self.write_method,
            "write_authority": self.write_authority,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if handler:
            return handler(params)
        return (0, None, ("UNKNOWN_COMMAND", command, 0))
