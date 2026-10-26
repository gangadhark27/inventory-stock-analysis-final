import pytest
from decimal import Decimal
from app.extensions import db
from app.models.product import Product
from app.models.stock_transaction import StockTransaction, TransactionType
from app.models.audit_log import AuditLog
from app.services.stock_service import (
    StockService,
    InsufficientStockError,
    InvalidQuantityError,
    ProductInactiveError,
    UnauthorizedStockOperationError,
    StockServiceError
)


def test_create_product_route(client, admin_user, sample_category):
    client.post("/login", data={"username": "admin_test", "password": "AdminPass123!"})
    res = client.post("/products/new", data={
        "sku": "NEW-PROD-001",
        "name": "New Awesome Widget",
        "description": "High performance widget",
        "category_id": sample_category.id,
        "supplier_id": 0,
        "unit_cost": "22.50",
        "selling_price": "45.00",
        "reorder_level": 15,
        "is_active": True
    }, follow_redirects=True)
    assert res.status_code == 200
    prod = Product.query.filter_by(sku="NEW-PROD-001").first()
    assert prod is not None
    assert prod.name == "New Awesome Widget"
    assert prod.quantity == 0


def test_duplicate_sku_rejected(client, admin_user, sample_product, sample_category):
    client.post("/login", data={"username": "admin_test", "password": "AdminPass123!"})
    res = client.post("/products/new", data={
        "sku": sample_product.sku,  # Existing SKU
        "name": "Duplicate SKU Item",
        "category_id": sample_category.id,
        "supplier_id": 0,
        "unit_cost": "10.00",
        "selling_price": "20.00",
        "reorder_level": 5,
        "is_active": True
    }, follow_redirects=True)
    assert b"already exists" in res.data


def test_product_deactivation_toggle(client, admin_user, sample_product):
    client.post("/login", data={"username": "admin_test", "password": "AdminPass123!"})
    assert sample_product.is_active is True

    # Toggle status to inactive
    client.post(f"/products/{sample_product.id}/toggle-status", follow_redirects=True)
    db.session.refresh(sample_product)
    assert sample_product.is_active is False
    assert sample_product.stock_status == "Inactive"


def test_stock_in_success(app, staff_user, sample_product):
    initial_qty = sample_product.quantity
    tx = StockService.record_stock_in(
        product_id=sample_product.id,
        quantity=25,
        user=staff_user,
        unit_cost=Decimal("16.00"),
        reference="PO-TEST-100",
        notes="Standard replenishment delivery"
    )

    assert tx.quantity == 25
    assert tx.previous_quantity == initial_qty
    assert tx.resulting_quantity == initial_qty + 25
    assert sample_product.quantity == initial_qty + 25

    # Verify audit log
    audit = AuditLog.query.filter_by(action="STOCK_IN", entity_id=str(sample_product.id)).first()
    assert audit is not None
    assert "Received +25 units" in audit.details


def test_stock_out_success(app, staff_user, sample_product):
    initial_qty = sample_product.quantity
    tx = StockService.record_stock_out(
        product_id=sample_product.id,
        quantity=10,
        user=staff_user,
        reason="Customer Sale",
        reference="SO-TEST-500",
        notes="Customer order fulfillment"
    )

    assert tx.quantity == 10
    assert tx.previous_quantity == initial_qty
    assert tx.resulting_quantity == initial_qty - 10
    assert sample_product.quantity == initial_qty - 10

    # Verify audit log
    audit = AuditLog.query.filter_by(action="STOCK_OUT", entity_id=str(sample_product.id)).first()
    assert audit is not None


def test_stock_out_insufficient_stock_rejected(app, staff_user, sample_product):
    current = sample_product.quantity
    with pytest.raises(InsufficientStockError) as exc_info:
        StockService.record_stock_out(
            product_id=sample_product.id,
            quantity=current + 100,  # Requesting more than available
            user=staff_user
        )
    assert "Insufficient stock" in str(exc_info.value)
    # Quantity unchanged
    db.session.refresh(sample_product)
    assert sample_product.quantity == current


def test_stock_negative_or_zero_rejected(app, staff_user, sample_product):
    with pytest.raises(InvalidQuantityError):
        StockService.record_stock_in(sample_product.id, quantity=0, user=staff_user)

    with pytest.raises(InvalidQuantityError):
        StockService.record_stock_in(sample_product.id, quantity=-5, user=staff_user)

    with pytest.raises(InvalidQuantityError):
        StockService.record_stock_out(sample_product.id, quantity=0, user=staff_user)

    with pytest.raises(InvalidQuantityError):
        StockService.record_stock_out(sample_product.id, quantity=-10, user=staff_user)


def test_stock_adjustment_permissions(app, admin_user, staff_user, sample_product):
    # Staff attempt must fail
    with pytest.raises(UnauthorizedStockOperationError):
        StockService.record_adjustment(
            product_id=sample_product.id,
            resulting_quantity=40,
            user=staff_user,
            reason="Physical Audit"
        )

    # Admin attempt succeeds
    tx = StockService.record_adjustment(
        product_id=sample_product.id,
        resulting_quantity=40,
        user=admin_user,
        reason="Physical Audit",
        notes="Verified by lead auditor"
    )
    assert sample_product.quantity == 40
    assert tx.resulting_quantity == 40
    assert tx.transaction_type == TransactionType.ADJUSTMENT


def test_stock_operation_on_inactive_product_rejected(app, staff_user, sample_product):
    sample_product.is_active = False
    db.session.commit()

    with pytest.raises(ProductInactiveError):
        StockService.record_stock_in(sample_product.id, quantity=10, user=staff_user)

    with pytest.raises(ProductInactiveError):
        StockService.record_stock_out(sample_product.id, quantity=5, user=staff_user)


def test_create_supplier_success(client, admin_user):
    client.post("/login", data={"username": "admin_test", "password": "AdminPass123!"})
    res = client.post("/suppliers/new", data={
        "name": "Global Tech Logistics",
        "contact_person": "Sarah Connor",
        "phone": "+1 555-0199",
        "email": "sarah@globaltech.com",
        "address": "100 Innovation Way"
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"registered successfully" in res.data


def test_analytics_page_loads_successfully(client, admin_user):
    client.post("/login", data={"username": "admin_test", "password": "AdminPass123!"})
    res = client.get("/analytics")
    assert res.status_code == 200
    assert b"Inventory Analytics &amp; Intelligence" in res.data or b"Inventory Analytics & Intelligence" in res.data


def test_categories_ordered_by_id(client, admin_user):
    from app.models.category import Category
    c2 = Category(name="Zebra Tools")
    c1 = Category(name="Alpha Supplies")
    db.session.add_all([c2, c1])
    db.session.commit()

    client.post("/login", data={"username": "admin_test", "password": "AdminPass123!"})
    res = client.get("/categories")
    assert res.status_code == 200
    # c2 was added before c1 so c2.id < c1.id even though 'Zebra' is alphabetically after 'Alpha'
    text = res.data.decode("utf-8")
    assert text.find(f"#{c2.id}") < text.find(f"#{c1.id}")


def test_suppliers_ordered_by_id(client, admin_user):
    from app.models.supplier import Supplier
    s2 = Supplier(name="Zeta Logistics")
    s1 = Supplier(name="Alpha Partners")
    db.session.add_all([s2, s1])
    db.session.commit()

    client.post("/login", data={"username": "admin_test", "password": "AdminPass123!"})
    res = client.get("/suppliers")
    assert res.status_code == 200
    text = res.data.decode("utf-8")
    assert text.find(f"#{s2.id}") < text.find(f"#{s1.id}")
