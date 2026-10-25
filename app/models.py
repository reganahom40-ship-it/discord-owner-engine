import sqlite3
import json
import os
from datetime import datetime, timezone
from contextlib import contextmanager
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config

def get_db_path():
    try:
        from flask import current_app
        if current_app and hasattr(current_app, "config"):
            return current_app.config.get("DATABASE_PATH", Config.DATABASE_PATH)
    except Exception:
        pass
    return Config.DATABASE_PATH

@contextmanager
def get_db():
    conn = sqlite3.connect(get_db_path(), timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def _ensure_column(conn, table, column, col_def):
    existing = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")

def init_db():
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'owner',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS saved_webhooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            target_channel TEXT,
            status TEXT NOT NULL DEFAULT 'untested',
            last_latency_ms INTEGER,
            last_tested_at TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            target_webhook TEXT NOT NULL,
            content TEXT NOT NULL,
            embed_title TEXT,
            embed_color TEXT DEFAULT '#4f46e5',
            embed_author TEXT,
            embed_thumbnail TEXT,
            embed_image TEXT,
            embed_footer TEXT,
            embed_fields_json TEXT,
            status TEXT NOT NULL DEFAULT 'scheduled',
            interval_minutes INTEGER NOT NULL DEFAULT 60,
            next_run_at TEXT,
            last_run_at TEXT,
            run_count INTEGER NOT NULL DEFAULT 0,
            max_runs INTEGER NOT NULL DEFAULT 5,
            last_latency_ms INTEGER,
            last_error TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS task_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type TEXT NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            progress_percent INTEGER NOT NULL DEFAULT 0,
            payload_json TEXT,
            result_json TEXT,
            error_message TEXT,
            retries INTEGER NOT NULL DEFAULT 0,
            max_retries INTEGER NOT NULL DEFAULT 3,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS internal_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_code TEXT UNIQUE NOT NULL,
            label TEXT NOT NULL,
            service_scope TEXT NOT NULL DEFAULT 'all',
            status TEXT NOT NULL DEFAULT 'active',
            expires_at TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            details TEXT NOT NULL,
            ip_address TEXT,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns(status);
        CREATE INDEX IF NOT EXISTS idx_task_jobs_status ON task_jobs(status);
        """)

        # Safe schema migrations for existing databases
        _ensure_column(conn, "saved_webhooks", "last_latency_ms", "INTEGER")
        _ensure_column(conn, "campaigns", "embed_author", "TEXT")
        _ensure_column(conn, "campaigns", "embed_thumbnail", "TEXT")
        _ensure_column(conn, "campaigns", "embed_image", "TEXT")
        _ensure_column(conn, "campaigns", "embed_footer", "TEXT")
        _ensure_column(conn, "campaigns", "embed_fields_json", "TEXT")
        _ensure_column(conn, "campaigns", "last_latency_ms", "INTEGER")

        # Seed single default owner if no users exist
        owner_row = conn.execute("SELECT id, role FROM users WHERE username = 'admin'").fetchone()
        now_iso = datetime.now(timezone.utc).isoformat()
        if not owner_row:
            hashed_pw = generate_password_hash("AdminPass6767!")
            conn.execute(
                "INSERT INTO users (username, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
                ("admin", "owner@platform.local", hashed_pw, "owner", now_iso)
            )
        elif owner_row["role"] != "owner":
            conn.execute("UPDATE users SET role = 'owner' WHERE id = ?", (owner_row["id"],))

        # Seed default system settings if not present
        default_settings = [
            ("discord_bot_token", Config.DISCORD_BOT_TOKEN or ""),
            ("discord_client_id", Config.DISCORD_CLIENT_ID or ""),
            ("discord_client_secret", Config.DISCORD_CLIENT_SECRET or ""),
            ("default_guild_id", ""),
            ("worker_interval_sec", "5")
        ]
        for k, v in default_settings:
            exists = conn.execute("SELECT key FROM system_settings WHERE key = ?", (k,)).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO system_settings (key, value, updated_at) VALUES (?, ?, ?)",
                    (k, v, now_iso)
                )

class Settings:
    @staticmethod
    def get(key, default=""):
        with get_db() as conn:
            row = conn.execute("SELECT value FROM system_settings WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else default

    @staticmethod
    def set(key, value):
        now_iso = datetime.now(timezone.utc).isoformat()
        with get_db() as conn:
            conn.execute(
                """INSERT INTO system_settings (key, value, updated_at) 
                VALUES (?, ?, ?) 
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
                (key, str(value), now_iso)
            )

    @staticmethod
    def get_all():
        with get_db() as conn:
            rows = conn.execute("SELECT key, value FROM system_settings").fetchall()
            return {r["key"]: r["value"] for r in rows}

class User:
    @staticmethod
    def get_owner():
        with get_db() as conn:
            row = conn.execute("SELECT * FROM users LIMIT 1").fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_by_id(user_id):
        with get_db() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_by_username_or_email(identifier):
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ? OR email = ?",
                (identifier.strip(), identifier.strip().lower())
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def verify_password(user_dict, password):
        return check_password_hash(user_dict["password_hash"], password)

    @staticmethod
    def update_password(user_id, new_password):
        pw_hash = generate_password_hash(new_password)
        with get_db() as conn:
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, user_id))

def record_audit(event_type, details, ip_address=None, conn=None):
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        if conn:
            conn.execute(
                "INSERT INTO audit_logs (event_type, details, ip_address, created_at) VALUES (?, ?, ?, ?)",
                (event_type, str(details), ip_address or "127.0.0.1", now_iso)
            )
        else:
            with get_db() as c:
                c.execute(
                    "INSERT INTO audit_logs (event_type, details, ip_address, created_at) VALUES (?, ?, ?, ?)",
                    (event_type, str(details), ip_address or "127.0.0.1", now_iso)
                )
    except Exception as e:
        print(f"[AUDIT ERROR] Failed to record audit log: {e}")
