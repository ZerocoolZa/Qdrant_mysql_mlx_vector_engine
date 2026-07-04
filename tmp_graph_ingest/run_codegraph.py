import ast, os, json
from collections import defaultdict, deque

FILE = '/Users/wws/Documents/MOVED_FROM_WAYNE_OLD_ACCOUNT/Prj_testbed/AA_MEMORIES/MEM_Complete_System.py'

with open(FILE, 'r') as f:
    source = f.read()

tree = ast.parse(source, filename=FILE)

nodes = []
edges = []
classes = []
imports = []

file_id = FILE
nodes.append({'id': file_id, 'type': 'FILE_PY', 'name': os.path.basename(FILE)})

for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        for alias in node.names:
            imports.append(alias.name)
    elif isinstance(node, ast.ImportFrom):
        if node.module:
            imports.append(node.module)

for item in ast.iter_child_nodes(tree):
    if isinstance(item, ast.ClassDef):
        class_id = file_id + '::' + item.name
        has_run = False
        has_state = False
        methods = []
        bases = [b.id for b in item.bases if isinstance(b, ast.Name)]
        
        for child in item.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(child.name)
                if child.name == 'Run':
                    has_run = True
                for n in ast.walk(child):
                    if isinstance(n, ast.Attribute):
                        if isinstance(n.value, ast.Name) and n.value.id == 'self':
                            if n.attr == 'state':
                                has_state = True
        
        node_type = 'MEMUNIT' if has_run and has_state else 'CLASS'
        classes.append({
            'name': item.name,
            'type': node_type,
            'methods': methods,
            'method_count': len(methods),
            'has_run': has_run,
            'has_state': has_state,
            'bases': bases,
            'line': item.lineno,
            'end_line': item.end_lineno,
        })
        nodes.append({'id': class_id, 'type': node_type, 'name': item.name, 'line': item.lineno})
        edges.append({'src': file_id, 'dst': class_id, 'type': 'DEFINES'})
        
        for base in bases:
            base_id = file_id + '::' + base
            edges.append({'src': class_id, 'dst': base_id, 'type': 'INHERITS'})

    elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
        func_id = file_id + '::' + item.name
        nodes.append({'id': func_id, 'type': 'FUNCTION', 'name': item.name, 'line': item.lineno})
        edges.append({'src': file_id, 'dst': func_id, 'type': 'DEFINES'})

adj = defaultdict(list)
radj = defaultdict(list)
for e in edges:
    adj[e['src']].append(e['dst'])
    radj[e['dst']].append(e['src'])

roots = [n['id'] for n in nodes if not radj.get(n['id'])]
leaves = [n['id'] for n in nodes if not adj.get(n['id'])]
hubs = [(n['id'], len(adj.get(n['id'], []))) for n in nodes if len(adj.get(n['id'], [])) >= 3]

type_counts = defaultdict(int)
for n in nodes:
    type_counts[n['type']] += 1

print('=' * 70)
print('CODE GRAPH: MEM_Complete_System.py')
print('=' * 70)
print()
print('PRIMITIVES:')
print('  Nodes:  ' + str(len(nodes)))
print('  Edges:  ' + str(len(edges)))
print()
print('NODE TYPES (' + str(len(type_counts)) + ' unique):')
for t, c in sorted(type_counts.items()):
    print('  ' + t.ljust(12) + '  x' + str(c))
print()
print('IMPORTS:')
for imp in imports:
    print('  ' + imp)
print()
print('CLASSES (' + str(len(classes)) + ' total):')
header = 'Name'.ljust(25) + 'Type'.ljust(10) + 'Methods'.ljust(8) + 'Run'.ljust(5) + 'State'.ljust(6) + 'Bases'.ljust(15) + 'Lines'
print(header)
print('-' * 95)
for c in classes:
    print(c['name'].ljust(25) + c['type'].ljust(10) + str(c['method_count']).ljust(8) + str(c['has_run']).ljust(5) + str(c['has_state']).ljust(6) + ','.join(c['bases']).ljust(15) + str(c['line']) + '-' + str(c['end_line']))
print()

memunits = [c for c in classes if c['type'] == 'MEMUNIT']
plain_classes = [c for c in classes if c['type'] == 'CLASS']
print('MEMUNIT classes (Run + self.state): ' + str(len(memunits)))
for m in memunits:
    print('  ' + m['name'] + ' -- methods: ' + str(m['methods']))
print()
print('PLAIN CLASS (no Run or no self.state): ' + str(len(plain_classes)))
print()

print('DERIVED:')
print('  Roots:      ' + str(len(roots)))
for r in roots:
    name = r.split('::')[-1] if '::' in r else os.path.basename(r)
    print('    ' + name)
print('  Leaves:     ' + str(len(leaves)))
print('  Hubs (>=3 outgoing): ' + str(len(hubs)))
for h_id, count in hubs:
    name = h_id.split('::')[-1] if '::' in h_id else os.path.basename(h_id)
    print('    ' + name + ': ' + str(count) + ' edges')
print()

all_methods = set()
for c in classes:
    for m in c['methods']:
        all_methods.add(m)
print('UNIQUE METHODS across all classes: ' + str(len(all_methods)))
for m in sorted(all_methods):
    owners = [c['name'] for c in classes if m in c['methods']]
    print('  ' + m.ljust(25) + ' <- ' + ', '.join(owners))
print()

edge_types = defaultdict(int)
for e in edges:
    edge_types[e['type']] += 1
print('EDGE TYPES:')
for t, c in sorted(edge_types.items()):
    print('  ' + t.ljust(12) + '  x' + str(c))
