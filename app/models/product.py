from datetime import datetime, timezone
from decimal import Decimal
from app.extensions import db

class Product(db.Model):
    __tablename__ = "products"
    __table_args__ = (
        db.CheckConstraint("quantity >= 0", name="check_positive_quantity"),
        db.CheckConstraint("reorder_level >= 0", name="check_positive_reorder_level"),
        db.CheckConstraint("unit_cost >= 0", name="check_positive_unit_cost"),
        db.CheckConstraint("selling_price >= 0", name="check_positive_selling_price"),
    )

    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True)

    unit_cost = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    selling_price = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    quantity = db.Column(db.Integer, nullable=False, default=0)
    reorder_level = db.Column(db.Integer, nullable=False, default=10)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    transactions = db.relationship(
        "StockTransaction",
        backref="product",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )

    @property
    def stock_status(self) -> str:
        if not self.is_active:
            return "Inactive"
        if self.quantity == 0:
            return "Out of Stock"
        if self.quantity <= self.reorder_level:
            return "Low Stock"
        return "In Stock"

    @property
    def status_badge_class(self) -> str:
        status = self.stock_status
        if status == "In Stock":
            return "success"
        if status == "Low Stock":
            return "warning text-dark"
        if status == "Out of Stock":
            return "danger"
        return "secondary"

    @property
    def inventory_cost_value(self) -> Decimal:
        return Decimal(self.quantity) * (self.unit_cost or Decimal("0.00"))

    @property
    def potential_selling_value(self) -> Decimal:
        return Decimal(self.quantity) * (self.selling_price or Decimal("0.00"))

    def __repr__(self):
        return f"<Product {self.sku} - {self.name} (Qty: {self.quantity})>"
