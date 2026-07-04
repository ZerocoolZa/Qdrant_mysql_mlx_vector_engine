# [@GHOST]{[@file<package_manager.py>][@domain<utility>][@role<package_authority>][@auth<cascade>][@date<2026-06-27>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<cascade>][@role<package_authority>][@return<Tuple3>][@orch<Orchestrator>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<one_class_one_domain_one_authority_complete>]}
# [@SUMMARY]{PackageManager — scans .py files for imports, extracts pip packages, checks installed, installs missing, resolves import errors, generates requirements.txt.}
# [@CLASS]{PackageManager}
# [@METHOD]{Run,scan_imports,extract_pips,check_installed,install_missing,resolve_import,generate_requirements,catalog,read_state,set_config}

"""
PackageManager — the package authority.

WHAT IT DOES:
  1. SCAN_IMPORTS    — walk a folder, AST-parse all .py files, extract every import statement
  2. EXTRACT_PIPS    — map import names to pip package names (e.g. import cv2 -> pip install opencv-python)
  3. CHECK_INSTALLED — check which packages are already installed via importlib
  4. INSTALL_MISSING — pip install the ones that are missing
  5. RESOLVE_IMPORT  — given an ImportError, figure out which pip package provides it and install
  6. GENERATE_REQUIREMENTS — write a requirements.txt from all discovered imports
  7. CATALOG         — list all third-party packages used across the project

USAGE:
  from utility.package_manager import PackageManager

  pm = PackageManager()

  # Scan project for all imports
  ok, data, err = pm.Run("scan_imports", {"path": "/Users/wws/project"})

  # Extract pip package names from imports
  ok, data, err = pm.Run("extract_pips", {"imports": data["imports"]})

  # Check which are installed
  ok, data, err = pm.Run("check_installed", {"packages": ["numpy", "cv2", "flask"]})

  # Install missing ones
  ok, data, err = pm.Run("install_missing", {"path": "/Users/wws/project"})

  # Resolve a specific ImportError
  ok, data, err = pm.Run("resolve_import", {"module": "cv2"})

  # Generate requirements.txt
  ok, data, err = pm.Run("generate_requirements", {"path": "/Users/wws/project"})

  # Catalog all third-party packages
  ok, data, err = pm.Run("catalog", {"path": "/Users/wws/project"})
"""

import os
import ast
import sys
import subprocess
import importlib
import importlib.metadata


STDLIB_MODULES = {
    "os", "sys", "re", "ast", "json", "csv", "math", "time", "datetime",
    "collections", "itertools", "functools", "pathlib", "typing", "io",
    "string", "textwrap", "unicodedata", "enum", "abc", "copy", "pickle",
    "shutil", "tempfile", "glob", "fnmatch", "hashlib", "hmac", "secrets",
    "base64", "binascii", "uuid", "sqlite3", "threading", "multiprocessing",
    "queue", "socket", "ssl", "select", "asyncio", "logging", "warnings",
    "unittest", "doctest", "traceback", "inspect", "dis", "code", "codeop",
    "compile", "compileall", "py_compile", "importlib", "configparser",
    "argparse", "getpass", "getopt", "optparse", "difflib", "pprint",
    "reprlib", "enum", "dataclasses", "contextlib", "weakref", "types",
    "operator", "decimal", "fractions", "statistics", "random", "bisect",
    "heapq", "array", "struct", "codecs", "unicodedata", "xml", "html",
    "urllib", "http", "email", "mailbox", "mimetypes", "base64", "json",
    "xmlrpc", "ipaddress", "netrc", "nntplib", "smtplib", "telnetlib",
    "ftplib", "poplib", "imaplib", "ssl", "select", "signal", "mmap",
    "ctypes", "platform", "errno", "gc", "atexit", "trace", "pstats",
    "cProfile", "profile", "timeit", "resource", "posix", "nt", "pwd",
    "grp", "termios", "tty", "pty", "fcntl", "resource", "syslog",
    "winsound", "msvcrt", "_thread", "concurrent", "subprocess",
    "tomllib", "zipfile", "tarfile", "gzip", "bz2", "lzma", "zlib",
    "csv", "json", "plistlib", "token", "tokenize", "tabnanny",
    "keyword", "tokenize", "linecache", "codecs", "unicodedata",
    "locale", "gettext", "calendar", "zoneinfo",
}

