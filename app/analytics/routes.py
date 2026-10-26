import json
from flask import render_template, request, jsonify
from flask_login import login_required
from app.analytics import bp
from app.analytics.services import AnalyticsService


@bp.route("/analytics")
@login_required
def index():
    period = request.args.get("period", "30d")
    if period not in ("7d", "30d", "90d", "all"):
        period = "30d"

    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()

    overview = AnalyticsService.get_inventory_overview()
    movement_data = AnalyticsService.get_stock_movement_timeseries(period=period, start_date=start_date, end_date=end_date)
    category_data = AnalyticsService.get_category_distribution()
    rankings = AnalyticsService.get_product_movement_rankings(period=period, limit=10)
    reorders = AnalyticsService.get_reorder_recommendations(target_cover_days=30, lead_time_days=7)

    return render_template(
        "analytics/index.html",
        overview=overview,
        period=period,
        start_date=start_date,
        end_date=end_date,
        movement_data=movement_data,
        category_data=category_data,
        movement_json=json.dumps(movement_data, default=str),
        category_json=json.dumps(category_data, default=str),
        fast_movers=rankings["fast_moving"],
        slow_movers=rankings["slow_moving"],
        reorders=reorders
    )


@bp.route("/analytics/api/movement")
@login_required
def api_movement():
    period = request.args.get("period", "30d")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    data = AnalyticsService.get_stock_movement_timeseries(period=period, start_date=start_date, end_date=end_date)
    return jsonify(data)
