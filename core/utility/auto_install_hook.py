# [@GHOST]{[@file<auto_install_hook.py>][@domain<utility>][@role<self_healing_import>][@auth<devin>][@date<2026-06-29>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<self_healing_import>][@return<Tuple3>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{AutoInstallFinder — sys.meta_path finder that self-heals ANY missing import at runtime by asking DomSystem to resolve + pip install the matching wheel, then retrying. No hardcoded module list.}
# [@CLASS]{AutoInstallFinder}
# [@METHOD]{find_spec,install,read_state,set_config}

"""
AutoInstallFinder — self-healing import hook.

WHAT IT DOES:
  Registers a finder at the END of sys.meta_path. When Python cannot find a
  module (every normal finder has failed), this finder asks the package
  authority (core.Dom_Unified.DomSystem -> core.utility.PackageManager) to
  resolve the missing module to a pip package and install it, then retries the
  import. No hardcoded module list — ANY missing third-party import is healed
  at runtime, including submodules that live in a separate pip wheel (e.g.
  PyQt6.QtWebEngineWidgets -> PyQt6-WebEngine, not just PyQt6).

WHY A META_PATH FINDER (not a try/except list):
  A curated "required modules" list is still a human manually deciding which
  errors to handle. A meta_path finder catches EVERY ModuleNotFoundError
  anywhere in the process — in this file, in a dependency, in a plugin loaded
  six months from now — and heals it the same way. The code does it itself.

USAGE:
    from auto_install_hook import install
    install()                                   # silent
    install(progress=my_loading_screen)         # with UI feedback
    # ... now `import anything_missing` just works

PROGRESS CALLBACK:
    Called as progress(event, **kwargs). Events:
      "resolve_start"  module=,           -> about to resolve a missing module
      "install_start"  module=, pip=,     -> pip install beginning
      "install_ok"     module=, pip=,     -> installed + import verified
      "install_fail"   module=, pip=,     -> installed but import still fails
      "no_pip"         module=, message=  -> resolve says no pip package
      "resolve_fail"   module=, error=    -> DomSystem returned an error
      "authority_fail" error=             -> could not load the package authority
      "error"          module=, error=    -> unexpected exception
"""

import sys
import os
import importlib
import importlib.abc
import importlib.util
import threading


# Modules the finder must NEVER try to auto-install. These are either stdlib
# (pip cannot provide them) or bootstrap-critical (importing them during
# resolution would recurse). Normal finders handle these; we only act when they
# have already failed, but this set is a safety net against edge cases.
_NEVER_RESOLVE = {
    "os", "sys", "re", "json", "ast", "importlib", "subprocess",
    "threading", "encodings", "builtins", "_frozen_importlib",
    "_frozen_importlib_external", "zipimport", "posixpath", "ntpath",
    "genericpath", "stat", "io", "codecs", "warnings", "_collections_abc",
    "collections", "functools", "types", "typing", "weakref", "heapq",
    "keyword", "token", "tokenize", "linecache", "traceback", "abc",
    "signal", "errno", "itertools", "operator", "reprlib", "copyreg",
    "contextlib", "enum", "math", "time", "datetime", "locale",
    "zlib", "bz2", "lzma", "gzip", "tarfile", "zipfile", "shutil",
    "tempfile", "fnmatch", "glob", "pathlib", "urllib", "http",
    "socket", "select", "ssl", "hashlib", "hmac", "secrets",
    "base64", "binascii", "uuid", "pickle", "copy", "struct",
    "logging", "string", "textwrap", "unicodedata", "inspect",
    "dis", "opcode", "codecs", "queue", "multiprocessing",
    "concurrent", "asyncio", "configparser", "argparse",
    "platform", "ctypes", "mmap", "fcntl", "resource",
    "Dom_Unified", "core",
}


