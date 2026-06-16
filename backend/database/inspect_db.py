import sqlite3

if __name__ == "__main__":
    conn = sqlite3.connect("complisoc.db")
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cur.fetchall()]
    print(tables)
    conn.close()