PIP_NAME_MAP = {
    "cv2": "opencv-python",
    "PIL": "Pillow",
    "pil": "Pillow",
    "sklearn": "scikit-learn",
    "skimage": "scikit-image",
    "bs4": "beautifulsoup4",
    "yaml": "PyYAML",
    "Crypto": "pycryptodome",
    "OpenSSL": "pyOpenSSL",
    "magic": "python-magic",
    "docx": "python-docx",
    "pptx": "python-pptx",
    "fitz": "PyMuPDF",
    "lxml": "lxml",
    "serial": "pyserial",
    "usb": "pyusb",
    "bluepy": "bluepy",
    "bleak": "bleak",
    "PyQt5": "PyQt5",
    "PyQt6": "PyQt6",
    "PySide6": "PySide6",
    "tkinter": None,
    "matplotlib": "matplotlib",
    "numpy": "numpy",
    "pandas": "pandas",
    "scipy": "scipy",
    "flask": "Flask",
    "django": "Django",
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "requests": "requests",
    "aiohttp": "aiohttp",
    "httpx": "httpx",
    "tqdm": "tqdm",
    "rich": "rich",
    "click": "click",
    "typer": "typer",
    "pydantic": "pydantic",
    "sqlalchemy": "SQLAlchemy",
    "redis": "redis",
    "celery": "celery",
    "pytest": "pytest",
    "selenium": "selenium",
    "playwright": "playwright",
    "boto3": "boto3",
    "openai": "openai",
    "anthropic": "anthropic",
    "langchain": "langchain",
    "transformers": "transformers",
    "torch": "torch",
    "tensorflow": "tensorflow",
    "onnx": "onnx",
    "onnxruntime": "onnxruntime",
    "coremltools": "coremltools",
    "mlx": "mlx",
    "qdrant_client": "qdrant-client",
    "pinecone": "pinecone-client",
    "pinecone_client": "pinecone-client",
    "pymysql": "PyMySQL",
    "mysql": "mysql-connector-python",
    "mysql.connector": "mysql-connector-python",
    "psycopg2": "psycopg2-binary",
    "pymongo": "pymongo",
    "supabase": "supabase",
    "notion": "notion-client",
    "discord": "discord.py",
    "telegram": "python-telegram-bot",
    "slack_sdk": "slack-sdk",
    "whisper": "openai-whisper",
    "pyperclip": "pyperclip",
    "watchdog": "watchdog",
    "psutil": "psutil",
    "GPUtil": "GPUtil",
    "pynvml": "pynvml",
    "wmi": "WMI",
    "keyring": "keyring",
    "cryptography": "cryptography",
    "paramiko": "paramiko",
    "fabric": "fabric",
    "invoke": "invoke",
    "dotenv": "python-dotenv",
    "jinja2": "Jinja2",
    "mako": "Mako",
    "markdown": "markdown",
    "pygments": "Pygments",
    "sphinx": "Sphinx",
    "mkdocs": "mkdocs",
    "pelican": "pelican",
    "feedparser": "feedparser",
    "newspaper": "newspaper3k",
    "twint": "twint",
    "snscrape": "snscrape",
    "yt_dlp": "yt-dlp",
    "pytube": "pytube",
    "spotipy": "spotipy",
    "pydub": "pydub",
    "soundfile": "soundfile",
    "librosa": "librosa",
    "sounddevice": "sounddevice",
    "pyaudio": "pyaudio",
    "opencv": "opencv-python",
    "face_recognition": "face-recognition",
    "dlib": "dlib",
    "easyocr": "easyocr",
    "paddleocr": "paddleocr",
    " pytesseract": "pytesseract",
    "imutils": "imutils",
    "albumentations": "albumentations",
    "imgaug": "imgaug",
    "shapely": "shapely",
    "geopandas": "geopandas",
    "folium": "folium",
    "branca": "branca",
    "cartopy": "Cartopy",
    "rasterio": "rasterio",
    "netCDF4": "netCDF4",
    "xarray": "xarray",
    "dask": "dask",
    "vaex": "vaex",
    "polars": "polars",
    "modin": "modin",
    "ray": "ray",
    "dgl": "dgl",
    "dgllife": "dgllife",
    "torch_geometric": "torch-geometric",
    "torchvision": "torchvision",
    "torchaudio": "torchaudio",
    "timm": "timm",
    "huggingface_hub": "huggingface-hub",
    "datasets": "datasets",
    "accelerate": "accelerate",
    "peft": "peft",
    "trl": "trl",
    "bitsandbytes": "bitsandbytes",
    "xformers": "xformers",
    "flash_attn": "flash-attn",
    "deepspeed": "deepspeed",
    "accelerate": "accelerate",
    "optuna": "optuna",
    "ray_tune": "ray[tune]",
    "wandb": "wandb",
    "mlflow": "mlflow",
    "tensorboard": "tensorboard",
    "tensorboardX": "tensorboardX",
    "neptune": "neptune-client",
    "aim": "aim",
    "dvc": "dvc",
    "hydra": "hydra-core",
    "omegaconf": "omegaconf",
    "yacs": "yacs",
    "colorlog": "colorlog",
    "loguru": "loguru",
    "structlog": "structlog",
    "eli5": "eli5",
    "shap": "shap",
    "lime": "lime",
    "interpret": "interpret",
    "dtreeviz": "dtreeviz",
    "graphviz": "graphviz",
    "pydot": "pydot",
    "networkx": "networkx",
    "pyvis": "pyvis",
    "scipy_sparse": "scipy[sparse]",
    "sparse": "sparse",
    "cupy": "cupy",
    "numba": "numba",
    "cython": "Cython",
    "numexpr": "numexpr",
    "bottleneck": "Bottleneck",
    "tables": "tables",
    "h5py": "h5py",
    "zarr": "zarr",
    "openpyxl": "openpyxl",
    "xlsxwriter": "XlsxWriter",
    "xlrd": "xlrd",
    "xlwt": "xlwt",
    "odf": "odfpy",
    "pypdf": "pypdf",
    "pypdf2": "PyPDF2",
    "pdfplumber": "pdfplumber",
    "pdfminer": "pdfminer.six",
    "reportlab": "reportlab",
    "fpdf": "fpdf2",
    "weasyprint": "weasyprint",
    "xlsx2html": "xlsx2html",
    "tabulate": "tabulate",
    "texttable": "texttable",
    "prettytable": "prettytable",
    "asciitable": "asciitable",
    "terminaltables": "terminaltables",
    "colorama": "colorama",
    "termcolor": "termcolor",
    "colored": "colored",
    "crayons": "crayons",
    "blessed": "blessed",
    "prompt_toolkit": "prompt-toolkit",
    "inquirer": "inquirer",
    "questionary": "questionary",
    "urwid": "urwid",
    "textual": "textual",
    "asciimatics": "asciimatics",
    "curses": None,
    "win32com": "pywin32",
    "win32api": "pywin32",
    "win32gui": "pywin32",
    "win32con": "pywin32",
    "pythoncom": "pywin32",
    "pywintypes": "pywin32",
    "win32event": "pywin32",
    "win32process": "pywin32",
    "win32service": "pywin32",
    "servicemanager": "pywin32",
    "perfmon": "pywin32",
    "win32evtlog": "pywin32",
    "win32evtlogutil": "pywin32",
    "ntsecuritycon": "pywin32",
    "win32security": "pywin32",
    "win32cred": "pywin32",
    "sspi": "pywin32",
    "sspio": "pywin32",
    "mmsystem": "pywin32",
    "win32clipboard": "pywin32",
    "win32console": "pywin32",
    "win32help": "pywin32",
    "win32inet": "pywin32",
    "win32net": "pywin32",
    "win32pdh": "pywin32",
    "win32profile": "pywin32",
    "win32ras": "pywin32",
    "win32trace": "pywin32",
    "win32verstamp": "pywin32",
    "win32wnet": "pywin32",
    "winxpgui": "pywin32",
    "dde": "pywin32",
    "afxres": "pywin32",
    "multimedia": "pywin32",
    "commctrl": "pywin32",
    "dbi": "pywin32",
    "odbc": "pywin32",
    "mapi": "pywin32",
    "exchange": "pywin32",
    "exchdapi": "pywin32",
    "pythondialog": "pythondialog",
    "pexpect": "pexpect",
    "ptyprocess": "ptyprocess",
    "sh": "sh",
    "plumbum": "plumbum",
    "xonsh": "xonsh",
    "sarge": "sarge",
    "cmd2": "cmd2",
    "cliff": "cliff",
    "cement": "cement",
    "fire": "fire",
    "asciinema": "asciinema",
    "manhole": "manhole",
    "pudb": "pudb",
    "ipdb": "ipdb",
    "web_pdb": "web-pdb",
    "pdbpp": "pdbpp",
    "debugpy": "debugpy",
    "pydevd": "pydevd-pycharm",
    "py-spy": "py-spy",
    "austin": "austin",
    "memray": "memray",
    "filprofiler": "filprofiler",
    "pyinstrument": "pyinstrument",
    "scalene": "scalene",
    "yappi": "yappi",
    "viztracer": "viztracer",
    "hunter": "hunter",
    "manhole": "manhole",
    "pysnooper": "pysnooper",
    "loguru": "loguru",
    "structlog": "structlog",
    "pip": None,
    "setuptools": None,
    "wheel": None,
    "pkg_resources": None,
    "distutils": None,
    "venv": None,
    "ensurepip": None,
}

