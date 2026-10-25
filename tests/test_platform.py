import os
import json
import pytest
from app import create_app
from app.models import init_db, get_db, User, Settings
from app.services.licensing import InternalKeyService
from app.services.discord_integration import DiscordIntegrationService
from app.services.scheduler import BackgroundWorker
from config import Config

@pytest.fixture
def client(tmp_path):
    test_db = str(tmp_path / "test_owner_platform.db")
    
    class TestConfig(Config):
        TESTING = True
        DATABASE_PATH = test_db
        ENABLE_BACKGROUND_WORKER = False
        SECRET_KEY = "test_owner_session_key"

    app = create_app(TestConfig)
    with app.test_client() as client:
        with app.app_context():
            yield client

def test_unauthenticated_redirection_and_health(client):
    h = client.get("/health")
    assert h.status_code == 200
    assert h.get_json()["status"] == "healthy"

    root = client.get("/")
    assert root.status_code == 302
    assert "/login" in root.headers["Location"]

    login_page = client.get("/login")
    assert login_page.status_code == 200
    assert b"Private Control Gateway" in login_page.data

    api_res = client.get("/api/owner/overview")
    assert api_res.status_code == 401
    assert api_res.get_json()["authenticated"] is False

def test_owner_authentication_flow(client):
    bad = client.post("/api/auth/login", json={"identifier": "admin", "password": "WrongPassword"})
    assert bad.status_code == 401

    good = client.post("/api/auth/login", json={"identifier": "admin", "password": "AdminPass6767!"})
    assert good.status_code == 200
    assert good.get_json()["success"] is True

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.get_json()["authenticated"] is True

    chg = client.post("/api/auth/change-password", json={
        "current_password": "AdminPass6767!",
        "new_password": "NewSecretPass6767!"
    })
    assert chg.status_code == 200

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 200

    relogin = client.post("/api/auth/login", json={"identifier": "admin", "password": "NewSecretPass6767!"})
    assert relogin.status_code == 200

def test_settings_bot_guilds_and_perk_matrix(client):
    client.post("/api/auth/login", json={"identifier": "admin", "password": "AdminPass6767!"})

    save_res = client.post("/api/owner/settings", json={
        "discord_bot_token": "TEST_BOT_TOKEN_VALID_01",
        "discord_client_id": "123456789012345678",
        "default_guild_id": "998877665544332211"
    })
    assert save_res.status_code == 200

    test_bot_res = client.post("/api/owner/test-bot", json={})
    assert test_bot_res.status_code == 200
    assert test_bot_res.get_json()["valid"] is True
    assert "latency_ms" in test_bot_res.get_json()

    guilds_res = client.get("/api/owner/bot-guilds")
    assert guilds_res.status_code == 200
    assert guilds_res.get_json()["success"] is True
    assert len(guilds_res.get_json()["guilds"]) == 2

    telemetry_res = client.get("/api/owner/guild-telemetry?guild_id=998877665544332211")
    assert telemetry_res.status_code == 200
    t_data = telemetry_res.get_json()
    assert t_data["success"] is True
    assert t_data["guild"]["premium_tier"] == 2
    assert "perk_matrix" in t_data["guild"]
    assert len(t_data["guild"]["perk_matrix"]["tiers"]) == 3

def test_webhook_latency_and_embed_studio_broadcasts(client):
    client.post("/api/auth/login", json={"identifier": "admin", "password": "AdminPass6767!"})

    wh_res = client.post("/api/owner/webhooks", json={
        "name": "Local Test Webhook",
        "url": "http://127.0.0.1:5000/api/mock/webhook"
    })
    assert wh_res.status_code == 201
    wh_id = wh_res.get_json()["webhook_id"]

    test_res = client.post(f"/api/owner/webhooks/{wh_id}/test")
    assert test_res.status_code == 200
    assert test_res.get_json()["success"] is True
    assert test_res.get_json()["latency_ms"] >= 0

    camp_res = client.post("/api/owner/campaigns", json={
        "title": "Rich Embed Broadcast",
        "target_webhook": "http://127.0.0.1:5000/api/mock/webhook",
        "content": "Automated server operational notice.",
        "embed_title": "Maintenance Window",
        "embed_author": "Ops Core",
        "embed_footer": "Verified System",
        "embed_color": "#4f46e5",
        "interval_minutes": 30,
        "max_runs": 3
    })
    assert camp_res.status_code == 201
    camp_id = camp_res.get_json()["campaign_id"]

    # Instant run_now trigger
    run_now = client.post(f"/api/owner/campaigns/{camp_id}/action", json={"action": "run_now"})
    assert run_now.status_code == 200
    assert run_now.get_json()["success"] is True

    pause_res = client.post(f"/api/owner/campaigns/{camp_id}/action", json={"action": "pause"})
    assert pause_res.status_code == 200
    assert pause_res.get_json()["new_status"] == "paused"

    del_res = client.post(f"/api/owner/campaigns/{camp_id}/action", json={"action": "delete"})
    assert del_res.status_code == 200

def test_expanded_tasks_and_inspector(client):
    client.post("/api/auth/login", json={"identifier": "admin", "password": "AdminPass6767!"})
    client.post("/api/owner/settings", json={"discord_bot_token": "TEST_BOT_TOKEN_VALID_01"})

    # Run immediate bot_ping task
    t_res = client.post("/api/owner/tasks", json={
        "task_type": "bot_ping",
        "name": "Discord REST Ping",
        "run_immediately": True
    })
    assert t_res.status_code == 201
    task_id = t_res.get_json()["job_id"]

    # Inspect task detail
    detail_res = client.get(f"/api/owner/tasks/{task_id}")
    assert detail_res.status_code == 200
    assert detail_res.get_json()["task"]["status"] == "completed"

    # Console logs check
    logs_res = client.get("/api/owner/console-logs")
    assert logs_res.status_code == 200
    assert len(logs_res.get_json()["console_logs"]) > 0

    # Clear completed tasks
    clr_res = client.post("/api/owner/tasks/clear-completed")
    assert clr_res.status_code == 200
    assert clr_res.get_json()["deleted"] >= 1

def test_batch_internal_keys_lifecycle(client):
    client.post("/api/auth/login", json={"identifier": "admin", "password": "AdminPass6767!"})

    gen_res = client.post("/api/owner/keys", json={
        "label": "Cloud Worker Node",
        "prefix": "NODE",
        "service_scope": "all",
        "duration_days": 60,
        "count": 3
    })
    assert gen_res.status_code == 201
    keys = gen_res.get_json()["keys"]
    assert len(keys) == 3
    assert keys[0]["key_code"].startswith("NODE-")

    val = InternalKeyService.validate_key(keys[0]["key_code"])
    assert val["valid"] is True

    rev_res = client.post(f"/api/owner/keys/{keys[0]['id']}/revoke")
    assert rev_res.status_code == 200

    val_rev = InternalKeyService.validate_key(keys[0]["key_code"])
    assert val_rev["valid"] is False
