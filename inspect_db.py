import sqlite3
conn = sqlite3.connect('/app/data/audit.sqlite3')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cur.fetchall()]
print('TABLES:', tables)
for t in tables:
    print(f'--- {t} ---')
    cur.execute(f'SELECT * FROM {t} ORDER BY rowid DESC LIMIT 3')
    for row in cur.fetchall():
        print(row)