# SUBMODULE_PIP_MAP — full dotted module name -> pip sub-package.
# Needed because the top-level package (e.g. PyQt6) may import fine while a
# submodule (e.g. PyQt6.QtWebEngineWidgets) lives in a SEPARATE pip wheel
# (PyQt6-WebEngine). resolve_import checks the full dotted module first, then
# consults this map before falling back to the top-level PIP_NAME_MAP.
SUBMODULE_PIP_MAP = {
    "PyQt6.QtWebEngineWidgets": "PyQt6-WebEngine",
    "PyQt6.QtWebEngineCore": "PyQt6-WebEngine",
    "PyQt6.QtWebEngineQuick": "PyQt6-WebEngine",
    "PyQt5.QtWebEngineWidgets": "PyQt5-WebEngine",
    "PyQt5.QtWebEngineCore": "PyQt5-WebEngine",
    "PyQt5.QtWebEngineQuick": "PyQt5-WebEngine",
    "PySide6.QtWebEngineWidgets": "PySide6-WebEngine",
    "PySide6.QtWebEngineCore": "PySide6-WebEngine",
    "PySide6.QtWebEngineQuick": "PySide6-WebEngine",
    "PyQt6.QtMultimedia": "PyQt6-Multimedia",
    "PyQt6.QtMultimediaWidgets": "PyQt6-Multimedia",
    "PyQt6.QtNetwork": "PyQt6-Network",
    "PyQt6.QtPdf": "PyQt6-Pdf",
    "PyQt6.QtPdfWidgets": "PyQt6-Pdf",
    "PyQt6.QtCharts": "PyQt6-Charts",
    "PyQt6.QtDataVisualization": "PyQt6-DataVisualization",
    "PyQt6.QtWebSockets": "PyQt6-WebSockets",
    "PyQt6.QtSerialPort": "PyQt6-SerialPort",
    "PyQt6.QtSql": "PyQt6-Sql",
    "PyQt6.QtTest": "PyQt6-Test",
    "PyQt6.QtSvg": "PyQt6-Svg",
    "PyQt6.QtSvgWidgets": "PyQt6-Svg",
    "PyQt6.QtOpenGL": "PyQt6-OpenGL",
    "PyQt6.QtOpenGLWidgets": "PyQt6-OpenGL",
    "PyQt6.QtQml": "PyQt6-Qml",
    "PyQt6.QtQuick": "PyQt6-Quick",
    "PyQt6.QtQuick3D": "PyQt6-Quick3D",
    "PyQt6.QtQuickWidgets": "PyQt6-Quick",
    "PyQt6.QtPositioning": "PyQt6-Positioning",
    "PyQt6.QtLocation": "PyQt6-Location",
    "PyQt6.QtBluetooth": "PyQt6-Bluetooth",
    "PyQt6.QtNfc": "PyQt6-Nfc",
    "PyQt6.QtSensors": "PyQt6-Sensors",
    "PyQt6.QtSerialBus": "PyQt6-SerialBus",
    "PyQt6.QtRemoteObjects": "PyQt6-RemoteObjects",
    "PyQt6.QtTextToSpeech": "PyQt6-TextToSpeech",
    "PyQt6.QtWebEngine": "PyQt6-WebEngine",
    "PySide6.QtMultimedia": "PySide6-Multimedia",
    "PySide6.QtNetwork": "PySide6-Network",
    "PySide6.QtPdf": "PySide6-Pdf",
    "PySide6.QtCharts": "PySide6-Charts",
}


