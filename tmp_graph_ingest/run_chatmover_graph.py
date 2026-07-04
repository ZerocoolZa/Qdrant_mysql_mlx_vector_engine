import os, ast, re, json
from collections import defaultdict

FILES = [
    '/Users/wws/Qdrant_mysql_mlx_vector_engine/chat_mover/Unifying Graph Codebases.md',
    '/Users/wws/Qdrant_mysql_mlx_vector_engine/chat_mover/MemUnit Architecture Deep Dive.md',
    '/Users/wws/Qdrant_mysql_mlx_vector_engine/chat_mover/Codex Chat Cleanup.md',
]

for fpath in FILES:
    name = os.path.basename(fpath)
    size = os.path.getsize(fpath)
    with open(fpath, 'r') as f:
        content = f.read()
    lines = content.split('\n')

    # Extract python code blocks
    py_blocks = re.findall(r'```python\n(.*?)```', content, re.DOTALL)

    # Extract class definitions from text
    class_mentions = re.findall(r'class\s+(\w+)', content)

    # Extract method/function mentions
    method_mentions = re.findall(r'def\s+(\w+)', content)

    # Extract Run() mentions
    run_mentions = len(re.findall(r'\.Run\(|def Run\(|Run\(command', content))

    # Extract MemUnit mentions
    memunit_mentions = len(re.findall(r'MemUnit|Memunit|memunit', content))

    # Extract domain mentions
    dom_mentions = re.findall(r'Dom\w+|dom_\w+', content)

    # Extract bracket/BCL mentions
    bcl_mentions = len(re.findall(r'BCL|bcl|bracket|Bracket|\[@\w+\]', content))

    # Extract rule mentions
    rule_mentions = len(re.findall(r'rule|Rule|@\w+\(\d+\)', content))

    # Extract ghost mentions
    ghost_mentions = len(re.findall(r'ghost|Ghost|GHOST', content))

    # Extract VBStyle mentions
    vbstyle_mentions = len(re.findall(r'VBStyle|VBSTYLE|vbstyle', content))

    # Extract file paths
    paths = re.findall(r'/Users/\S+\.(?:py|c|md|sql|db|json)', content)

    print('=' * 70)
    print('FILE: ' + name)
    print('Size: ' + str(size) + ' bytes | Lines: ' + str(len(lines)))
    print('=' * 70)
    print('Python code blocks: ' + str(len(py_blocks)))
    print('Class mentions: ' + str(len(class_mentions)) + ' -> ' + str(list(set(class_mentions))[:15]))
    print('Method mentions: ' + str(len(method_mentions)) + ' -> ' + str(list(set(method_mentions))[:15]))
    print('Run() mentions: ' + str(run_mentions))
    print('MemUnit mentions: ' + str(memunit_mentions))
    print('Domain mentions: ' + str(len(dom_mentions)) + ' -> ' + str(list(set(dom_mentions))[:15]))
    print('BCL/bracket mentions: ' + str(bcl_mentions))
    print('Rule mentions: ' + str(rule_mentions))
    print('Ghost mentions: ' + str(ghost_mentions))
    print('VBStyle mentions: ' + str(vbstyle_mentions))
    print('File paths found: ' + str(len(paths)) + ' -> ' + str(list(set(paths))[:10]))
    print()

    # If there are python code blocks, AST parse them
    for i, block in enumerate(py_blocks):
        try:
            tree = ast.parse(block)
            classes_in_block = []
            for item in ast.iter_child_nodes(tree):
                if isinstance(item, ast.ClassDef):
                    has_run = any(isinstance(c, ast.FunctionDef) and c.name == 'Run' for c in item.body)
                    has_state = False
                    for child in item.body:
                        for n in ast.walk(child):
                            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == 'self' and n.attr == 'state':
                                has_state = True
                    node_type = 'MEMUNIT' if has_run and has_state else 'CLASS'
                    methods = [c.name for c in item.body if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef))]
                    classes_in_block.append({
                        'name': item.name,
                        'type': node_type,
                        'methods': methods,
                        'has_run': has_run,
                        'has_state': has_state,
                    })

            if classes_in_block:
                print('  Code block #' + str(i+1) + ': ' + str(len(classes_in_block)) + ' classes')
                for c in classes_in_block:
                    print('    ' + c['name'].ljust(25) + c['type'].ljust(10) + 'Run=' + str(c['has_run']) + ' State=' + str(c['has_state']) + ' methods=' + str(c['methods']))
        except SyntaxError:
            print('  Code block #' + str(i+1) + ': (syntax error, skipped)')
    print()
