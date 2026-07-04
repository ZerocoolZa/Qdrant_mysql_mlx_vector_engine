#[@GHOST]
#[@VBSTYLE]
#[@FILEID] PlfIrSpec.py
#[@SUMMARY] PLF IR Specification — opcode table, value types, instruction format, function descriptor
#[@CLASS] PlfIrSpec
#[@METHOD] Run
#[@DATE] 2026-07-04
#[@AUTHOR] Wayne / Cascade
#[@SESSION] CHECKPOINT-PLF-IR-1
#[@CONTEXT] Stage 2 of PLF — executable intermediate representation spec

"""
PLF IR — Portable Language Format Intermediate Representation

Architecture:
    Stack machine (like WASM/JVM)
    Variable-length encoding (LEB128 for operands)
    Typed values on the stack
    Linear memory + call stack
    Functions referenced by ID (U32)

Instruction Format:
    [opcode:U8] [operand0:LEB128] [operand1:LEB128] ...
    Most instructions have 0-2 operands.
    LEB128 encodes 7 bits per byte, MSB=1 means continuation.

Value Types (tagged on stack):
    NULL    0x00    empty
    I32     0x01    32-bit signed integer
    I64     0x02    64-bit signed integer
    F32     0x03    32-bit float
    F64     0x04    64-bit float
    PTR     0x05    pointer into linear memory
    STR     0x06    string reference (SID into string pool)
    REF     0x07    reference to PLF object (object_id)
    ARR     0x08    array reference
    FN      0x09    function reference (func_id)

Function Descriptor (in PLF Container):
    func_id     U32     unique function ID
    name_sid    U32     string pool index for name
    param_count U8      number of parameters
    local_count U16     number of local variable slots
    code_offset U32     offset into bytecode section
    code_length U32     length of bytecode for this function

Opcode Groups:
    0x01-0x0F   Stack operations
    0x10-0x1F   Constants
    0x20-0x2F   Arithmetic
    0x30-0x3F   Bitwise
    0x40-0x4F   Comparison
    0x50-0x5F   Control flow
    0x60-0x6F   Memory
    0x70-0x7F   Type conversion
    0x80-0x8F   Function / call frame
    0x90-0x9F   Object (PLF container interaction)
    0xA0-0xAF   System
    0xB0-0xBF   PLF-specific

Usage:
    from PlfIrSpec import PlfIrSpec
    spec = PlfIrSpec()
    ok, data, err = spec.Run("get_opcode", {"name": "ADD"})
    ok, data, err = spec.Run("get_opcode_name", {"opcode": 0x20})
    ok, data, err = spec.Run("list_opcodes", {"group": "ARITHMETIC"})
    ok, data, err = spec.Run("operand_count", {"opcode": 0x20})
"""

from typing import Dict, List, Tuple, Optional


# ── Value Types ──────────────────────────────────────────────

TYPE_NULL = 0x00
TYPE_I32  = 0x01
TYPE_I64  = 0x02
TYPE_F32  = 0x03
TYPE_F64  = 0x04
TYPE_PTR  = 0x05
TYPE_STR  = 0x06
TYPE_REF  = 0x07
TYPE_ARR  = 0x08
TYPE_FN   = 0x09

TYPE_NAMES = {
    TYPE_NULL: "NULL",
    TYPE_I32:  "I32",
    TYPE_I64:  "I64",
    TYPE_F32:  "F32",
    TYPE_F64:  "F64",
    TYPE_PTR:  "PTR",
    TYPE_STR:  "STR",
    TYPE_REF:  "REF",
    TYPE_ARR:  "ARR",
    TYPE_FN:   "FN",
}

TYPE_IDS = {v: k for k, v in TYPE_NAMES.items()}


# ── Opcodes ──────────────────────────────────────────────────

# Stack operations (0x01-0x0F)
OP_POP       = 0x01   # pop top, discard
OP_DUP       = 0x02   # duplicate top
OP_SWAP      = 0x03   # swap top two
OP_OVER      = 0x04   # copy second-from-top to top
OP_ROT       = 0x05   # rotate top three (3rd → 1st)
OP_DROP2     = 0x06   # pop top two, discard
OP_DUP2      = 0x07   # duplicate top two
OP_DEPTH     = 0x08   # push current stack depth

