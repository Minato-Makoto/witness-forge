import sqlite3
import os

db_path = "witness.sqlite3"

if not os.path.exists(db_path):
    print(f"Database not found: {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get table schema
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='memories'")
schema = cursor.fetchone()
print("Table Schema:")
print(schema[0] if schema else "No 'memories' table found")
print("\n" + "="*80 + "\n")

# Get count
cursor.execute("SELECT COUNT(*) FROM memories")
total = cursor.fetchone()[0]
print(f"Total memories: {total}\n")

# Get recent entries (limit to first column to avoid errors)
cursor.execute("SELECT * FROM memories ORDER BY rowid DESC LIMIT 5")
rows = cursor.fetchall()

print("Recent 5 memories:")
for i, row in enumerate(rows, 1):
    print(f"{i}. {row}")

conn.close()
