from datetime import datetime, timezone
from flask import render_template, request
from flask_login import login_required
from app.reports import bp
from app.models.product import Product
from app.models.category import Category
from app.models.supplier import Supplier
from app.models.stock_transaction import StockTransaction
from app.analytics.services import AnalyticsService
from app.pdf_utils import generate_pdf_response
from app.utils import generate_csv_response


@bp.route("/reports")
@login_required
def index():
    overview = AnalyticsService.get_inventory_overview()
    return render_template("reports/index.html", overview=overview)


@bp.route("/reports/export/inventory")
@login_required
def export_inventory():
    """PDF Export: Master Product Inventory Catalog."""
    category_id = request.args.get("category_id", type=int)
    fmt = request.args.get("format", "pdf").lower()
    
    query = Product.query
    if category_id:
        query = query.filter_by(category_id=category_id)

    products = query.order_by(Product.name).all()

    headers = [
        "S.No",
        "SKU",
        "Product Name",
        "Category",
        "Supplier",
        "Stock",
        "Reorder",
        "Status",
        "Unit Cost",
        "Selling Price",
        "Total Cost Value"
    ]

    rows = []
    for idx, p in enumerate(products, start=1):
        rows.append([
            idx,
            p.sku,
            p.name,
            p.category.name if p.category else "Uncategorized",
            p.supplier.name if p.supplier else "N/A",
            p.quantity,
            p.reorder_level,
            p.stock_status,
            f"${p.unit_cost:.2f}",
            f"${p.selling_price:.2f}",
            f"${p.inventory_cost_value:.2f}"
        ])

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if fmt == "csv":
        return generate_csv_response(headers, rows, f"inventory_catalog_{timestamp}.csv")

    col_widths = [30, 75, 160, 110, 100, 40, 45, 60, 50, 50, 65]
    return generate_pdf_response(
        title="StockPulse — Master Product Catalog",
        subtitle="Complete catalog of inventory items, current on-hand units, and valuations",
        headers=headers,
        data_rows=rows,
        filename=f"inventory_catalog_{timestamp}.pdf",
        col_widths=col_widths,
        orientation="landscape"
    )


@bp.route("/reports/export/categories")
@login_required
def export_categories():
    """PDF Export: Category Summary and Valuation Breakdown."""
    fmt = request.args.get("format", "pdf").lower()
    cat_data = AnalyticsService.get_category_distribution()

    # Sort categories by ID (small number to big number)
    sorted_categories = sorted(cat_data["categories"], key=lambda c: c["id"])

    headers = [
        "S.No",
        "Category Name",
        "Active Products",
        "Total Units",
        "Inventory Cost Value",
        "Portfolio Share"
    ]

    rows = []
    for idx, c in enumerate(sorted_categories, start=1):
        rows.append([
            idx,
            c["name"],
            f"{c['product_count']} items",
            f"{c['total_quantity']:,} units",
            f"${c['cost_value']:,.2f}",
            f"{c.get('value_percentage', 0.0):.1f}%"
        ])

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if fmt == "csv":
        return generate_csv_response(headers, rows, f"category_summary_{timestamp}.csv")

    col_widths = [40, 180, 80, 80, 95, 65]
    return generate_pdf_response(
        title="StockPulse — Category Valuation Summary",
        subtitle="Taxonomy classification, unit volume distribution, and portfolio capital allocation",
        headers=headers,
        data_rows=rows,
        filename=f"category_summary_{timestamp}.pdf",
        col_widths=col_widths,
        orientation="portrait"
    )


