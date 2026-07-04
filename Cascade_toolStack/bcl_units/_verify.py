import sqlite3
db = sqlite3.connect('mac_commands_comprehensive.db')
c = db.cursor()
c.execute('SELECT COUNT(*) FROM commands')
print('Commands:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM training_samples')
print('Training samples:', c.fetchone()[0])
print()
print('=== CATEGORIES ===')
c.execute('SELECT category, COUNT(*) FROM commands GROUP BY category ORDER BY COUNT(*) DESC')
for r in c.fetchall():
    print(f'  {r[0]:30s} {r[1]:5d}')
print()
c.execute("SELECT COUNT(*) FROM commands WHERE description IS NOT NULL AND description != ''")
print('With description:', c.fetchone()[0])
c.execute("SELECT COUNT(*) FROM commands WHERE description IS NULL OR description = ''")
print('Without description:', c.fetchone()[0])
print()
print('=== SAMPLE COMMANDS ===')
for cmd in ['rm','git','curl','ls','ps','kill','chmod','brew','bash','find','df','du','date','whoami']:
    c.execute('SELECT name, category, description, risk_score FROM commands WHERE name=?', (cmd,))
    row = c.fetchone()
    if row:
        desc = (row[2] or '(empty)')[:50]
        print(f'  {row[0]:10s} cat={row[1]:25s} risk={row[3]:.2f} desc={desc}')
    else:
        print(f'  {cmd:10s} NOT FOUND')
print()
print('=== CURL TRAINING SAMPLES ===')
c.execute('SELECT command, context, risk_score FROM training_samples WHERE command LIKE "curl%" LIMIT 5')
for r in c.fetchall():
    print(f'  {r[0]:45s} ctx={r[1]:20s} risk={r[2]:.2f}')
print()
print('=== RM TRAINING SAMPLES ===')
c.execute('SELECT command, context, risk_score FROM training_samples WHERE command LIKE "rm %" LIMIT 5')
for r in c.fetchall():
    print(f'  {r[0]:45s} ctx={r[1]:20s} risk={r[2]:.2f}')
db.close()
