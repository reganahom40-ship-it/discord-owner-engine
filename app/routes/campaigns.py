import json
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from app.models import get_db, record_audit
from app.routes.auth import owner_required
from app.services.discord_integration import DiscordIntegrationService
from app.services.scheduler import worker

campaigns_bp = Blueprint("owner_campaigns", __name__, url_prefix="/api/owner/campaigns")

@campaigns_bp.route("", methods=["GET"])
@owner_required
def list_campaigns():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM campaigns ORDER BY id DESC").fetchall()
        return jsonify({"campaigns": [dict(r) for r in rows]})

@campaigns_bp.route("", methods=["POST"])
@owner_required
def create_campaign():
    data = request.get_json() or {}

    title = data.get("title", "").strip()
    target_webhook = data.get("target_webhook", "").strip()
    content = data.get("content", "").strip()
    embed_title = data.get("embed_title", "").strip() or None
    embed_color = data.get("embed_color", "#4f46e5").strip()
    embed_author = data.get("embed_author", "").strip() or None
    embed_thumbnail = data.get("embed_thumbnail", "").strip() or None
    embed_image = data.get("embed_image", "").strip() or None
    embed_footer = data.get("embed_footer", "").strip() or None
    embed_fields = data.get("embed_fields")
    embed_fields_json = json.dumps(embed_fields) if embed_fields and isinstance(embed_fields, list) else None

    interval_minutes = max(int(data.get("interval_minutes", 60)), 1)
    max_runs = max(int(data.get("max_runs", 5)), 1)

    if not title:
        return jsonify({"error": "Campaign title required"}), 400
    if not target_webhook:
        return jsonify({"error": "Target webhook required"}), 400
    if not content:
        return jsonify({"error": "Message content cannot be empty"}), 400

    is_valid, reason = DiscordIntegrationService.validate_webhook_url(target_webhook)
    if not is_valid:
        return jsonify({"error": reason}), 400

    now_iso = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO campaigns 
            (title, target_webhook, content, embed_title, embed_color, embed_author, embed_thumbnail, embed_image, embed_footer, embed_fields_json, status, interval_minutes, next_run_at, max_runs, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'scheduled', ?, ?, ?, ?)""",
            (title, target_webhook, content, embed_title, embed_color, embed_author, embed_thumbnail, embed_image, embed_footer, embed_fields_json, interval_minutes, now_iso, max_runs, now_iso)
        )
        camp_id = cursor.lastrowid
        record_audit("CAMPAIGN_SCHEDULED", f"Scheduled owner broadcast campaign '{title}' (ID {camp_id})", conn=conn)

    return jsonify({"success": True, "campaign_id": camp_id, "message": "Broadcast campaign scheduled"}), 201

@campaigns_bp.route("/preview", methods=["POST"])
@owner_required
def preview_campaign():
    data = request.get_json() or {}
    content = data.get("content", "")
    embed_title = data.get("embed_title", "")
    embed_color = data.get("embed_color", "#4f46e5")
    embed_author = data.get("embed_author", "")
    embed_footer = data.get("embed_footer", "Private Owner Control Panel • Verified Transmission")

    return jsonify({
        "preview": {
            "author": "Owner Control Panel",
            "content": content if not embed_title else "",
            "embed": {
                "author": embed_author,
                "title": embed_title,
                "description": content,
                "color": embed_color,
                "footer": embed_footer
            } if embed_title or embed_author else None
        }
    })

@campaigns_bp.route("/test-dispatch", methods=["POST"])
@owner_required
def test_dispatch():
    data = request.get_json() or {}
    target_webhook = data.get("target_webhook", "").strip()
    content = data.get("content", "⚡ Test broadcast verification from Private Owner Control Center.")
    embed_title = data.get("embed_title", "Test Broadcast")
    embed_color = data.get("embed_color", "#4f46e5")
    embed_author = data.get("embed_author", "").strip() or None
    embed_thumbnail = data.get("embed_thumbnail", "").strip() or None
    embed_image = data.get("embed_image", "").strip() or None
    embed_footer = data.get("embed_footer", "").strip() or None
    embed_fields = data.get("embed_fields")

    result = DiscordIntegrationService.send_webhook_message(
        webhook_url=target_webhook,
        content=content,
        embed_title=embed_title,
        embed_color=embed_color,
        embed_author=embed_author,
        embed_thumbnail=embed_thumbnail,
        embed_image=embed_image,
        embed_footer=embed_footer,
        embed_fields=embed_fields
    )
    return jsonify(result), 200 if result["success"] else 400

@campaigns_bp.route("/<int:camp_id>/action", methods=["POST"])
@owner_required
def campaign_action(camp_id):
    data = request.get_json() or {}
    action = data.get("action", "").lower()

    if action not in ("pause", "resume", "cancel", "delete", "run_now"):
        return jsonify({"error": "Invalid action"}), 400

    with get_db() as conn:
        row = conn.execute("SELECT * FROM campaigns WHERE id = ?", (camp_id,)).fetchone()
        if not row:
            return jsonify({"error": "Campaign not found"}), 404
        camp = dict(row)

        if action == "delete":
            conn.execute("DELETE FROM campaigns WHERE id = ?", (camp_id,))
            record_audit("CAMPAIGN_DELETED", f"Deleted campaign #{camp_id}", conn=conn)
            return jsonify({"success": True, "message": "Campaign deleted"})

    if action == "run_now":
        res = worker.execute_single_campaign(camp)
        return jsonify({
            "success": res["success"],
            "campaign_id": camp_id,
            "latency_ms": res.get("latency_ms"),
            "message": res.get("message") or res.get("error", "Executed")
        }), 200 if res["success"] else 400

    new_status = "paused" if action == "pause" else ("scheduled" if action == "resume" else "cancelled")
    with get_db() as conn:
        conn.execute("UPDATE campaigns SET status = ? WHERE id = ?", (new_status, camp_id))
        record_audit("CAMPAIGN_ACTION", f"Campaign #{camp_id} set to '{new_status}'", conn=conn)

    return jsonify({"success": True, "campaign_id": camp_id, "new_status": new_status})
