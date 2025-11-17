import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterator, Optional


DB_PATH = Path(__file__).resolve().parents[1] / "bot.db"


def init_db() -> None:
    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                language_code TEXT,
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                media_url TEXT NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT,
                media_count INTEGER DEFAULT 0,
                media_types TEXT,
                file_sizes_mb TEXT,
                created_at TEXT NOT NULL
            )
            """
        )

        # Migration: rename column instagram_url -> media_url if needed
        cur.execute("PRAGMA table_info(downloads)")
        cols = [row[1] for row in cur.fetchall()]
        if "instagram_url" in cols and "media_url" not in cols:
            try:
                cur.execute("ALTER TABLE downloads RENAME COLUMN instagram_url TO media_url")
            except sqlite3.OperationalError:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS downloads_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id INTEGER NOT NULL,
                        media_url TEXT NOT NULL,
                        status TEXT NOT NULL,
                        error_message TEXT,
                        media_count INTEGER DEFAULT 0,
                        media_types TEXT,
                        file_sizes_mb TEXT,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    INSERT INTO downloads_new (id, chat_id, media_url, status, error_message, media_count, media_types, file_sizes_mb, created_at)
                    SELECT id, chat_id, instagram_url, status, error_message, media_count, media_types, file_sizes_mb, created_at
                    FROM downloads
                    """
                )
                cur.execute("DROP TABLE downloads")
                cur.execute("ALTER TABLE downloads_new RENAME TO downloads")

        conn.commit()


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def upsert_user(
    chat_id: int,
    username: Optional[str],
    first_name: Optional[str],
    last_name: Optional[str],
    language_code: Optional[str],
) -> None:
    now = datetime.utcnow().isoformat()

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO users (chat_id, username, first_name, last_name, language_code, created_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                last_name=excluded.last_name,
                language_code=excluded.language_code,
                last_seen_at=excluded.last_seen_at
            """,
            (chat_id, username, first_name, last_name, language_code, now, now),
        )
        conn.commit()


def log_download(
    chat_id: int,
    media_url: str,
    status: str,
    error_message: Optional[str] = None,
    media_count: int = 0,
    media_types: Optional[str] = None,
    file_sizes_mb: Optional[str] = None,
) -> None:
    now = datetime.utcnow().isoformat()

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO downloads (
                chat_id, media_url, status, error_message, 
                media_count, media_types, file_sizes_mb, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (chat_id, media_url, status, error_message, media_count, media_types, file_sizes_mb, now),
        )
        conn.commit()


def get_detailed_stats() -> Dict[str, any]:
    """Batafsil statistika olish."""
    with get_connection() as conn:
        cur = conn.cursor()
        
        # Asosiy statistika
        cur.execute("SELECT COUNT(*) FROM users")
        users_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM downloads")
        downloads_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM downloads WHERE status = 'success'")
        success_count = cur.fetchone()[0]
        
        # Media turlari statistikasi
        cur.execute(
            """
            SELECT media_types, COUNT(*) as count 
            FROM downloads 
            WHERE status = 'success' AND media_types IS NOT NULL
            GROUP BY media_types
            ORDER BY count DESC
            LIMIT 10
            """
        )
        media_types_stats = cur.fetchall()
        
        # Oxirgi 7 kundagi faollik
        cur.execute(
            """
            SELECT DATE(created_at) as day, COUNT(*) as count
            FROM downloads
            WHERE created_at >= datetime('now', '-7 days')
            GROUP BY DATE(created_at)
            ORDER BY day DESC
            """
        )
        daily_activity = cur.fetchall()
        
        return {
            "users_count": users_count,
            "downloads_count": downloads_count,
            "success_count": success_count,
            "success_rate": round((success_count / downloads_count * 100) if downloads_count > 0 else 0, 1),
            "media_types_stats": media_types_stats,
            "daily_activity": daily_activity,
        }
