from datetime import datetime, timezone
from decimal import Decimal
from app.extensions import db

class TransactionType:
    STOCK_IN = "STOCK_IN"
    STOCK_OUT = "STOCK_OUT"
    ADJUSTMENT = "ADJUSTMENT"
    CHOICES = [STOCK_IN, STOCK_OUT, ADJUSTMENT]


class StockTransaction(db.Model):
    __tablename__ = "stock_transactions"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)

    transaction_type = db.Column(db.String(20), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)  # Positive magnitude of the movement
    previous_quantity = db.Column(db.Integer, nullable=False)
    resulting_quantity = db.Column(db.Integer, nullable=False)

    unit_cost = db.Column(db.Numeric(10, 2), nullable=True)
    reference = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    @property
    def net_change(self) -> int:
        """Signed quantity change reflecting inventory impact."""
        if self.transaction_type == TransactionType.STOCK_IN:
            return self.quantity
        elif self.transaction_type == TransactionType.STOCK_OUT:
            return -self.quantity
        elif self.transaction_type == TransactionType.ADJUSTMENT:
            return self.resulting_quantity - self.previous_quantity
        return 0

    @property
    def type_badge_class(self) -> str:
        if self.transaction_type == TransactionType.STOCK_IN:
            return "success"
        elif self.transaction_type == TransactionType.STOCK_OUT:
            return "danger"
        return "primary"

    def __repr__(self):
        return f"<StockTransaction #{self.id} {self.transaction_type} ({self.quantity} units)>"
