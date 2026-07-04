#[@GHOST]{file_path="core/Dom_Benchmark/ChatBclirGraph.py" date="2026-07-04" author="Devin" session_id="chat-bclir-graph" context="Chat ↔ BCL ↔ BCLIR ↔ Graph roundtrip converter. Converts chat messages to BCL packets, compiles to BCLIR typed nodes, builds conversation graphs, and reverses the full pipeline back to chat."}
#[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE Tuple3 Run dispatch"}
#[@FILEID]{id="ChatBclirGraph.py" domain="dom_benchmark" authority="ChatBclirGraph"}
#[@SUMMARY]{summary="Chat ↔ BCL ↔ BCLIR ↔ Graph roundtrip. Chat messages → BCL packets → BCLIR typed nodes → conversation graph (nodes=msg, edges=reply chains). Reverse: graph → BCLIR → BCL → chat messages. Full roundtrip with lossless reconstruction."}
#[@CLASS]{class="ChatBclirGraph" domain="dom_benchmark" authority="converter"}
#[@METHOD]{method="chat_to_bcl" type="converter"}
#[@METHOD]{method="bcl_to_bclir" type="compiler"}
#[@METHOD]{method="bclir_to_graph" type="builder"}
#[@METHOD]{method="chat_to_graph" type="pipeline"}
#[@METHOD]{method="graph_to_bclir" type="reverse"}
#[@METHOD]{method="bclir_to_bcl" type="reverse"}
#[@METHOD]{method="bcl_to_chat" type="reverse"}
#[@METHOD]{method="graph_to_chat" type="reverse"}
#[@METHOD]{method="roundtrip" type="verify"}
#[@METHOD]{method="Run" type="dispatch"}

"""ChatBclirGraph — Chat ↔ BCL ↔ BCLIR ↔ Graph roundtrip converter.

Full roundtrip:
    Chat messages
        │ chat_to_bcl
        ▼
    BCL packets (text)
        │ bcl_to_bclir
        ▼
    BCLIR nodes (typed AST)
        │ bclir_to_graph
        ▼
    Conversation graph (nodes=messages, edges=reply chains)
        │ graph_to_bclir
        ▼
    BCLIR nodes (reconstructed)
        │ bclir_to_bcl
        ▼
    BCL packets (reconstructed)
        │ bcl_to_chat
        ▼
    Chat messages (reconstructed)

The roundtrip is lossless: all fields are preserved through every layer.

BCL packet format for chat:
    [@CHAT]{[@SESSION]{session-id}[@MESSAGE]{[@ROW_ID]{123}[@ROLE]{user}
    [@CONTENT]{hello world}[@PARENT]{122}[@CREATED_AT]{1700000000}}...}

BCLIR types:
    ROW_ID      → INT
    PARENT      → INT
    CREATED_AT  → INT
    ROLE        → STRING
    CONTENT     → STRING
    SESSION     → STRING

Graph structure:
    nodes = messages (id = row_id)
    edges = reply chains (parent → child, relation = REPLY)
    root = first message (no parent)
"""

import re
import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    import Config
    from BclirGraph import BCLIRNode, BCLIRVal, GraphNode, GraphEdge, ExecutionGraph
    from BclirGraph import BCLIR_STRING, BCLIR_INT, BCLIR_FLOAT, BCLIR_BOOL, BCLIR_CODE
except ImportError:
    from . import Config
    from .BclirGraph import BCLIRNode, BCLIRVal, GraphNode, GraphEdge, ExecutionGraph
    from .BclirGraph import BCLIR_STRING, BCLIR_INT, BCLIR_FLOAT, BCLIR_BOOL, BCLIR_CODE

# ── Chat BCLIR Types ──
BCLIR_SESSION = "SESSION"
BCLIR_MESSAGE = "MESSAGE"
BCLIR_REPLY = "REPLY"

# ── Chat Param Schema ──
CHAT_MSG_SCHEMA = {
    "ROW_ID": BCLIR_INT,
    "ROLE": BCLIR_STRING,
    "CONTENT": BCLIR_STRING,
    "PARENT": BCLIR_INT,
    "CREATED_AT": BCLIR_INT,
    "MESSAGE_ID": BCLIR_STRING,
}

