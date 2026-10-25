import json
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, session
from app.models import get_db, record_audit, Settings
from app.routes.auth import owner_required
from app.services.discord_integration import DiscordIntegrationService
from app.services.scheduler import worker

dashboard_bp = Blueprint("owner_dashboard", __name__, url_prefix="/api/owner")

@dashboard_bp.route("/overview", methods=["GET"])
@owner_required
def get_overview():
    bot_token = Settings.get("discord_bot_token", "")
    bot_status = "unconfigured"
    bot_name = None
    bot_latency_ms = None

    if bot_token:
        verify = DiscordIntegrationService.verify_bot_token(bot_token)
        if verify["valid"]:
            bot_status = "connected"
            bot_name = verify["bot"].get("username")
            bot_latency_ms = verify.get("latency_ms")
        else:
            bot_status = "error"

    with get_db() as conn:
        active_campaigns = conn.execute("SELECT COUNT(*) FROM campaigns WHERE status IN ('scheduled', 'running')").fetchone()[0]
        running_tasks = conn.execute("SELECT COUNT(*) FROM task_jobs WHERE status = 'running'").fetchone()[0]
        pending_tasks = conn.execute("SELECT COUNT(*) FROM task_jobs WHERE status = 'pending'").fetchone()[0]
        failed_tasks = conn.execute("SELECT COUNT(*) FROM task_jobs WHERE status = 'failed'").fetchone()[0]
        completed_tasks = conn.execute("SELECT COUNT(*) FROM task_jobs WHERE status = 'completed'").fetchone()[0]
        total_webhooks = conn.execute("SELECT COUNT(*) FROM saved_webhooks").fetchone()[0]
        active_keys = conn.execute("SELECT COUNT(*) FROM internal_keys WHERE status = 'active'").fetchone()[0]
        recent_logs = conn.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 30").fetchall()

    return jsonify({
        "telemetry": {
            "bot_status": bot_status,
            "bot_name": bot_name,
            "bot_latency_ms": bot_latency_ms,
            "worker_running": worker.running,
            "worker_last_run": worker.last_run,
            "jobs_processed": worker.jobs_processed,
            "active_campaigns": active_campaigns,
            "running_tasks": running_tasks,
            "pending_tasks": pending_tasks,
            "failed_tasks": failed_tasks,
            "completed_tasks": completed_tasks,
            "total_webhooks": total_webhooks,
            "active_keys": active_keys
        },
        "console_logs": worker.get_logs(),
        "recent_logs": [dict(l) for l in recent_logs]
    })

@dashboard_bp.route("/console-logs", methods=["GET"])
@owner_required
def get_console_logs():
    return jsonify({"console_logs": worker.get_logs(), "worker_running": worker.running})

@dashboard_bp.route("/settings", methods=["GET", "POST"])
@owner_required
def handle_settings():
    if request.method == "POST":
        data = request.get_json() or {}
        if "discord_bot_token" in data and data["discord_bot_token"] != "********":
            Settings.set("discord_bot_token", data["discord_bot_token"].strip())
        if "discord_client_id" in data:
            Settings.set("discord_client_id", data["discord_client_id"].strip())
        if "discord_client_secret" in data and data["discord_client_secret"] != "********":
            Settings.set("discord_client_secret", data["discord_client_secret"].strip())
        if "default_guild_id" in data:
            Settings.set("default_guild_id", data["default_guild_id"].strip())

        record_audit("SETTINGS_UPDATED", "Owner updated platform integrations and credentials")
        return jsonify({"success": True, "message": "Settings saved successfully"})

    all_settings = Settings.get_all()
    bot_token = all_settings.get("discord_bot_token", "")
    secret = all_settings.get("discord_client_secret", "")
    return jsonify({
        "settings": {
            "discord_bot_token_set": bool(bot_token),
            "discord_bot_token_masked": (bot_token[:6] + "..." + bot_token[-4:]) if len(bot_token) > 10 else ("Configured" if bot_token else ""),
            "discord_client_id": all_settings.get("discord_client_id", ""),
            "discord_client_secret_set": bool(secret),
            "default_guild_id": all_settings.get("default_guild_id", ""),
            "bot_invite_url": DiscordIntegrationService.generate_bot_invite(all_settings.get("discord_client_id", ""))
        }
    })

