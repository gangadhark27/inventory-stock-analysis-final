from datetime import datetime
from decimal import Decimal
from flask import Flask, render_template
from config import Config
from app.extensions import db, login_manager, csrf


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize Flask extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Register Blueprints
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp)

    from app.inventory import bp as inventory_bp
    app.register_blueprint(inventory_bp)

    from app.analytics import bp as analytics_bp
    app.register_blueprint(analytics_bp)

    from app.reports import bp as reports_bp
    app.register_blueprint(reports_bp)

    # Template filters
    @app.template_filter("currency")
    def currency_filter(val):
        if val is None:
            return "$0.00"
        try:
            return f"${Decimal(str(val)):,.2f}"
        except Exception:
            return f"${val}"

    @app.template_filter("datetime_format")
    def datetime_format_filter(value, format_str="%Y-%m-%d %H:%M"):
        if not value:
            return "N/A"
        if isinstance(value, str):
            return value
        return value.strftime(format_str)

    # Custom Error Handlers
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    # Safe database auto-initialization (ensures tables exist without overwriting records)
    with app.app_context():
        db.create_all()
        # On Vercel serverless instances, auto-seed demo data if database is empty
        import os
        if os.environ.get("VERCEL"):
            try:
                from app.models.user import User
                if User.query.count() == 0:
                    from app.seed import seed_database
                    seed_database(reset_first=False)
            except Exception:
                pass

    return app