# Constants (0x10-0x1F)
OP_CONST_I32 = 0x10   # push i32 immediate (operand: value)
OP_CONST_I64 = 0x11   # push i64 immediate (operand: value)
OP_CONST_F32 = 0x12   # push f32 immediate (operand: pool_index)
OP_CONST_F64 = 0x13   # push f64 immediate (operand: pool_index)
OP_CONST_STR = 0x14   # push string (operand: SID)
OP_CONST_NULL = 0x15  # push null
OP_CONST_TRUE = 0x16  # push i32 1
OP_CONST_FALSE = 0x17 # push i32 0

# Arithmetic (0x20-0x2F)
OP_ADD       = 0x20   # pop b, pop a, push a+b
OP_SUB       = 0x21   # pop b, pop a, push a-b
OP_MUL       = 0x22   # pop b, pop a, push a*b
OP_DIV       = 0x23   # pop b, pop a, push a/b (integer or float)
OP_MOD       = 0x24   # pop b, pop a, push a%b
OP_NEG       = 0x25   # pop a, push -a
OP_ABS       = 0x26   # pop a, push abs(a)
OP_MIN       = 0x27   # pop b, pop a, push min(a,b)
OP_MAX       = 0x28   # pop b, pop a, push max(a,b)

# Bitwise (0x30-0x3F)
OP_AND       = 0x30   # pop b, pop a, push a&b
OP_OR        = 0x31   # pop b, pop a, push a|b
OP_XOR       = 0x32   # pop b, pop a, push a^b
OP_NOT       = 0x33   # pop a, push ~a
OP_SHL       = 0x34   # pop b, pop a, push a<<b
OP_SHR       = 0x35   # pop b, pop a, push a>>b

# Comparison (0x40-0x4F) — pushes I32 0 or 1
OP_EQ        = 0x40   # pop b, pop a, push (a==b)
OP_NE        = 0x41   # pop b, pop a, push (a!=b)
OP_LT        = 0x42   # pop b, pop a, push (a<b)
OP_GT        = 0x43   # pop b, pop a, push (a>b)
OP_LE        = 0x44   # pop b, pop a, push (a<=b)
OP_GE        = 0x45   # pop b, pop a, push (a>=b)

# Control flow (0x50-0x5F)
OP_JMP       = 0x50   # unconditional jump (operand: target_addr)
OP_JZ        = 0x51   # pop v, jump if v==0 (operand: target_addr)
OP_JNZ       = 0x52   # pop v, jump if v!=0 (operand: target_addr)
OP_CALL      = 0x53   # call function (operand: func_id)
OP_RET       = 0x54   # return from function (value stays on caller stack)
OP_HALT      = 0x55   # stop execution
OP_NOP       = 0x56   # no operation
OP_TRY       = 0x57   # begin try block (operand: catch_addr)
OP_THROW     = 0x58   # pop value, throw as exception
OP_CATCH     = 0x59   # catch marker (operand: handler_addr)

# Memory (0x60-0x6F)
OP_LOAD      = 0x60   # pop ptr, push value at ptr (operand: type, size)
OP_STORE     = 0x61   # pop value, pop ptr, store at ptr (operand: type, size)
OP_ALLOCA    = 0x62   # push ptr to N bytes on stack (operand: size)
OP_MEMCPY    = 0x63   # pop len, pop src, pop dst, copy
OP_MEMSET    = 0x64   # pop val, pop len, pop ptr, set
OP_LOAD8     = 0x65   # pop ptr, push U8 at ptr as I32
OP_LOAD16    = 0x66   # pop ptr, push U16 at ptr as I32
OP_LOAD32    = 0x67   # pop ptr, push U32 at ptr as I32
OP_LOAD64    = 0x68   # pop ptr, push U64 at ptr as I64
OP_STORE8    = 0x69   # pop val, pop ptr, store U8
OP_STORE16   = 0x6A   # pop val, pop ptr, store U16
OP_STORE32   = 0x6B   # pop val, pop ptr, store U32
OP_STORE64   = 0x6C   # pop val, pop ptr, store U64

