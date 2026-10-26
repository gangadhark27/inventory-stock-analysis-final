from decimal import Decimal
from typing import Optional
from app.extensions import db
from app.models.product import Product
from app.models.stock_transaction import StockTransaction, TransactionType
from app.models.audit_log import AuditLog
from app.models.user import User, Role


class StockServiceError(Exception):
    """Base exception for all stock mutation failures."""
    pass


class ProductNotFoundError(StockServiceError):
    pass


class ProductInactiveError(StockServiceError):
    pass


class InvalidQuantityError(StockServiceError):
    pass


class InsufficientStockError(StockServiceError):
    pass


class UnauthorizedStockOperationError(StockServiceError):
    pass


class StockService:
    """
    Centralized service for all stock mutations.
    Guarantees atomic execution, validation, logging, and state integrity.
    """

    @staticmethod
    def _validate_user(user: User):
        if not user or not user.is_active:
            raise UnauthorizedStockOperationError("An active, authenticated user is required for stock operations.")

    @staticmethod
    def _get_active_product(product_id: int) -> Product:
        product = db.session.get(Product, product_id)
        if not product:
            raise ProductNotFoundError(f"Product with ID {product_id} does not exist.")
        if not product.is_active:
            raise ProductInactiveError(f"Product '{product.name}' (SKU: {product.sku}) is deactivated.")
        return product

    @classmethod
    def record_stock_in(
        cls,
        product_id: int,
        quantity: int,
        user: User,
        unit_cost: Optional[Decimal] = None,
        reference: Optional[str] = None,
        notes: Optional[str] = None
    ) -> StockTransaction:
        """
        Record incoming stock received.
        Increments product inventory quantity atomically and logs transaction.
        """
        cls._validate_user(user)

        if not isinstance(quantity, int) or quantity <= 0:
            raise InvalidQuantityError("Stock-in quantity must be a positive integer greater than zero.")

        try:
            product = cls._get_active_product(product_id)

            prev_qty = product.quantity
            new_qty = prev_qty + quantity

            # If unit cost provided on receiving, optionally update product unit cost
            cost_to_record = unit_cost if unit_cost is not None else product.unit_cost
            if unit_cost is not None and unit_cost >= 0:
                product.unit_cost = unit_cost

            # Update product quantity
            product.quantity = new_qty

            # Create StockTransaction
            tx = StockTransaction(
                product_id=product.id,
                user_id=user.id,
                transaction_type=TransactionType.STOCK_IN,
                quantity=quantity,
                previous_quantity=prev_qty,
                resulting_quantity=new_qty,
                unit_cost=cost_to_record,
                reference=reference.strip() if reference else None,
                notes=notes.strip() if notes else None
            )
            db.session.add(tx)

            # Create AuditLog
            audit = AuditLog(
                user_id=user.id,
                action="STOCK_IN",
                entity_type="Product",
                entity_id=str(product.id),
                details=f"Received +{quantity} units for {product.sku} ({product.name}). Prev: {prev_qty}, New: {new_qty}. Ref: {reference or 'None'}."
            )
            db.session.add(audit)

            db.session.commit()
            return tx

        except StockServiceError:
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            raise StockServiceError(f"Database error during stock-in: {str(e)}") from e

    @classmethod
    def record_stock_out(
        cls,
        product_id: int,
        quantity: int,
        user: User,
        reason: Optional[str] = None,
        reference: Optional[str] = None,
        notes: Optional[str] = None
    ) -> StockTransaction:
        """
        Record outgoing stock for sales, internal usage, or order fulfillment.
        Prevents negative inventory and updates atomically.
        """
        cls._validate_user(user)

        if not isinstance(quantity, int) or quantity <= 0:
            raise InvalidQuantityError("Stock-out quantity must be a positive integer greater than zero.")

        try:
            product = cls._get_active_product(product_id)

            if product.quantity < quantity:
                raise InsufficientStockError(
                    f"Insufficient stock for '{product.name}' (SKU: {product.sku}). "
                    f"Requested: {quantity}, Available: {product.quantity}."
                )

            prev_qty = product.quantity
            new_qty = prev_qty - quantity

            product.quantity = new_qty

            combined_notes = []
            if reason:
                combined_notes.append(f"Reason: {reason.strip()}")
            if notes:
                combined_notes.append(notes.strip())

            tx = StockTransaction(
                product_id=product.id,
                user_id=user.id,
                transaction_type=TransactionType.STOCK_OUT,
                quantity=quantity,
                previous_quantity=prev_qty,
                resulting_quantity=new_qty,
                unit_cost=product.unit_cost,
                reference=reference.strip() if reference else None,
                notes=" | ".join(combined_notes) if combined_notes else None
            )
            db.session.add(tx)

            audit = AuditLog(
                user_id=user.id,
                action="STOCK_OUT",
                entity_type="Product",
                entity_id=str(product.id),
                details=f"Issued -{quantity} units for {product.sku} ({product.name}). Prev: {prev_qty}, New: {new_qty}. Reason: {reason or 'Unspecified'}."
            )
            db.session.add(audit)

            db.session.commit()
            return tx

        except StockServiceError:
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            raise StockServiceError(f"Database error during stock-out: {str(e)}") from e

    @classmethod
    def record_adjustment(
        cls,
        product_id: int,
        resulting_quantity: int,
        user: User,
        reason: str,
        notes: Optional[str] = None
    ) -> StockTransaction:
        """
        Record a physical count reconciliation / authorized inventory adjustment.
        Restricted to Admin accounts or authorized staff.
        """
        cls._validate_user(user)
        if not user.is_admin:
            raise UnauthorizedStockOperationError("Only Administrator accounts are permitted to perform direct stock adjustments.")

        if not isinstance(resulting_quantity, int) or resulting_quantity < 0:
            raise InvalidQuantityError("Resulting stock quantity after adjustment cannot be negative.")

        if not reason or not reason.strip():
            raise StockServiceError("A valid adjustment reason is strictly required for audit compliance.")

        try:
            product = cls._get_active_product(product_id)

            prev_qty = product.quantity
            delta = resulting_quantity - prev_qty

            if delta == 0:
                raise StockServiceError("Adjustment resulting quantity is identical to current stock. No change made.")

            # Store absolute magnitude in tx.quantity, with net direction captured by prev and resulting quantities
            abs_change = abs(delta)

            product.quantity = resulting_quantity

            combined_notes = [f"Audit Reason: {reason.strip()}"]
            if notes and notes.strip():
                combined_notes.append(notes.strip())

            tx = StockTransaction(
                product_id=product.id,
                user_id=user.id,
                transaction_type=TransactionType.ADJUSTMENT,
                quantity=abs_change,
                previous_quantity=prev_qty,
                resulting_quantity=resulting_quantity,
                unit_cost=product.unit_cost,
                reference=f"ADJ-{reason.strip()[:20]}",
                notes=" | ".join(combined_notes)
            )
            db.session.add(tx)

            audit = AuditLog(
                user_id=user.id,
                action="STOCK_ADJUSTMENT",
                entity_type="Product",
                entity_id=str(product.id),
                details=f"Adjusted stock for {product.sku} ({product.name}) from {prev_qty} to {resulting_quantity} (Delta: {delta:+d}). Reason: {reason}."
            )
            db.session.add(audit)

            db.session.commit()
            return tx

        except StockServiceError:
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            raise StockServiceError(f"Database error during stock adjustment: {str(e)}") from e
