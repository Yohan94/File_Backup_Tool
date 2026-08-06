"""One-time migration: dedupe file_metadata and add the unique index.

SQLite can't ALTER TABLE ADD CONSTRAINT, but a unique index is equivalent.
Safe to re-run: with no duplicates left, it becomes a no-op.
"""
import sqlite3
import sys

db = sys.argv[1] if len(sys.argv) > 1 else "backup_app.db"
con = sqlite3.connect(db)
try:
    dupes = con.execute("""
        SELECT COUNT(*) - COUNT(DISTINCT job_id || '|' || file_path) FROM file_metadata
    """).fetchone()[0]
    print(f"Duplicate rows to remove: {dupes}")

    # Keep the highest id (most recent) per (job_id, file_path).
    con.execute("""
        DELETE FROM file_metadata WHERE id NOT IN (
            SELECT MAX(id) FROM file_metadata GROUP BY job_id, file_path
        )
    """)
    con.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_file_metadata_job_path
        ON file_metadata (job_id, file_path)
    """)
    con.commit()
    print("Migration complete.")
finally:
    con.close()
