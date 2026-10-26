from decimal import Decimal
from app.extensions import db
from app.models.product import Product
from app.models.category import Category
from app.models.stock_transaction import StockTransaction, TransactionType
from app.services.stock_service import StockService
from app.analytics.services import AnalyticsService


def test_inventory_overview_calculations(app, sample_product, sample_category):
    # Add a low-stock product
    low_prod = Product(
        sku="LOW-001",
        name="Low Item",
        category_id=sample_category.id,
        unit_cost=Decimal("10.00"),
        selling_price=Decimal("20.00"),
        quantity=5,
        reorder_level=10,
        is_active=True
    )
    # Add an out-of-stock product
    out_prod = Product(
        sku="OUT-001",
        name="Out of Stock Item",
        category_id=sample_category.id,
        unit_cost=Decimal("5.00"),
        selling_price=Decimal("12.00"),
        quantity=0,
        reorder_level=10,
        is_active=True
    )
    db.session.add_all([low_prod, out_prod])
    db.session.commit()

    overview = AnalyticsService.get_inventory_overview()
    # sample_product has 50 units @ 15.50 = 775.00
    # low_prod has 5 units @ 10.00 = 50.00
    # out_prod has 0 units @ 5.00 = 0.00
    # Total units = 55, total cost = 825.00
    assert overview["total_products"] == 3
    assert overview["total_units"] == 55
    assert overview["total_cost_value"] == Decimal("825.00")
    assert overview["low_stock_count"] == 1
    assert overview["out_of_stock_count"] == 1
    assert overview["healthy_stock_count"] == 1


def test_empty_database_analytics(app):
    # Analytics should handle 0 products and 0 transactions gracefully
    overview = AnalyticsService.get_inventory_overview()
    assert overview["total_products"] == 0
    assert overview["total_units"] == 0
    assert overview["total_cost_value"] == Decimal("0.00")

    movement = AnalyticsService.get_stock_movement_timeseries()
    assert movement["total_in"] == 0
    assert movement["total_out"] == 0

    cats = AnalyticsService.get_category_distribution()
    assert len(cats["labels"]) == 0

    rankings = AnalyticsService.get_product_movement_rankings()
    assert len(rankings["fast_moving"]) == 0

    reorders = AnalyticsService.get_reorder_recommendations()
    assert len(reorders) == 0


def test_stock_movement_and_fast_moving_rankings(app, staff_user, sample_product):
    # Record some stock out movements
    StockService.record_stock_out(sample_product.id, 10, staff_user, reason="Sale 1")
    StockService.record_stock_out(sample_product.id, 15, staff_user, reason="Sale 2")

    rankings = AnalyticsService.get_product_movement_rankings(period="30d")
    assert len(rankings["fast_moving"]) == 1
    assert rankings["fast_moving"][0]["units_moved"] == 25
    assert rankings["fast_moving"][0]["tx_count"] == 2


def test_reorder_recommendations_velocity_and_priority(app, staff_user, sample_product):
    # Initially sample_product has 50 units, reorder level 10 -> priority OPTIMAL
    reorders = AnalyticsService.get_reorder_recommendations()
    target_rec = next(r for r in reorders if r["product"].id == sample_product.id)
    assert target_rec["priority"] == "OPTIMAL"

    # Now issue 45 units -> leaving 5 units (<= 10 reorder level) -> priority HIGH
    StockService.record_stock_out(sample_product.id, 45, staff_user, reason="Bulk Order")
    reorders2 = AnalyticsService.get_reorder_recommendations()
    target_rec2 = next(r for r in reorders2 if r["product"].id == sample_product.id)
    assert target_rec2["priority"] == "HIGH"
    assert target_rec2["suggested_order"] > 0