@bp.route("/reports/export/low-stock")
@login_required
def export_low_stock():
    """PDF Export: Low Stock & Out of Stock Replenishment Alert."""
    fmt = request.args.get("format", "pdf").lower()
    products = Product.query.filter(
        Product.is_active == True,
        Product.quantity <= Product.reorder_level
    ).order_by(Product.quantity.asc()).all()

    headers = [
        "S.No",
        "SKU",
        "Product Name",
        "Category",
        "Stock",
        "Threshold",
        "Deficit",
        "Status",
        "Unit Cost",
        "Est. Replenishment Cost"
    ]

    rows = []
    for idx, p in enumerate(products, start=1):
        deficit = max(0, p.reorder_level - p.quantity)
        cost_to_threshold = deficit * (p.unit_cost or 0)
        rows.append([
            idx,
            p.sku,
            p.name,
            p.category.name if p.category else "Uncategorized",
            p.quantity,
            p.reorder_level,
            deficit,
            p.stock_status,
            f"${p.unit_cost:.2f}",
            f"${cost_to_threshold:.2f}"
        ])

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if fmt == "csv":
        return generate_csv_response(headers, rows, f"low_stock_alert_{timestamp}.csv")

    col_widths = [30, 80, 180, 120, 45, 50, 45, 65, 55, 115]
    return generate_pdf_response(
        title="StockPulse — Low Stock & Replenishment Alert",
        subtitle="Prioritized listing of inventory items currently at or below minimum reorder thresholds",
        headers=headers,
        data_rows=rows,
        filename=f"low_stock_alert_{timestamp}.pdf",
        col_widths=col_widths,
        orientation="landscape"
    )