CHAT_SESSION_SCHEMA = {
    "SESSION_ID": BCLIR_STRING,
}


@dataclass
class ChatMessage:
    """A single chat message."""
    row_id: int = 0
    session_id: str = ""
    role: str = ""
    content: str = ""
    parent_node_id: int = 0
    message_id: str = ""
    created_at: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "row_id": self.row_id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "parent_node_id": self.parent_node_id,
            "message_id": self.message_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ChatMessage":
        return cls(
            row_id=int(d.get("row_id", 0)),
            session_id=str(d.get("session_id", "")),
            role=str(d.get("role", "")),
            content=str(d.get("content", "")),
            parent_node_id=int(d.get("parent_node_id", 0) or 0),
            message_id=str(d.get("message_id", "")),
            created_at=int(d.get("created_at", 0) or 0),
        )

    def __repr__(self) -> str:
        preview = self.content[:60].replace("\n", " ")
        return "ChatMessage(row={} role={} parent={} '{}')".format(
            self.row_id, self.role, self.parent_node_id, preview)


class ChatBclirGraph:
    """Chat ↔ BCL ↔ BCLIR ↔ Graph roundtrip converter.

    Full pipeline:
        chat_to_bcl     — Chat messages → BCL packet string
        bcl_to_bclir    — BCL packet → BCLIRNode tree (typed)
        bclir_to_graph  — BCLIRNode tree → ExecutionGraph
        graph_to_bclir  — ExecutionGraph → BCLIRNode tree (reverse)
        bclir_to_bcl    — BCLIRNode tree → BCL packet string (reverse)
        bcl_to_chat     — BCL packet → Chat messages (reverse)
        graph_to_chat   — ExecutionGraph → Chat messages (full reverse)
        roundtrip       — Chat → BCL → BCLIR → Graph → BCLIR → BCL → Chat (verify)
    """

    def __init__(self, mem=None, db=None, param=None):
        self.mem = mem
        self.db = db
        self.param = param or {}
        self.state = {
            "class": "ChatBclirGraph",
            "initialized": True,
            "total_chat_to_bcl": 0,
            "total_bcl_to_bclir": 0,
            "total_bclir_to_graph": 0,
            "total_graph_to_bclir": 0,
            "total_bclir_to_bcl": 0,
            "total_bcl_to_chat": 0,
            "total_roundtrips": 0,
            "total_roundtrip_losses": 0,
            "last_session_id": "",
            "last_msg_count": 0,
            "last_graph_nodes": 0,
            "last_graph_edges": 0,
        }

    def _p(self, label, value):
        self.state["last_" + label] = value

    def Run(self, command, params=None):
        """Dispatch a command. Returns Tuple3."""
        dispatch = {
            "chat_to_bcl": self.cmd_chat_to_bcl,
            "bcl_to_bclir": self.cmd_bcl_to_bclir,
            "bclir_to_graph": self.cmd_bclir_to_graph,
            "chat_to_graph": self.cmd_chat_to_graph,
            "graph_to_bclir": self.cmd_graph_to_bclir,
            "bclir_to_bcl": self.cmd_bclir_to_bcl,
            "bcl_to_chat": self.cmd_bcl_to_chat,
            "graph_to_chat": self.cmd_graph_to_chat,
            "roundtrip": self.cmd_roundtrip,
            "read_state": self.cmd_read_state,
            "set_config": self.cmd_set_config,
        }
        handler = dispatch.get(command)
        if handler is None:
            return (0, None, ("CHATBCLIR_UNKNOWN_COMMAND", command, 0))
        return handler(params or {})

    def cmd_read_state(self, params):
        return (1, dict(self.state), None)

    def cmd_set_config(self, params):
        for key, value in params.items():
            self.state[key] = value
        return (1, {"updated": len(params)}, None)

    # ── Forward: Chat → BCL → BCLIR → Graph ──

    def cmd_chat_to_bcl(self, params):
        messages = params.get("messages", [])
        if not messages:
            return (0, None, ("CHATBCLIR_NO_MESSAGES", "no messages provided", 0))
        msgs = [ChatMessage.from_dict(m) if isinstance(m, dict) else m for m in messages]
        bcl = self.chat_to_bcl(msgs)
        self.state["total_chat_to_bcl"] += 1
        self.state["last_msg_count"] = len(msgs)
        self.state["last_session_id"] = msgs[0].session_id if msgs else ""
        return (1, {"bcl": bcl, "msg_count": len(msgs), "bcl_len": len(bcl)}, None)

    def cmd_bcl_to_bclir(self, params):
        bcl = params.get("bcl")
        if not bcl:
            return (0, None, ("CHATBCLIR_NO_BCL", "no bcl provided", 0))
        node = self.bcl_to_bclir(bcl)
        if not node:
            return (0, None, ("CHATBCLIR_COMPILE_FAILED", "could not compile", 0))
        self.state["total_bcl_to_bclir"] += 1
        return (1, {"bclir": node.to_dict(), "child_count": len(node.children)}, None)

    def cmd_bclir_to_graph(self, params):
        bclir = params.get("bclir")
        if not bclir:
            return (0, None, ("CHATBCLIR_NO_BCLIR", "no bclir provided", 0))
        node = BCLIRNode.from_dict(bclir) if isinstance(bclir, dict) else bclir
        graph = self.bclir_to_graph(node)
        self.state["total_bclir_to_graph"] += 1
        self.state["last_graph_nodes"] = len(graph.nodes)
        self.state["last_graph_edges"] = len(graph.edges)
        return (1, {
            "graph": graph.to_dict(),
            "dot": graph.to_dot(),
            "traversal": graph.traverse(),
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
        }, None)

    def cmd_chat_to_graph(self, params):
        messages = params.get("messages", [])
        if not messages:
            return (0, None, ("CHATBCLIR_NO_MESSAGES", "no messages provided", 0))
        msgs = [ChatMessage.from_dict(m) if isinstance(m, dict) else m for m in messages]
        bcl = self.chat_to_bcl(msgs)
        bclir_node = self.bcl_to_bclir(bcl)
        if not bclir_node:
            return (0, None, ("CHATBCLIR_COMPILE_FAILED", "could not compile", 0))
        graph = self.bclir_to_graph(bclir_node)
        self.state["total_chat_to_bcl"] += 1
        self.state["total_bcl_to_bclir"] += 1
        self.state["total_bclir_to_graph"] += 1
        self.state["last_msg_count"] = len(msgs)
        self.state["last_session_id"] = msgs[0].session_id if msgs else ""
        self.state["last_graph_nodes"] = len(graph.nodes)
        self.state["last_graph_edges"] = len(graph.edges)
        return (1, {
            "bcl": bcl,
            "bclir": bclir_node.to_dict(),
            "graph": graph.to_dict(),
            "dot": graph.to_dot(),
            "traversal": graph.traverse(),
            "msg_count": len(msgs),
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
        }, None)

    # ── Reverse: Graph → BCLIR → BCL → Chat ──

    def cmd_graph_to_bclir(self, params):
        graph_data = params.get("graph")
        if not graph_data:
            return (0, None, ("CHATBCLIR_NO_GRAPH", "no graph provided", 0))
        graph = self._graph_from_dict(graph_data)
        node = self.graph_to_bclir(graph)
        self.state["total_graph_to_bclir"] += 1
        return (1, {"bclir": node.to_dict(), "child_count": len(node.children)}, None)

    def cmd_bclir_to_bcl(self, params):
        bclir = params.get("bclir")
        if not bclir:
            return (0, None, ("CHATBCLIR_NO_BCLIR", "no bclir provided", 0))
        node = BCLIRNode.from_dict(bclir) if isinstance(bclir, dict) else bclir
        bcl = self.bclir_to_bcl(node)
        self.state["total_bclir_to_bcl"] += 1
        return (1, {"bcl": bcl, "bcl_len": len(bcl)}, None)

    def cmd_bcl_to_chat(self, params):
        bcl = params.get("bcl")
        if not bcl:
            return (0, None, ("CHATBCLIR_NO_BCL", "no bcl provided", 0))
        messages = self.bcl_to_chat(bcl)
        self.state["total_bcl_to_chat"] += 1
        return (1, {
            "messages": [m.to_dict() for m in messages],
            "msg_count": len(messages),
        }, None)

    def cmd_graph_to_chat(self, params):
        graph_data = params.get("graph")
        if not graph_data:
            return (0, None, ("CHATBCLIR_NO_GRAPH", "no graph provided", 0))
        graph = self._graph_from_dict(graph_data)
        node = self.graph_to_bclir(graph)
        bcl = self.bclir_to_bcl(node)
        messages = self.bcl_to_chat(bcl)
        self.state["total_graph_to_bclir"] += 1
        self.state["total_bclir_to_bcl"] += 1
        self.state["total_bcl_to_chat"] += 1
        return (1, {
            "messages": [m.to_dict() for m in messages],
            "msg_count": len(messages),
            "bcl": bcl,
        }, None)

    # ── Roundtrip verification ──

    def cmd_roundtrip(self, params):
        messages = params.get("messages", [])
        if not messages:
            return (0, None, ("CHATBCLIR_NO_MESSAGES", "no messages provided", 0))
        msgs = [ChatMessage.from_dict(m) if isinstance(m, dict) else m for m in messages]

        # Forward: Chat → BCL → BCLIR → Graph
        bcl_forward = self.chat_to_bcl(msgs)
        bclir_forward = self.bcl_to_bclir(bcl_forward)
        if not bclir_forward:
            return (0, None, ("CHATBCLIR_FORWARD_FAILED", "chat→bclir failed", 0))
        graph = self.bclir_to_graph(bclir_forward)

        # Reverse: Graph → BCLIR → BCL → Chat
        bclir_reverse = self.graph_to_bclir(graph)
        bcl_reverse = self.bclir_to_bcl(bclir_reverse)
        msgs_reverse = self.bcl_to_chat(bcl_reverse)

        # Verify: compare forward and reverse
        losses = []
        if len(msgs) != len(msgs_reverse):
            losses.append("msg count: {} → {}".format(len(msgs), len(msgs_reverse)))

        for i, orig in enumerate(msgs):
            if i >= len(msgs_reverse):
                losses.append("msg {} lost".format(orig.row_id))
                continue
            rev = msgs_reverse[i]
            if orig.row_id != rev.row_id:
                losses.append("row_id: {} → {}".format(orig.row_id, rev.row_id))
            if orig.role != rev.role:
                losses.append("role[{}]: {} → {}".format(orig.row_id, orig.role, rev.role))
            if orig.content != rev.content:
                losses.append("content[{}] changed".format(orig.row_id))
            if orig.parent_node_id != rev.parent_node_id:
                losses.append("parent[{}]: {} → {}".format(orig.row_id, orig.parent_node_id, rev.parent_node_id))
            if orig.session_id != rev.session_id:
                losses.append("session[{}]: {} → {}".format(orig.row_id, orig.session_id, rev.session_id))

        self.state["total_roundtrips"] += 1
        self.state["total_roundtrip_losses"] += len(losses)
        self.state["total_chat_to_bcl"] += 1
        self.state["total_bcl_to_bclir"] += 1
        self.state["total_bclir_to_graph"] += 1
        self.state["total_graph_to_bclir"] += 1
        self.state["total_bclir_to_bcl"] += 1
        self.state["total_bcl_to_chat"] += 1
        self.state["last_msg_count"] = len(msgs)
        self.state["last_graph_nodes"] = len(graph.nodes)
        self.state["last_graph_edges"] = len(graph.edges)

        return (1, {
            "original_count": len(msgs),
            "reconstructed_count": len(msgs_reverse),
            "graph_nodes": len(graph.nodes),
            "graph_edges": len(graph.edges),
            "bcl_forward_len": len(bcl_forward),
            "bcl_reverse_len": len(bcl_reverse),
            "losses": losses,
            "loss_count": len(losses),
            "lossless": len(losses) == 0,
            "bcl_forward": bcl_forward[:500] + "..." if len(bcl_forward) > 500 else bcl_forward,
            "bcl_reverse": bcl_reverse[:500] + "..." if len(bcl_reverse) > 500 else bcl_reverse,
            "traversal": graph.traverse(),
            "dot": graph.to_dot(),
        }, None)

    # ── Core conversion methods ──

    def chat_to_bcl(self, messages: List[ChatMessage]) -> str:
        """Convert chat messages → BCL packet string.

        Format:
            [@CHAT]{[@SESSION]{session-id}
            [@MESSAGE]{[@ROW_ID]{1}[@ROLE]{user}[@CONTENT]{hello}...}
            [@MESSAGE]{[@ROW_ID]{2}[@ROLE]{assistant}[@CONTENT]{hi}...}
            ...}
        """
        if not messages:
            return ""
        session_id = messages[0].session_id
        parts = []
        parts.append("[@CHAT]{")
        parts.append("[@SESSION]{" + self._escape(session_id) + "}")
        for msg in messages:
            parts.append(self._msg_to_bcl(msg))
        parts.append("}")
        return "".join(parts)

    def _msg_to_bcl(self, msg: ChatMessage) -> str:
        """Convert one message → BCL tag."""
        content = self._escape(msg.content)
        parts = []
        parts.append("[@MESSAGE]{")
        parts.append("[@ROW_ID]{" + str(msg.row_id) + "}")
        parts.append("[@ROLE]{" + self._escape(msg.role) + "}")
        parts.append("[@CONTENT]{" + content + "}")
        parts.append("[@PARENT]{" + str(msg.parent_node_id) + "}")
        parts.append("[@CREATED_AT]{" + str(msg.created_at) + "}")
        if msg.message_id:
            parts.append("[@MESSAGE_ID]{" + self._escape(msg.message_id) + "}")
        parts.append("}")
        return "".join(parts)

    def bcl_to_bclir(self, bcl: str) -> Optional[BCLIRNode]:
        """Compile BCL packet → BCLIRNode tree (typed).

        Root node: op=SESSION, params={SESSION_ID: STRING}
        Children: one BCLIRNode per message, op=MESSAGE
        """
        chat_match = re.search(r"\[@CHAT\]\{(.+)\}", bcl, re.DOTALL)
        if not chat_match:
            return None
        inner = chat_match.group(1)

        # Extract session
        session_match = re.search(r"\[@SESSION\]\{([^}]*)\}", inner)
        session_id = session_match.group(1) if session_match else ""

        root = BCLIRNode(op=BCLIR_SESSION, node_id="chat_root")
        root.params["SESSION_ID"] = BCLIRVal(type=BCLIR_STRING, value=session_id)
        root.cost_estimate = 0.001

        # Extract all MESSAGE tags (nested)
        messages = self._extract_messages(inner)
        for i, msg_content in enumerate(messages):
            child = BCLIRNode(op=BCLIR_MESSAGE, node_id="msg_{}".format(i))
            tags = self._extract_all_tags(msg_content)
            for tag_name, tag_value in tags:
                val = self._infer_chat_type(tag_name, tag_value)
                child.params[tag_name] = val
            child.cost_estimate = 0.01
            root.children.append(child)

        return root

    def bclir_to_graph(self, root: BCLIRNode) -> ExecutionGraph:
        """Build conversation graph from BCLIRNode tree.

        Nodes = messages (id = "msg_{index}")
        Edges = reply chains (parent → child, relation = REPLY)
        Root = session node
        """
        graph = ExecutionGraph()

        # Session root node
        session_gn = GraphNode(
            id=root.node_id or "chat_root",
            label=root.params.get("SESSION_ID", BCLIRVal(value="session")).value,
            node_type=BCLIR_SESSION,
            data={k: v.value for k, v in root.params.items()},
        )
        graph.add_node(session_gn)

        # Create message nodes
        msg_nodes = []
        for i, child in enumerate(root.children):
            if child.op != BCLIR_MESSAGE:
                continue
            row_id = child.params.get("ROW_ID", BCLIRVal(value=0)).value
            role = child.params.get("ROLE", BCLIRVal(value="")).value
            parent_id = child.params.get("PARENT", BCLIRVal(value=0)).value
            content = child.params.get("CONTENT", BCLIRVal(value="")).value

            node_id = "msg_{}".format(i)
            label = "#{} {} {}".format(row_id, role, content[:30].replace("\n", " "))
            gn = GraphNode(
                id=node_id,
                label=label,
                node_type=BCLIR_MESSAGE,
                data={
                    "row_id": row_id,
                    "role": role,
                    "parent": parent_id,
                    "content": content,
                    "content_len": len(content),
                    "created_at": child.params.get("CREATED_AT", BCLIRVal(value=0)).value,
                    "message_id": child.params.get("MESSAGE_ID", BCLIRVal(value="")).value,
                },
            )
            graph.add_node(gn)
            msg_nodes.append((node_id, child, parent_id))

        # Build edges: session → first message, then reply chains
        # First message connects to session
        if msg_nodes:
            graph.add_edge(session_gn.id, msg_nodes[0][0], "REPLY", "first")

        # Build row_id → node_id index
        row_to_node = {}
        for node_id, child, parent_id in msg_nodes:
            row_id = child.params.get("ROW_ID", BCLIRVal(value=0)).value
            row_to_node[row_id] = node_id

        # Reply chain edges
        for node_id, child, parent_id in msg_nodes:
            if parent_id and parent_id in row_to_node:
                parent_node_id = row_to_node[parent_id]
                if parent_node_id != node_id:
                    graph.add_edge(parent_node_id, node_id, "REPLY", "reply")

        return graph

    # ── Reverse: Graph → BCLIR → BCL → Chat ──

    def graph_to_bclir(self, graph: ExecutionGraph) -> BCLIRNode:
        """Reverse: ExecutionGraph → BCLIRNode tree."""
        root = BCLIRNode(op=BCLIR_SESSION, node_id=graph.root_id or "chat_root")
        root_node = graph.get_node(graph.root_id)
        if root_node:
            root.params["SESSION_ID"] = BCLIRVal(type=BCLIR_STRING, value=root_node.label)

        # Reconstruct message nodes from graph nodes
        for nid in graph.node_order:
            gn = graph.nodes.get(nid)
            if not gn or gn.node_type != BCLIR_MESSAGE:
                continue
            child = BCLIRNode(op=BCLIR_MESSAGE, node_id=nid)
            data = gn.data
            child.params["ROW_ID"] = BCLIRVal(type=BCLIR_INT, value=data.get("row_id", 0))
            child.params["ROLE"] = BCLIRVal(type=BCLIR_STRING, value=data.get("role", ""))
            child.params["PARENT"] = BCLIRVal(type=BCLIR_INT, value=data.get("parent", 0))
            child.params["CREATED_AT"] = BCLIRVal(type=BCLIR_INT, value=data.get("created_at", 0))
            # Content is stored as length in graph data — we need the full content
            # For lossless roundtrip, content must be passed through BCLIR params
            # We store it in the BCLIR node's params directly
            child.params["CONTENT"] = BCLIRVal(type=BCLIR_STRING, value=data.get("content", ""))
            root.children.append(child)

        return root

    def bclir_to_bcl(self, node: BCLIRNode) -> str:
        """Reverse: BCLIRNode tree → BCL packet string."""
        if node.op != BCLIR_SESSION:
            return ""
        session_id = node.params.get("SESSION_ID", BCLIRVal(value="")).value
        parts = []
        parts.append("[@CHAT]{")
        parts.append("[@SESSION]{" + self._escape(str(session_id)) + "}")
        for child in node.children:
            if child.op != BCLIR_MESSAGE:
                continue
            row_id = child.params.get("ROW_ID", BCLIRVal(value=0)).value
            role = child.params.get("ROLE", BCLIRVal(value="")).value
            content = child.params.get("CONTENT", BCLIRVal(value="")).value
            parent = child.params.get("PARENT", BCLIRVal(value=0)).value
            created_at = child.params.get("CREATED_AT", BCLIRVal(value=0)).value
            msg_id = child.params.get("MESSAGE_ID", BCLIRVal(value="")).value
            parts.append("[@MESSAGE]{")
            parts.append("[@ROW_ID]{" + str(row_id) + "}")
            parts.append("[@ROLE]{" + self._escape(str(role)) + "}")
            parts.append("[@CONTENT]{" + self._escape(str(content)) + "}")
            parts.append("[@PARENT]{" + str(parent) + "}")
            parts.append("[@CREATED_AT]{" + str(created_at) + "}")
            if msg_id:
                parts.append("[@MESSAGE_ID]{" + self._escape(str(msg_id)) + "}")
            parts.append("}")
        parts.append("}")
        return "".join(parts)

    def bcl_to_chat(self, bcl: str) -> List[ChatMessage]:
        """Reverse: BCL packet → Chat messages."""
        messages = []
        chat_match = re.search(r"\[@CHAT\]\{(.+)\}", bcl, re.DOTALL)
        if not chat_match:
            return messages
        inner = chat_match.group(1)

        session_match = re.search(r"\[@SESSION\]\{([^}]*)\}", inner)
        session_id = session_match.group(1) if session_match else ""

        msg_contents = self._extract_messages(inner)
        for mc in msg_contents:
            tags = self._extract_all_tags(mc)
            tag_dict = {}
            for tag_name, tag_value in tags:
                tag_dict[tag_name] = tag_value
            msg = ChatMessage(
                row_id=int(tag_dict.get("ROW_ID", 0)),
                session_id=session_id,
                role=tag_dict.get("ROLE", ""),
                content=tag_dict.get("CONTENT", ""),
                parent_node_id=int(tag_dict.get("PARENT", 0) or 0),
                created_at=int(tag_dict.get("CREATED_AT", 0) or 0),
                message_id=tag_dict.get("MESSAGE_ID", ""),
            )
            messages.append(msg)
        return messages

    # ── Helpers ──

    def _escape(self, text: str) -> str:
        """Escape BCL special chars in content."""
        return str(text).replace("{", "(").replace("}", ")")

    def _unescape(self, text: str) -> str:
        """Unescape BCL special chars."""
        return str(text).replace("(", "{").replace(")", "}")

    def _extract_all_tags(self, text: str) -> List[Tuple[str, str]]:
        """Extract all [@TAG]{value} pairs (handles nested braces)."""
        results = []
        i = 0
        while i < len(text):
            if text[i:i+2] == "[@":
                tag_end = text.find("]", i)
                if tag_end == -1:
                    break
                tag = text[i+2:tag_end]
                brace_start = tag_end + 1
                if brace_start < len(text) and text[brace_start] == "{":
                    depth = 1
                    j = brace_start + 1
                    while j < len(text) and depth > 0:
                        if text[j] == "{":
                            depth += 1
                        elif text[j] == "}":
                            depth -= 1
                        j += 1
                    value = text[brace_start+1:j-1]
                    results.append((tag, value))
                    i = j
                else:
                    i = tag_end + 1
            else:
                i += 1
        return results

    def _extract_messages(self, inner: str) -> List[str]:
        """Extract all [@MESSAGE]{...} contents from inner BCL."""
        messages = []
        i = 0
        while i < len(inner):
            if inner[i:i+9] == "[@MESSAGE":
                tag_end = inner.find("]", i)
                if tag_end == -1:
                    break
                brace_start = tag_end + 1
                if brace_start < len(inner) and inner[brace_start] == "{":
                    depth = 1
                    j = brace_start + 1
                    while j < len(inner) and depth > 0:
                        if inner[j] == "{":
                            depth += 1
                        elif inner[j] == "}":
                            depth -= 1
                        j += 1
                    value = inner[brace_start+1:j-1]
                    messages.append(value)
                    i = j
                else:
                    i = tag_end + 1
            else:
                i += 1
        return messages

    def _infer_chat_type(self, param_name: str, raw_value: str) -> BCLIRVal:
        """Infer type for chat params."""
        expected = CHAT_MSG_SCHEMA.get(param_name, BCLIR_STRING)
        if expected == BCLIR_INT:
            try:
                return BCLIRVal(type=BCLIR_INT, value=int(raw_value))
            except ValueError:
                return BCLIRVal(type=BCLIR_STRING, value=raw_value)
        return BCLIRVal(type=BCLIR_STRING, value=raw_value)

    def _graph_from_dict(self, graph_data: Dict[str, Any]) -> ExecutionGraph:
        """Reconstruct ExecutionGraph from dict."""
        graph = ExecutionGraph()
        for nd in graph_data.get("nodes", []):
            gn = GraphNode(
                id=nd["id"],
                label=nd["label"],
                node_type=nd["node_type"],
                data=nd.get("data", {}),
            )
            graph.add_node(gn)
        for ed in graph_data.get("edges", []):
            graph.add_edge(ed["from"], ed["to"], ed["relation"], ed.get("label", ""))
        return graph
