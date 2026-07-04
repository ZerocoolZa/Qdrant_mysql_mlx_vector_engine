#!/usr/bin/env python3
#[@GHOST]{file_path="core/Dom_Common/__init__.py" date="2026-07-04" author="devin" session_id="bcl-common-module" context="Dom_Common package init. Exports ClassBCL, ClassRules, ClassGraph, ClassTest, ClassErrors."}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3"}
#[@FILEID]{id="__init__.py" domain="dom_common" authority="package"}
#[@SUMMARY]{summary="Dom_Common package — 5 shared classes: ClassBCL, ClassRules, ClassGraph, ClassTest, ClassErrors."}

"""Dom_Common — Shared module between C BCL units and Python domains.

Classes:
  ClassBCL    — BCL packet parser/writer
  ClassRules  — Rule checking, editing, updating, creating
  ClassGraph  — Wraps Reports v4 execution graph / code structure / code flow
  ClassTest   — Wraps ClassTester from Reports v4 for in-Python testing
  ClassErrors — Self-learning error→fix system with live debugging / hot-fix
"""

try:
    from .ClassBCL import ClassBCL
    from .ClassRules import ClassRules
    from .ClassGraph import ClassGraph
    from .ClassTest import ClassTest
    from .ClassErrors import ClassErrors
except ImportError:
    from ClassBCL import ClassBCL
    from ClassRules import ClassRules
    from ClassGraph import ClassGraph
    from ClassTest import ClassTest
    from ClassErrors import ClassErrors

__all__ = ["ClassBCL", "ClassRules", "ClassGraph", "ClassTest", "ClassErrors"]
