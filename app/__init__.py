import os
from flask import Flask, render_template, jsonify, redirect, url_for, session
from config import Config
from app.models import init_db
from app.services.scheduler import worker

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize SQLite database
    with app.app_context():
        init_db()

    # Register API blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.campaigns import campaigns_bp
    from app.routes.internal_keys import keys_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(campaigns_bp)
    app.register_blueprint(keys_bp)

    # Health check endpoint
    @app.route("/health", methods=["GET"])
    def health_check():
        return jsonify({
            "status": "healthy",
            "service": "Private Owner Control Panel",
            "database": "connected",
            "worker_running": worker.running
        })

    # Page routes
    @app.route("/")
    def index():
        if "user_id" not in session or session.get("role") not in ("owner", "admin"):
            return redirect(url_for("login_page"))
        return render_template("dashboard.html")

    @app.route("/login")
    def login_page():
        if "user_id" in session and session.get("role") in ("owner", "admin"):
            return redirect(url_for("index"))
        return render_template("login.html")

    # Start background worker daemon if configured
    if app.config.get("ENABLE_BACKGROUND_WORKER", True) and not app.testing:
        worker.start()

    return app