# Type conversion (0x70-0x7F)
OP_CONV_I32  = 0x70   # pop v, push (I32)v
OP_CONV_I64  = 0x71   # pop v, push (I64)v
OP_CONV_F32  = 0x72   # pop v, push (F32)v
OP_CONV_F64  = 0x73   # pop v, push (F64)v
OP_IS_NULL   = 0x74   # pop v, push (v == null)
OP_TYPEOF    = 0x75   # pop v, push type tag as I32

# Function / call frame (0x80-0x8F)
OP_LOCAL_GET = 0x80   # push local variable (operand: local_index)
OP_LOCAL_SET = 0x81   # pop into local variable (operand: local_index)
OP_PARAM_GET = 0x82   # push parameter (operand: param_index)
OP_RET_VAL   = 0x83   # pop return value, store in frame
OP_CALL_IND  = 0x84   # indirect call — pop func_id from stack, call

# Object / PLF container (0x90-0x9F)
OP_OBJ_NEW   = 0x90   # create object (operand: type_id), push REF
OP_OBJ_GET   = 0x91   # pop obj_id, push object payload as STR
OP_OBJ_SET   = 0x92   # pop payload, pop obj_id, set object payload
OP_OBJ_LEN   = 0x93   # pop obj_id, push object length as I32
OP_OBJ_FIELD = 0x94   # pop obj_id, pop field_sid, push field value
OP_OBJ_TYPE  = 0x95   # pop obj_id, push type_id as I32
OP_OBJ_NAME  = 0x96   # pop obj_id, push name SID

# System (0xA0-0xAF)
OP_PRINT     = 0xA0   # pop value, print to stdout
OP_DEBUG     = 0xA1   # dump stack state
OP_SYSCALL   = 0xA2   # system call (operand: syscall_id)
OP_TRACE     = 0xA3   # trace instruction (operand: trace_id)

# PLF-specific (0xB0-0xBF)
OP_PACK      = 0xB0   # pack stack values into PLF container
OP_UNPACK    = 0xB1   # unpack PLF object onto stack
OP_RESOLVE   = 0xB2   # resolve symbol by SID, push REF
OP_SERIALIZE = 0xB3   # serialize current state to PLF bytecode
OP_DESERIAL  = 0xB4   # deserialize PLF bytecode into VM state


# ── Opcode Metadata ──────────────────────────────────────────

