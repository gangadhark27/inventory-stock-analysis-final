import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from decimal import Decimal
from app import create_app

from app.extensions import db
from config import TestConfig
from app.models.user import User, Role
from app.models.category import Category
from app.models.supplier import Supplier
from app.models.product import Product


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_user(app):
    user = User(
        username="admin_test",
        full_name="Admin Test User",
        role=Role.ADMIN,
        is_active=True
    )
    user.set_password("AdminPass123!")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def staff_user(app):
    user = User(
        username="staff_test",
        full_name="Staff Test User",
        role=Role.STAFF,
        is_active=True
    )
    user.set_password("StaffPass123!")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def inactive_user(app):
    user = User(
        username="inactive_test",
        full_name="Inactive User",
        role=Role.STAFF,
        is_active=False
    )
    user.set_password("InactivePass123!")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def sample_category(app):
    cat = Category(name="Electronics", description="Electronic components")
    db.session.add(cat)
    db.session.commit()
    return cat


@pytest.fixture
def sample_supplier(app):
    sup = Supplier(name="Apex Supplies", contact_person="Marcus", email="marcus@apex.com")
    db.session.add(sup)
    db.session.commit()
    return sup


@pytest.fixture
def sample_product(app, sample_category, sample_supplier):
    prod = Product(
        sku="TEST-SKU-001",
        name="Test Sensor Module",
        description="A high precision sensor",
        category_id=sample_category.id,
        supplier_id=sample_supplier.id,
        unit_cost=Decimal("15.50"),
        selling_price=Decimal("29.99"),
        quantity=50,
        reorder_level=10,
        is_active=True
    )
    db.session.add(prod)
    db.session.commit()
    return prod
