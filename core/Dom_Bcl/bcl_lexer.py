#!/usr/bin/env python3
# [@GHOST]{file_path="/Users/wws/Qdrant_mysql_mlx_vector_engine/BCL/bcl_lexer.py"
# date="2026-06-27" author="Cascade" session_id="bcl-vbstype-fix"
# context="Stage 1: BCL Lexer — character-level tokenizer, no regex"}
# [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
# [@FILEID]{id="bcl_lexer.py" domain="BCL" authority="BCLTokenizer"}
# [@SUMMARY]{summary="BCL Lexer: raw BCL text in, typed tokens out. Character-level, no regex, no interpretation."}
# [@CLASS]{class="BCLTokenizer" domain="BCL" authority="single"}
# [@METHOD]{method="Run" type="dispatch"}
# [@METHOD]{method="tokenize" type="command"}
# [@METHOD]{method="lex_container" type="command"}
# [@METHOD]{method="lex_string" type="command"}
# [@METHOD]{method="lex_number" type="command"}
# [@METHOD]{method="lex_bareword" type="command"}
# [@METHOD]{method="_p" type="helper"}
# [@METHOD]{method="read_state" type="command"}
# [@METHOD]{method="set_config" type="command"}
# [@METHOD]{method="__init__" type="ctor"}

from bcl_config import (
    ESCAPE_MAP, CONTAINER_OPEN, BRACE_OPEN, BRACE_CLOSE,
    PAREN_OPEN, PAREN_CLOSE, SEMICOLON, STRING, NUMBER, BAREWORD, EOF,
    TYPE_NAMES, WHITESPACE, DELIMITERS,
)


