import sqlite3
from pathlib import Path

for relative_path in ["complisoc.db", "complisoc/complisoc.db"]:
    path = Path(relative_path)
    print("path:", path)
    print("exists:", path.exists())
    if path.exists():
        with sqlite3.connect(path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            print("tables:", [row[0] for row in cur.fetchall()])
    print()
