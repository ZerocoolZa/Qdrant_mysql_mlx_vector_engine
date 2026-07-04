#[@GHOST]{file_path="core/Dom_Benchmark/__init__.py" date="2026-07-04" author="Devin" session_id="benchmark-framework" context="Package init for Dom_Benchmark — Error Fix Benchmark Framework. Exports Runner, ErrorModel, FixCandidate, ValidationResult, Scoring, Config."}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
#[@FILEID]{id="__init__.py" domain="dom_benchmark" authority="PackageInit"}
#[@SUMMARY]{summary="Package init for Dom_Benchmark. Exports Runner, ErrorModel, FixCandidate, ValidationResult, Scoring, Config."}
#[@CLASS]{class="Dom_Benchmark" domain="dom_benchmark" authority="package"}

"""Dom_Benchmark — Error Fix Benchmark Framework.

A professional benchmarking framework for testing AI error fixing:
  Generator → Trigger → Capture → AI Fix → Apply → Re-run → Validate

Exports:
  - Runner: Core orchestration engine
  - ErrorModel: Single error test case
  - FixCandidate: A proposed fix
  - ValidationResult: Validation results for a fix
  - Scoring: Scoring engine
  - Config: Configuration constants
"""

from .Config import *
from .ErrorModel import ErrorModel, FixCandidate, ValidationResult
from .Scoring import Scoring
from .Runner import Runner

__all__ = [
    "Runner",
    "ErrorModel",
    "FixCandidate",
    "ValidationResult",
    "Scoring",
    "Config",
]