@dashboard_bp.route("/test-bot", methods=["POST"])
@owner_required
def test_bot():
    data = request.get_json() or {}
    token = data.get("bot_token")
    if not token or token == "********":
        token = Settings.get("discord_bot_token", "")

    if not token:
        return jsonify({"valid": False, "error": "No Bot Token provided or configured"}), 400

    result = DiscordIntegrationService.verify_bot_token(token)
    return jsonify(result)

@dashboard_bp.route("/bot-guilds", methods=["GET"])
@owner_required
def bot_guilds():
    bot_token = Settings.get("discord_bot_token", "")
    if not bot_token:
        return jsonify({"success": False, "error": "Discord Bot Token not configured", "guilds": []})
    res = DiscordIntegrationService.get_bot_guilds(bot_token)
    return jsonify(res)

@dashboard_bp.route("/guild-telemetry", methods=["GET"])
@owner_required
def guild_telemetry():
    guild_id = request.args.get("guild_id") or Settings.get("default_guild_id")
    if not guild_id:
        return jsonify({"success": False, "error": "No Guild ID specified. Please enter a Server ID."}), 400

    bot_token = Settings.get("discord_bot_token", "")
    if not bot_token:
        return jsonify({"success": False, "error": "Bot token not configured. Enter bot token in Integrations first."}), 400

    telemetry = DiscordIntegrationService.get_guild_telemetry(bot_token, guild_id)
    return jsonify(telemetry)

@dashboard_bp.route("/webhooks", methods=["GET", "POST"])
@owner_required
def handle_webhooks():
    if request.method == "POST":
        data = request.get_json() or {}
        name = data.get("name", "").strip()
        url = data.get("url", "").strip()
        channel = data.get("target_channel", "").strip()

        if not name or not url:
            return jsonify({"error": "Name and Webhook URL required"}), 400

        is_valid, msg = DiscordIntegrationService.validate_webhook_url(url)
        if not is_valid:
            return jsonify({"error": msg}), 400

        now_iso = datetime.now(timezone.utc).isoformat()
        with get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO saved_webhooks (name, url, target_channel, status, created_at) VALUES (?, ?, ?, 'untested', ?)",
                (name, url, channel, now_iso)
            )
            wh_id = cursor.lastrowid
            record_audit("WEBHOOK_SAVED", f"Saved webhook '{name}' (ID {wh_id})", conn=conn)

        return jsonify({"success": True, "webhook_id": wh_id, "message": "Webhook saved successfully"}), 201

    with get_db() as conn:
        rows = conn.execute("SELECT * FROM saved_webhooks ORDER BY id DESC").fetchall()
        return jsonify({"webhooks": [dict(r) for r in rows]})

@dashboard_bp.route("/webhooks/<int:wh_id>", methods=["DELETE"])
@owner_required
def delete_webhook(wh_id):
    with get_db() as conn:
        conn.execute("DELETE FROM saved_webhooks WHERE id = ?", (wh_id,))
        record_audit("WEBHOOK_DELETED", f"Deleted webhook #{wh_id}", conn=conn)
    return jsonify({"success": True, "message": "Webhook deleted"})

