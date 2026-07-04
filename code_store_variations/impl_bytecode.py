import dis
import marshal
import types
import struct

class DomBytecode:
    """Python bytecode operations: compile, disassemble, extract, inject, patch, optimize."""

    def __init__(self, mem=None, db=None, param=None):
        self.state = {"config": {}, "catalog": [], "results": []}
        self.mem = mem
        self.db = db

    def Run(self, command, params=None):
        params = params or {}
        handlers = {
            "compare": self.compare,
            "compile": self.compile,
            "decompile": self.decompile,
            "disassemble": self.disassemble,
            "extract_code": self.extract_code,
            "extract_constants": self.extract_constants,
            "extract_names": self.extract_names,
            "inject": self.inject,
            "optimize": self.optimize,
            "patch": self.patch,
        }
        handler = handlers.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params)

    def compile(self, params=None):
        params = params or {}
        try:
            source = params.get("source", "")
            mode = params.get("mode", "exec")
            filename = params.get("filename", "<dom_bytecode>")
            code_obj = compile(source, filename, mode)
            result = {"domain": "bytecode", "method": "compile", "data": {"co_name": code_obj.co_name, "co_code_len": len(code_obj.co_code), "arg_count": code_obj.co_argcount, "stack_size": code_obj.co_stacksize}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COMPILE_ERROR", str(e), 0))

    def disassemble(self, params=None):
        params = params or {}
        try:
            source = params.get("source", "")
            code_obj = params.get("code")
            if code_obj is None:
                code_obj = compile(source, "<dis>", "exec") if source else None
            if code_obj is None:
                return (0, None, ("DISASSEMBLE_ERROR", "no source or code provided", 0))
            instructions = []
            for ins in dis.get_instructions(code_obj):
                instructions.append({"offset": ins.offset, "opname": ins.opname, "arg": ins.arg, "argrepr": ins.argrepr, "starts_line": ins.starts_line})
            result = {"domain": "bytecode", "method": "disassemble", "data": instructions, "count": len(instructions)}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DISASSEMBLE_ERROR", str(e), 0))

    def extract_constants(self, params=None):
        params = params or {}
        try:
            source = params.get("source", "")
            code_obj = params.get("code")
            if code_obj is None:
                code_obj = compile(source, "<extract>", "exec") if source else None
            if code_obj is None:
                return (0, None, ("EXTRACT_CONSTANTS_ERROR", "no source or code", 0))
            consts = []
            for c in code_obj.co_consts:
                if isinstance(c, types.CodeType):
                    consts.append({"type": "code", "name": c.co_name})
                else:
                    consts.append({"type": type(c).__name__, "value": c})
            result = {"domain": "bytecode", "method": "extract_constants", "data": consts, "count": len(consts)}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EXTRACT_CONSTANTS_ERROR", str(e), 0))

    def extract_names(self, params=None):
        params = params or {}
        try:
            source = params.get("source", "")
            code_obj = params.get("code")
            if code_obj is None:
                code_obj = compile(source, "<extract>", "exec") if source else None
            if code_obj is None:
                return (0, None, ("EXTRACT_NAMES_ERROR", "no source or code", 0))
            names = {
                "co_names": list(code_obj.co_names),
                "co_varnames": list(code_obj.co_varnames),
                "co_freevars": list(code_obj.co_freevars),
                "co_cellvars": list(code_obj.co_cellvars),
            }
            result = {"domain": "bytecode", "method": "extract_names", "data": names}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EXTRACT_NAMES_ERROR", str(e), 0))

    def extract_code(self, params=None):
        params = params or {}
        try:
            source = params.get("source", "")
            code_obj = params.get("code")
            if code_obj is None:
                code_obj = compile(source, "<extract>", "exec") if source else None
            if code_obj is None:
                return (0, None, ("EXTRACT_CODE_ERROR", "no source or code", 0))
            raw = marshal.dumps(code_obj)
            result = {"domain": "bytecode", "method": "extract_code", "data": {"bytes_len": len(raw), "hex_head": raw[:32].hex(), "co_name": code_obj.co_name}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("EXTRACT_CODE_ERROR", str(e), 0))

    def compare(self, params=None):
        params = params or {}
        try:
            source_a = params.get("source_a", "")
            source_b = params.get("source_b", "")
            code_a = compile(source_a, "<a>", "exec") if source_a else None
            code_b = compile(source_b, "<b>", "exec") if source_b else None
            if code_a is None or code_b is None:
                return (0, None, ("COMPARE_ERROR", "need both sources", 0))
            instr_a = [(i.opname, i.arg) for i in dis.get_instructions(code_a)]
            instr_b = [(i.opname, i.arg) for i in dis.get_instructions(code_b)]
            same = instr_a == instr_b
            diff = []
            for idx in range(max(len(instr_a), len(instr_b))):
                a = instr_a[idx] if idx < len(instr_a) else None
                b = instr_b[idx] if idx < len(instr_b) else None
                if a != b:
                    diff.append({"index": idx, "a": a, "b": b})
            result = {"domain": "bytecode", "method": "compare", "data": {"identical": same, "diff_count": len(diff), "diffs": diff[:20]}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("COMPARE_ERROR", str(e), 0))

    def decompile(self, params=None):
        params = params or {}
        try:
            source = params.get("source", "")
            code_obj = params.get("code")
            if code_obj is None:
                code_obj = compile(source, "<decomp>", "exec") if source else None
            if code_obj is None:
                return (0, None, ("DECOMPILE_ERROR", "no source or code", 0))
            lines = []
            for ins in dis.get_instructions(code_obj):
                lines.append(f"{ins.offset:4d} {ins.opname:<20s} {ins.argrepr}")
            pseudo = "\n".join(lines)
            result = {"domain": "bytecode", "method": "decompile", "data": pseudo, "line_count": len(lines)}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("DECOMPILE_ERROR", str(e), 0))

    def inject(self, params=None):
        params = params or {}
        try:
            source = params.get("source", "")
            injection = params.get("injection", "pass")
            mode = params.get("mode", "prepend")
            if mode == "prepend":
                new_source = injection + "\n" + source
            elif mode == "append":
                new_source = source + "\n" + injection
            else:
                new_source = source + "\n" + injection
            code_obj = compile(new_source, "<inject>", "exec")
            result = {"domain": "bytecode", "method": "inject", "data": {"new_source": new_source, "co_code_len": len(code_obj.co_code), "mode": mode}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("INJECT_ERROR", str(e), 0))

    def optimize(self, params=None):
        params = params or {}
        try:
            source = params.get("source", "")
            level = params.get("level", 2)
            code_obj = compile(source, "<opt>", "exec")
            optimized = code_obj.replace()
            instr_count = len(list(dis.get_instructions(optimized)))
            consts_count = len(optimized.co_consts)
            result = {"domain": "bytecode", "method": "optimize", "data": {"instr_count": instr_count, "consts_count": consts_count, "level": level}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("OPTIMIZE_ERROR", str(e), 0))

    def patch(self, params=None):
        params = params or {}
        try:
            source = params.get("source", "")
            replacements = params.get("replacements", {})
            patched = source
            for old, new in replacements.items():
                patched = patched.replace(old, new)
            code_obj = compile(patched, "<patch>", "exec")
            result = {"domain": "bytecode", "method": "patch", "data": {"patched_source": patched, "co_code_len": len(code_obj.co_code), "replacements": len(replacements)}}
            return (1, result, None)
        except Exception as e:
            return (0, None, ("PATCH_ERROR", str(e), 0))