class BCLTokenizer:
    """Lexer: converts BCL text to list of Token dicts. Character-level, no regex."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "text": "",
            "pos": 0,
            "length": 0,
            "tokens": [],
            "errors": [],
            "memunit": mem,
            "db_manager": db,
        }
        if param:
            for key, value in param.items():
                self.state["config"][key] = value

    def Run(self, command, params=None):
        params = params or {}
        if command == "tokenize":
            return self.Tokenize(params)
        elif command == "lex_container":
            return self.LexContainer(params)
        elif command == "lex_string":
            return self.LexString(params)
        elif command == "lex_number":
            return self.LexNumber(params)
        elif command == "lex_bareword":
            return self.LexBareword(params)
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

    def Peek(self, offset=0):
        p = self.state["pos"] + offset
        if p < self.state["length"]:
            return (1, self.state["text"][p], None)
        return (1, "\0", None)

    def Advance(self):
        pos = self.state["pos"]
        if pos < self.state["length"]:
            ch = self.state["text"][pos]
            self.state["pos"] = pos + 1
            return (1, ch, None)
        return (1, "\0", None)

    def SkipWhitespace(self):
        text = self.state["text"]
        length = self.state["length"]
        while self.state["pos"] < length and text[self.state["pos"]] in WHITESPACE:
            self.state["pos"] += 1
        return (1, self.state["pos"], None)

    def MakeToken(self, token_type, value, pos):
        return (1, {"type": token_type, "type_name": TYPE_NAMES.get(token_type, "UNKNOWN"),
                    "value": value, "pos": pos}, None)

    def Tokenize(self, params):
        text = self._p(params, "text")
        if text is None:
            return (0, None, ("MISSING_PARAM", "text required", 0))
        self.state["text"] = text
        self.state["length"] = len(text)
        self.state["pos"] = 0
        self.state["tokens"] = []
        self.state["errors"] = []
        while self.state["pos"] < self.state["length"]:
            self.SkipWhitespace()
            if self.state["pos"] >= self.state["length"]:
                break
            ch = self.state["text"][self.state["pos"]]
            start = self.state["pos"]
            if ch == "[" and self.Peek(1)[1] == "@":
                result = self.LexContainer({"start": start})
                if result[0] == 0:
                    return result
                self.state["tokens"].append(result[1])
            elif ch == "]":
                err = ("STRAY_CLOSE_BRACKET", "Stray ']' outside container name at pos %d" % start, start)
                self.state["errors"].append(err)
                return (0, None, err)
            elif ch == "{":
                self.Advance()
                tok = self.MakeToken(BRACE_OPEN, "{", start)
                self.state["tokens"].append(tok[1])
            elif ch == "}":
                self.Advance()
                tok = self.MakeToken(BRACE_CLOSE, "}", start)
                self.state["tokens"].append(tok[1])
            elif ch == "(":
                self.Advance()
                tok = self.MakeToken(PAREN_OPEN, "(", start)
                self.state["tokens"].append(tok[1])
            elif ch == ")":
                self.Advance()
                tok = self.MakeToken(PAREN_CLOSE, ")", start)
                self.state["tokens"].append(tok[1])
            elif ch == ";":
                self.Advance()
                tok = self.MakeToken(SEMICOLON, ";", start)
                self.state["tokens"].append(tok[1])
            elif ch == '"':
                result = self.LexString({"start": start})
                if result[0] == 0:
                    return result
                self.state["tokens"].append(result[1])
            elif ch.isdigit() or (ch == "-" and self.Peek(1)[1].isdigit()):
                result = self.LexNumber({"start": start})
                if result[0] == 0:
                    return result
                self.state["tokens"].append(result[1])
            else:
                result = self.LexBareword({"start": start})
                if result[0] == 1 and result[1] is not None:
                    self.state["tokens"].append(result[1])
        eof_tok = self.MakeToken(EOF, None, self.state["pos"])
        self.state["tokens"].append(eof_tok[1])
        return (1, {"tokens": self.state["tokens"], "count": len(self.state["tokens"]),
                    "errors": self.state["errors"]}, None)

    def LexContainer(self, params):
        start = self._p(params, "start", self.state["pos"])
        self.state["pos"] += 2
        name_start = self.state["pos"]
        text = self.state["text"]
        while self.state["pos"] < self.state["length"] and text[self.state["pos"]] != "]":
            self.state["pos"] += 1
        if self.state["pos"] >= self.state["length"]:
            err = ("UNCLOSED_CONTAINER", "Unclosed container name missing ]", 0)
            self.state["errors"].append(err)
            return (0, None, err)
        name = text[name_start:self.state["pos"]]
        self.state["pos"] += 1
        return self.MakeToken(CONTAINER_OPEN, name, start)

    def LexString(self, params):
        start = self._p(params, "start", self.state["pos"])
        self.state["pos"] += 1
        chars = []
        text = self.state["text"]
        while self.state["pos"] < self.state["length"] and text[self.state["pos"]] != '"':
            if text[self.state["pos"]] == "\\" and self.state["pos"] + 1 < self.state["length"]:
                next_ch = text[self.state["pos"] + 1]
                chars.append(ESCAPE_MAP.get(next_ch, next_ch))
                self.state["pos"] += 2
            else:
                chars.append(text[self.state["pos"]])
                self.state["pos"] += 1
        if self.state["pos"] >= self.state["length"]:
            err = ("UNCLOSED_STRING", "Unclosed string missing quote", 0)
            self.state["errors"].append(err)
            return (0, None, err)
        self.state["pos"] += 1
        return self.MakeToken(STRING, "".join(chars), start)

    def LexNumber(self, params):
        start = self._p(params, "start", self.state["pos"])
        num_start = self.state["pos"]
        text = self.state["text"]
        if text[self.state["pos"]] == "-":
            self.state["pos"] += 1
        while self.state["pos"] < self.state["length"] and (text[self.state["pos"]].isdigit() or text[self.state["pos"]] == "."):
            self.state["pos"] += 1
        raw = text[num_start:self.state["pos"]]
        if raw.count(".") > 1:
            return (0, None, ("LEX_NUMBER_INVALID", "Malformed number (multiple dots): %s" % raw, start))
        if "." in raw:
            return self.MakeToken(NUMBER, float(raw), start)
        return self.MakeToken(NUMBER, int(raw), start)

    def LexBareword(self, params):
        start = self._p(params, "start", self.state["pos"])
        word_start = self.state["pos"]
        text = self.state["text"]
        while self.state["pos"] < self.state["length"] and text[self.state["pos"]] not in DELIMITERS:
            self.state["pos"] += 1
        word = text[word_start:self.state["pos"]]
        if word:
            return self.MakeToken(BAREWORD, word, start)
        self.state["pos"] += 1
        return (1, None, None)
