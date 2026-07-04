#!/usr/bin/env python3
"""
Search MySQL databases for all MemUnit references.
Collects locations (database, table, row IDs, file paths) and saves to .md
"""

import mysql.connector
import os
import re
from datetime import datetime

OUTPUT_MD = '/Users/wws/Qdrant_mysql_mlx_vector_engine/tmp_graph_ingest/memunit_references.md'

SEARCH_TERMS = ['MemUnit', 'memunit', 'MEMUNIT', 'Memunit', 'Core_MainUnit', 'core_memunit', 'CORE_MEMUNIT']

DBS_TO_SEARCH = ['vb_shared', 'vb_code_test', 'CODEBASE', 'vbstyle_documents']

def get_connection():
    return mysql.connector.connect(
        host='localhost',
        port=3306,
        user='root',
        password='',
        charset='utf8mb4',
        collation='utf8mb4_general_ci'
    )

def get_text_columns(cursor, db_name, table_name):
    cursor.execute(f"""
        SELECT COLUMN_NAME
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        AND DATA_TYPE IN ('text', 'longtext', 'mediumtext', 'varchar', 'char', 'tinytext')
    """, (db_name, table_name))
    return [row[0] for row in cursor.fetchall()]

def get_primary_key(cursor, db_name, table_name):
    try:
        cursor.execute(f"""
            SELECT COLUMN_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            AND CONSTRAINT_NAME = 'PRIMARY'
        """, (db_name, table_name))
        rows = cursor.fetchall()
        if rows:
            return rows[0][0]
    except Exception:
        pass
    return 'id'

PATH_RE = re.compile(r"/Users/[^\s'\"<>\\]+\.(?:py|c|md|sql|db|json|swift|txt|yaml|yml)")

def search_table(cursor, db_name, table_name):
    results = []
    columns = get_text_columns(cursor, db_name, table_name)
    if not columns:
        return results

    pk = get_primary_key(cursor, db_name, table_name)

    # Build ONE query with OR across all columns x all terms
    like_parts = []
    params = []
    for col in columns:
        for term in SEARCH_TERMS:
            like_parts.append(f"`{col}` LIKE %s")
            params.append(f'%{term}%')

    where_clause = ' OR '.join(like_parts)
    col_list = ', '.join(f'`{c}`' for c in columns)
    sql = f"SELECT `{pk}`, {col_list} FROM `{db_name}`.`{table_name}` WHERE {where_clause} LIMIT 500"

    try:
        cursor.execute(sql, params)
        rows = cursor.fetchall()
    except Exception:
        return results

    for row in rows:
        row_id = row[0]
        cell_values = row[1:]
        row_paths = set()
        previews = []
        for i, cell in enumerate(cell_values):
            text_str = str(cell) if cell else ''
            if not text_str:
                continue
            found = PATH_RE.findall(text_str)
            row_paths.update(found)
            # Detect which term matched which column
            for term in SEARCH_TERMS:
                if term.lower() in text_str.lower():
                    previews.append({
                        'column': columns[i],
                        'term': term,
                        'text_preview': text_str[:200],
                    })
                    break

        results.append({
            'db': db_name,
            'table': table_name,
            'row_id': row_id,
            'paths': list(row_paths),
            'previews': previews,
        })
    return results

