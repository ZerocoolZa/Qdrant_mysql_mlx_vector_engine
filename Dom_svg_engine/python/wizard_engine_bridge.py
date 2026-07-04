#!/usr/bin/env python3
"""
wizard_engine_bridge.py — ctypes bridge to the C Wizard SVG Animation Engine.

Provides a Python interface to:
  - Load/save JSON scene files
  - Generate SVG output
  - Build scenes programmatically
  - Run the compiled C engine
"""

import ctypes
import os
import subprocess
from pathlib import Path
from typing import Optional

# Engine paths
ENGINE_DIR = Path(__file__).parent.parent / "c"
LIB_PATH = ENGINE_DIR / "libwizard_engine.dylib"
CLI_PATH = ENGINE_DIR / "wizard_engine"


class WizardEngineBridge:
    """Bridge to the compiled C wizard engine."""

    def __init__(self, lib_path: Optional[str] = None):
        self.lib_path = lib_path or str(LIB_PATH)
        self.cli_path = str(CLI_PATH)
        self._lib = None
        # Don't load the dylib — use CLI subprocess for all operations
        # (ctypes with large structs is fragile)

    def _load_lib(self):
        """Load the shared library (lazy, only if needed)."""
        if self._lib is not None:
            return
        if not os.path.exists(self.lib_path):
            raise FileNotFoundError(
                f"Engine library not found at {self.lib_path}. "
                "Run 'make' in the c/ directory first."
            )
        self._lib = ctypes.CDLL(self.lib_path)
        self._setup_signatures()

    def _setup_signatures(self):
        lib = self._lib

        # Scene management
        lib.scene_init.argtypes = [ctypes.c_void_p]
        lib.scene_set_name.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.scene_set_size.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        lib.scene_set_background.argtypes = [
            ctypes.c_void_p, ctypes.c_float, ctypes.c_float, ctypes.c_float
        ]
        lib.scene_set_duration.argtypes = [ctypes.c_void_p, ctypes.c_float]

        # JSON parse/export
        lib.parse_scene_json.argtypes = [ctypes.c_char_p, ctypes.c_void_p]
        lib.parse_scene_json.restype = ctypes.c_int

        lib.load_scene_file.argtypes = [ctypes.c_char_p, ctypes.c_void_p]
        lib.load_scene_file.restype = ctypes.c_int

        lib.export_svg.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.export_svg.restype = ctypes.c_int

        lib.export_svg_to_string.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int
        ]
        lib.export_svg_to_string.restype = ctypes.c_int

    def load_scene(self, json_str: str) -> bytes:
        """Load a scene from a JSON string into a raw scene buffer."""
        # Scene struct is large (~6MB) due to particle arrays
        scene_buf = ctypes.create_string_buffer(8 * 1024 * 1024)  # 8MB
        self._lib.scene_init(scene_buf)
        result = self._lib.parse_scene_json(
            json_str.encode("utf-8"), scene_buf
        )
        if result != 0:
            raise ValueError(f"Failed to parse scene JSON (error {result})")
        return scene_buf

    def load_scene_file(self, filepath: str) -> bytes:
        """Load a scene from a JSON file."""
        scene_buf = ctypes.create_string_buffer(8 * 1024 * 1024)  # 8MB
        self._lib.scene_init(scene_buf)
        result = self._lib.load_scene_file(
            filepath.encode("utf-8"), scene_buf
        )
        if result != 0:
            raise ValueError(f"Failed to load scene file: {filepath}")
        return scene_buf

    def export_svg_file(self, scene_buf: bytes, output_path: str) -> int:
        """Export a scene to an SVG file."""
        result = self._lib.export_svg(scene_buf, output_path.encode("utf-8"))
        if result != 0:
            raise RuntimeError(f"Failed to export SVG to {output_path}")
        return result

    def export_svg_string(self, scene_buf: bytes, max_len: int = 1048576) -> str:
        """Export a scene to an SVG string."""
        output = ctypes.create_string_buffer(max_len)
        n = self._lib.export_svg_to_string(scene_buf, output, max_len)
        if n < 0:
            raise RuntimeError("Failed to export SVG to string")
        return output.raw[:n].decode("utf-8")

    def render_json_to_svg(self, json_str: str, output_path: str) -> int:
        """Convenience: load JSON scene and export SVG in one call."""
        scene_buf = self.load_scene(json_str)
        return self.export_svg_file(scene_buf, output_path)

    def render_json_to_svg_string(self, json_str: str) -> str:
        """Convenience: load JSON scene and return SVG string."""
        scene_buf = self.load_scene(json_str)
        return self.export_svg_string(scene_buf)

    def run_cli(self, scene_path: str, output_path: str) -> str:
        """Run the CLI engine directly."""
        result = subprocess.run(
            [self.cli_path, scene_path, output_path],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"Engine CLI failed: {result.stderr}")
        return result.stderr

    def run_demo(self, output_path: str) -> str:
        """Generate the built-in wizard demo scene."""
        result = subprocess.run(
            [self.cli_path, "--demo", output_path],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"Demo failed: {result.stderr}")
        return result.stderr

    def run_mcp_demo(self, output_path: str) -> str:
        """Generate the built-in MCP node graph demo."""
        result = subprocess.run(
            [self.cli_path, "--mcp-demo", output_path],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"MCP demo failed: {result.stderr}")
        return result.stderr
