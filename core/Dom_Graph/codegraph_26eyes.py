# [@GHOST]{[@file<codegraph_26eyes.py>][@domain<Dom_Graph>][@role<bridge>][@auth<cascade>][@date<2026-06-27>][@ver<1.0.0>]}
# [@VBSTYLE]{[@auth<system>][@role<codegraph_bridge>][@return<dict>][@orch<none>][@no<decorators|print|hardcoded>]}
# [@SUMMARY]{Bridges SQLite code graph DB with Eyes26 for 26-angle analysis on real code}
# [@WCL]{[@self_contalled<true>][@inputs<dom_graph.db>][@outputs<26-eye packets>]}

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .eyes_26 import GhostBracket, Eyes26

import os
DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dom_graph.db')


class GraphNode:
    def __init__(
        self,
        id: int,
        node_type: str,
        name: str,
        qualified_name: str,
        file_path: str,
        line_no: int,
        parent_qname: str,
        metadata_json: str,
        label: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.id = id
        self.node_type = node_type
        self.name = name
        self.qualified_name = qualified_name
        self.file_path = file_path
        self.line_no = line_no
        self.parent_qname = parent_qname
        self.metadata_json = metadata_json
        self.label = label
        self.metadata = metadata or {}

    def Run(self, command, params=None):
        return (0, None, ("unknown_command", command, 0))


class GraphEdge:
    def __init__(
        self,
        id: int,
        src_id: int,
        dst_id: int,
        edge_type: str,
        file_path: str,
        line_no: int,
        detail: str,
        metadata_json: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.id = id
        self.src_id = src_id
        self.dst_id = dst_id
        self.edge_type = edge_type
        self.file_path = file_path
        self.line_no = line_no
        self.detail = detail
        self.metadata_json = metadata_json
        self.metadata = metadata or {}

    def Run(self, command, params=None):
        return (0, None, ("unknown_command", command, 0))


class GraphLoadConfig:
    def __init__(
        self,
        node_limit: Optional[int] = None,
        edge_limit: Optional[int] = None,
        node_types: Optional[Set[str]] = None,
        edge_types: Optional[Set[str]] = None,
        file_contains: Optional[str] = None,
        name_contains: Optional[str] = None,
        focus_node_id: Optional[int] = None,
        focus_qname: Optional[str] = None,
        neighborhood_depth: int = 1,
        include_reverse_neighbors: bool = True,
        include_metadata: bool = True,
        cluster_mode: str = 'type',
    ):
        self.node_limit = node_limit
        self.edge_limit = edge_limit
        self.node_types = node_types
        self.edge_types = edge_types
        self.file_contains = file_contains
        self.name_contains = name_contains
        self.focus_node_id = focus_node_id
        self.focus_qname = focus_qname
        self.neighborhood_depth = neighborhood_depth
        self.include_reverse_neighbors = include_reverse_neighbors
        self.include_metadata = include_metadata
        self.cluster_mode = cluster_mode

    def Run(self, command, params=None):
        return (0, None, ("unknown_command", command, 0))


class CodeGraphSnapshot:
    def __init__(self):
        self.nodes: Dict[int, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        self.out_edges: Dict[int, List[GraphEdge]] = defaultdict(list)
        self.in_edges: Dict[int, List[GraphEdge]] = defaultdict(list)
        self.diagnostics: List[Dict[str, Any]] = []

    def visible_node_ids(self) -> Set[int]:
        return set(self.nodes.keys())

    def degree(self, node_id: int) -> int:
        return len(self.out_edges.get(node_id, [])) + len(self.in_edges.get(node_id, []))

    def neighbors(self, node_id: int, edge_types: Optional[Set[str]] = None, include_reverse: bool = True) -> Set[int]:
        out: Set[int] = set()
        for edge in self.out_edges.get(node_id, []):
            if edge_types is None or edge.edge_type in edge_types:
                out.add(edge.dst_id)
        if include_reverse:
            for edge in self.in_edges.get(node_id, []):
                if edge_types is None or edge.edge_type in edge_types:
                    out.add(edge.src_id)
        return out

    def neighborhood(self, seed_id: int, depth: int, edge_types: Optional[Set[str]] = None, include_reverse: bool = True) -> Set[int]:
        seen = {seed_id}
        queue = deque([(seed_id, 0)])
        while queue:
            node_id, d = queue.popleft()
            if d >= depth:
                continue
            for nxt in self.neighbors(node_id, edge_types=edge_types, include_reverse=include_reverse):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append((nxt, d + 1))
        return seen

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


class Core26EyesCodeGraph:
    """
    Converts a code graph database into code-graph-specific bracket packets
    and analyzes them with all 26 Ghost eyes.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.ghost_eyes = Eyes26()

    # ------------------------------------------------------------------
    # DB loading
    # ------------------------------------------------------------------
    def load_snapshot(self, config: Optional[GraphLoadConfig] = None) -> CodeGraphSnapshot:
        config = config or GraphLoadConfig()
        snapshot = CodeGraphSnapshot()
        cur = self.conn.cursor()

        node_sql = (
            'SELECT id, node_type, name, qualified_name, file_path, line_no, '
            'parent_qname, metadata_json, label FROM nodes'
        )
        node_where: List[str] = []
        node_params: List[Any] = []

        if config.node_types:
            node_where.append('node_type IN ({})'.format(','.join('?' for _ in config.node_types)))
            node_params.extend(sorted(config.node_types))
        if config.file_contains:
            node_where.append('LOWER(COALESCE(file_path, "")) LIKE ?')
            node_params.append(f'%{config.file_contains.lower()}%')
        if config.name_contains:
            needle = f'%{config.name_contains.lower()}%'
            node_where.append('(LOWER(COALESCE(name, "")) LIKE ? OR LOWER(COALESCE(qualified_name, "")) LIKE ?)')
            node_params.extend([needle, needle])
        if config.focus_node_id is not None:
            node_where.append('id = ?')
            node_params.append(config.focus_node_id)
        if config.focus_qname:
            node_where.append('qualified_name = ?')
            node_params.append(config.focus_qname)

        if node_where:
            node_sql += ' WHERE ' + ' AND '.join(node_where)
        node_sql += ' ORDER BY id'
        if config.node_limit:
            node_sql += f' LIMIT {int(config.node_limit)}'

        cur.execute(node_sql, node_params)
        for row in cur.fetchall():
            node = self.row_to_node(row)
            snapshot.nodes[node.id] = node

        if not snapshot.nodes and (config.focus_node_id is None and not config.focus_qname):
            # fallback to a sane window when filters returned nothing
            cur.execute(
                'SELECT id, node_type, name, qualified_name, file_path, line_no, '
                'parent_qname, metadata_json, label FROM nodes ORDER BY id LIMIT 500'
            )
            for row in cur.fetchall():
                node = self.row_to_node(row)
                snapshot.nodes[node.id] = node

        visible_ids = set(snapshot.nodes.keys())

        edge_sql = (
            'SELECT id, src_id, dst_id, edge_type, file_path, line_no, detail, metadata_json '
            'FROM edges'
        )
        edge_where: List[str] = []
        edge_params: List[Any] = []
        if config.edge_types:
            edge_where.append('edge_type IN ({})'.format(','.join('?' for _ in config.edge_types)))
            edge_params.extend(sorted(config.edge_types))
        if visible_ids:
            placeholders = ','.join('?' for _ in visible_ids)
            edge_where.append(f'((src_id IN ({placeholders})) OR (dst_id IN ({placeholders})))')
            edge_params.extend(sorted(visible_ids))
            edge_params.extend(sorted(visible_ids))
        if edge_where:
            edge_sql += ' WHERE ' + ' AND '.join(edge_where)
        edge_sql += ' ORDER BY id'
        if config.edge_limit:
            edge_sql += f' LIMIT {int(config.edge_limit)}'

        cur.execute(edge_sql, edge_params)
        loaded_edges = [self.row_to_edge(row) for row in cur.fetchall()]

        if config.focus_node_id is not None or config.focus_qname:
            seed_id = config.focus_node_id
            if seed_id is None and config.focus_qname:
                for node in snapshot.nodes.values():
                    if node.qualified_name == config.focus_qname:
                        seed_id = node.id
                        break
            if seed_id is not None:
                provisional_nodes = dict(snapshot.nodes)
                keep = self.expand_neighborhood(
                    seed_id,
                    loaded_edges,
                    depth=config.neighborhood_depth,
                    edge_types=config.edge_types,
                    include_reverse=config.include_reverse_neighbors,
                )
                if seed_id not in keep:
                    keep.add(seed_id)
                missing_ids = [nid for nid in keep if nid not in provisional_nodes]
                if missing_ids:
                    extra_nodes = self.load_nodes_by_ids(missing_ids)
                    provisional_nodes.update(extra_nodes)
                snapshot.nodes = {nid: provisional_nodes[nid] for nid in keep if nid in provisional_nodes}
                visible_ids = set(snapshot.nodes.keys())
                loaded_edges = [
                    edge for edge in loaded_edges
                    if edge.src_id in visible_ids and edge.dst_id in visible_ids
                ]

        for edge in loaded_edges:
            if edge.src_id not in snapshot.nodes or edge.dst_id not in snapshot.nodes:
                continue
            snapshot.edges.append(edge)
            snapshot.out_edges[edge.src_id].append(edge)
            snapshot.in_edges[edge.dst_id].append(edge)

        snapshot.diagnostics.append({
            'db_path': self.db_path,
            'visible_nodes': len(snapshot.nodes),
            'visible_edges': len(snapshot.edges),
            'node_types': dict(Counter(node.node_type for node in snapshot.nodes.values())),
            'edge_types': dict(Counter(edge.edge_type for edge in snapshot.edges)),
            'config': self.config_to_dict(config),
        })
        return snapshot

    def _row_to_node(self, row: sqlite3.Row) -> GraphNode:
        metadata_json = row['metadata_json'] or '{}'
        try:
            metadata = json.loads(metadata_json)
        except Exception:
            metadata = {'raw': metadata_json}
        return GraphNode(
            id=row['id'],
            node_type=row['node_type'] or '',
            name=row['name'] or '',
            qualified_name=row['qualified_name'] or '',
            file_path=row['file_path'] or '',
            line_no=row['line_no'] or 0,
            parent_qname=row['parent_qname'] or '',
            metadata_json=metadata_json,
            label=row['label'] or row['name'] or row['qualified_name'] or str(row['id']),
            metadata=metadata,
        )

    def _row_to_edge(self, row: sqlite3.Row) -> GraphEdge:
        metadata_json = row['metadata_json'] or '{}'
        try:
            metadata = json.loads(metadata_json)
        except Exception:
            metadata = {'raw': metadata_json}
        return GraphEdge(
            id=row['id'],
            src_id=row['src_id'],
            dst_id=row['dst_id'],
            edge_type=row['edge_type'] or '',
            file_path=row['file_path'] or '',
            line_no=row['line_no'] or 0,
            detail=row['detail'] or '',
            metadata_json=metadata_json,
            metadata=metadata,
        )

    def _load_nodes_by_ids(self, node_ids: Iterable[int]) -> Dict[int, GraphNode]:
        node_ids = sorted(set(int(nid) for nid in node_ids))
        if not node_ids:
            return {}
        placeholders = ','.join('?' for _ in node_ids)
        sql = (
            'SELECT id, node_type, name, qualified_name, file_path, line_no, '
            'parent_qname, metadata_json, label FROM nodes '
            f'WHERE id IN ({placeholders}) ORDER BY id'
        )
        cur = self.conn.cursor()
        cur.execute(sql, node_ids)
        return {row['id']: self.row_to_node(row) for row in cur.fetchall()}

    def _expand_neighborhood(
        self,
        seed_id: int,
        edges: List[GraphEdge],
        depth: int,
        edge_types: Optional[Set[str]],
        include_reverse: bool,
    ) -> Set[int]:
        out_map: Dict[int, List[int]] = defaultdict(list)
        in_map: Dict[int, List[int]] = defaultdict(list)
        for edge in edges:
            if edge_types and edge.edge_type not in edge_types:
                continue
            out_map[edge.src_id].append(edge.dst_id)
            in_map[edge.dst_id].append(edge.src_id)

        seen: Set[int] = {seed_id}
        queue = deque([(seed_id, 0)])
        while queue:
            node_id, d = queue.popleft()
            if d >= depth:
                continue
            for nxt in out_map.get(node_id, []):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append((nxt, d + 1))
            if include_reverse:
                for nxt in in_map.get(node_id, []):
                    if nxt not in seen:
                        seen.add(nxt)
                        queue.append((nxt, d + 1))
        return seen

    def _config_to_dict(self, config: GraphLoadConfig) -> Dict[str, Any]:
        return {
            'node_limit': config.node_limit,
            'edge_limit': config.edge_limit,
            'node_types': sorted(config.node_types) if config.node_types else None,
            'edge_types': sorted(config.edge_types) if config.edge_types else None,
            'file_contains': config.file_contains,
            'name_contains': config.name_contains,
            'focus_node_id': config.focus_node_id,
            'focus_qname': config.focus_qname,
            'neighborhood_depth': config.neighborhood_depth,
            'include_reverse_neighbors': config.include_reverse_neighbors,
            'include_metadata': config.include_metadata,
            'cluster_mode': config.cluster_mode,
        }

    # ------------------------------------------------------------------
    # Packet building
    # ------------------------------------------------------------------
    def snapshot_to_bracket(self, snapshot: CodeGraphSnapshot, config: Optional[GraphLoadConfig] = None) -> str:
        config = config or GraphLoadConfig()
        packet: List[str] = ['[CodeGraph']
        packet.append(self.emit_packet_header(snapshot, config))
        packet.append(self.emit_type_clusters(snapshot, config.cluster_mode))
        packet.append(self.emit_file_clusters(snapshot))
        packet.append(self.emit_parent_clusters(snapshot))
        packet.append(self.emit_nodes(snapshot, include_metadata=config.include_metadata))
        packet.append(self.emit_edges(snapshot))
        packet.append(self.emit_metrics(snapshot))
        packet.append(']')
        return ''.join(packet)

    def _safe(self, value: Any) -> str:
        text = str(value if value is not None else 'none')
        text = text.replace('[', '{').replace(']', '}')
        return text

    def _emit_packet_header(self, snapshot: CodeGraphSnapshot, config: GraphLoadConfig) -> str:
        return (
            f'[Meta'
            f'[Nodes:{len(snapshot.nodes)}]'
            f'[Edges:{len(snapshot.edges)}]'
            f'[NodeTypes:{len({n.node_type for n in snapshot.nodes.values()})}]'
            f'[EdgeTypes:{len({e.edge_type for e in snapshot.edges})}]'
            f'[Cluster:{self.safe(config.cluster_mode)}]'
            f'[Depth:{config.neighborhood_depth}]'
            f']'
        )

    def _emit_type_clusters(self, snapshot: CodeGraphSnapshot, _cluster_mode: str) -> str:
        groups: Dict[str, List[GraphNode]] = defaultdict(list)
        for node in snapshot.nodes.values():
            groups[node.node_type].append(node)
        chunks = ['[TypeClusters']
        for node_type in sorted(groups):
            members = sorted(groups[node_type], key=lambda n: (n.file_path, n.qualified_name))
            chunks.append(f'[Cluster[Key:{self.safe(node_type)}][Count:{len(members)}]')
            for node in members[:80]:
                chunks.append(f'[Member[ID:{node.id}][Name:{self.safe(node.name)}]]')
            chunks.append(']')
        chunks.append(']')
        return ''.join(chunks)

    def _emit_file_clusters(self, snapshot: CodeGraphSnapshot) -> str:
        groups: Dict[str, List[GraphNode]] = defaultdict(list)
        for node in snapshot.nodes.values():
            groups[node.file_path or 'none'].append(node)
        chunks = ['[FileClusters']
        for file_path in sorted(groups):
            members = sorted(groups[file_path], key=lambda n: (n.node_type, n.qualified_name))
            chunks.append(f'[File[Path:{self.safe(file_path)}][Count:{len(members)}]')
            for node in members[:50]:
                chunks.append(f'[Member[ID:{node.id}][Type:{self.safe(node.node_type)}][Name:{self.safe(node.name)}]]')
            chunks.append(']')
        chunks.append(']')
        return ''.join(chunks)

    def _emit_parent_clusters(self, snapshot: CodeGraphSnapshot) -> str:
        groups: Dict[str, List[GraphNode]] = defaultdict(list)
        for node in snapshot.nodes.values():
            groups[node.parent_qname or '<root>'].append(node)
        chunks = ['[ParentClusters']
        for parent_qname in sorted(groups):
            members = sorted(groups[parent_qname], key=lambda n: (n.node_type, n.qualified_name))
            chunks.append(f'[Parent[QName:{self.safe(parent_qname)}][Count:{len(members)}]')
            for node in members[:50]:
                chunks.append(f'[Member[ID:{node.id}][Type:{self.safe(node.node_type)}][Name:{self.safe(node.name)}]]')
            chunks.append(']')
        chunks.append(']')
        return ''.join(chunks)

    def _emit_nodes(self, snapshot: CodeGraphSnapshot, include_metadata: bool) -> str:
        chunks = ['[Nodes']
        ordered_nodes = sorted(snapshot.nodes.values(), key=lambda n: (n.node_type, n.file_path, n.qualified_name))
        for node in ordered_nodes:
            degree = snapshot.degree(node.id)
            packet = (
                f'[Node'
                f'[ID:{node.id}]'
                f'[Type:{self.safe(node.node_type)}]'
                f'[Name:{self.safe(node.name)}]'
                f'[QName:{self.safe(node.qualified_name)}]'
                f'[Path:{self.safe(node.file_path or "none")}]'
                f'[Line:{node.line_no}]'
                f'[Parent:{self.safe(node.parent_qname or "none")}]'
                f'[Degree:{degree}]'
            )
            if include_metadata and node.metadata:
                for key, value in sorted(node.metadata.items(), key=lambda kv: kv[0]):
                    packet += f'[Meta[{self.safe(key)}:{self.safe(value)}]]'
            packet += ']'
            chunks.append(packet)
        chunks.append(']')
        return ''.join(chunks)

    def _emit_edges(self, snapshot: CodeGraphSnapshot) -> str:
        chunks = ['[Edges']
        for edge in sorted(snapshot.edges, key=lambda e: (e.edge_type, e.src_id, e.dst_id, e.id)):
            chunks.append(
                f'[Edge'
                f'[ID:{edge.id}]'
                f'[Src:{edge.src_id}]'
                f'[Dst:{edge.dst_id}]'
                f'[Type:{self.safe(edge.edge_type)}]'
                f'[Path:{self.safe(edge.file_path or "none")}]'
                f'[Line:{edge.line_no}]'
                f'[Detail:{self.safe(edge.detail or "none")}]'
                f']'
            )
        chunks.append(']')
        return ''.join(chunks)

    def _emit_metrics(self, snapshot: CodeGraphSnapshot) -> str:
        node_type_counts = Counter(node.node_type for node in snapshot.nodes.values())
        edge_type_counts = Counter(edge.edge_type for edge in snapshot.edges)
        max_degree = 0
        top_node: Optional[GraphNode] = None
        for node in snapshot.nodes.values():
            degree = snapshot.degree(node.id)
            if degree > max_degree:
                max_degree = degree
                top_node = node
        chunks = ['[Metrics']
        chunks.append(f'[NodeCount:{len(snapshot.nodes)}]')
        chunks.append(f'[EdgeCount:{len(snapshot.edges)}]')
        chunks.append(f'[MaxDegree:{max_degree}]')
        chunks.append(f'[TopNode:{self.safe(top_node.qualified_name if top_node else "none")}]')
        for key, value in sorted(node_type_counts.items()):
            chunks.append(f'[NodeType[{self.safe(key)}:{value}]]')
        for key, value in sorted(edge_type_counts.items()):
            chunks.append(f'[EdgeType[{self.safe(key)}:{value}]]')
        chunks.append(']')
        return ''.join(chunks)

    # ------------------------------------------------------------------
    # Eye-specific adapters
    # ------------------------------------------------------------------
    def build_eye_context(self, snapshot: CodeGraphSnapshot, config: Optional[GraphLoadConfig] = None) -> Dict[str, Any]:
        config = config or GraphLoadConfig()
        node_type_counts = Counter(node.node_type for node in snapshot.nodes.values())
        edge_type_counts = Counter(edge.edge_type for edge in snapshot.edges)
        degrees = {node.id: snapshot.degree(node.id) for node in snapshot.nodes.values()}
        top_nodes = sorted(snapshot.nodes.values(), key=lambda n: (-degrees[n.id], n.qualified_name))[:25]
        by_file: Dict[str, List[int]] = defaultdict(list)
        by_parent: Dict[str, List[int]] = defaultdict(list)
        for node in snapshot.nodes.values():
            by_file[node.file_path or 'none'].append(node.id)
            by_parent[node.parent_qname or '<root>'].append(node.id)

        return {
            'config': self.config_to_dict(config),
            'node_type_counts': dict(node_type_counts),
            'edge_type_counts': dict(edge_type_counts),
            'degrees': degrees,
            'top_nodes': [
                {
                    'id': node.id,
                    'qualified_name': node.qualified_name,
                    'node_type': node.node_type,
                    'degree': degrees[node.id],
                    'file_path': node.file_path,
                }
                for node in top_nodes
            ],
            'by_file': {key: sorted(value) for key, value in by_file.items()},
            'by_parent': {key: sorted(value) for key, value in by_parent.items()},
            'isolated_nodes': sorted(node.id for node in snapshot.nodes.values() if degrees[node.id] == 0),
            'root_like_nodes': sorted(node.id for node in snapshot.nodes.values() if not node.parent_qname),
            'db_targets': sorted(node.id for node in snapshot.nodes.values() if node.node_type == 'db_target'),
            'widgets': sorted(node.id for node in snapshot.nodes.values() if node.node_type == 'widget'),
            'signals': sorted(node.id for node in snapshot.nodes.values() if node.node_type == 'signal'),
            'slots': sorted(node.id for node in snapshot.nodes.values() if node.node_type == 'slot'),
        }

    def analyze_with_26_eyes(self, config: Optional[GraphLoadConfig] = None) -> Dict[str, Any]:
        config = config or GraphLoadConfig()
        snapshot = self.load_snapshot(config)
        bracket_packet = self.snapshot_to_bracket(snapshot, config)
        engine = GhostBracket(bracket_packet)
        eye_results = self.ghost_eyes.inspect_all(engine)
        context = self.build_eye_context(snapshot, config)
        enriched = self.enrich_eye_results(eye_results, snapshot, context)
        return {
            'packet': bracket_packet,
            'packet_length': len(bracket_packet),
            'snapshot': snapshot,
            'eye_results': enriched,
            'context': context,
        }

    def _enrich_eye_results(
        self,
        eye_results: Dict[str, Any],
        snapshot: CodeGraphSnapshot,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        node_lookup = snapshot.nodes
        for eye_name, packet in eye_results.items():
            result = packet.setdefault('result', {})
            if eye_name == 'tree':
                result['graph_roots'] = [
                    node_lookup[nid].qualified_name
                    for nid in context['root_like_nodes']
                    if nid in node_lookup
                ][:40]
            elif eye_name == 'depth':
                result['graph_depth_hint'] = self.estimate_graph_depth(snapshot)
            elif eye_name == 'adjacency':
                result['edge_count'] = len(snapshot.edges)
                result['density'] = self.estimate_density(snapshot)
            elif eye_name == 'feature':
                result['top_degrees'] = context['top_nodes'][:15]
            elif eye_name == 'semantic':
                result['node_type_counts'] = context['node_type_counts']
            elif eye_name == 'constraint':
                result['edge_type_counts'] = context['edge_type_counts']
            elif eye_name == 'embedding':
                result['embedding_ready_nodes'] = len(snapshot.nodes)
            elif eye_name == 'hypergraph':
                result['file_clusters'] = len(context['by_file'])
                result['parent_clusters'] = len(context['by_parent'])
            elif eye_name == 'cross_layer':
                result['widget_nodes'] = len(context['widgets'])
                result['db_targets'] = len(context['db_targets'])
            elif eye_name == 'event':
                result['source_events'] = snapshot.diagnostics
            elif eye_name == 'temporal':
                result['analysis_steps'] = [
                    'load_snapshot',
                    'snapshot_to_bracket',
                    'ghost_26_eye_inspect',
                    'eye_enrichment',
                ]
            elif eye_name == 'lock':
                result['isolated_nodes'] = context['isolated_nodes'][:50]
            elif eye_name == 'scaffold':
                result['cluster_mode'] = context['config']['cluster_mode']
            elif eye_name == 'validation':
                result['graph_checks'] = self.validation_checks(snapshot)
            elif eye_name == 'code_to_bracket':
                result['packet_length'] = sum(len(node.qualified_name) for node in snapshot.nodes.values())
            elif eye_name == 'bracket_to_code':
                result['recoverable_nodes'] = len(snapshot.nodes)
            elif eye_name == 'tensor':
                result['node_type_channels'] = len(context['node_type_counts'])
            elif eye_name == 'metrics':
                result['code_graph_metrics'] = self.graph_metrics(snapshot, context)
            elif eye_name == 'impact':
                result['hot_nodes'] = context['top_nodes'][:10]
            elif eye_name == 'risk':
                result['risk_summary'] = self.risk_summary(snapshot, context)
        return eye_results

    def _estimate_graph_depth(self, snapshot: CodeGraphSnapshot) -> int:
        if not snapshot.nodes:
            return 0
        roots = [node.id for node in snapshot.nodes.values() if not snapshot.in_edges.get(node.id)]
        if not roots:
            roots = list(snapshot.nodes.keys())[:10]
        max_depth = 0
        for root in roots[:25]:
            seen = {root}
            queue = deque([(root, 0)])
            while queue:
                node_id, depth = queue.popleft()
                max_depth = max(max_depth, depth)
                for edge in snapshot.out_edges.get(node_id, []):
                    if edge.dst_id not in seen:
                        seen.add(edge.dst_id)
                        queue.append((edge.dst_id, depth + 1))
        return max_depth

    def _estimate_density(self, snapshot: CodeGraphSnapshot) -> float:
        node_count = len(snapshot.nodes)
        if node_count <= 1:
            return 0.0
        possible = node_count * (node_count - 1)
        return round(len(snapshot.edges) / possible, 6)

    def _validation_checks(self, snapshot: CodeGraphSnapshot) -> Dict[str, Any]:
        orphan_edges = [edge.id for edge in snapshot.edges if edge.src_id not in snapshot.nodes or edge.dst_id not in snapshot.nodes]
        self_loops = [edge.id for edge in snapshot.edges if edge.src_id == edge.dst_id]
        missing_files = [node.id for node in snapshot.nodes.values() if node.node_type != 'import' and not node.file_path]
        return {
            'orphan_edges': orphan_edges,
            'self_loops': self_loops,
            'nodes_missing_file_path': missing_files,
            'ok': not orphan_edges,
        }

    def _graph_metrics(self, snapshot: CodeGraphSnapshot, context: Dict[str, Any]) -> Dict[str, Any]:
        degrees = context['degrees']
        degree_values = list(degrees.values()) or [0]
        avg_degree = round(sum(degree_values) / max(1, len(degree_values)), 3)
        return {
            'avg_degree': avg_degree,
            'max_degree': max(degree_values) if degree_values else 0,
            'isolated_node_count': len(context['isolated_nodes']),
            'file_cluster_count': len(context['by_file']),
            'parent_cluster_count': len(context['by_parent']),
            'widget_count': len(context['widgets']),
            'signal_count': len(context['signals']),
            'slot_count': len(context['slots']),
            'db_target_count': len(context['db_targets']),
        }

    def _risk_summary(self, snapshot: CodeGraphSnapshot, context: Dict[str, Any]) -> Dict[str, Any]:
        high_degree = [row for row in context['top_nodes'] if row['degree'] >= 10]
        cross_file_edges = 0
        for edge in snapshot.edges:
            src = snapshot.nodes.get(edge.src_id)
            dst = snapshot.nodes.get(edge.dst_id)
            if src and dst and src.file_path != dst.file_path:
                cross_file_edges += 1
        return {
            'high_degree_nodes': high_degree,
            'cross_file_edges': cross_file_edges,
            'isolated_node_count': len(context['isolated_nodes']),
            'risk_hint': 'elevated' if cross_file_edges > 50 or len(high_degree) > 10 else 'normal',
        }

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    def get_eye_summary(self, analysis_bundle: Dict[str, Any]) -> List[Tuple[int, str, Any]]:
        eye_results = analysis_bundle['eye_results']
        eye_names = [
            (1, 'tree', 'Tree Structure'),
            (2, 'token', 'Token Sequence'),
            (3, 'depth', 'Depth Levels'),
            (4, 'sibling', 'Sibling Relationships'),
            (5, 'parent', 'Parent Mappings'),
            (6, 'path', 'Full Paths'),
            (7, 'leaf', 'Leaf Nodes'),
            (8, 'subtree', 'Subtree Snapshots'),
            (9, 'adjacency', 'Adjacency Matrix'),
            (10, 'feature', 'Feature Vectors'),
            (11, 'semantic', 'Semantic Roles'),
            (12, 'constraint', 'Constraints'),
            (13, 'embedding', 'Embeddings'),
            (14, 'hypergraph', 'Hypergraph Layers'),
            (15, 'cross_layer', 'Cross-Layer Dependencies'),
            (16, 'event', 'Event Log'),
            (17, 'temporal', 'Temporal Log'),
            (18, 'lock', 'Lock Status'),
            (19, 'scaffold', 'Scaffold Status'),
            (20, 'validation', 'Validation'),
            (21, 'code_to_bracket', 'Code→Bracket'),
            (22, 'bracket_to_code', 'Bracket→Code'),
            (23, 'tensor', 'Tensor Representation'),
            (24, 'metrics', 'Aggregate Metrics'),
            (25, 'impact', 'Change Impact'),
            (26, 'risk', 'Change Risk'),
        ]
        summary: List[Tuple[int, str, Any]] = []
        for eye_id, eye_name, description in eye_names:
            packet = eye_results.get(eye_name)
            if packet:
                summary.append((eye_id, description, packet.get('result', {})))
        return summary

    def close(self):
        self.conn.close()

    def Run(self, command, params=None):
        if command == "read_state":
            return self.read_state(params)
        return (0, None, ("unknown_command", command, 0))

    def read_state(self, params=None):
        return (1, {}, None)


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------
def _parse_csv_set(value: Optional[str]) -> Optional[Set[str]]:
    if not value:
        return None
    parts = {item.strip() for item in value.split(',') if item.strip()}
    return parts or None


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Run Ghost 26-eyes analysis on a code graph SQLite DB.')
    parser.add_argument('--db', default=DEFAULT_DB_PATH, help='Path to code_graph.db')
    parser.add_argument('--node-limit', type=int, default=800, help='Max nodes to load')
    parser.add_argument('--edge-limit', type=int, default=1600, help='Max edges to load')
    parser.add_argument('--node-types', default='', help='Comma-separated node types filter')
    parser.add_argument('--edge-types', default='', help='Comma-separated edge types filter')
    parser.add_argument('--file-contains', default='', help='Filter file_path contains')
    parser.add_argument('--name-contains', default='', help='Filter name/qname contains')
    parser.add_argument('--focus-node-id', type=int, default=None, help='Focus one node id')
    parser.add_argument('--focus-qname', default='', help='Focus one qualified_name')
    parser.add_argument('--depth', type=int, default=1, help='Neighborhood depth for focus modes')
    parser.add_argument('--cluster-mode', default='type', choices=['type', 'file', 'parent', 'none'], help='Cluster mode')
    parser.add_argument('--no-metadata', action='store_true', help='Do not include node metadata in packet')
    parser.add_argument('--json-out', default='', help='Write full analysis bundle summary to JSON file')
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()


    config = GraphLoadConfig(
        node_limit=args.node_limit,
        edge_limit=args.edge_limit,
        node_types=_parse_csv_set(args.node_types),
        edge_types=_parse_csv_set(args.edge_types),
        file_contains=args.file_contains or None,
        name_contains=args.name_contains or None,
        focus_node_id=args.focus_node_id,
        focus_qname=args.focus_qname or None,
        neighborhood_depth=max(0, int(args.depth)),
        include_reverse_neighbors=True,
        include_metadata=not args.no_metadata,
        cluster_mode=args.cluster_mode,
    )

    analyzer = Core26EyesCodeGraph(args.db)
    try:
        snapshot = analyzer.load_snapshot(config)

        bracket = analyzer.snapshot_to_bracket(snapshot, config)

        analysis_bundle = analyzer.analyze_with_26_eyes(config)

        for eye_id, description, result in analyzer.get_eye_summary(analysis_bundle):
            if isinstance(result, dict):
                if 'node_count' in result:
                    metric = f"{result['node_count']} nodes"
                elif 'count' in result:
                    metric = f"{result['count']} items"
                elif 'max_depth' in result:
                    metric = f"depth={result['max_depth']}"
                elif 'shape' in result:
                    metric = f"shape={result['shape']}"
                elif 'ok' in result:
                    metric = '✓ valid' if result['ok'] else '✗ invalid'
                elif 'code_graph_metrics' in result:
                    metric = f"avg_degree={result['code_graph_metrics'].get('avg_degree', 0)}"
                elif 'risk_summary' in result:
                    metric = result['risk_summary'].get('risk_hint', 'n/a')
                else:
                    metric = f"{len(result)} keys"
            else:
                metric = str(result)[:48]

        if args.json_out:
            out_path = Path(args.json_out)
            payload = {
                'db_path': analyzer.db_path,
                'packet_length': analysis_bundle['packet_length'],
                'context': analysis_bundle['context'],
                'eye_results': analysis_bundle['eye_results'],
                'snapshot_summary': snapshot.diagnostics,
            }
            out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')

    finally:
        analyzer.close()


if __name__ == '__main__':
    main()
