# [@GHOST]{[@file<__init__.py>][@domain<Dom_Gui>][@role<package>][@auth<cascade>][@date<2026-06-27>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<system>][@role<package_init>][@return<none>][@orch<none>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{Dom_Gui — Dynamic GUI System (DGS) — import as: from core.Dom_Gui import *}
# [@WCL]{[@exports<GUIParser|GUIBuilder|EventRouter|ThemeLoader|GUITreeNode|GuiDB|GuiBus|config_gui|graphs>]}

from .parser import GUIParser
from .node import GUITreeNode
from .builder import GUIBuilder
from .router import EventRouter
from .theme import ThemeLoader
from .db import GuiDB
from .bus import GuiBus

from . import config
from . import graphs

__all__ = [
    "GUIParser",
    "GUITreeNode",
    "GUIBuilder",
    "EventRouter",
    "ThemeLoader",
    "GuiDB",
    "GuiBus",
    "config",
    "graphs",
]

__version__ = "1.1.0"
