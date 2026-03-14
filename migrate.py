import sqlite3
conn = sqlite3.connect("/app/data/sales_analyzer.db")
cur = conn.cursor()
cur.execute("PRAGMA table_info(analyses)")
cols = [r[1] for r in cur.fetchall()]
print("Current columns:", cols)
if "golden_pitch_deck_id" not in cols:
    cur.execute("ALTER TABLE analyses ADD COLUMN golden_pitch_deck_id TEXT")
    print("Added golden_pitch_deck_id")
if "skip_comparison" not in cols:
    cur.execute("ALTER TABLE analyses ADD COLUMN skip_comparison BOOLEAN DEFAULT 0 NOT NULL")
    print("Added skip_comparison")
conn.commit()
conn.close()
print("Migration complete")
