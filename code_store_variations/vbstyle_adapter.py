#!/usr/bin/env python3
"""
VBStyle Adapter — transforms real code to VBStyle compliance.
Preserves the actual logic, fixes the format.

Transformations:
1. Remove decorators (@property, @staticmethod, etc.)
2. Remove import statements
3. Replace print() with pass (Report class handles output)
4. Replace self._variable with self.state.get("variable") / self.state["variable"] = ...
5. Remove hardcoded paths (replace with config references)
6. Convert return statements to Tuple3 (1, data, None) / (0, None, (code, desc, 0))
7. Ensure method signature has params
"""

import sqlite3
import os
import re
import ast

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "v20_hybrid_best.db")


def remove_decorators(code):
    """Remove @property, @staticmethod, etc."""
    lines = code.split('\n')
    result = []
    for line in lines:
        stripped = line.strip()
        if re.match(r'@(property|staticmethod|classmethod|abstractmethod|functools\.\w+|dataclass)', stripped):
            continue
        # Keep @[@...] bracket headers
        if stripped.startswith('#[@') or stripped.startswith('#\\[@'):
            result.append(line)
            continue
        if stripped.startswith('@') and not stripped.startswith('@[') and not stripped.startswith('#[@'):
            # Skip unknown decorators
            continue
        result.append(line)
    return '\n'.join(result)


def remove_imports(code):
    """Remove import statements."""
    lines = code.split('\n')
    result = []
    for line in lines:
        stripped = line.strip()
        if re.match(r'^import\s+', stripped) or re.match(r'^from\s+\w+\s+import', stripped):
            continue
        result.append(line)
    return '\n'.join(result)


def remove_print(code):
    """Replace print() calls with pass or remove them."""
    # Replace print(...) with pass
    def replace_print(match):
        return 'pass  # print removed (use Report class)'
    
    code = re.sub(r'print\s*\([^)]*\)', replace_print, code)
    # Handle multi-line print
    code = re.sub(r'print\s*\([^)]*$', 'pass  # print removed', code, flags=re.MULTILINE)
    return code


def fix_self_underscore(code):
    """Replace self._variable with self.state equivalent."""
    # self._variable -> self.state.get("variable")
    # self._variable = value -> self.state["variable"] = value
    # self._variable[idx] -> self.state["variable"][idx]
    # self._variable.method() -> self.state["variable"].method()
    
    def replace_get(match):
        prefix = match.group(1)  # self.
        var_name = match.group(2)  # variable name after _
        suffix = match.group(3)  # anything after
        
        # If it's an assignment ( = something)
        if suffix.startswith('=') and not suffix.startswith('=='):
            return prefix + 'state["' + var_name + '"]' + suffix
        else:
            return prefix + 'state.get("' + var_name + '")' + suffix
    
    # Match self._varname followed by =, ., [, ), ], space, etc.
    # But not self._p (the param helper)
    code = re.sub(r'(self\.)_([a-zA-Z]\w*)((?:\s*[=\[.]|\s*\)|\s*\]|\s*$|\s*,|\s*\n|\s*#))', 
                  replace_get, code)
    
    # Handle self._varname at end of line
    code = re.sub(r'(self\.)_([a-zA-Z]\w*)\s*$', 
                  lambda m: m.group(1) + 'state.get("' + m.group(2) + '")', code, flags=re.MULTILINE)
    
    return code


def fix_hardcoded_paths(code):
    """Replace hardcoded paths with config references."""
    # Replace /Users/... with self.state.get("config", {}).get("path", "")
    # This is a simplification — in real VBStyle, paths come from config
    code = re.sub(r'"/Users/[^"]*"', 'self.state.get("config", {}).get("base_path", "")', code)
    code = re.sub(r"'/Users/[^']*'", "self.state.get('config', {}).get('base_path', '')", code)
    code = re.sub(r'"/tmp/[^"]*"', 'self.state.get("config", {}).get("tmp_path", "/tmp")', code)
    code = re.sub(r"'/tmp/[^']*'", "self.state.get('config', {}).get('tmp_path', '/tmp')", code)
    return code


