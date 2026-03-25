import sqlite3
from contextlib import contextmanager

DB_PATH = "members.db"


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS members (
                discord_id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_checked TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        """)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def add_member(discord_id: str, email: str):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO members (discord_id, email, is_active)
            VALUES (?, ?, 1)
            ON CONFLICT(discord_id) DO UPDATE SET
                email = excluded.email,
                verified_at = CURRENT_TIMESTAMP,
                is_active = 1
        """, (discord_id, email))


def get_member(discord_id: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM members WHERE discord_id = ?", (discord_id,)
        ).fetchone()


def get_all_active_members():
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM members WHERE is_active = 1"
        ).fetchall()


def deactivate_member(discord_id: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE members SET is_active = 0 WHERE discord_id = ?", (discord_id,)
        )


def get_member_by_email(email: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM members WHERE email = ? AND is_active = 1", (email,)
        ).fetchone()


def update_last_checked(discord_id: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE members SET last_checked = CURRENT_TIMESTAMP WHERE discord_id = ?",
            (discord_id,)
        )
