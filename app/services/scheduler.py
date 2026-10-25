import os
import threading
import time
import json
import requests
from collections import deque
from datetime import datetime, timedelta, timezone
from app.models import get_db, record_audit, Settings
from app.services.discord_integration import DiscordIntegrationService

class BackgroundWorker:
    def __init__(self, check_interval_sec=5):
        self.check_interval_sec = check_interval_sec
        self.running = False
        self.thread = None
        self.last_run = None
        self.last_keepalive = 0
        self.jobs_processed = 0
        self.console_logs = deque(maxlen=120)
        self._log("SYSTEM", "Background worker initialized and standing by.")

    def _log(self, level, message):
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        entry = {"timestamp": ts, "level": level, "message": message}
        self.console_logs.append(entry)

    def get_logs(self):
        return list(self.console_logs)

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True, name="OwnerDaemonWorker")
        self.thread.start()
        self._log("INFO", "Owner background daemon worker started (interval: 5s).")
        print("[WORKER] Owner background daemon worker started.")

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        self._log("WARN", "Owner background daemon worker stopped.")
        print("[WORKER] Owner background daemon worker stopped.")

    def _send_cloud_keepalive(self):
        now_ts = time.time()
        if now_ts - self.last_keepalive < 240:  # Every 4 minutes
            return
        self.last_keepalive = now_ts
        ext_url = os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("PUBLIC_URL")
        railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
        if not ext_url and railway_domain:
            ext_url = f"https://{railway_domain}"
        if ext_url:
            try:
                requests.get(f"{ext_url.rstrip('/')}/health", timeout=5)
                self._log("INFO", f"Cloud keep-alive heartbeat sent to {ext_url}/health")
            except Exception:
                pass

    def _loop(self):
        while self.running:
            try:
                self.last_run = datetime.now(timezone.utc).isoformat()
                self._send_cloud_keepalive()
                self.process_campaigns()
                self.process_tasks()
            except Exception as e:
                self._log("ERROR", f"Worker cycle error: {e}")
                print(f"[WORKER ERROR] Worker exception: {e}")
            time.sleep(self.check_interval_sec)

    def execute_single_campaign(self, camp):
        now = datetime.now(timezone.utc)
        camp_id = camp["id"]
        with get_db() as conn:
            conn.execute("UPDATE campaigns SET status = 'running' WHERE id = ?", (camp_id,))

        embed_fields = None
        if camp.get("embed_fields_json"):
            try:
                embed_fields = json.loads(camp["embed_fields_json"])
            except Exception:
                embed_fields = None

        self._log("EXEC", f"Dispatching campaign #{camp_id} ('{camp['title']}')...")
        result = DiscordIntegrationService.send_webhook_message(
            webhook_url=camp["target_webhook"],
            content=camp["content"],
            embed_title=camp.get("embed_title"),
            embed_color=camp.get("embed_color") or "#4f46e5",
            embed_author=camp.get("embed_author"),
            embed_thumbnail=camp.get("embed_thumbnail"),
            embed_image=camp.get("embed_image"),
            embed_footer=camp.get("embed_footer"),
            embed_fields=embed_fields
        )

        new_run_count = camp["run_count"] + 1
        last_run_iso = now.isoformat()
        latency_ms = result.get("latency_ms")

        if result["success"]:
            if new_run_count >= camp["max_runs"]:
                new_status = "completed"
                next_run_iso = None
            else:
                new_status = "scheduled"
                next_run_iso = (now + timedelta(minutes=camp["interval_minutes"])).isoformat()
            last_error = None
            self._log("OK", f"Campaign '{camp['title']}' delivered ({new_run_count}/{camp['max_runs']}, {latency_ms or 0}ms).")
        else:
            new_status = "scheduled"
            next_run_iso = (now + timedelta(minutes=min(camp["interval_minutes"], 5))).isoformat()
            last_error = result.get("error", "Dispatch failed")
            self._log("ERR", f"Campaign '{camp['title']}' failed: {last_error}")

        with get_db() as conn:
            conn.execute(
                """UPDATE campaigns 
                SET status = ?, run_count = ?, last_run_at = ?, next_run_at = ?, last_latency_ms = ?, last_error = ?
                WHERE id = ?""",
                (new_status, new_run_count, last_run_iso, next_run_iso, latency_ms, last_error, camp_id)
            )
            record_audit(
                "BROADCAST_RUN",
                f"Campaign '{camp['title']}' run {new_run_count}/{camp['max_runs']} - Status: {new_status}",
                conn=conn
            )
        self.jobs_processed += 1
        return result

    def process_campaigns(self):
        now_iso = datetime.now(timezone.utc).isoformat()
        campaigns_to_run = []
        with get_db() as conn:
            rows = conn.execute(
                """SELECT * FROM campaigns 
                WHERE status = 'scheduled' AND (next_run_at IS NULL OR next_run_at <= ?)""",
                (now_iso,)
            ).fetchall()
            campaigns_to_run = [dict(r) for r in rows]

        for camp in campaigns_to_run:
            self.execute_single_campaign(camp)

    def process_tasks(self):
        now_iso = datetime.now(timezone.utc).isoformat()
        tasks = []
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM task_jobs WHERE status = 'pending' ORDER BY id ASC LIMIT 5"
            ).fetchall()
            tasks = [dict(r) for r in rows]

        for task in tasks:
            task_id = task["id"]
            self._log("TASK", f"Starting task #{task_id}: {task['name']} ({task['task_type']})")
            with get_db() as conn:
                conn.execute(
                    "UPDATE task_jobs SET status = 'running', progress_percent = 35, updated_at = ? WHERE id = ?",
                    (now_iso, task_id)
                )

            success, result_data, error_msg = self._execute_task_job(task)

            updated_iso = datetime.now(timezone.utc).isoformat()
            with get_db() as conn:
                if success:
                    conn.execute(
                        """UPDATE task_jobs 
                        SET status = 'completed', progress_percent = 100, result_json = ?, error_message = NULL, updated_at = ? 
                        WHERE id = ?""",
                        (json.dumps(result_data), updated_iso, task_id)
                    )
                    self._log("OK", f"Task #{task_id} ('{task['name']}') completed.")
                else:
                    new_retries = task["retries"] + 1
                    status = "failed" if new_retries >= task["max_retries"] else "pending"
                    conn.execute(
                        """UPDATE task_jobs 
                        SET status = ?, retries = ?, error_message = ?, updated_at = ? 
                        WHERE id = ?""",
                        (status, new_retries, error_msg, updated_iso, task_id)
                    )
                    self._log("ERR", f"Task #{task_id} failed (attempt {new_retries}/{task['max_retries']}): {error_msg}")
            self.jobs_processed += 1

    def _execute_task_job(self, task):
        task_type = task["task_type"]
        payload = {}
        if task["payload_json"]:
            try:
                payload = json.loads(task["payload_json"])
            except Exception:
                pass

        bot_token = Settings.get("discord_bot_token", "")
        client_id = Settings.get("discord_client_id", "")

        if task_type == "quest_sync":
            quest_name = payload.get("quest_name", "Developer Quest Role Metadata Sync")
            if not bot_token:
                return False, None, "Bot token not configured in Integrations settings. Quest synchronization requires an authorized Discord bot."

            sync_res = DiscordIntegrationService.sync_quest_role_metadata(bot_token, client_id)
            if not sync_res["success"]:
                return False, None, f"Quest metadata sync failed: {sync_res.get('error')}"

            return True, {
                "quest": quest_name,
                "sync_details": sync_res,
                "status": "synchronized"
            }, None

        elif task_type == "bot_ping":
            if not bot_token:
                return False, None, "Bot token not configured. Cannot measure Discord REST latency."
            verify = DiscordIntegrationService.verify_bot_token(bot_token)
            if not verify["valid"]:
                return False, None, verify.get("error", "Bot ping failed")
            return True, {
                "bot_username": verify["bot"].get("username"),
                "bot_id": verify["bot"].get("id"),
                "latency_ms": verify.get("latency_ms", 0),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }, None

        elif task_type == "token_health":
            if not bot_token:
                return False, None, "Bot token not configured."
            verify = DiscordIntegrationService.verify_bot_token(bot_token)
            if not verify["valid"]:
                return False, None, verify.get("error")
            guilds_res = DiscordIntegrationService.get_bot_guilds(bot_token)
            return True, {
                "token_valid": True,
                "bot_user": verify["bot"].get("username"),
                "latency_ms": verify.get("latency_ms", 0),
                "connected_guilds_count": len(guilds_res.get("guilds", [])),
                "audited_at": datetime.now(timezone.utc).isoformat()
            }, None

        elif task_type == "guild_audit":
            guild_id = payload.get("guild_id") or Settings.get("default_guild_id")
            if not guild_id:
                return False, None, "No Guild ID specified for guild telemetry audit."
            if not bot_token:
                return False, None, "Bot token not configured. Cannot inspect Discord Guild telemetry."

            res = DiscordIntegrationService.get_guild_telemetry(bot_token, guild_id)
            if not res["success"]:
                return False, None, res.get("error", "Failed guild telemetry check")

            return True, res["guild"], None

        elif task_type == "webhook_check":
            url = payload.get("url")
            is_valid, msg = DiscordIntegrationService.validate_webhook_url(url)
            if not is_valid:
                return False, None, msg
            return True, {"url": url, "valid": True}, None

        return True, {"executed": task_type}, None

worker = BackgroundWorker()