@bp.route("/reports/export/transactions")
@login_required
def export_transactions():
    """PDF Export: Historical Stock Movement Ledger."""
    fmt = request.args.get("format", "pdf").lower()
    tx_type = request.args.get("type", "").strip()
    product_id = request.args.get("product_id", type=int)
    start_date_str = request.args.get("start_date", "").strip()
    end_date_str = request.args.get("end_date", "").strip()

    query = StockTransaction.query

    if tx_type:
        query = query.filter_by(transaction_type=tx_type)
    if product_id:
        query = query.filter_by(product_id=product_id)

    if start_date_str:
        try:
            start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            query = query.filter(StockTransaction.created_at >= start_dt)
        except ValueError:
            pass

    if end_date_str:
        try:
            end_dt = datetime.strptime(end_date_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            query = query.filter(StockTransaction.created_at <= end_dt)
        except ValueError:
            pass

    txs = query.order_by(StockTransaction.created_at.desc()).all()

    headers = [
        "Tx ID",
        "Timestamp (UTC)",
        "SKU",
        "Product Name",
        "Type",
        "Change",
        "Prev",
        "Result",
        "User",
        "Reference",
        "Notes"
    ]

    rows = []
    for t in txs:
        prefix = "+" if t.transaction_type == "STOCK_IN" else ("-" if t.transaction_type == "STOCK_OUT" else "")
        rows.append([
            f"#{t.id}",
            t.created_at.strftime("%Y-%m-%d %H:%M"),
            t.product.sku if t.product else "N/A",
            t.product.name if t.product else "Deleted Product",
            t.transaction_type.replace("_", " "),
            f"{prefix}{t.quantity}",
            t.previous_quantity,
            t.resulting_quantity,
            t.user.username if t.user else "System",
            t.reference or "—",
            t.notes or "—"
        ])

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if fmt == "csv":
        return generate_csv_response(headers, rows, f"stock_transactions_{timestamp}.csv")

    col_widths = [40, 75, 75, 140, 65, 45, 35, 40, 60, 80, 130]
    return generate_pdf_response(
        title="StockPulse — Stock Movement Transaction Ledger",
        subtitle="Chronological audit trail of all warehouse receipts, dispatches, and adjustments",
        headers=headers,
        data_rows=rows,
        filename=f"stock_transactions_{timestamp}.pdf",
        col_widths=col_widths,
        orientation="landscape"
    )


@bp.route("/reports/export/reorder")
@login_required
def export_reorder():
    """PDF Export: Reorder Demand and Replenishment Recommendations."""
    fmt = request.args.get("format", "pdf").lower()
    reorders = AnalyticsService.get_reorder_recommendations()

    headers = [
        "Priority",
        "SKU",
        "Product Name",
        "Stock",
        "Reorder Lvl",
        "Daily Velocity",
        "Target Stock",
        "Suggested Order",
        "Est. Cost",
        "Methodology"
    ]

    rows = []
    for r in reorders:
        rows.append([
            r["priority"],
            r["product"].sku,
            r["product"].name,
            r["current_stock"],
            r["reorder_level"],
            f"{r['daily_velocity']:.2f}/day",
            f"{r['target_stock']} units",
            r["suggested_order"],
            f"${r['estimated_cost']:.2f}",
            r["method_used"]
        ])

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if fmt == "csv":
        return generate_csv_response(headers, rows, f"reorder_recommendations_{timestamp}.csv")

    col_widths = [55, 75, 150, 45, 55, 65, 65, 65, 65, 145]
    return generate_pdf_response(
        title="StockPulse — Intelligent Stock Replenishment Plan",
        subtitle="Procurement forecasts based on 30-day velocity, lead-time buffers, and safety stock",
        headers=headers,
        data_rows=rows,
        filename=f"reorder_plan_{timestamp}.pdf",
        col_widths=col_widths,
        orientation="landscape"
    )


@bp.route("/reports/export/fast-moving")
@login_required
def export_fast_moving():
    """PDF Export: Fast-Moving Products Report."""
    fmt = request.args.get("format", "pdf").lower()
    period = request.args.get("period", "30d")
    rankings = AnalyticsService.get_product_movement_rankings(period=period, limit=25)

    headers = [
        "Rank",
        "SKU",
        "Product Name",
        "Units Issued",
        "Transactions",
        "Current Stock",
        "Last Movement Date"
    ]

    rows = []
    for idx, item in enumerate(rankings["fast_moving"], start=1):
        last_dt = item["last_movement"].strftime("%Y-%m-%d %H:%M") if item["last_movement"] else "N/A"
        rows.append([
            f"#{idx}",
            item["product"].sku,
            item["product"].name,
            f"{item['units_moved']} units",
            item["tx_count"],
            f"{item['product'].quantity} in stock",
            last_dt
        ])

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if fmt == "csv":
        return generate_csv_response(headers, rows, f"fast_moving_products_{timestamp}.csv")

    col_widths = [45, 80, 200, 75, 70, 75, 100]
    return generate_pdf_response(
        title=f"StockPulse — Fast-Moving Inventory Report ({period.upper()})",
        subtitle="Top outgoing SKUs ranked by outbound volume and dispatch frequency",
        headers=headers,
        data_rows=rows,
        filename=f"fast_moving_products_{timestamp}.pdf",
        col_widths=col_widths,
        orientation="portrait"
    )



@bp.route("/reports/export/suppliers")
@login_required
def export_suppliers():
    """PDF Export: Registered Suppliers List in Numerical S.No/ID order."""
    fmt = request.args.get("format", "pdf").lower()
    suppliers = Supplier.query.order_by(Supplier.id.asc()).all()

    headers = [
        "S.No (ID)",
        "Supplier Name",
        "Contact Person",
        "Phone Number",
        "Email Address",
        "Address",
        "Products Supplied"
    ]

    rows = []
    for s in suppliers:
        rows.append([
            f"#{s.id}",
            s.name,
            s.contact_person or "—",
            s.phone or "—",
            s.email or "—",
            s.address or "—",
            f"{s.products.count()} SKUs"
        ])

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if fmt == "csv":
        return generate_csv_response(headers, rows, f"suppliers_list_{timestamp}.csv")

    col_widths = [45, 130, 95, 85, 120, 180, 85]
    return generate_pdf_response(
        title="StockPulse — Registered Suppliers & Vendors",
        subtitle="Wholesale vendor directory and procurement communication channels",
        headers=headers,
        data_rows=rows,
        filename=f"suppliers_list_{timestamp}.pdf",
        col_widths=col_widths,
        orientation="landscape"
    )
