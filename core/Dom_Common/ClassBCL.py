#!/usr/bin/env python3
#[@GHOST]{file_path="core/Dom_Common/ClassBCL.py" date="2026-07-04" author="devin" session_id="bcl-common-module" context="BCL (Bracket Command Language) parser and writer. Parses [@TAG]{value} packets, supports nesting, extraction, validation, and packet building."}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
#[@FILEID]{id="ClassBCL.py" domain="dom_common" authority="ClassBCL"}
#[@SUMMARY]{summary="ClassBCL — BCL (Bracket Command Language) parser/writer. Parses [@TAG]{value} packets with nesting support, extracts values, validates bracket matching, builds OK/ERR packets."}
#[@CLASS]{class="ClassBCL" domain="dom_common" authority="parser"}
#[@METHOD]{method="parse" type="parser"}
#[@METHOD]{method="write" type="writer"}
#[@METHOD]{method="extract" type="extractor"}
#[@METHOD]{method="extract_all" type="extractor"}
#[@METHOD]{method="validate" type="validator"}
#[@METHOD]{method="packet" type="builder"}
#[@METHOD]{method="read_state" type="state"}
#[@METHOD]{method="set_config" type="config"}
#[@METHOD]{method="Run" type="dispatch"}
#[@METHOD]{method="_p" type="helper"}

"""ClassBCL — BCL (Bracket Command Language) parser and writer.

BCL format uses bracket tags like [@KEY]{value}. Values can contain
nested BCL packets. This class parses BCL text into a list of
{tag, value} dicts, writes dicts back to BCL strings, extracts
values by key, validates bracket matching, and builds OK/ERR
packets.
"""

try:
    import Config
except ImportError:
    from . import Config

# ── Error Codes ──
ERR_PARSE = "BCL_PARSE_ERROR"
ERR_WRITE = "BCL_WRITE_ERROR"
ERR_EXTRACT = "BCL_EXTRACT_ERROR"
ERR_VALIDATE = "BCL_VALIDATE_ERROR"
ERR_PACKET = "BCL_PACKET_ERROR"
ERR_UNKNOWN_CMD = "BCL_UNKNOWN_COMMAND"
ERR_BAD_PARAMS = "BCL_BAD_PARAMS"

# ── BCL Markers ──
TAG_OPEN = "[@"
TAG_CLOSE = "]"
BRACE_OPEN = "{"
BRACE_CLOSE = "}"


