import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).resolve().parent / "topics_history.db"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posted_shorts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_summary TEXT NOT NULL,
                youtube_video_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

def get_recent_topics(limit: int = 50) -> list[str]:
    init_db()
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT topic_summary FROM posted_shorts ORDER BY id DESC LIMIT ?", (limit,))
        return [row[0] for row in cursor.fetchall()]

def record_published_short(topic_summary: str, video_id: str):
    init_db()
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "INSERT INTO posted_shorts (topic_summary, youtube_video_id) VALUES (?, ?)",
            (topic_summary, video_id)
        )