@dashboard_bp.route("/webhooks/<int:wh_id>/test", methods=["POST"])
@owner_required
def test_saved_webhook(wh_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM saved_webhooks WHERE id = ?", (wh_id,)).fetchone()
        if not row:
            return jsonify({"error": "Webhook not found"}), 404

        url = row["url"]
        result = DiscordIntegrationService.send_webhook_message(
            webhook_url=url,
            content="⚡ **Verified Transmission Test** from Private Owner Control Center.",
            embed_title="Webhook Connectivity & Latency Verification"
        )

        now_iso = datetime.now(timezone.utc).isoformat()
        new_status = "healthy" if result["success"] else "failed"
        latency_ms = result.get("latency_ms")
        conn.execute(
            "UPDATE saved_webhooks SET status = ?, last_latency_ms = ?, last_tested_at = ? WHERE id = ?",
            (new_status, latency_ms, now_iso, wh_id)
        )

    return jsonify(result)

@dashboard_bp.route("/tasks", methods=["GET", "POST"])
@owner_required
def handle_tasks():
    if request.method == "POST":
        data = request.get_json() or {}
        task_type = data.get("task_type", "quest_sync")
        name = data.get("name", "Owner Task Execution").strip()
        payload = data.get("payload", {})
        run_immediately = bool(data.get("run_immediately", False))

        now_iso = datetime.now(timezone.utc).isoformat()
        with get_db() as conn:
            cursor = conn.execute(
                """INSERT INTO task_jobs 
                (task_type, name, status, progress_percent, payload_json, created_at, updated_at)
                VALUES (?, ?, 'pending', 0, ?, ?, ?)""",
                (task_type, name, json.dumps(payload), now_iso, now_iso)
            )
            job_id = cursor.lastrowid
            record_audit("TASK_QUEUED", f"Queued {task_type} task: '{name}'", conn=conn)

        if run_immediately:
            worker.process_tasks()

        return jsonify({"success": True, "job_id": job_id, "message": "Job queued successfully"}), 201

    with get_db() as conn:
        rows = conn.execute("SELECT * FROM task_jobs ORDER BY id DESC LIMIT 60").fetchall()
        return jsonify({"tasks": [dict(r) for r in rows]})

@dashboard_bp.route("/tasks/<int:task_id>", methods=["GET"])
@owner_required
def get_task_detail(task_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM task_jobs WHERE id = ?", (task_id,)).fetchone()
        if not row:
            return jsonify({"error": "Task not found"}), 404
        return jsonify({"task": dict(row)})

@dashboard_bp.route("/tasks/clear-completed", methods=["POST"])
@owner_required
def clear_completed_tasks():
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM task_jobs WHERE status IN ('completed', 'cancelled', 'failed')")
        deleted = cursor.rowcount
        record_audit("TASKS_PURGED", f"Purged {deleted} finished/cancelled tasks", conn=conn)
    return jsonify({"success": True, "deleted": deleted, "message": f"Cleared {deleted} tasks"})

@dashboard_bp.route("/tasks/<int:task_id>/action", methods=["POST"])
@owner_required
def task_action(task_id):
    data = request.get_json() or {}
    action = data.get("action", "").lower()

    if action not in ("cancel", "pause", "resume", "retry", "run_now"):
        return jsonify({"error": "Invalid action"}), 400

    now_iso = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        row = conn.execute("SELECT * FROM task_jobs WHERE id = ?", (task_id,)).fetchone()
        if not row:
            return jsonify({"error": "Task not found"}), 404

        current = row["status"]
        if action == "cancel":
            new_status = "cancelled"
        elif action == "pause" and current in ("pending", "running"):
            new_status = "paused"
        elif action == "resume" and current == "paused":
            new_status = "pending"
        elif action in ("retry", "run_now"):
            new_status = "pending"
            conn.execute(
                "UPDATE task_jobs SET status = 'pending', retries = 0, error_message = NULL, progress_percent = 0, updated_at = ? WHERE id = ?",
                (now_iso, task_id)
            )
        else:
            return jsonify({"error": f"Cannot {action} task in state '{current}'"}), 400

        if action not in ("retry", "run_now"):
            conn.execute("UPDATE task_jobs SET status = ?, updated_at = ? WHERE id = ?", (new_status, now_iso, task_id))
        record_audit("TASK_STATUS_UPDATE", f"Task #{task_id} transitioned to '{new_status}'", conn=conn)

    if action == "run_now":
        worker.process_tasks()

    return jsonify({"success": True, "task_id": task_id, "new_status": new_status})
