#!/usr/bin/env python3
#[@REVIEW]{[@date<2026-06-29>][@reviewer<devin>][@status<warn>][@notes<DomainLoader: loads and instantiates domain classes from DB. Has Run() dispatch and Tuple3 returns and _p helper. BUT: NO VBStyle identity headers (no GHOST/VBSTYLE/FILEID/SUMMARY/CLASS/METHOD). Uses self._GetConfig/self._GetClass/self._Instantiate/self._ListClasses/self._ListConstants (self._ violation -- only _p is allowed). Uses typing imports (Any, Dict, Tuple). No print/decorators. No hardcoded /Users/wws/ path (uses Path(__file__).parent).>][@todos<1. Add VBStyle identity headers (GHOST/VBSTYLE/FILEID/SUMMARY/CLASS/METHOD). 2. Rename self._GetConfig/self._GetClass/self._Instantiate/self._ListClasses/self._ListConstants to PascalCase without self._ prefix. 3. Remove typing imports (Any, Dict, Tuple) -- not VBStyle.>]}
"""
Domain Loader - Launch unified domain from database.
Reads Config constants and class definitions from DB, instantiates classes dynamically.
"""
import sqlite3
import ast
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "dom_graph_work.db"


class DomainLoader:
    """Load and instantiate domain classes from database."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        self.conn = sqlite3.connect(self.db_path)
        self.cur = self.conn.cursor()
        self.config_cache = {}
        self.class_cache = {}
    def Run(self, command: str, params: Dict = None) -> Tuple[int, Any, Any]:
        """Dispatch method."""
        params = params or {}
        if command == "get_config":
            return self.GetConfig(params)
        elif command == "get_class":
            return self.GetClass(params)
        elif command == "instantiate":
            return self.Instantiate(params)
        elif command == "list_classes":
            return self.ListClasses(params)
        elif command == "list_constants":
            return self.ListConstants(params)
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown command: {command}", 0))
        return (0, None, ("UNKNOWN_COMMAND", f"Unknown command: {command}", 0))
    def _p(self, params: Dict, key: str, default: Any = None) -> Any:
        """Helper to get param value."""
        if not params:
            return (1, default, None)
        return (1, params.get(key, default), None)
        return params.get(key, default)
    def GetConfig(self, params: Dict) -> Tuple[int, Any, Any]:
        """Get a Config constant from DB."""
        name = self._p(params, "name", "")
        if not name:
            # Return all constants
            self.cur.execute("SELECT name, value, type FROM config_constants")
            result = {row[0]: (row[2], row[1]) for row in self.cur.fetchall()}
            return (1, result, None)
        
        self.cur.execute("SELECT value, type FROM config_constants WHERE name = ?", (name,))
        row = self.cur.fetchone()
        if not row:
            return (0, None, ("CONSTANT_NOT_FOUND", f"Config constant not found: {name}", 0))
        
        value_str, type_ = row
        # Convert string back to proper type
        if type_ == "int":
            value = int(value_str)
        elif type_ == "float":
            value = float(value_str)
        elif type_ == "list":
            value = ast.literal_eval(value_str)
        elif type_ == "dict":
            value = ast.literal_eval(value_str)
        else:
            value = value_str
        
        return (1, value, None)
        return (1, value, None)
    def GetClass(self, params: Dict) -> Tuple[int, Any, Any]:
        """Get class definition from DB."""
        class_name = self._p(params, "class_name", "")
        if not class_name:
            return (0, None, ("MISSING_PARAM", "class_name required", 0))
        
        self.cur.execute("SELECT file, class_text, lineno FROM class_registry WHERE class_name = ?", (class_name,))
        row = self.cur.fetchone()
        if not row:
            return (0, None, ("CLASS_NOT_FOUND", f"Class not found: {class_name}", 0))
        
        file, class_text, lineno = row
        return (1, {"file": file, "class_text": class_text, "lineno": lineno}, None)
        return (1, {"file": file, "class_text": class_text, "lineno": lineno}, None)
    def _ListClasses(self, params: Dict) -> Tuple[int, Any, Any]:
        """List all classes in registry."""
        self.cur.execute("SELECT class_name, file, method_count FROM class_registry ORDER BY class_name")
        classes = [{"name": row[0], "file": row[1], "methods": row[2]} for row in self.cur.fetchall()]
        return (1, classes, None)
        return (1, classes, None)
    def _ListConstants(self, params: Dict) -> Tuple[int, Any, Any]:
        """List all Config constants."""
        self.cur.execute("SELECT name, type, description FROM config_constants ORDER BY name")
        constants = [{"name": row[0], "type": row[1], "description": row[2]} for row in self.cur.fetchall()]
        return (1, constants, None)
        return (1, constants, None)
    def Instantiate(self, params: Dict) -> Tuple[int, Any, Any]:
        """Instantiate a class from the actual Python file (not from DB code)."""
        class_name = self._p(params, "class_name", "")
        if not class_name:
            return (0, None, ("MISSING_PARAM", "class_name required", 0))
        
        # Get the file where this class is defined
        self.cur.execute("SELECT file FROM class_registry WHERE class_name = ?", (class_name,))
        row = self.cur.fetchone()
        if not row:
            return (0, None, ("CLASS_NOT_FOUND", f"Class not found: {class_name}", 0))
        
        file = row[0]
        module_name = file.replace(".py", "")
        
        # Import the module and get the class
        sys.path.insert(0, str(BASE_DIR))
        try:
            module = __import__(module_name)
            cls = getattr(module, class_name)
            instance = cls()
            return (1, instance, None)
        except Exception as e:
            return (0, None, ("INSTANTIATION_ERROR", str(e), 0))
            return (0, None, ("INSTANTIATION_ERROR", str(e), 0))


def main():
    """Test the domain loader."""
    loader = DomainLoader()
    
    # List all classes
    result = loader.Run("list_classes")
    if result[0] == 1:
        pass  # was print()}")
        for cls in result[1]:
            pass  # was print()
    
    # List all constants
    result = loader.Run("list_constants")
    if result[0] == 1:
        pass  # was print()}")
        for const in result[1]:
            pass  # was print()
    
    # Instantiate Config
    result = loader.Run("instantiate", {"class_name": "Config"})
    if result[0] == 1:
        cfg = result[1]
        pass  # was print()}")
        db_result = cfg.Run("build_db")
        pass  # was print()
        if db_result[0] == 1:
            pass  # was print()
    else:
        pass  # was print()
    
    # Instantiate a graph viewer
    result = loader.Run("instantiate", {"class_name": "SpecGraph"})
    if result[0] == 1:
        pass  # was print()}")
    else:
        pass  # was print()


if __name__ == "__main__":
    main()