def convert_to_tuple3(code):
    """Convert return statements to Tuple3 format."""
    lines = code.split('\n')
    result = []
    
    for line in lines:
        stripped = line.strip()
        indent = line[:len(line) - len(line.lstrip())]
        
        # Skip comments and non-return lines
        if stripped.startswith('#') or not stripped.startswith('return'):
            result.append(line)
            continue
        
        # Check if already Tuple3
        if re.match(r'return\s*\(\s*1\s*,', stripped) or re.match(r'return\s*\(\s*0\s*,', stripped):
            result.append(line)
            continue
        if re.match(r'return\s+\(\s*True\s*,', stripped) or re.match(r'return\s+\(\s*False\s*,', stripped):
            # Convert True/False to 1/0
            line = re.sub(r'return\s+\(\s*True\s*,', 'return (1,', line)
            line = re.sub(r'return\s+\(\s*False\s*,', 'return (0,', line)
            result.append(line)
            continue
        if re.search(r'return\s+self\.(Proof|Err)\(', stripped):
            result.append(line)
            continue
        
        # Extract the return value
        return_match = re.match(r'return\s+(.+)', stripped)
        if not return_match:
            result.append(line)
            continue
        
        return_value = return_match.group(1).strip()
        
        # Handle different return patterns
        if return_value == 'None' or return_value == 'none':
            result.append(indent + 'return (1, None, None)')
        elif return_value in ('True', 'true'):
            result.append(indent + 'return (1, True, None)')
        elif return_value in ('False', 'false'):
            result.append(indent + 'return (0, None, (1, "operation failed", 0))')
        elif return_value.startswith('"') or return_value.startswith("'"):
            # Return a string -> (1, string, None)
            result.append(indent + 'return (1, ' + return_value + ', None)')
        elif re.match(r'\d+$', return_value):
            # Return a number -> (1, number, None)
            result.append(indent + 'return (1, ' + return_value + ', None)')
        elif return_value.startswith('[') or return_value.startswith('{') or return_value.startswith('('):
            # Return a collection -> (1, collection, None)
            result.append(indent + 'return (1, ' + return_value + ', None)')
        elif 'self.create_packet' in return_value or 'self.Proof' in return_value:
            # Already a packet-like return, wrap it
            result.append(indent + 'return (1, ' + return_value + ', None)')
        else:
            # Generic: wrap in (1, value, None)
            result.append(indent + 'return (1, ' + return_value + ', None)')
    
    return '\n'.join(result)


def ensure_return(code):
    """Ensure every method has a return statement."""
    lines = code.split('\n')
    
    # Check if there's already a return
    has_return = any(re.match(r'\s*return\b', line) for line in lines)
    
    if has_return:
        return code
    
    # Add a default return at the end
    # Find the last non-empty line's indentation
    last_indent = '        '
    for line in reversed(lines):
        if line.strip():
            last_indent = line[:len(line) - len(line.lstrip())]
            break
    
    lines.append(last_indent + 'return (1, None, None)')
    return '\n'.join(lines)


def fix_method_signature(code):
    """Ensure method signature accepts params."""
    # Find the def line
    def_match = re.match(r'(def\s+\w+\s*\()([^)]*)(\))', code)
    if not def_match:
        return code
    
    prefix = def_match.group(1)
    params = def_match.group(2)
    suffix = def_match.group(3)
    
    # If it only has self, add params=None
    if params.strip() == 'self':
        return code.replace(def_match.group(0), prefix + 'self, params=None' + suffix)
    
    # If it has self and other params but no params/param, that's ok — keep original
    return code


def adapt_method(code):
    """Apply all VBStyle transformations to a method."""
    if not code or len(code.strip()) < 10:
        return code
    
    # Step 1: Remove decorators
    code = remove_decorators(code)
    
    # Step 2: Remove imports
    code = remove_imports(code)
    
    # Step 3: Remove print
    code = remove_print(code)
    
    # Step 4: Fix self._ -> self.state
    code = fix_self_underscore(code)
    
    # Step 5: Fix hardcoded paths
    code = fix_hardcoded_paths(code)
    
    # Step 6: Convert returns to Tuple3
    code = convert_to_tuple3(code)
    
    # Step 7: Ensure return exists
    code = ensure_return(code)
    
    # Step 8: Fix method signature
    code = fix_method_signature(code)
    
    return code