class PackageManager:
    """
    Package authority — scans, extracts, checks, installs, resolves, generates.
    VBStyle compliant: Run() dispatch, Tuple3 returns, self.state dict.
    """

    def __init__(self, mem=None, db=None, param=None):
        self.state = {
            "config": {
                "project_root": param.get("project_root", os.getcwd()) if param else os.getcwd(),
                "python_executable": param.get("python", sys.executable) if param else sys.executable,
                "dry_run": param.get("dry_run", False) if param else False,
                "upgrade": param.get("upgrade", False) if param else False,
                "exclude_stdlib": param.get("exclude_stdlib", True) if param else True,
            },
            "scanned_imports": [],
            "pip_packages": [],
            "installed": {},
            "missing": [],
            "requirements_path": None,
            "stats": {"scanned": 0, "extracted": 0, "installed": 0, "resolved": 0, "errors": 0},
        }
        if param:
            for key, val in param.items():
                if key in self.state["config"]:
                    self.state["config"][key] = val

    def Run(self, command, params=None):
        dispatch = {
            "scan_imports": self.cmd_scan_imports,
            "extract_pips": self.cmd_extract_pips,
            "check_installed": self.cmd_check_installed,
            "install_missing": self.cmd_install_missing,
            "resolve_import": self.cmd_resolve_import,
            "generate_requirements": self.cmd_generate_requirements,
            "catalog": self.cmd_catalog,
            "read_state": self.read_state,
            "set_config": self.set_config,
        }
        handler = dispatch.get(command)
        if not handler:
            return (0, None, ("ERR_UNKNOWN_CMD", "Unknown: " + str(command), 0))
        return handler(params or {})

    def read_state(self, params=None):
        safe = {k: v for k, v in self.state.items() if k not in ("conn",)}
        return (1, safe, None)

    def set_config(self, params):
        for key, val in params.items():
            if key in self.state["config"]:
                self.state["config"][key] = val
        return (1, dict(self.state["config"]), None)

    def p(self, params, key, default=None):
        if not params:
            return default
        return params.get(key, default)

    # ════════════════════════════════════════════
    # SCAN_IMPORTS — walk folder, AST-parse all .py files, extract imports
    # ════════════════════════════════════════════

    def cmd_scan_imports(self, params):
        path = self.p(params, "path")
        if not path or not os.path.isdir(path):
            return (0, None, ("ERR_PATH", "Invalid path: " + str(path), 0))
        all_imports = []
        py_files = []
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("__pycache__", "node_modules", ".git", "venv", "env", ".venv")]
            for fname in files:
                if fname.endswith(".py"):
                    py_files.append(os.path.join(root, fname))
        for pyfile in py_files:
            ok, data, err = self.extract_imports_from_file(pyfile)
            if ok and data["imports"]:
                all_imports.extend(data["imports"])
                self.state["stats"]["scanned"] += 1
        unique = {}
        for imp in all_imports:
            top = imp["module"].split(".")[0] if imp["module"] else imp.get("name", "").split(".")[0]
            if top and top not in unique:
                unique[top] = {
                    "module": top,
                    "is_stdlib": top in STDLIB_MODULES,
                    "files": [],
                    "import_type": imp["type"],
                }
            if top in unique:
                unique[top]["files"].append(imp["file"])
        third_party = [v for v in unique.values() if not v["is_stdlib"]] if self.state["config"]["exclude_stdlib"] else list(unique.values())
        self.state["scanned_imports"] = list(unique.values())
        return (1, {
            "scanned_files": len(py_files),
            "total_imports": len(all_imports),
            "unique_modules": len(unique),
            "third_party": len(third_party),
            "stdlib": len(unique) - len(third_party),
            "imports": all_imports,
            "modules": list(unique.values()),
            "third_party_modules": third_party,
        }, None)

    def extract_imports_from_file(self, filepath):
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
        except Exception as e:
            return (0, None, ("ERR_READ", str(e), 0))
        imports = []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return (1, {"file": filepath, "imports": [], "count": 0}, None)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({
                        "type": "import",
                        "module": alias.name,
                        "alias": alias.asname,
                        "lineno": node.lineno,
                        "file": filepath,
                    })
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append({
                        "type": "from",
                        "module": module,
                        "name": alias.name,
                        "alias": alias.asname,
                        "lineno": node.lineno,
                        "file": filepath,
                    })
        return (1, {"file": filepath, "imports": imports, "count": len(imports)}, None)

    # ════════════════════════════════════════════
    # EXTRACT_PIPS — map import names to pip package names
    # ════════════════════════════════════════════

    def cmd_extract_pips(self, params):
        imports = self.p(params, "imports")
        if not imports:
            modules = self.state.get("scanned_imports", [])
            if not modules:
                return (0, None, ("ERR_NO_IMPORTS", "Run scan_imports first or pass imports param", 0))
        else:
            modules = imports
        pip_packages = []
        seen = set()
        for mod in modules:
            if isinstance(mod, dict):
                mod_name = mod.get("module", "")
            else:
                mod_name = str(mod)
            if not mod_name or mod_name in STDLIB_MODULES:
                continue
            pip_name = PIP_NAME_MAP.get(mod_name, mod_name)
            if pip_name is None:
                continue
            if pip_name not in seen:
                seen.add(pip_name)
                pip_packages.append({
                    "import_name": mod_name,
                    "pip_name": pip_name,
                    "installed": None,
                })
                self.state["stats"]["extracted"] += 1
        self.state["pip_packages"] = pip_packages
        return (1, {
            "total": len(pip_packages),
            "packages": pip_packages,
        }, None)

    # ════════════════════════════════════════════
    # CHECK_INSTALLED — check which packages are installed
    # ════════════════════════════════════════════

    def cmd_check_installed(self, params):
        packages = self.p(params, "packages")
        if not packages:
            packages = [p["pip_name"] for p in self.state.get("pip_packages", [])]
            if not packages:
                return (0, None, ("ERR_NO_PACKAGES", "Run extract_pips first or pass packages param", 0))
        results = {}
        missing = []
        for pkg in packages:
            pip_name = pkg if isinstance(pkg, str) else pkg.get("pip_name", "")
            import_name = pkg if isinstance(pkg, str) else pkg.get("import_name", pip_name)
            is_installed = False
            version = None
            try:
                mod = importlib.import_module(import_name)
                is_installed = True
                try:
                    version = importlib.metadata.version(pip_name)
                except Exception:
                    version = getattr(mod, "__version__", "unknown")
            except ImportError:
                pass
            except Exception:
                pass
            if not is_installed:
                try:
                    version = importlib.metadata.version(pip_name)
                    is_installed = True
                except Exception:
                    pass
            results[pip_name] = {
                "import_name": import_name,
                "installed": is_installed,
                "version": version,
            }
            if not is_installed:
                missing.append(pip_name)
        self.state["installed"] = results
        self.state["missing"] = missing
        return (1, {
            "total": len(results),
            "installed": sum(1 for v in results.values() if v["installed"]),
            "missing": len(missing),
            "missing_packages": missing,
            "details": results,
        }, None)

    # ════════════════════════════════════════════
    # INSTALL_MISSING — pip install missing packages
    # ════════════════════════════════════════════

    def cmd_install_missing(self, params):
        path = self.p(params, "path")
        dry_run = self.p(params, "dry_run", self.state["config"]["dry_run"])
        upgrade = self.p(params, "upgrade", self.state["config"]["upgrade"])
        if path:
            ok, scan_data, scan_err = self.cmd_scan_imports({"path": path})
            if not ok:
                return (0, None, scan_err)
            ok, pip_data, pip_err = self.cmd_extract_pips({"imports": scan_data["modules"]})
            if not ok:
                return (0, None, pip_err)
            ok, check_data, check_err = self.cmd_check_installed({"packages": pip_data["packages"]})
            if not ok:
                return (0, None, check_err)
            missing = check_data["missing_packages"]
        else:
            missing = self.state.get("missing", [])
            if not missing:
                ok, check_data, check_err = self.cmd_check_installed({})
                if not ok:
                    return (0, None, check_err)
                missing = check_data["missing_packages"]
        if not missing:
            return (1, {"installed": [], "message": "All packages already installed"}, None)
        results = []
        python_exe = self.state["config"]["python_executable"]
        for pkg in missing:
            if dry_run:
                results.append({"package": pkg, "action": "dry_run", "success": True, "output": "Would install " + pkg})
                continue
            cmd = [python_exe, "-m", "pip", "install"]
            if upgrade:
                cmd.append("--upgrade")
            cmd.append(pkg)
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                success = proc.returncode == 0
                results.append({
                    "package": pkg,
                    "action": "install" if not upgrade else "upgrade",
                    "success": success,
                    "returncode": proc.returncode,
                    "stdout": proc.stdout[-500:] if proc.stdout else "",
                    "stderr": proc.stderr[-500:] if proc.stderr else "",
                })
                if success:
                    self.state["stats"]["installed"] += 1
                else:
                    self.state["stats"]["errors"] += 1
            except subprocess.TimeoutExpired:
                results.append({"package": pkg, "action": "install", "success": False, "error": "timeout"})
                self.state["stats"]["errors"] += 1
            except Exception as e:
                results.append({"package": pkg, "action": "install", "success": False, "error": str(e)})
                self.state["stats"]["errors"] += 1
        installed_count = sum(1 for r in results if r.get("success"))
        return (1, {
            "total": len(results),
            "installed": installed_count,
            "failed": len(results) - installed_count,
            "results": results,
        }, None)

    # ════════════════════════════════════════════
    # RESOLVE_IMPORT — given a module name, find and install the pip package
    # ════════════════════════════════════════════

    def cmd_resolve_import(self, params):
        module = self.p(params, "module")
        if not module:
            return (0, None, ("ERR_MODULE", "module name required", 0))
        top = module.split(".")[0]
        # stdlib short-circuit — but only when the requested module is not a
        # known submodule that lives in a third-party wheel (defensive).
        if top in STDLIB_MODULES and module not in SUBMODULE_PIP_MAP:
            return (1, {"module": module, "stdlib": True, "pip_name": None, "message": top + " is stdlib, no pip install needed"}, None)
        # Check the FULL dotted module first. The top-level package may import
        # fine while a submodule lives in a separate pip wheel — e.g. PyQt6
        # imports but PyQt6.QtWebEngineWidgets requires the PyQt6-WebEngine
        # wheel. Only the full import proves the submodule is actually present.
        try:
            importlib.import_module(module)
            return (1, {"module": module, "installed": True, "pip_name": None, "message": module + " already installed"}, None)
        except ImportError:
            pass
        # Submodule -> sub-package mapping (full dotted name takes priority),
        # then fall back to the top-level PIP_NAME_MAP.
        if module in SUBMODULE_PIP_MAP:
            pip_name = SUBMODULE_PIP_MAP[module]
        else:
            pip_name = PIP_NAME_MAP.get(top, top)
        if pip_name is None:
            return (0, None, ("ERR_NO_PIP", module + " is not a pip package (stdlib or built-in)", 0))
        dry_run = self.p(params, "dry_run", self.state["config"]["dry_run"])
        python_exe = self.state["config"]["python_executable"]
        if dry_run:
            return (1, {
                "module": module,
                "pip_name": pip_name,
                "action": "dry_run",
                "success": True,
                "message": "Would pip install " + pip_name,
            }, None)
        cmd = [python_exe, "-m", "pip", "install", pip_name]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            success = proc.returncode == 0
            self.state["stats"]["resolved"] += 1
            if not success:
                self.state["stats"]["errors"] += 1
            return (1, {
                "module": module,
                "pip_name": pip_name,
                "action": "install",
                "success": success,
                "returncode": proc.returncode,
                "stdout": proc.stdout[-500:] if proc.stdout else "",
                "stderr": proc.stderr[-500:] if proc.stderr else "",
            }, None)
        except subprocess.TimeoutExpired:
            self.state["stats"]["errors"] += 1
            return (0, None, ("ERR_TIMEOUT", "pip install " + pip_name + " timed out", 0))
        except Exception as e:
            self.state["stats"]["errors"] += 1
            return (0, None, ("ERR_INSTALL", str(e), 0))

    # ════════════════════════════════════════════
    # GENERATE_REQUIREMENTS — write requirements.txt from all discovered imports
    # ════════════════════════════════════════════

    def cmd_generate_requirements(self, params):
        path = self.p(params, "path")
        output = self.p(params, "output")
        if not path or not os.path.isdir(path):
            return (0, None, ("ERR_PATH", "Invalid path: " + str(path), 0))
        if not output:
            output = os.path.join(path, "requirements.txt")
        ok, scan_data, scan_err = self.cmd_scan_imports({"path": path})
        if not ok:
            return (0, None, scan_err)
        ok, pip_data, pip_err = self.cmd_extract_pips({"imports": scan_data["modules"]})
        if not ok:
            return (0, None, pip_err)
        ok, check_data, check_err = self.cmd_check_installed({"packages": pip_data["packages"]})
        if not ok:
            return (0, None, check_err)
        lines = []
        lines.append("# requirements.txt — generated by PackageManager")
        lines.append("# Do not edit manually. Regenerate with: pm.Run('generate_requirements', {...})")
        lines.append("")
        installed_pkgs = []
        missing_pkgs = []
        for pkg in pip_data["packages"]:
            pip_name = pkg["pip_name"]
            detail = check_data["details"].get(pip_name, {})
            if detail.get("installed"):
                version = detail.get("version", "")
                if version and version != "unknown":
                    installed_pkgs.append(pip_name + "==" + str(version))
                else:
                    installed_pkgs.append(pip_name)
            else:
                missing_pkgs.append(pip_name)
        for line in sorted(installed_pkgs):
            lines.append(line)
        if missing_pkgs:
            lines.append("")
            lines.append("# Missing packages (not yet installed):")
            for line in sorted(missing_pkgs):
                lines.append("# " + line)
        content = "\n".join(lines) + "\n"
        try:
            with open(output, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            self.state["stats"]["errors"] += 1
            return (0, None, ("ERR_WRITE", str(e), 0))
        self.state["requirements_path"] = output
        return (1, {
            "written": True,
            "file": output,
            "total_packages": len(installed_pkgs) + len(missing_pkgs),
            "installed": len(installed_pkgs),
            "missing": len(missing_pkgs),
            "content": content,
        }, None)

    # ════════════════════════════════════════════
    # CATALOG — list all third-party packages used across the project
    # ════════════════════════════════════════════

    def cmd_catalog(self, params):
        path = self.p(params, "path", self.state["config"]["project_root"])
        if not os.path.isdir(path):
            return (0, None, ("ERR_PATH", "Invalid path: " + str(path), 0))
        ok, scan_data, scan_err = self.cmd_scan_imports({"path": path})
        if not ok:
            return (0, None, scan_err)
        ok, pip_data, pip_err = self.cmd_extract_pips({"imports": scan_data["modules"]})
        if not ok:
            return (0, None, pip_err)
        ok, check_data, check_err = self.cmd_check_installed({"packages": pip_data["packages"]})
        if not ok:
            return (0, None, check_err)
        catalog = []
        for pkg in pip_data["packages"]:
            pip_name = pkg["pip_name"]
            detail = check_data["details"].get(pip_name, {})
            mod_info = None
            for m in scan_data["modules"]:
                if m["module"] == pkg["import_name"]:
                    mod_info = m
                    break
            catalog.append({
                "import_name": pkg["import_name"],
                "pip_name": pip_name,
                "installed": detail.get("installed", False),
                "version": detail.get("version"),
                "file_count": len(mod_info["files"]) if mod_info else 0,
                "files": list(set(mod_info["files"])) if mod_info else [],
            })
        installed_count = sum(1 for c in catalog if c["installed"])
        return (1, {
            "root": path,
            "total_packages": len(catalog),
            "installed": installed_count,
            "missing": len(catalog) - installed_count,
            "catalog": sorted(catalog, key=lambda x: x["pip_name"].lower()),
        }, None)
