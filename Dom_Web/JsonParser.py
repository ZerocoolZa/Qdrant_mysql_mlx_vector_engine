#!/usr/bin/env python3
"""
#[@GHOST]{[@file<JsonParser.py>][@state<active>][@date<2026-07-03>][@ver<2.0>][@auth<Cascade>]}
#[@VBSTYLE]{[@auth<system>][@role<web_component>][@return<Tuple3>][@orch<WebScraping>][@mem<none>][@db<none>]}
#[@FILEID]{[@path<JsonParser.py>][@hash<placeholder>]}
#[@SUMMARY]{JSON parser with dot-notation value extraction}
#[@CLASS]{JsonParser}
#[@METHOD]{__init__, parse, extract_value, Run}
"""

import json
from typing import Optional, Tuple, Dict, Any


class JsonParser:
    """
    JSON parser for extracting structured data from JSON content.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            'parsed': None,
            'keys': [],
            'structure': {}
        }

    def parse(self, json_content: str) -> Tuple[int, Dict[str, Any], Optional[Tuple]]:
        try:
            parsed = json.loads(json_content)
            self.state['parsed'] = parsed
            self.state['keys'] = list(parsed.keys()) if isinstance(parsed, dict) else []
            return (1, parsed, None)
        except json.JSONDecodeError as e:
            return (0, None, (33, f"JSON decode error: {str(e)}", 0))
        except Exception as e:
            return (0, None, (34, f"Exception: {str(e)}", 0))

    def extract_value(self, json_content: str, key_path: str) -> Tuple[int, Any, Optional[Tuple]]:
        success, parsed, error = self.parse(json_content)
        if not success:
            return (0, None, error)
        try:
            keys = key_path.split('.')
            value = parsed
            for key in keys:
                if isinstance(value, dict):
                    value = value.get(key)
                elif isinstance(value, list) and key.isdigit():
                    value = value[int(key)]
                else:
                    return (0, None, (35, f"Key path not found: {key_path}", 0))
            return (1, value, None)
        except Exception as e:
            return (0, None, (36, f"Extract error: {str(e)}", 0))

    def Run(self, command: str, params: Optional[dict] = None) -> Tuple[int, str, Optional[Tuple]]:
        if params is None:
            params = {}
        if command == "parse":
            json_content = params.get('json')
            if not json_content:
                return (0, None, (37, "Missing required param: json", 0))
            return self.parse(json_content)
        elif command == "extract_value":
            json_content = params.get('json')
            key_path = params.get('key_path')
            if not json_content or not key_path:
                return (0, None, (38, "Missing required params: json, key_path", 0))
            return self.extract_value(json_content, key_path)
        else:
            return (0, None, (39, f"Unknown command: {command}", 0))