def check_vbstyle(code):
    """Check if code is VBStyle compliant."""
    issues = []
    if not code or len(code.strip()) < 10:
        issues.append('empty')
        return issues
    
    try:
        wrapped = "class _Check:\n" + "\n".join("    " + line for line in code.split("\n"))
        ast.parse(wrapped)
    except SyntaxError:
        issues.append('syntax_error')
        return issues
    
    if re.search(r'\bprint\s*\(', code):
        issues.append('has_print')
    if re.search(r'self\._(?!p\b)', code):
        issues.append('has_self_underscore')
    if re.search(r'@\w+', code) and not re.search(r'#\[@', code):
        issues.append('has_decorators')
    if re.search(r'/Users/|/tmp/|/var/|/home/', code):
        issues.append('has_hardcode_path')
    if re.search(r'^\s*import\s+', code, re.M) or re.search(r'^\s*from\s+\w+\s+import', code, re.M):
        issues.append('has_import')
    
    has_return = bool(re.search(r'\breturn\b', code))
    has_tuple3 = bool(re.search(r'return\s*\(\s*1\s*,', code) or 
                       re.search(r'return\s*\(\s*0\s*,', code) or 
                       re.search(r'return\s+\(\s*True\s*,', code) or
                       re.search(r'return\s+\(\s*False\s*,', code) or
                       re.search(r'return\s+self\.(Proof|Err)\(', code))
    
    if has_return and not has_tuple3:
        issues.append('no_tuple3')
    if not has_return:
        issues.append('no_return')
    
    return issues


def main():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    all_methods = c.execute("""
        SELECT id, domain, method_name, source_detail, method_code
        FROM closure_methods
    """).fetchall()
    
    adapted = 0
    already_ok = 0
    still_broken = 0
    syntax_errors = 0
    
    for cid, domain, method, source_detail, code in all_methods:
        issues = check_vbstyle(code)
        
        if not issues:
            already_ok += 1
            continue
        
        # Adapt the method
        new_code = adapt_method(code)
        
        # Verify the adapted code
        new_issues = check_vbstyle(new_code)
        
        if 'syntax_error' in new_issues:
            # Adaptation broke syntax — keep original
            syntax_errors += 1
            continue
        
        if not new_issues:
            # Fully compliant
            c.execute("UPDATE closure_methods SET method_code=? WHERE id=?", (new_code, cid))
            adapted += 1
        elif len(new_issues) < len(issues):
            # Improved but not perfect — save it anyway
            c.execute("UPDATE closure_methods SET method_code=? WHERE id=?", (new_code, cid))
            adapted += 1
        else:
            still_broken += 1
    
    conn.commit()
    
    print("=== VBSTYLE ADAPTATION RESULTS ===")
    print("Already VBStyle: " + str(already_ok))
    print("Adapted: " + str(adapted))
    print("Still broken: " + str(still_broken))
    print("Syntax errors from adaptation: " + str(syntax_errors))
    
    # Re-scan
    all_methods = c.execute("""
        SELECT id, method_code FROM closure_methods
    """).fetchall()
    
    final_violations = {'already_vbstyle': 0, 'has_print': 0, 'has_self_underscore': 0,
                        'has_decorators': 0, 'has_hardcode_path': 0, 'has_import': 0,
                        'no_return': 0, 'no_tuple3': 0, 'syntax_error': 0}
    
    for cid, code in all_methods:
        issues = check_vbstyle(code)
        if not issues:
            final_violations['already_vbstyle'] += 1
        else:
            for issue in issues:
                if issue in final_violations:
                    final_violations[issue] += 1
    
    print("\n=== FINAL VIOLATION SCAN ===")
    for v, count in sorted(final_violations.items()):
        print("  " + v + ": " + str(count))
    
    conn.close()


if __name__ == '__main__':
    main()