def main():
    conn = get_connection()
    cursor = conn.cursor()  # tuple cursor — faster than dictionary

    print('Searching MySQL for MemUnit references...')
    print(f'Databases: {DBS_TO_SEARCH}')
    print(f'Search terms: {SEARCH_TERMS}')
    print()

    all_results = []
    all_paths = set()

    for db in DBS_TO_SEARCH:
        try:
            cursor.execute(f"SHOW TABLES FROM `{db}`")
            tables = [row[0] for row in cursor.fetchall()]
            print(f'{db}: {len(tables)} tables')
        except Exception as e:
            print(f'{db}: SKIP ({e})')
            continue

        for table in tables:
            hits = search_table(cursor, db, table)
            if hits:
                print(f'  {table}: {len(hits)} hits')
                all_results.extend(hits)
                for h in hits:
                    all_paths.update(h['paths'])

    cursor.close()
    conn.close()

    # Deduplicate by db:table:row_id
    seen = set()
    unique_results = []
    for r in all_results:
        key = f"{r['db']}:{r['table']}:{r['row_id']}"
        if key not in seen:
            seen.add(key)
            unique_results.append(r)

    # Group by db.table
    grouped = {}
    for r in unique_results:
        key = f"{r['db']}.{r['table']}"
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(r)

    sorted_paths = sorted(all_paths)

    # Write markdown
    with open(OUTPUT_MD, 'w') as f:
        f.write('# MemUnit References: MySQL Database Search\n\n')
        f.write(f'**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n')
        f.write(f'**Databases searched:** {", ".join(DBS_TO_SEARCH)}\n\n')
        f.write(f'**Search terms:** {", ".join(SEARCH_TERMS)}\n\n')
        f.write(f'**Total unique hits:** {len(unique_results)}\n\n')
        f.write(f'**Total file paths found:** {len(sorted_paths)}\n\n')
        f.write('---\n\n')

        f.write('## Summary by Table\n\n')
        f.write('| Database.Table | Hit Count |\n')
        f.write('|----------------|----------|\n')
        for key in sorted(grouped.keys()):
            f.write(f'| `{key}` | {len(grouped[key])} |\n')
        f.write('\n---\n\n')

        f.write('## File Paths Referenced Alongside MemUnit\n\n')
        f.write('These are file paths found in MySQL rows that also mention MemUnit.\n')
        f.write('They indicate where MemUnit-related code, specs, or documentation lives.\n\n')

        f.write('### Python Files\n\n')
        py_paths = [p for p in sorted_paths if p.endswith('.py')]
        for p in py_paths:
            f.write(f'- `{p}`\n')
        f.write(f'\n**Total:** {len(py_paths)}\n\n')

        f.write('### Markdown Files\n\n')
        md_paths = [p for p in sorted_paths if p.endswith('.md')]
        for p in md_paths:
            f.write(f'- `{p}`\n')
        f.write(f'\n**Total:** {len(md_paths)}\n\n')

        f.write('### SQL/DB Files\n\n')
        sql_paths = [p for p in sorted_paths if p.endswith('.sql') or p.endswith('.db')]
        for p in sql_paths:
            f.write(f'- `{p}`\n')
        f.write(f'\n**Total:** {len(sql_paths)}\n\n')

        f.write('### Swift Files\n\n')
        swift_paths = [p for p in sorted_paths if p.endswith('.swift')]
        for p in swift_paths:
            f.write(f'- `{p}`\n')
        f.write(f'\n**Total:** {len(swift_paths)}\n\n')

        f.write('### Other Files\n\n')
        other_paths = [p for p in sorted_paths if not p.endswith(('.py', '.md', '.sql', '.db', '.swift'))]
        for p in other_paths:
            f.write(f'- `{p}`\n')
        f.write(f'\n**Total:** {len(other_paths)}\n\n')

        f.write('---\n\n')

        f.write('## Detailed Hits by Table\n\n')
        for key in sorted(grouped.keys()):
            hits = grouped[key]
            all_terms = set()
            all_cols = set()
            for h in hits:
                for p in h.get('previews', []):
                    all_terms.add(p['term'])
                    all_cols.add(p['column'])
            f.write(f'### `{key}` ({len(hits)} hits)\n\n')
            f.write(f'- **Terms matched:** {", ".join(sorted(all_terms))}\n')
            f.write(f'- **Columns:** {", ".join(sorted(all_cols))}\n\n')

            f.write('| Row ID | Column | Term | Text Preview |\n')
            f.write('|--------|--------|------|-------------|\n')
            shown = 0
            for h in hits:
                for p in h.get('previews', []):
                    if shown >= 50:
                        break
                    preview = p['text_preview'].replace('|', '\\|').replace('\n', ' ')[:120]
                    f.write(f"| {h['row_id']} | `{p['column']}` | `{p['term']}` | {preview} |\n")
                    shown += 1
                if shown >= 50:
                    break
            remaining = sum(len(h.get('previews', [])) for h in hits) - shown
            if remaining > 0:
                f.write(f'| ... | | | *{remaining} more* |\n')
            f.write('\n')

        f.write('---\n\n')

        f.write('## Key Tables Analysis\n\n')
        for key in sorted(grouped.keys()):
            hits = grouped[key]
            all_terms = set()
            all_cols = set()
            for h in hits:
                for p in h.get('previews', []):
                    all_terms.add(p['term'])
                    all_cols.add(p['column'])
            sample_ids = [str(h['row_id']) for h in hits[:5]]
            f.write(f'### `{key}`\n\n')
            f.write(f'- **Hits:** {len(hits)}\n')
            f.write(f'- **Terms matched:** {", ".join(sorted(all_terms))}\n')
            f.write(f'- **Columns searched:** {", ".join(sorted(all_cols))}\n')
            f.write(f'- **Sample row IDs:** {", ".join(sample_ids)}\n\n')

        f.write('---\n\n')
        f.write('## Methodology\n\n')
        f.write('1. Connected to MySQL as root on localhost:3306\n')
        f.write(f'2. Searched databases: {", ".join(DBS_TO_SEARCH)}\n')
        f.write(f'3. For each table, searched all TEXT/VARCHAR/CHAR columns\n')
        f.write(f'4. Search terms: {", ".join(SEARCH_TERMS)}\n')
        f.write('5. Extracted file paths from matching rows using regex\n')
        f.write('6. Deduplicated results and grouped by database.table\n')
        f.write('7. Saved to this .md file\n\n')
        f.write('---\n')
        f.write('\n*Generated by `search_memunit_refs.py`*\n')

    print(f'\nDone! Results saved to: {OUTPUT_MD}')
    print(f'Total unique hits: {len(unique_results)}')
    print(f'Total file paths: {len(sorted_paths)}')
    print(f'Tables with hits: {len(grouped)}')

if __name__ == '__main__':
    main()