class ClassBCL:
    """BCL parser/writer. Parses [@TAG]{value} packets with nesting."""

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param
        self.config = Config
        self.state = {
            "class": "ClassBCL",
            "parsed_count": 0,
            "written_count": 0,
            "last_error": None,
            "config": {},
        }

    def _p(self, label, value):
        """Helper to log state transitions. No-op safe."""
        self.state["last_" + label] = value

    def Run(self, command, params=None):
        """Dispatch a command. Returns Tuple3."""
        dispatch = {
            "parse": self.cmd_parse,
            "write": self.cmd_write,
            "extract": self.cmd_extract,
            "extract_all": self.cmd_extract_all,
            "validate": self.cmd_validate,
            "packet": self.cmd_packet,
            "read_state": self.cmd_read_state,
            "set_config": self.cmd_set_config,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, (ERR_UNKNOWN_CMD, "Unknown command: " + str(command), 0))
        return handler(params)

    def cmd_parse(self, params):
        """Parse BCL text into list of {tag, value} dicts."""
        if params is None or not isinstance(params, dict):
            return (0, None, (ERR_BAD_PARAMS, "params must be a dict with 'text'", 0))
        text = params.get("text")
        if text is None:
            return (0, None, (ERR_BAD_PARAMS, "missing 'text' key", 0))
        if not isinstance(text, str):
            return (0, None, (ERR_BAD_PARAMS, "text must be a string", 0))
        packets = self._parse_packets(text)
        self.state["parsed_count"] = self.state.get("parsed_count", 0) + len(packets)
        self._p("parse", len(packets))
        result = {"packets": packets, "raw": text}
        return (1, result, None)

    def cmd_write(self, params):
        """Write list of {tag, value} dicts to BCL string."""
        if params is None or not isinstance(params, dict):
            return (0, None, (ERR_BAD_PARAMS, "params must be a dict with 'packets'", 0))
        packets = params.get("packets")
        if packets is None:
            return (0, None, (ERR_BAD_PARAMS, "missing 'packets' key", 0))
        if not isinstance(packets, list):
            return (0, None, (ERR_BAD_PARAMS, "packets must be a list", 0))
        bcl_str = self._write_packets(packets)
        self.state["written_count"] = self.state.get("written_count", 0) + len(packets)
        self._p("write", len(packets))
        return (1, bcl_str, None)

    def cmd_extract(self, params):
        """Extract first value for a key from BCL text."""
        if params is None or not isinstance(params, dict):
            return (0, None, (ERR_BAD_PARAMS, "params must be a dict", 0))
        text = params.get("text")
        key = params.get("key")
        if text is None or key is None:
            return (0, None, (ERR_BAD_PARAMS, "missing 'text' or 'key'", 0))
        if not isinstance(text, str) or not isinstance(key, str):
            return (0, None, (ERR_BAD_PARAMS, "text and key must be strings", 0))
        packets = self._parse_packets(text)
        result = self._find_first(packets, key)
        self._p("extract", key if result is not None else None)
        return (1, result, None)

    def cmd_extract_all(self, params):
        """Extract all values for a key from BCL text."""
        if params is None or not isinstance(params, dict):
            return (0, None, (ERR_BAD_PARAMS, "params must be a dict", 0))
        text = params.get("text")
        key = params.get("key")
        if text is None or key is None:
            return (0, None, (ERR_BAD_PARAMS, "missing 'text' or 'key'", 0))
        if not isinstance(text, str) or not isinstance(key, str):
            return (0, None, (ERR_BAD_PARAMS, "text and key must be strings", 0))
        packets = self._parse_packets(text)
        values = self._find_all(packets, key)
        self._p("extract_all", len(values))
        return (1, values, None)

    def cmd_validate(self, params):
        """Validate BCL text — check bracket matching."""
        if params is None or not isinstance(params, dict):
            return (0, None, (ERR_BAD_PARAMS, "params must be a dict with 'text'", 0))
        text = params.get("text")
        if text is None:
            return (0, None, (ERR_BAD_PARAMS, "missing 'text' key", 0))
        if not isinstance(text, str):
            return (0, None, (ERR_BAD_PARAMS, "text must be a string", 0))
        errors = self._validate_text(text)
        valid = len(errors) == 0
        self._p("validate", valid)
        result = {"valid": valid, "errors": errors}
        return (1, result, None)

    def cmd_packet(self, params):
        """Build a BCL packet: [@OK]{body} or [@ERR]{body}."""
        if params is None or not isinstance(params, dict):
            return (0, None, (ERR_BAD_PARAMS, "params must be a dict", 0))
        ok_or_err = params.get("ok_or_err")
        body = params.get("body")
        if ok_or_err is None:
            return (0, None, (ERR_BAD_PARAMS, "missing 'ok_or_err' key", 0))
        if not isinstance(ok_or_err, str):
            return (0, None, (ERR_BAD_PARAMS, "ok_or_err must be a string", 0))
        tag = ok_or_err.upper()
        if tag not in ("OK", "ERR"):
            return (0, None, (ERR_PACKET, "ok_or_err must be 'OK' or 'ERR'", 0))
        if body is None:
            body = ""
        if not isinstance(body, str):
            body = str(body)
        bcl_str = TAG_OPEN + tag + TAG_CLOSE + BRACE_OPEN + body + BRACE_CLOSE
        self._p("packet", tag)
        return (1, bcl_str, None)

    def cmd_read_state(self, params):
        """Return current state dict."""
        return (1, self.state, None)

    def cmd_set_config(self, params):
        """Set config from params dict."""
        if params is None:
            self.state["config"] = {}
            return (1, None, None)
        if not isinstance(params, dict):
            return (0, None, (ERR_BAD_PARAMS, "params must be a dict", 0))
        self.state["config"] = params
        self._p("config", list(params.keys()))
        return (1, None, None)

    # ── Internal parser (state machine) ──

    def _parse_packets(self, text):
        """Parse BCL text into list of {tag, value} dicts."""
        packets = []
        i = 0
        length = len(text)
        while i < length:
            # Scan for [@ to start a tag
            tag_start = text.find(TAG_OPEN, i)
            if tag_start == -1:
                break
            # Read tag name until ] or whitespace
            j = tag_start + len(TAG_OPEN)
            tag_name = ""
            while j < length and text[j] != TAG_CLOSE and text[j] not in (" ", "\t", "\n", "\r"):
                tag_name = tag_name + text[j]
                j = j + 1
            if tag_name == "":
                # No valid tag name, advance past this [@
                i = tag_start + len(TAG_OPEN)
                continue
            # Skip optional whitespace between tag and value
            while j < length and text[j] in (" ", "\t", "\n", "\r"):
                j = j + 1
            # If ] follows whitespace, skip it
            if j < length and text[j] == TAG_CLOSE:
                j = j + 1
                # Skip optional whitespace after ]
                while j < length and text[j] in (" ", "\t", "\n", "\r"):
                    j = j + 1
            value = ""
            # If { follows, read value until matching } (track nesting)
            if j < length and text[j] == BRACE_OPEN:
                j = j + 1
                value_start = j
                depth = 1
                while j < length and depth > 0:
                    if text[j] == BRACE_OPEN:
                        depth = depth + 1
                    elif text[j] == BRACE_CLOSE:
                        depth = depth - 1
                        if depth == 0:
                            break
                    j = j + 1
                if depth == 0:
                    value = text[value_start:j]
                    j = j + 1  # skip closing }
                else:
                    # Unmatched brace — take rest of string
                    value = text[value_start:]
                    j = length
            else:
                # No { follows, value is empty string
                value = ""
            packets.append({"tag": tag_name, "value": value})
            i = j
        return packets

    def _find_first(self, packets, key):
        """Recursively find first value for a key in parsed packets."""
        for pkt in packets:
            if pkt.get("tag") == key:
                return pkt.get("value", "")
            value = pkt.get("value", "")
            if isinstance(value, str) and TAG_OPEN in value:
                nested = self._parse_packets(value)
                found = self._find_first(nested, key)
                if found is not None:
                    return found
        return None

    def _find_all(self, packets, key):
        """Recursively find all values for a key in parsed packets."""
        values = []
        for pkt in packets:
            if pkt.get("tag") == key:
                values.append(pkt.get("value", ""))
            value = pkt.get("value", "")
            if isinstance(value, str) and TAG_OPEN in value:
                nested = self._parse_packets(value)
                values.extend(self._find_all(nested, key))
        return values

    def _write_packets(self, packets):
        """Write list of {tag, value} dicts to BCL string."""
        parts = []
        for pkt in packets:
            if not isinstance(pkt, dict):
                continue
            tag = pkt.get("tag", "")
            value = pkt.get("value", "")
            if not isinstance(tag, str):
                tag = str(tag)
            if not isinstance(value, str):
                value = str(value)
            parts.append(TAG_OPEN + tag + TAG_CLOSE + BRACE_OPEN + value + BRACE_CLOSE)
        return "".join(parts)

    def _validate_text(self, text):
        """Validate BCL text — check bracket matching."""
        errors = []
        length = len(text)
        i = 0
        brace_depth = 0
        bracket_depth = 0
        while i < length:
            ch = text[i]
            if ch == "[":
                bracket_depth = bracket_depth + 1
            elif ch == "]":
                bracket_depth = bracket_depth - 1
                if bracket_depth < 0:
                    errors.append("Unmatched ] at position " + str(i))
                    bracket_depth = 0
            elif ch == BRACE_OPEN:
                brace_depth = brace_depth + 1
            elif ch == BRACE_CLOSE:
                brace_depth = brace_depth - 1
                if brace_depth < 0:
                    errors.append("Unmatched } at position " + str(i))
                    brace_depth = 0
            i = i + 1
        if bracket_depth > 0:
            errors.append("Unmatched [ — " + str(bracket_depth) + " unclosed brackets")
        if brace_depth > 0:
            errors.append("Unmatched { — " + str(brace_depth) + " unclosed braces")
        return errors
