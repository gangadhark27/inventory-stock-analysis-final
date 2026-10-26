from decimal import Decimal
from app.utils import sanitize_csv_cell
from app.models.product import Product


def test_sanitize_csv_cell_formula_injection():
    # Formula injection indicators must be escaped
    assert sanitize_csv_cell("=1+1") == "'=1+1"
    assert sanitize_csv_cell("+cmd|' /C calc'!A0") == "'+cmd|' /C calc'!A0"
    assert sanitize_csv_cell("-5+2") == "'-5+2"
    assert sanitize_csv_cell("@SUM(1,2)") == "'@SUM(1,2)"
    assert sanitize_csv_cell("Normal text") == "Normal text"
    assert sanitize_csv_cell(123) == "123"
    assert sanitize_csv_cell(None) == ""


def test_export_inventory_pdf(client, admin_user, sample_product):
    client.post("/login", data={"username": "admin_test", "password": "AdminPass123!"})
    res = client.get("/reports/export/inventory")
    assert res.status_code == 200
    assert res.mimetype == "application/pdf"
    assert res.data.startswith(b"%PDF-")
    assert ".pdf" in res.headers["Content-Disposition"]


def test_export_inventory_csv(client, admin_user, sample_product):
    client.post("/login", data={"username": "admin_test", "password": "AdminPass123!"})
    res = client.get("/reports/export/inventory?format=csv")
    assert res.status_code == 200
    assert res.mimetype == "text/csv"
    assert "attachment; filename=" in res.headers["Content-Disposition"]
    
    csv_text = res.data.decode("utf-8")
    assert "S.No,SKU,Product Name" in csv_text
    assert sample_product.sku in csv_text
    assert sample_product.name in csv_text


def test_export_categories_pdf(client, admin_user, sample_category):
    client.post("/login", data={"username": "admin_test", "password": "AdminPass123!"})
    res = client.get("/reports/export/categories")
    assert res.status_code == 200
    assert res.mimetype == "application/pdf"
    assert res.data.startswith(b"%PDF-")


def test_export_low_stock_pdf(client, admin_user, sample_category):
    client.post("/login", data={"username": "admin_test", "password": "AdminPass123!"})
    res = client.get("/reports/export/low-stock")
    assert res.status_code == 200
    assert res.mimetype == "application/pdf"
    assert res.data.startswith(b"%PDF-")


def test_export_transactions_pdf(client, staff_user):
    client.post("/login", data={"username": "staff_test", "password": "StaffPass123!"})
    res = client.get("/reports/export/transactions")
    assert res.status_code == 200
    assert res.mimetype == "application/pdf"
    assert res.data.startswith(b"%PDF-")


def test_export_fast_moving_pdf(client, staff_user):
    client.post("/login", data={"username": "staff_test", "password": "StaffPass123!"})
    res = client.get("/reports/export/fast-moving")
    assert res.status_code == 200
    assert res.mimetype == "application/pdf"
    assert res.data.startswith(b"%PDF-")


def test_export_suppliers_pdf(client, admin_user, sample_supplier):
    client.post("/login", data={"username": "admin_test", "password": "AdminPass123!"})
    res = client.get("/reports/export/suppliers")
    assert res.status_code == 200
    assert res.mimetype == "application/pdf"
    assert res.data.startswith(b"%PDF-")