OPCODE_NAMES = {
    # Stack
    OP_POP:       "POP",
    OP_DUP:       "DUP",
    OP_SWAP:      "SWAP",
    OP_OVER:      "OVER",
    OP_ROT:       "ROT",
    OP_DROP2:     "DROP2",
    OP_DUP2:      "DUP2",
    OP_DEPTH:     "DEPTH",
    # Constants
    OP_CONST_I32: "CONST_I32",
    OP_CONST_I64: "CONST_I64",
    OP_CONST_F32: "CONST_F32",
    OP_CONST_F64: "CONST_F64",
    OP_CONST_STR: "CONST_STR",
    OP_CONST_NULL:"CONST_NULL",
    OP_CONST_TRUE:"CONST_TRUE",
    OP_CONST_FALSE:"CONST_FALSE",
    # Arithmetic
    OP_ADD:       "ADD",
    OP_SUB:       "SUB",
    OP_MUL:       "MUL",
    OP_DIV:       "DIV",
    OP_MOD:       "MOD",
    OP_NEG:       "NEG",
    OP_ABS:       "ABS",
    OP_MIN:       "MIN",
    OP_MAX:       "MAX",
    # Bitwise
    OP_AND:       "AND",
    OP_OR:        "OR",
    OP_XOR:       "XOR",
    OP_NOT:       "NOT",
    OP_SHL:       "SHL",
    OP_SHR:       "SHR",
    # Comparison
    OP_EQ:        "EQ",
    OP_NE:        "NE",
    OP_LT:        "LT",
    OP_GT:        "GT",
    OP_LE:        "LE",
    OP_GE:        "GE",
    # Control flow
    OP_JMP:       "JMP",
    OP_JZ:        "JZ",
    OP_JNZ:       "JNZ",
    OP_CALL:      "CALL",
    OP_RET:       "RET",
    OP_HALT:      "HALT",
    OP_NOP:       "NOP",
    OP_TRY:       "TRY",
    OP_THROW:     "THROW",
    OP_CATCH:     "CATCH",
    # Memory
    OP_LOAD:      "LOAD",
    OP_STORE:     "STORE",
    OP_ALLOCA:    "ALLOCA",
    OP_MEMCPY:    "MEMCPY",
    OP_MEMSET:    "MEMSET",
    OP_LOAD8:     "LOAD8",
    OP_LOAD16:    "LOAD16",
    OP_LOAD32:    "LOAD32",
    OP_LOAD64:    "LOAD64",
    OP_STORE8:    "STORE8",
    OP_STORE16:   "STORE16",
    OP_STORE32:   "STORE32",
    OP_STORE64:   "STORE64",
    # Type conversion
    OP_CONV_I32:  "CONV_I32",
    OP_CONV_I64:  "CONV_I64",
    OP_CONV_F32:  "CONV_F32",
    OP_CONV_F64:  "CONV_F64",
    OP_IS_NULL:   "IS_NULL",
    OP_TYPEOF:    "TYPEOF",
    # Function
    OP_LOCAL_GET: "LOCAL_GET",
    OP_LOCAL_SET: "LOCAL_SET",
    OP_PARAM_GET: "PARAM_GET",
    OP_RET_VAL:   "RET_VAL",
    OP_CALL_IND:  "CALL_IND",
    # Object
    OP_OBJ_NEW:   "OBJ_NEW",
    OP_OBJ_GET:   "OBJ_GET",
    OP_OBJ_SET:   "OBJ_SET",
    OP_OBJ_LEN:   "OBJ_LEN",
    OP_OBJ_FIELD: "OBJ_FIELD",
    OP_OBJ_TYPE:  "OBJ_TYPE",
    OP_OBJ_NAME:  "OBJ_NAME",
    # System
    OP_PRINT:     "PRINT",
    OP_DEBUG:     "DEBUG",
    OP_SYSCALL:   "SYSCALL",
    OP_TRACE:     "TRACE",
    # PLF
    OP_PACK:      "PACK",
    OP_UNPACK:    "UNPACK",
    OP_RESOLVE:   "RESOLVE",
    OP_SERIALIZE: "SERIALIZE",
    OP_DESERIAL:  "DESERIAL",
}

OPCODE_IDS = {v: k for k, v in OPCODE_NAMES.items()}

