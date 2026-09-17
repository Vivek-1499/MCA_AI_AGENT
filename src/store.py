import sqlite3
import os
from typing import List, Dict, Optional
from contextlib import contextmanager

DB_PATH = "processed_docs.db"

@contextmanager
def get_db_cursor():
    """Context manager to handle SQLite connections cleanly."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    finally:
        conn.close()

def init_db():
    with get_db_cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                filename TEXT,
                category TEXT,
                source_tab TEXT,
                file_size_bytes INTEGER,
                extracted_text_preview TEXT,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Migration checks
        try:
            cursor.execute("ALTER TABLE processed_documents ADD COLUMN source_tab TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE processed_documents ADD COLUMN file_size_bytes INTEGER")
        except sqlite3.OperationalError:
            pass

def is_url_processed(url: str) -> bool:
    with get_db_cursor() as cursor:
        cursor.execute("SELECT 1 FROM processed_documents WHERE url = ?", (url,))
        return cursor.fetchone() is not None

def get_processed_count() -> int:
    with get_db_cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM processed_documents")
        return cursor.fetchone()[0]

def get_summary_by_category() -> Dict[str, int]:
    with get_db_cursor() as cursor:
        cursor.execute("SELECT category, COUNT(*) FROM processed_documents GROUP BY category")
        rows = cursor.fetchall()
        return {row[0]: row[1] for row in rows}

def record_processed_doc(url: str, filename: str, category: str, source_tab: str, text_preview: str, file_size_bytes: int = 0):
    with get_db_cursor() as cursor:
        cursor.execute("""
            INSERT OR REPLACE INTO processed_documents (url, filename, category, source_tab, file_size_bytes, extracted_text_preview)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (url, filename, category, source_tab, file_size_bytes, text_preview[:500]))
