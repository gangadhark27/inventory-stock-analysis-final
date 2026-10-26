from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Any, Optional
import pandas as pd
from sqlalchemy import func
from app.extensions import db
from app.models.product import Product
from app.models.category import Category
from app.models.stock_transaction import StockTransaction, TransactionType


class AnalyticsService:
    """
    Data analytics and inventory intelligence service.
    Integrates SQLAlchemy optimized queries and Pandas aggregations.
    """

    @staticmethod
    def get_date_bounds(period: str = "30d", start_date: Optional[str] = None, end_date: Optional[str] = None):
        """Parse date filter and return UTC datetime start and end bounds."""
        now = datetime.now(timezone.utc)
        
        if period == "7d":
            start = now - timedelta(days=7)
            end = now
        elif period == "30d":
            start = now - timedelta(days=30)
            end = now
        elif period == "90d":
            start = now - timedelta(days=90)
            end = now
        elif period == "custom" and start_date and end_date:
            try:
                start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                end = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            except ValueError:
                start = now - timedelta(days=30)
                end = now
        else:  # "all" or fallback
            start = datetime(2020, 1, 1, tzinfo=timezone.utc)
            end = now

        return start, end

    @classmethod
    def get_inventory_overview(cls) -> Dict[str, Any]:
        """
        Computes high-level KPIs and inventory valuation.
        Uses Decimal arithmetic to prevent binary floating-point inaccuracy.
        """
        active_products = Product.query.filter_by(is_active=True).all()
        
        total_products = len(active_products)
        total_units = sum(p.quantity for p in active_products)
        total_cost_value = sum(p.inventory_cost_value for p in active_products) if active_products else Decimal("0.00")
        total_selling_value = sum(p.potential_selling_value for p in active_products) if active_products else Decimal("0.00")

        low_stock_list = [p for p in active_products if 0 < p.quantity <= p.reorder_level]
        out_of_stock_list = [p for p in active_products if p.quantity == 0]
        healthy_stock_list = [p for p in active_products if p.quantity > p.reorder_level]

        inactive_count = Product.query.filter_by(is_active=False).count()

        return {
            "total_products": total_products,
            "total_units": total_units,
            "total_cost_value": total_cost_value,
            "total_selling_value": total_selling_value,
            "low_stock_count": len(low_stock_list),
            "out_of_stock_count": len(out_of_stock_list),
            "healthy_stock_count": len(healthy_stock_list),
            "inactive_count": inactive_count,
            "low_stock_products": low_stock_list,
            "out_of_stock_products": out_of_stock_list,
        }

    @classmethod
    def get_stock_movement_timeseries(cls, period: str = "30d", start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Builds daily stock-in vs stock-out aggregations using Pandas.
        """
        start_dt, end_dt = cls.get_date_bounds(period, start_date, end_date)

        # Query relevant transactions
        txs = StockTransaction.query.filter(
            StockTransaction.created_at >= start_dt,
            StockTransaction.created_at <= end_dt
        ).all()

        if not txs:
            # Generate empty series for the period
            dates = pd.date_range(start=start_dt.date(), end=end_dt.date(), freq="D")
            labels = [d.strftime("%b %d") for d in dates]
            return {
                "labels": labels,
                "incoming": [0] * len(labels),
                "outgoing": [0] * len(labels),
                "net_flow": [0] * len(labels),
                "total_in": 0,
                "total_out": 0,
                "total_tx_count": 0,
            }

        # Convert to Pandas DataFrame
        data = [{
            "date": t.created_at.date(),
            "type": t.transaction_type,
            "quantity": t.quantity,
            "net_change": t.net_change
        } for t in txs]
        df = pd.DataFrame(data)

        # Create complete date range index to prevent gaps
        date_index = pd.date_range(start=start_dt.date(), end=end_dt.date(), freq="D")
        full_df = pd.DataFrame({"date": [d.date() for d in date_index]}).set_index("date")

        # Inbound
        in_df = df[df["type"] == TransactionType.STOCK_IN].groupby("date")["quantity"].sum()
        # Outbound
        out_df = df[df["type"] == TransactionType.STOCK_OUT].groupby("date")["quantity"].sum()

        merged = full_df.join(in_df.rename("incoming")).join(out_df.rename("outgoing")).fillna(0)
        merged["net_flow"] = merged["incoming"] - merged["outgoing"]

        labels = [d.strftime("%b %d") for d in merged.index]
        incoming_series = [int(v) for v in merged["incoming"]]
        outgoing_series = [int(v) for v in merged["outgoing"]]
        net_series = [int(v) for v in merged["net_flow"]]

        return {
            "labels": labels,
            "incoming": incoming_series,
            "outgoing": outgoing_series,
            "net_flow": net_series,
            "total_in": sum(incoming_series),
            "total_out": sum(outgoing_series),
            "total_tx_count": len(txs),
        }

    @classmethod
    def get_category_distribution(cls) -> Dict[str, Any]:
        """
        Category-wise distribution of products, unit quantities, and cost values.
        """
        categories = Category.query.all()
        labels = []
        quantities = []
        cost_values = []
        product_counts = []
        
        total_inventory_cost = Decimal("0.00")
        cat_stats = []

        for cat in categories:
            prods = cat.products.filter_by(is_active=True).all()
            qty = sum(p.quantity for p in prods)
            cost = sum(p.inventory_cost_value for p in prods)
            count = len(prods)
            total_inventory_cost += cost

            cat_stats.append({
                "id": cat.id,
                "name": cat.name,
                "product_count": count,
                "total_quantity": qty,
                "cost_value": float(cost),
                "cost_decimal": cost,
            })

            labels.append(cat.name)
            quantities.append(qty)
            cost_values.append(float(cost))
            product_counts.append(count)

        # Compute percentages
        for stat in cat_stats:
            if total_inventory_cost > Decimal("0.00"):
                stat["value_percentage"] = round(float((Decimal(str(stat["cost_value"])) / total_inventory_cost) * 100), 1)
            else:
                stat["value_percentage"] = 0.0

        return {
            "labels": labels,
            "quantities": quantities,
            "cost_values": cost_values,
            "product_counts": product_counts,
            "categories": cat_stats,
            "total_cost": float(total_inventory_cost),
            "total_cost_decimal": total_inventory_cost
        }

    @classmethod
    def get_product_movement_rankings(cls, period: str = "30d", limit: int = 10) -> Dict[str, List[Dict[str, Any]]]:
        """
        Ranks fast-moving and slow-moving products by actual stock-out transactions.
        """
        start_dt, end_dt = cls.get_date_bounds(period)

        active_products = {p.id: p for p in Product.query.filter_by(is_active=True).all()}

        out_txs = StockTransaction.query.filter(
            StockTransaction.transaction_type == TransactionType.STOCK_OUT,
            StockTransaction.created_at >= start_dt,
            StockTransaction.created_at <= end_dt
        ).all()

        if not out_txs:
            # All products have insufficient data for this period
            all_products_summary = [{
                "product": p,
                "units_moved": 0,
                "tx_count": 0,
                "last_movement": None,
                "status": "Insufficient Data"
            } for p in active_products.values()]
            return {
                "fast_moving": [],
                "slow_moving": all_products_summary[:limit],
            }

        df = pd.DataFrame([{
            "product_id": t.product_id,
            "quantity": t.quantity,
            "created_at": t.created_at
        } for t in out_txs])

        # Group by product
        agg_df = df.groupby("product_id").agg(
            total_units=("quantity", "sum"),
            tx_count=("quantity", "count"),
            last_movement=("created_at", "max")
        ).reset_index()

        moved_product_ids = set(agg_df["product_id"])

        fast_moving = []
        for _, row in agg_df.sort_values(by="total_units", ascending=False).iterrows():
            pid = int(row["product_id"])
            if pid in active_products:
                fast_moving.append({
                    "product": active_products[pid],
                    "units_moved": int(row["total_units"]),
                    "tx_count": int(row["tx_count"]),
                    "last_movement": row["last_movement"],
                    "status": "Active Mover"
                })

        # Slow moving or unmoved active products
        unmoved = []
        for pid, prod in active_products.items():
            if pid not in moved_product_ids:
                # Check if there is ever any history
                total_ever = prod.transactions.filter_by(transaction_type=TransactionType.STOCK_OUT).count()
                unmoved.append({
                    "product": prod,
                    "units_moved": 0,
                    "tx_count": 0,
                    "last_movement": None,
                    "status": "Zero Movement (Period)" if total_ever > 0 else "Insufficient Data"
                })

        return {
            "fast_moving": fast_moving[:limit],
            "slow_moving": unmoved[:limit]
        }

    @classmethod
    def get_reorder_recommendations(cls, target_cover_days: int = 30, lead_time_days: int = 7) -> List[Dict[str, Any]]:
        """
        Computes transparent reorder recommendations.
        Formula:
          - Daily Run Rate = (Stock Issued over past 30 days) / 30
          - If Daily Run Rate > 0:
              Target Stock = Reorder Level + (Daily Run Rate * (target_cover_days + lead_time_days))
          - Else (Insufficient history):
              Target Stock = Reorder Level * 2 (or standard threshold coverage)
          - Suggested Reorder Quantity = max(0, ceil(Target Stock - Current Stock))
        """
        now = datetime.now(timezone.utc)
        thirty_days_ago = now - timedelta(days=30)

        active_products = Product.query.filter_by(is_active=True).all()
        recommendations = []

        # Get 30-day stock out transactions
        out_txs = StockTransaction.query.filter(
            StockTransaction.transaction_type == TransactionType.STOCK_OUT,
            StockTransaction.created_at >= thirty_days_ago
        ).all()

        sales_by_product = {}
        for t in out_txs:
            sales_by_product[t.product_id] = sales_by_product.get(t.product_id, 0) + t.quantity

        for p in active_products:
            thirty_day_sales = sales_by_product.get(p.id, 0)
            daily_velocity = thirty_day_sales / 30.0

            if daily_velocity > 0:
                # Velocity-based target
                safety_buffer = p.reorder_level
                forecast_lead_demand = daily_velocity * lead_time_days
                cycle_demand = daily_velocity * target_cover_days
                target_stock = int(round(safety_buffer + forecast_lead_demand + cycle_demand))
                method_used = "Velocity-Based (30d Sales + Lead Time)"
            else:
                # Threshold fallback
                target_stock = max(p.reorder_level * 2, p.reorder_level + 10)
                method_used = "Threshold Baseline (2x Reorder Level)"

            deficit = target_stock - p.quantity
            suggested_order = max(0, deficit)
            estimated_cost = Decimal(suggested_order) * (p.unit_cost or Decimal("0.00"))

            # Calculate urgency priority
            if p.quantity == 0:
                priority = "CRITICAL"
                priority_badge = "danger"
            elif p.quantity <= p.reorder_level:
                priority = "HIGH"
                priority_badge = "warning text-dark"
            elif suggested_order > 0:
                priority = "MEDIUM"
                priority_badge = "info text-dark"
            else:
                priority = "OPTIMAL"
                priority_badge = "success"

            recommendations.append({
                "product": p,
                "current_stock": p.quantity,
                "reorder_level": p.reorder_level,
                "thirty_day_sales": thirty_day_sales,
                "daily_velocity": round(daily_velocity, 2),
                "target_stock": target_stock,
                "suggested_order": suggested_order,
                "estimated_cost": estimated_cost,
                "method_used": method_used,
                "priority": priority,
                "priority_badge": priority_badge,
            })

        # Sort by urgency: CRITICAL first, then HIGH, then suggested order desc
        priority_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "OPTIMAL": 3}
        recommendations.sort(key=lambda x: (priority_rank[x["priority"]], -x["suggested_order"]))

        return recommendations