# Operand count per opcode: {opcode: num_operands}
OPCODE_OPERANDS = {
    OP_POP: 0,        OP_DUP: 0,       OP_SWAP: 0,      OP_OVER: 0,
    OP_ROT: 0,        OP_DROP2: 0,     OP_DUP2: 0,      OP_DEPTH: 0,
    OP_CONST_I32: 1,  OP_CONST_I64: 1, OP_CONST_F32: 1, OP_CONST_F64: 1,
    OP_CONST_STR: 1,  OP_CONST_NULL: 0,OP_CONST_TRUE: 0,OP_CONST_FALSE: 0,
    OP_ADD: 0,        OP_SUB: 0,       OP_MUL: 0,       OP_DIV: 0,
    OP_MOD: 0,        OP_NEG: 0,       OP_ABS: 0,       OP_MIN: 0,
    OP_MAX: 0,
    OP_AND: 0,        OP_OR: 0,        OP_XOR: 0,       OP_NOT: 0,
    OP_SHL: 0,        OP_SHR: 0,
    OP_EQ: 0,         OP_NE: 0,        OP_LT: 0,        OP_GT: 0,
    OP_LE: 0,         OP_GE: 0,
    OP_JMP: 1,        OP_JZ: 1,        OP_JNZ: 1,       OP_CALL: 1,
    OP_RET: 0,        OP_HALT: 0,      OP_NOP: 0,       OP_TRY: 1,
    OP_THROW: 0,      OP_CATCH: 1,
    OP_LOAD: 2,       OP_STORE: 2,     OP_ALLOCA: 1,    OP_MEMCPY: 0,
    OP_MEMSET: 0,     OP_LOAD8: 0,     OP_LOAD16: 0,    OP_LOAD32: 0,
    OP_LOAD64: 0,     OP_STORE8: 0,    OP_STORE16: 0,   OP_STORE32: 0,
    OP_STORE64: 0,
    OP_CONV_I32: 0,   OP_CONV_I64: 0,  OP_CONV_F32: 0,  OP_CONV_F64: 0,
    OP_IS_NULL: 0,    OP_TYPEOF: 0,
    OP_LOCAL_GET: 1,  OP_LOCAL_SET: 1, OP_PARAM_GET: 1, OP_RET_VAL: 0,
    OP_CALL_IND: 0,
    OP_OBJ_NEW: 1,    OP_OBJ_GET: 0,   OP_OBJ_SET: 0,   OP_OBJ_LEN: 0,
    OP_OBJ_FIELD: 0,  OP_OBJ_TYPE: 0,  OP_OBJ_NAME: 0,
    OP_PRINT: 0,      OP_DEBUG: 0,     OP_SYSCALL: 1,   OP_TRACE: 1,
    OP_PACK: 0,       OP_UNPACK: 0,    OP_RESOLVE: 1,   OP_SERIALIZE: 0,
    OP_DESERIAL: 0,
}

# Group names for organization
OPCODE_GROUPS = {
    "STACK":       [OP_POP, OP_DUP, OP_SWAP, OP_OVER, OP_ROT, OP_DROP2, OP_DUP2, OP_DEPTH],
    "CONSTANT":    [OP_CONST_I32, OP_CONST_I64, OP_CONST_F32, OP_CONST_F64,
                    OP_CONST_STR, OP_CONST_NULL, OP_CONST_TRUE, OP_CONST_FALSE],
    "ARITHMETIC":  [OP_ADD, OP_SUB, OP_MUL, OP_DIV, OP_MOD, OP_NEG, OP_ABS, OP_MIN, OP_MAX],
    "BITWISE":     [OP_AND, OP_OR, OP_XOR, OP_NOT, OP_SHL, OP_SHR],
    "COMPARISON":  [OP_EQ, OP_NE, OP_LT, OP_GT, OP_LE, OP_GE],
    "CONTROL":     [OP_JMP, OP_JZ, OP_JNZ, OP_CALL, OP_RET, OP_HALT, OP_NOP, OP_TRY, OP_THROW, OP_CATCH],
    "MEMORY":      [OP_LOAD, OP_STORE, OP_ALLOCA, OP_MEMCPY, OP_MEMSET,
                    OP_LOAD8, OP_LOAD16, OP_LOAD32, OP_LOAD64,
                    OP_STORE8, OP_STORE16, OP_STORE32, OP_STORE64],
    "CONVERSION":  [OP_CONV_I32, OP_CONV_I64, OP_CONV_F32, OP_CONV_F64, OP_IS_NULL, OP_TYPEOF],
    "FUNCTION":    [OP_LOCAL_GET, OP_LOCAL_SET, OP_PARAM_GET, OP_RET_VAL, OP_CALL_IND],
    "OBJECT":      [OP_OBJ_NEW, OP_OBJ_GET, OP_OBJ_SET, OP_OBJ_LEN, OP_OBJ_FIELD, OP_OBJ_TYPE, OP_OBJ_NAME],
    "SYSTEM":      [OP_PRINT, OP_DEBUG, OP_SYSCALL, OP_TRACE],
    "PLF":         [OP_PACK, OP_UNPACK, OP_RESOLVE, OP_SERIALIZE, OP_DESERIAL],
}

