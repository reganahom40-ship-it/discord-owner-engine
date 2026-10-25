import secrets
import string
from datetime import datetime, timedelta, timezone
from app.models import get_db, record_audit

def generate_key_string(prefix="OWN"):
    charset = string.ascii_uppercase + string.digits
    clean_prefix = ''.join(c for c in (prefix or "OWN").upper() if c.isalnum())[:8] or "OWN"
    parts = [''.join(secrets.choice(charset) for _ in range(4)) for _ in range(3)]
    return f"{clean_prefix}-{'-'.join(parts)}"

class InternalKeyService:
    @staticmethod
    def create_key(label, service_scope="all", duration_days=90, prefix="OWN"):
        key_code = generate_key_string(prefix)
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        expires_at = (now + timedelta(days=duration_days)).isoformat() if duration_days > 0 else None

        with get_db() as conn:
            cursor = conn.execute(
                """INSERT INTO internal_keys (key_code, label, service_scope, status, expires_at, created_at)
                VALUES (?, ?, ?, 'active', ?, ?)""",
                (key_code, label.strip(), service_scope, expires_at, now_iso)
            )
            key_id = cursor.lastrowid
            record_audit("INTERNAL_KEY_CREATED", f"Created internal key '{label}' ({key_code})", conn=conn)

        return {
            "id": key_id,
            "key_code": key_code,
            "label": label,
            "service_scope": service_scope,
            "expires_at": expires_at,
            "status": "active"
        }

    @staticmethod
    def list_keys():
        with get_db() as conn:
            rows = conn.execute("SELECT * FROM internal_keys ORDER BY id DESC").fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def revoke_key(key_id):
        with get_db() as conn:
            conn.execute("UPDATE internal_keys SET status = 'revoked' WHERE id = ?", (key_id,))
            record_audit("INTERNAL_KEY_REVOKED", f"Revoked internal authorization key #{key_id}", conn=conn)
        return True

    @staticmethod
    def validate_key(key_code):
        key_code = key_code.strip().upper()
        with get_db() as conn:
            row = conn.execute("SELECT * FROM internal_keys WHERE key_code = ?", (key_code,)).fetchone()
            if not row:
                return {"valid": False, "error": "Authorization key not found"}

            data = dict(row)
            if data["status"] == "revoked":
                return {"valid": False, "error": "Authorization key has been revoked"}

            if data["expires_at"]:
                now_iso = datetime.now(timezone.utc).isoformat()
                if data["expires_at"] < now_iso:
                    return {"valid": False, "error": "Authorization key has expired"}

            return {"valid": True, "key": data}
