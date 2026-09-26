import os
import sqlite3
from config import DB_PATH

def get_connection():
    directory = os.path.dirname(DB_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_message_id INTEGER NOT NULL,
            chat_id TEXT NOT NULL,
            chat_name TEXT,
            sender_name TEXT,
            message_text TEXT,
            media_path TEXT,
            category TEXT,
            importance TEXT,
            title TEXT,
            summary TEXT,
            sentiment TEXT,
            market_impact TEXT,
            ai_response TEXT,
            created_at TEXT,
            UNIQUE(chat_id, telegram_message_id)
        )
    """)
    conn.commit()
    conn.close()

def message_exists(chat_id, telegram_message_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM messages WHERE chat_id=? AND telegram_message_id=?",
        (str(chat_id), telegram_message_id)
    ).fetchone()
    conn.close()
    return row is not None

def save_message(
    telegram_message_id, chat_id, chat_name, sender_name,
    message_text, media_path, category, importance, title,
    summary, sentiment, market_impact, ai_response, created_at
):
    conn = get_connection()
    conn.execute("""
        INSERT OR IGNORE INTO messages (
            telegram_message_id, chat_id, chat_name, sender_name,
            message_text, media_path, category, importance, title,
            summary, sentiment, market_impact, ai_response, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        telegram_message_id, str(chat_id), chat_name, sender_name,
        message_text, media_path, category, importance, title,
        summary, sentiment, market_impact, ai_response, created_at
    ))
    conn.commit()
    conn.close()

def stats():
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    important = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE importance IN ('medium','high','critical')"
    ).fetchone()[0]
    conn.close()
    return total, important