# Syscall IDs
SYSCALL_PRINT_STR  = 0x01
SYSCALL_PRINT_INT  = 0x02
SYSCALL_PRINT_FLT  = 0x03
SYSCALL_READ_LINE  = 0x04
SYSCALL_OPEN_FILE  = 0x05
SYSCALL_READ_FILE  = 0x06
SYSCALL_WRITE_FILE = 0x07
SYSCALL_CLOSE_FILE = 0x08
SYSCALL_DB_QUERY   = 0x10
SYSCALL_DB_EXEC    = 0x11
SYSCALL_HTTP_GET   = 0x20
SYSCALL_HTTP_POST  = 0x21

SYSCALL_NAMES = {
    SYSCALL_PRINT_STR:  "PRINT_STR",
    SYSCALL_PRINT_INT:  "PRINT_INT",
    SYSCALL_PRINT_FLT:  "PRINT_FLT",
    SYSCALL_READ_LINE:  "READ_LINE",
    SYSCALL_OPEN_FILE:  "OPEN_FILE",
    SYSCALL_READ_FILE:  "READ_FILE",
    SYSCALL_WRITE_FILE: "WRITE_FILE",
    SYSCALL_CLOSE_FILE: "CLOSE_FILE",
    SYSCALL_DB_QUERY:   "DB_QUERY",
    SYSCALL_DB_EXEC:    "DB_EXEC",
    SYSCALL_HTTP_GET:   "HTTP_GET",
    SYSCALL_HTTP_POST:  "HTTP_POST",
}