class AutoInstallFinder(importlib.abc.MetaPathFinder):
    """
    Meta-path finder that self-heals missing imports via the package authority.
    VBStyle spirit: self.state dict, no print, no self._, Tuple3 internally.
    find_spec is required by the importlib.abc.MetaPathFinder protocol.
    """

    def __init__(self, mem=None, db=None, param=None):
        cfg = param or {}
        self.state = {
            "config": {
                "progress": cfg.get("progress", None),
                "dry_run": cfg.get("dry_run", False),
                "max_resolve_attempts": cfg.get("max_resolve_attempts", 1),
            },
            "authority": None,
            "authority_kind": None,
            "resolving": threading.local(),
            "stats": {
                "resolve_starts": 0,
                "install_starts": 0,
                "install_ok": 0,
                "install_fail": 0,
                "no_pip": 0,
                "resolve_fail": 0,
                "errors": 0,
            },
            "installed_pips": [],
        }

    def _p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    def read_state(self, params=None):
        return (1, dict(self.state), None)

    def set_config(self, params):
        if not params:
            return (0, None, ("ERR_PARAMS", "config values required", 0))
        for key, val in params.items():
            if key in self.state["config"]:
                self.state["config"][key] = val
        return (1, dict(self.state["config"]), None)

    def _progress(self, event, **kwargs):
        cb = self.state["config"]["progress"]
        if cb:
            try:
                cb(event, **kwargs)
            except Exception:
                pass

    # ════════════════════════════════════════════
    # PACKAGE AUTHORITY — DomSystem first, PackageManager fallback
    # ════════════════════════════════════════════

    def _load_authority(self):
        """Eagerly load the package authority so find_spec never triggers
        re-entrant imports of Dom_Unified (which could recurse into us).
        Returns (ok, kind, error)."""
        if self.state["authority"] is not None:
            return (1, self.state["authority_kind"], None)
        # Try DomSystem (the "system" manager) first.
        try:
            from Dom_Unified import DomSystem
            self.state["authority"] = DomSystem()
            self.state["authority_kind"] = "domsystem"
            return (1, "domsystem", None)
        except Exception as exc:
            dom_err = str(exc)
        # Fallback: direct PackageManager (lighter, fewer deps).
        try:
            from core.utility.package_manager import PackageManager
            self.state["authority"] = PackageManager()
            self.state["authority_kind"] = "packagemanager"
            return (1, "packagemanager", None)
        except Exception as exc2:
            self.state["authority"] = None
            return (0, None, ("ERR_AUTHORITY",
                              "DomSystem: %s | PackageManager: %s" % (dom_err, str(exc2)), 0))

    def _resolve_and_install(self, module):
        """Ask the authority to resolve + pip install the module.
        Returns (ok, data, error) Tuple3."""
        ok, kind, err = self._load_authority()
        if not ok:
            return (0, None, err)
        authority = self.state["authority"]
        call = {"module": module, "dry_run": self.state["config"]["dry_run"]}
        if kind == "domsystem":
            return authority.Run("package", {"action": "resolve", **call})
        return authority.Run("resolve_import", call)

    # ════════════════════════════════════════════
    # META PATH FINDER PROTOCOL
    # ════════════════════════════════════════════

    def find_spec(self, fullname, path=None, target=None):
        # Recursion guard: if we are already resolving a missing import, do not
        # re-enter (the installer's own imports must not trigger another install
        # attempt — that would infinite-loop or deadlock).
        if getattr(self.state["resolving"], "active", False):
            return None
        top = fullname.split(".")[0]
        if top in _NEVER_RESOLVE:
            return None
        self.state["resolving"].active = True
        try:
            self.state["stats"]["resolve_starts"] += 1
            self._progress("resolve_start", module=fullname)
            ok, data, err = self._resolve_and_install(fullname)
            if not ok:
                self.state["stats"]["resolve_fail"] += 1
                self._progress("resolve_fail", module=fullname, error=err)
                return None
            pip_name = data.get("pip_name") if isinstance(data, dict) else None
            if not pip_name:
                # resolve said "already installed" or "stdlib" — but we are here
                # because the import failed. Nothing more we can do.
                self.state["stats"]["no_pip"] += 1
                msg = data.get("message", "") if isinstance(data, dict) else ""
                self._progress("no_pip", module=fullname, message=msg)
                return None
            self.state["stats"]["install_starts"] += 1
            self._progress("install_start", module=fullname, pip=pip_name)
            # pip install has now run (resolve_import installs by default).
            # Invalidate caches so the freshly-installed package is visible.
            importlib.invalidate_caches()
            # Retry: temporarily remove ourselves so standard finders get a
            # clean chance at the now-installed module.
            self.state["resolving"].active = False
            sys.meta_path.remove(self)
            try:
                spec = importlib.util.find_spec(fullname)
            finally:
                sys.meta_path.append(self)
                self.state["resolving"].active = True
            if spec is not None:
                self.state["stats"]["install_ok"] += 1
                if pip_name not in self.state["installed_pips"]:
                    self.state["installed_pips"].append(pip_name)
                self._progress("install_ok", module=fullname, pip=pip_name)
            else:
                self.state["stats"]["install_fail"] += 1
                self._progress("install_fail", module=fullname, pip=pip_name)
            return spec
        except Exception as exc:
            self.state["stats"]["errors"] += 1
            self._progress("error", module=fullname, error=str(exc))
            return None
        finally:
            self.state["resolving"].active = False


# ════════════════════════════════════════════
# MODULE-LEVEL INSTALL HELPER
# ════════════════════════════════════════════

def install(progress=None, dry_run=False, project_root=None):
    """Create an AutoInstallFinder, eagerly load its package authority, and
    append it to the END of sys.meta_path. Returns the finder (or None if the
    authority could not be loaded and no_fallback is False).

    project_root: if given, prepended to sys.path so Dom_Unified / core.utility
                  is importable. If None, inferred from this file's location
                  (core/utility/ -> repo root two levels up).
    """
    if project_root is None:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    core_root = os.path.join(project_root, "core")
    for p in (project_root, core_root):
        if p not in sys.path:
            sys.path.insert(0, p)
    finder = AutoInstallFinder(param={"progress": progress, "dry_run": dry_run})
    ok, kind, err = finder._load_authority()
    if not ok:
        if progress:
            progress("authority_fail", error=str(err))
        # Still install the finder — it will retry authority load lazily and
        # fail gracefully per-module if the authority never becomes available.
    # Append at END: normal finders get first chance; we only heal truly-missing.
    if finder not in sys.meta_path:
        sys.meta_path.append(finder)
    return finder
