import json
from flask import render_template, request
from flask_login import login_required
from app.dashboard import bp
from app.models.stock_transaction import StockTransaction
from app.analytics.services import AnalyticsService


@bp.route("/")
@login_required
def index():
    period = request.args.get("period", "30d")
    if period not in ("7d", "30d", "90d", "all"):
        period = "30d"

    # Compute live KPIs from database
    overview = AnalyticsService.get_inventory_overview()

    # Time series for stock movements
    movement_data = AnalyticsService.get_stock_movement_timeseries(period=period)

    # Category distribution
    category_data = AnalyticsService.get_category_distribution()

    # Product rankings
    rankings = AnalyticsService.get_product_movement_rankings(period=period, limit=5)

    # Recent stock transactions
    recent_txs = StockTransaction.query.order_by(StockTransaction.created_at.desc()).limit(8).all()

    return render_template(
        "dashboard/index.html",
        overview=overview,
        period=period,
        movement_data=movement_data,
        category_data=category_data,
        movement_json=json.dumps(movement_data, default=str),
        category_json=json.dumps(category_data, default=str),
        top_movers=rankings["fast_moving"],
        recent_txs=recent_txs,
    )