class PlfIrSpec:

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "opcode_names": OPCODE_NAMES,
            "opcode_ids": OPCODE_IDS,
            "opcode_operands": OPCODE_OPERANDS,
            "opcode_groups": OPCODE_GROUPS,
            "type_names": TYPE_NAMES,
            "type_ids": TYPE_IDS,
            "syscall_names": SYSCALL_NAMES,
        }

    def Run(self, command, params=None):
        dispatch = {
            "get_opcode": self._get_opcode,
            "get_opcode_name": self._get_opcode_name,
            "list_opcodes": self._list_opcodes,
            "operand_count": self._operand_count,
            "list_groups": self._list_groups,
            "list_types": self._list_types,
            "get_type_id": self._get_type_id,
            "get_type_name": self._get_type_name,
            "list_syscalls": self._list_syscalls,
            "spec": self._spec,
            "validate_opcode": self._validate_opcode,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, ("UNKNOWN_COMMAND", f"Unknown: {command}", 0))
        return handler(params or {})

    def _p(self):
        return self.state

    def read_state(self):
        return self.state

    def set_config(self, config):
        self.state.update(config)
        return (1, {"state": self.state}, None)

    # ── Queries ──────────────────────────────────────────────

    def _get_opcode(self, params):
        name = params.get("name", "")
        oid = OPCODE_IDS.get(name)
        if oid is None:
            return (0, None, ("OPCODE_NOT_FOUND", f"Unknown opcode: {name}", 0))
        return (1, {"opcode": oid, "name": name,
                     "operands": OPCODE_OPERANDS.get(oid, 0)}, None)

    def _get_opcode_name(self, params):
        oid = params.get("opcode", -1)
        name = OPCODE_NAMES.get(oid)
        if name is None:
            return (0, None, ("OPCODE_NOT_FOUND", f"Unknown opcode: 0x{oid:02X}", 0))
        return (1, {"opcode": oid, "name": name,
                     "operands": OPCODE_OPERANDS.get(oid, 0)}, None)

    def _list_opcodes(self, params):
        group = params.get("group")
        if group:
            opcodes = OPCODE_GROUPS.get(group, [])
            result = [{"opcode": o, "name": OPCODE_NAMES[o],
                        "operands": OPCODE_OPERANDS.get(o, 0)} for o in opcodes]
        else:
            result = [{"opcode": o, "name": n,
                        "operands": OPCODE_OPERANDS.get(o, 0)}
                      for o, n in sorted(OPCODE_NAMES.items())]
        return (1, {"opcodes": result, "count": len(result)}, None)

    def _operand_count(self, params):
        oid = params.get("opcode", -1)
        if oid not in OPCODE_NAMES:
            return (0, None, ("OPCODE_NOT_FOUND", f"Unknown opcode: 0x{oid:02X}", 0))
        return (1, {"opcode": oid, "name": OPCODE_NAMES[oid],
                     "operands": OPCODE_OPERANDS.get(oid, 0)}, None)

    def _list_groups(self, params):
        groups = {g: len(ops) for g, ops in OPCODE_GROUPS.items()}
        return (1, {"groups": groups, "count": len(groups)}, None)

    def _list_types(self, params):
        result = [{"type_id": t, "name": n} for t, n in sorted(TYPE_NAMES.items())]
        return (1, {"types": result, "count": len(result)}, None)

    def _get_type_id(self, params):
        name = params.get("name", "")
        tid = TYPE_IDS.get(name)
        if tid is None:
            return (0, None, ("TYPE_NOT_FOUND", f"Unknown type: {name}", 0))
        return (1, {"type_id": tid, "name": name}, None)

    def _get_type_name(self, params):
        tid = params.get("type_id", -1)
        name = TYPE_NAMES.get(tid)
        if name is None:
            return (0, None, ("TYPE_NOT_FOUND", f"Unknown type: {tid}", 0))
        return (1, {"type_id": tid, "name": name}, None)

    def _list_syscalls(self, params):
        result = [{"syscall_id": s, "name": n}
                  for s, n in sorted(SYSCALL_NAMES.items())]
        return (1, {"syscalls": result, "count": len(result)}, None)

    def _spec(self, params):
        return (1, {
            "architecture": "stack_machine",
            "encoding": "LEB128",
            "opcode_count": len(OPCODE_NAMES),
            "type_count": len(TYPE_NAMES),
            "syscall_count": len(SYSCALL_NAMES),
            "groups": {g: len(ops) for g, ops in OPCODE_GROUPS.items()},
            "instruction_format": "[opcode:U8] [operand:LEB128]*",
            "function_descriptor": "func_id:U32 name_sid:U32 param_count:U8 local_count:U16 code_offset:U32 code_length:U32",
        }, None)

    def _validate_opcode(self, params):
        oid = params.get("opcode", -1)
        if oid not in OPCODE_NAMES:
            return (0, None, ("INVALID_OPCODE", f"0x{oid:02X} is not a valid opcode", 0))
        return (1, {"valid": True, "opcode": oid, "name": OPCODE_NAMES[oid]}, None)


if __name__ == "__main__":
    spec = PlfIrSpec()

    ok, data, _ = spec.Run("spec", {})
    print("=== PLF IR Specification ===")
    print(f"Architecture: {data['architecture']}")
    print(f"Encoding: {data['encoding']}")
    print(f"Opcodes: {data['opcode_count']}")
    print(f"Types: {data['type_count']}")
    print(f"Syscalls: {data['syscall_count']}")
    print(f"Instruction: {data['instruction_format']}")
    print()

    ok, data, _ = spec.Run("list_groups", {})
    print("Opcode Groups:")
    for g, count in data["groups"].items():
        print(f"  {g:15s} {count} opcodes")
    print()

    ok, data, _ = spec.Run("list_opcodes", {"group": "ARITHMETIC"})
    print(f"Arithmetic opcodes ({data['count']}):")
    for o in data["opcodes"]:
        print(f"  0x{o['opcode']:02X}  {o['name']:15s}  operands={o['operands']}")
    print()

    ok, data, _ = spec.Run("list_types", {})
    print(f"Value types ({data['count']}):")
    for t in data["types"]:
        print(f"  0x{t['type_id']:02X}  {t['name']}")
    print()

    ok, data, _ = spec.Run("list_syscalls", {})
    print(f"Syscalls ({data['count']}):")
    for s in data["syscalls"]:
        print(f"  0x{s['syscall_id']:02X}  {s['name']}")
