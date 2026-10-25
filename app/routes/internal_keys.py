from flask import Blueprint, request, jsonify
from app.routes.auth import owner_required
from app.services.licensing import InternalKeyService

keys_bp = Blueprint("internal_keys", __name__, url_prefix="/api/owner/keys")

@keys_bp.route("", methods=["GET"])
@owner_required
def list_keys():
    keys = InternalKeyService.list_keys()
    return jsonify({"keys": keys})

@keys_bp.route("", methods=["POST"])
@owner_required
def generate_key():
    data = request.get_json() or {}
    label = data.get("label", "Worker Node").strip()
    service_scope = data.get("service_scope", "all")
    duration_days = int(data.get("duration_days", 90))
    prefix = data.get("prefix", "OWN").strip() or "OWN"
    count = min(max(int(data.get("count", 1)), 1), 25)

    if not label:
        return jsonify({"error": "Key label is required"}), 400

    created = []
    for i in range(count):
        item_label = f"{label} #{i+1}" if count > 1 else label
        new_key = InternalKeyService.create_key(item_label, service_scope, duration_days, prefix=prefix)
        created.append(new_key)

    return jsonify({"success": True, "key": created[0], "keys": created}), 201

@keys_bp.route("/<int:key_id>/revoke", methods=["POST"])
@owner_required
def revoke_key(key_id):
    InternalKeyService.revoke_key(key_id)
    return jsonify({"success": True, "message": "Key revoked successfully"})
