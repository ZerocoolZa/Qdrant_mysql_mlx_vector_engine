class DomAsm:
    """Assembly analysis: encode, decode, disassemble, opcode/register/jump extraction, function/label maps, cross references, report."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {},
            "catalog": [],
            "results": [],
            "instructions": [],
            "labels": {},
            "functions": {},
        }
        self.mem = mem
        self.db = db
        self._opcode_table = {
            "MOV": 0x01, "ADD": 0x02, "SUB": 0x03, "MUL": 0x04, "DIV": 0x05,
            "JMP": 0x10, "JZ": 0x11, "JNZ": 0x12, "CALL": 0x13, "RET": 0x14,
            "PUSH": 0x20, "POP": 0x21, "CMP": 0x30, "NOP": 0x00, "HLT": 0xFF,
        }
        self._reverse_table = {v: k for k, v in self._opcode_table.items()}
        self._registers = {"AX", "BX", "CX", "DX", "SI", "DI", "SP", "BP", "R0", "R1", "R2", "R3"}

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "cross_reference": self.cross_reference,
            "decode": self.decode,
            "disassemble": self.disassemble,
            "encode": self.encode,
            "extract_jumps": self.extract_jumps,
            "extract_opcodes": self.extract_opcodes,
            "extract_registers": self.extract_registers,
            "function_map": self.function_map,
            "label_map": self.label_map,
            "report": self.report,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def _parse_instruction(self, line):
        line = line.strip()
        if not line or line.startswith(";"):
            return None
        parts = line.replace(",", " ").split()
        if not parts:
            return None
        mnemonic = parts[0].upper()
        operands = [p for p in parts[1:] if p]
        return {"mnemonic": mnemonic, "operands": operands, "raw": line}

    def encode(self, params=None):
        params = params or {}
        try:
            mnemonic = (params.get("mnemonic") or "").upper()
            operands = params.get("operands", [])
            if mnemonic not in self._opcode_table:
                return (0, None, ("UNKNOWN_OPCODE", f"unknown mnemonic: {mnemonic}", 0))
            opcode = self._opcode_table[mnemonic]
            encoded = [opcode]
            for op in operands:
                if op.upper() in self._registers:
                    encoded.append(ord(op[0].upper()))
                else:
                    try:
                        encoded.append(int(op, 0))
                    except ValueError:
                        encoded.append(sum(ord(c) for c in op) & 0xFF)
            result = {"domain": "asm", "method": "encode", "data": {"mnemonic": mnemonic, "operands": operands, "bytes": encoded}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("ENCODE_ERROR", str(e), 0))

    def decode(self, params=None):
        params = params or {}
        try:
            byte_stream = params.get("bytes") or []
            if not byte_stream:
                return (0, None, ("EMPTY_BYTES", "bytes list required", 0))
            opcode = byte_stream[0]
            mnemonic = self._reverse_table.get(opcode, "UNK")
            operands = list(byte_stream[1:])
            result = {"domain": "asm", "method": "decode", "data": {"mnemonic": mnemonic, "operands": operands, "bytes": list(byte_stream)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DECODE_ERROR", str(e), 0))

    def disassemble(self, params=None):
        params = params or {}
        try:
            text = params.get("text") or ""
            if not text:
                return (0, None, ("EMPTY_TEXT", "assembly text required", 0))
            instructions = []
            for line in text.splitlines():
                instr = self._parse_instruction(line)
                if instr:
                    instructions.append(instr)
            self.state["instructions"] = instructions
            result = {"domain": "asm", "method": "disassemble", "data": {"count": len(instructions), "instructions": instructions}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DISASSEMBLE_ERROR", str(e), 0))

    def extract_opcodes(self, params=None):
        params = params or {}
        try:
            text = params.get("text") or ""
            instructions = self.state["instructions"]
            if text:
                instructions = []
                for line in text.splitlines():
                    instr = self._parse_instruction(line)
                    if instr:
                        instructions.append(instr)
            opcodes = [instr["mnemonic"] for instr in instructions]
            result = {"domain": "asm", "method": "extract_opcodes", "data": {"opcodes": opcodes, "count": len(opcodes)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EXTRACT_OPCODES_ERROR", str(e), 0))

    def extract_registers(self, params=None):
        params = params or {}
        try:
            text = params.get("text") or ""
            instructions = self.state["instructions"]
            if text:
                instructions = []
                for line in text.splitlines():
                    instr = self._parse_instruction(line)
                    if instr:
                        instructions.append(instr)
            registers = set()
            for instr in instructions:
                for op in instr["operands"]:
                    if op.upper() in self._registers:
                        registers.add(op.upper())
            result = {"domain": "asm", "method": "extract_registers", "data": {"registers": sorted(registers), "count": len(registers)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EXTRACT_REGISTERS_ERROR", str(e), 0))

    def extract_jumps(self, params=None):
        params = params or {}
        try:
            text = params.get("text") or ""
            instructions = self.state["instructions"]
            if text:
                instructions = []
                for line in text.splitlines():
                    instr = self._parse_instruction(line)
                    if instr:
                        instructions.append(instr)
            jump_mnemonics = {"JMP", "JZ", "JNZ", "CALL"}
            jumps = []
            for idx, instr in enumerate(instructions):
                if instr["mnemonic"] in jump_mnemonics:
                    target = instr["operands"][0] if instr["operands"] else None
                    jumps.append({"line": idx, "mnemonic": instr["mnemonic"], "target": target})
            result = {"domain": "asm", "method": "extract_jumps", "data": {"jumps": jumps, "count": len(jumps)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EXTRACT_JUMPS_ERROR", str(e), 0))

    def label_map(self, params=None):
        params = params or {}
        try:
            text = params.get("text") or ""
            labels = {}
            line_no = 0
            for line in (text.splitlines() if text else []):
                stripped = line.strip()
                if stripped.endswith(":") and not stripped.startswith(";"):
                    label = stripped[:-1]
                    labels[label] = line_no
                line_no += 1
            self.state["labels"] = labels
            result = {"domain": "asm", "method": "label_map", "data": {"labels": labels, "count": len(labels)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("LABEL_MAP_ERROR", str(e), 0))

    def function_map(self, params=None):
        params = params or {}
        try:
            text = params.get("text") or ""
            functions = {}
            current = None
            body = []
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.endswith(":") and not stripped.startswith(";"):
                    if current is not None:
                        functions[current] = body
                    current = stripped[:-1]
                    body = []
                elif current is not None:
                    body.append(stripped)
            if current is not None:
                functions[current] = body
            self.state["functions"] = functions
            result = {"domain": "asm", "method": "function_map", "data": {"functions": functions, "count": len(functions)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("FUNCTION_MAP_ERROR", str(e), 0))

    def cross_reference(self, params=None):
        params = params or {}
        try:
            text = params.get("text") or ""
            ok, label_data, err = self.label_map({"text": text})
            labels = label_data.get("data", {}).get("labels", {}) if ok else {}
            ok2, jump_data, err2 = self.extract_jumps({"text": text})
            jumps = jump_data.get("data", {}).get("jumps", []) if ok2 else []
            xrefs = {}
            for jump in jumps:
                target = jump.get("target")
                if target:
                    xrefs.setdefault(target, []).append(jump["line"])
            result = {"domain": "asm", "method": "cross_reference", "data": {"labels": labels, "xrefs": xrefs}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("CROSS_REFERENCE_ERROR", str(e), 0))

    def report(self, params=None):
        params = params or {}
        try:
            data = {
                "instructions": len(self.state["instructions"]),
                "labels": len(self.state["labels"]),
                "functions": len(self.state["functions"]),
                "label_names": list(self.state["labels"].keys()),
                "function_names": list(self.state["functions"].keys()),
            }
            result = {"domain": "asm", "method": "report", "data": data}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("REPORT_ERROR", str(e), 0))
