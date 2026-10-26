from datetime import datetime, timezone
from decimal import Decimal
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from sqlalchemy import or_

from app.inventory import bp
from app.extensions import db
from app.models.product import Product
from app.models.category import Category
from app.models.supplier import Supplier
from app.models.stock_transaction import StockTransaction, TransactionType
from app.models.audit_log import AuditLog
from app.models.user import User
from app.forms import (
    ProductForm,
    CategoryForm,
    SupplierForm,
    StockInForm,
    StockOutForm,
    StockAdjustmentForm
)
from app.services.stock_service import StockService, StockServiceError
from app.utils import admin_required


# =========================================================================
# PRODUCTS MANAGEMENT
# =========================================================================

@bp.route("/products")
@login_required
def products():
    search = request.args.get("search", "").strip()
    category_id = request.args.get("category_id", type=int)
    status_filter = request.args.get("status", "").strip()
    sort_by = request.args.get("sort_by", "name").strip()
    order = request.args.get("order", "asc").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 15

    query = Product.query

    # Search filter (name or SKU)
    if search:
        query = query.filter(or_(
            Product.name.ilike(f"%{search}%"),
            Product.sku.ilike(f"%{search}%")
        ))

    # Category filter
    if category_id:
        query = query.filter(Product.category_id == category_id)

    # Status filter
    if status_filter == "in_stock":
        query = query.filter(Product.is_active == True, Product.quantity > Product.reorder_level)
    elif status_filter == "low_stock":
        query = query.filter(Product.is_active == True, Product.quantity > 0, Product.quantity <= Product.reorder_level)
    elif status_filter == "out_of_stock":
        query = query.filter(Product.is_active == True, Product.quantity == 0)
    elif status_filter == "inactive":
        query = query.filter(Product.is_active == False)

    # Sorting
    sort_column = Product.name
    if sort_by == "sku":
        sort_column = Product.sku
    elif sort_by == "quantity":
        sort_column = Product.quantity
    elif sort_by == "unit_cost":
        sort_column = Product.unit_cost
    elif sort_by == "selling_price":
        sort_column = Product.selling_price
    elif sort_by == "updated_at":
        sort_column = Product.updated_at

    if order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    categories = Category.query.order_by(Category.id.asc()).all()

    return render_template(
        "inventory/products.html",
        products=pagination.items,
        pagination=pagination,
        categories=categories,
        search=search,
        selected_category=category_id,
        selected_status=status_filter,
        sort_by=sort_by,
        order=order
    )


@bp.route("/products/new", methods=["GET", "POST"])
@login_required
@admin_required
def new_product():
    form = ProductForm()
    categories = Category.query.order_by(Category.id.asc()).all()
    suppliers = Supplier.query.order_by(Supplier.name).all()

    form.category_id.choices = [(c.id, c.name) for c in categories]
    form.supplier_id.choices = [(0, "-- None / Independent --")] + [(s.id, s.name) for s in Supplier.query.order_by(Supplier.id.asc()).all()]

    if not categories:
        flash("Please create at least one category before adding products.", "warning")
        return redirect(url_for("inventory.new_category"))

    if form.validate_on_submit():
        sku_clean = form.sku.data.strip().upper()
        existing = Product.query.filter_by(sku=sku_clean).first()
        if existing:
            flash(f"A product with SKU '{sku_clean}' already exists.", "danger")
            return render_template("inventory/product_form.html", form=form, title="Create New Product")

        supplier_id = form.supplier_id.data if form.supplier_id.data != 0 else None

        product = Product(
            sku=sku_clean,
            name=form.name.data.strip(),
            description=form.description.data.strip() if form.description.data else None,
            category_id=form.category_id.data,
            supplier_id=supplier_id,
            unit_cost=form.unit_cost.data,
            selling_price=form.selling_price.data,
            quantity=0,  # Initial stock starts at 0; must be received via stock-in
            reorder_level=form.reorder_level.data,
            is_active=form.is_active.data
        )
        db.session.add(product)
        db.session.commit()

        audit = AuditLog(
            user_id=current_user.id,
            action="CREATE_PRODUCT",
            entity_type="Product",
            entity_id=str(product.id),
            details=f"Created product '{product.name}' with SKU '{product.sku}'."
        )
        db.session.add(audit)
        db.session.commit()

        flash(f"Product '{product.name}' created successfully. Record incoming stock to set its initial quantity.", "success")
        return redirect(url_for("inventory.product_detail", product_id=product.id))

    return render_template("inventory/product_form.html", form=form, title="Create New Product")


@bp.route("/products/<int:product_id>")
@login_required
def product_detail(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        abort(404)

    recent_transactions = product.transactions.order_by(StockTransaction.created_at.desc()).limit(15).all()
    return render_template("inventory/product_detail.html", product=product, transactions=recent_transactions)


@bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_product(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        abort(404)

    form = ProductForm(obj=product)
    categories = Category.query.order_by(Category.id.asc()).all()
    suppliers = Supplier.query.order_by(Supplier.name).all()

    form.category_id.choices = [(c.id, c.name) for c in categories]
    form.supplier_id.choices = [(0, "-- None / Independent --")] + [(s.id, s.name) for s in Supplier.query.order_by(Supplier.id.asc()).all()]

    if request.method == "GET":
        form.supplier_id.data = product.supplier_id or 0

    if form.validate_on_submit():
        sku_clean = form.sku.data.strip().upper()
        if sku_clean != product.sku:
            existing = Product.query.filter_by(sku=sku_clean).first()
            if existing:
                flash(f"A product with SKU '{sku_clean}' already exists.", "danger")
                return render_template("inventory/product_form.html", form=form, title=f"Edit Product: {product.name}", product=product)

        product.sku = sku_clean
        product.name = form.name.data.strip()
        product.description = form.description.data.strip() if form.description.data else None
        product.category_id = form.category_id.data
        product.supplier_id = form.supplier_id.data if form.supplier_id.data != 0 else None
        product.unit_cost = form.unit_cost.data
        product.selling_price = form.selling_price.data
        product.reorder_level = form.reorder_level.data
        product.is_active = form.is_active.data

        db.session.commit()

        audit = AuditLog(
            user_id=current_user.id,
            action="UPDATE_PRODUCT",
            entity_type="Product",
            entity_id=str(product.id),
            details=f"Updated product '{product.name}' (SKU: {product.sku})."
        )
        db.session.add(audit)
        db.session.commit()

        flash(f"Product '{product.name}' updated successfully.", "success")
        return redirect(url_for("inventory.product_detail", product_id=product.id))

    return render_template("inventory/product_form.html", form=form, title=f"Edit Product: {product.name}", product=product)


@bp.route("/products/<int:product_id>/toggle-status", methods=["POST"])
@login_required
@admin_required
def toggle_product_status(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        abort(404)

    product.is_active = not product.is_active
    db.session.commit()

    action_name = "DEACTIVATE_PRODUCT" if not product.is_active else "ACTIVATE_PRODUCT"
    status_str = "activated" if product.is_active else "deactivated"

    audit = AuditLog(
        user_id=current_user.id,
        action=action_name,
        entity_type="Product",
        entity_id=str(product.id),
        details=f"Product '{product.name}' (SKU: {product.sku}) was {status_str}."
    )
    db.session.add(audit)
    db.session.commit()

    flash(f"Product '{product.name}' has been {status_str}.", "info")
    return redirect(request.referrer or url_for("inventory.products"))


# =========================================================================
# CATEGORY MANAGEMENT
# =========================================================================

@bp.route("/categories")
@login_required
def categories():
    cats = Category.query.order_by(Category.id.asc()).all()
    return render_template("inventory/categories.html", categories=cats)


@bp.route("/categories/new", methods=["GET", "POST"])
@login_required
@admin_required
def new_category():
    form = CategoryForm()
    if form.validate_on_submit():
        name_clean = form.name.data.strip()
        existing = Category.query.filter(Category.name.ilike(name_clean)).first()
        if existing:
            flash(f"A category named '{name_clean}' already exists.", "danger")
            return render_template("inventory/category_form.html", form=form, title="Create New Category")

        cat = Category(
            name=name_clean,
            description=form.description.data.strip() if form.description.data else None
        )
        db.session.add(cat)
        db.session.commit()

        audit = AuditLog(
            user_id=current_user.id,
            action="CREATE_CATEGORY",
            entity_type="Category",
            entity_id=str(cat.id),
            details=f"Created category '{cat.name}'."
        )
        db.session.add(audit)
        db.session.commit()

        flash(f"Category '{cat.name}' created successfully.", "success")
        return redirect(url_for("inventory.categories"))

    return render_template("inventory/category_form.html", form=form, title="Create New Category")


@bp.route("/categories/<int:category_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_category(category_id):
    cat = db.session.get(Category, category_id)
    if not cat:
        abort(404)

    form = CategoryForm(obj=cat)
    if form.validate_on_submit():
        name_clean = form.name.data.strip()
        if name_clean.lower() != cat.name.lower():
            existing = Category.query.filter(Category.name.ilike(name_clean)).first()
            if existing:
                flash(f"A category named '{name_clean}' already exists.", "danger")
                return render_template("inventory/category_form.html", form=form, title=f"Edit Category: {cat.name}")

        cat.name = name_clean
        cat.description = form.description.data.strip() if form.description.data else None
        db.session.commit()

        audit = AuditLog(
            user_id=current_user.id,
            action="UPDATE_CATEGORY",
            entity_type="Category",
            entity_id=str(cat.id),
            details=f"Updated category '{cat.name}'."
        )
        db.session.add(audit)
        db.session.commit()

        flash(f"Category '{cat.name}' updated successfully.", "success")
        return redirect(url_for("inventory.categories"))

    return render_template("inventory/category_form.html", form=form, title=f"Edit Category: {cat.name}")


@bp.route("/categories/<int:category_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_category(category_id):
    cat = db.session.get(Category, category_id)
    if not cat:
        abort(404)

    # Prevent deleting if products are assigned
    active_count = cat.products.count()
    if active_count > 0:
        flash(f"Cannot delete category '{cat.name}' because {active_count} product(s) are assigned to it.", "danger")
        return redirect(url_for("inventory.categories"))

    cat_name = cat.name
    db.session.delete(cat)
    db.session.commit()

    audit = AuditLog(
        user_id=current_user.id,
        action="DELETE_CATEGORY",
        entity_type="Category",
        entity_id=str(category_id),
        details=f"Deleted category '{cat_name}'."
    )
    db.session.add(audit)
    db.session.commit()

    flash(f"Category '{cat_name}' was deleted.", "info")
    return redirect(url_for("inventory.categories"))


# =========================================================================
# SUPPLIER MANAGEMENT (ADMIN ONLY)
# =========================================================================

@bp.route("/suppliers")
@login_required
@admin_required
def suppliers():
    all_suppliers = Supplier.query.order_by(Supplier.id.asc()).all()
    return render_template("inventory/suppliers.html", suppliers=all_suppliers)


@bp.route("/suppliers/new", methods=["GET", "POST"])
@login_required
@admin_required
def new_supplier():
    form = SupplierForm()
    if form.validate_on_submit():
        name_clean = form.name.data.strip()
        existing = Supplier.query.filter(Supplier.name.ilike(name_clean)).first()
        if existing:
            flash(f"A supplier named '{name_clean}' already exists.", "danger")
            return render_template("inventory/supplier_form.html", form=form, title="Create New Supplier")

        sup = Supplier(
            name=name_clean,
            contact_person=form.contact_person.data.strip() if form.contact_person.data else None,
            phone=form.phone.data.strip() if form.phone.data else None,
            email=form.email.data.strip() if form.email.data else None,
            address=form.address.data.strip() if form.address.data else None,
        )
        db.session.add(sup)
        db.session.commit()

        audit = AuditLog(
            user_id=current_user.id,
            action="CREATE_SUPPLIER",
            entity_type="Supplier",
            entity_id=str(sup.id),
            details=f"Created supplier '{sup.name}'."
        )
        db.session.add(audit)
        db.session.commit()

        flash(f"Supplier '{sup.name}' registered successfully.", "success")
        return redirect(url_for("inventory.suppliers"))

    return render_template("inventory/supplier_form.html", form=form, title="Create New Supplier")


@bp.route("/suppliers/<int:supplier_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_supplier(supplier_id):
    sup = db.session.get(Supplier, supplier_id)
    if not sup:
        abort(404)

    form = SupplierForm(obj=sup)
    if form.validate_on_submit():
        name_clean = form.name.data.strip()
        if name_clean.lower() != sup.name.lower():
            existing = Supplier.query.filter(Supplier.name.ilike(name_clean)).first()
            if existing:
                flash(f"A supplier named '{name_clean}' already exists.", "danger")
                return render_template("inventory/supplier_form.html", form=form, title=f"Edit Supplier: {sup.name}")

        sup.name = name_clean
        sup.contact_person = form.contact_person.data.strip() if form.contact_person.data else None
        sup.phone = form.phone.data.strip() if form.phone.data else None
        sup.email = form.email.data.strip() if form.email.data else None
        sup.address = form.address.data.strip() if form.address.data else None
        db.session.commit()

        audit = AuditLog(
            user_id=current_user.id,
            action="UPDATE_SUPPLIER",
            entity_type="Supplier",
            entity_id=str(sup.id),
            details=f"Updated supplier '{sup.name}'."
        )
        db.session.add(audit)
        db.session.commit()

        flash(f"Supplier '{sup.name}' updated successfully.", "success")
        return redirect(url_for("inventory.suppliers"))

    return render_template("inventory/supplier_form.html", form=form, title=f"Edit Supplier: {sup.name}")


@bp.route("/suppliers/<int:supplier_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_supplier(supplier_id):
    sup = db.session.get(Supplier, supplier_id)
    if not sup:
        abort(404)

    sup_name = sup.name
    # Unlink products safely (FK ondelete=SET NULL handles db-level, update python side too)
    for prod in sup.products:
        prod.supplier_id = None

    db.session.delete(sup)
    db.session.commit()

    audit = AuditLog(
        user_id=current_user.id,
        action="DELETE_SUPPLIER",
        entity_type="Supplier",
        entity_id=str(supplier_id),
        details=f"Deleted supplier '{sup_name}'. Products unlinked safely."
    )
    db.session.add(audit)
    db.session.commit()

    flash(f"Supplier '{sup_name}' deleted.", "info")
    return redirect(url_for("inventory.suppliers"))


# =========================================================================
# STOCK OPERATIONS (MUTATIONS CENTRALIZED VIA STOCK_SERVICE)
# =========================================================================

@bp.route("/stock/in", methods=["GET", "POST"])
@login_required
def stock_in():
    form = StockInForm()
    active_products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    form.product_id.choices = [(p.id, f"{p.sku} — {p.name} (Current: {p.quantity} units)") for p in active_products]

    # Pre-select product if passed in query string
    preselect_id = request.args.get("product_id", type=int)
    if request.method == "GET" and preselect_id:
        form.product_id.data = preselect_id

    if form.validate_on_submit():
        try:
            tx = StockService.record_stock_in(
                product_id=form.product_id.data,
                quantity=form.quantity.data,
                user=current_user,
                unit_cost=form.unit_cost.data,
                reference=form.reference.data,
                notes=form.notes.data
            )
            flash(
                f"Successfully received {tx.quantity} units for {tx.product.name} (SKU: {tx.product.sku}). "
                f"New inventory balance: {tx.resulting_quantity} units.",
                "success"
            )
            return redirect(url_for("inventory.product_detail", product_id=tx.product_id))
        except StockServiceError as e:
            flash(f"Stock-in failed: {str(e)}", "danger")

    return render_template("inventory/stock_in.html", form=form)


@bp.route("/stock/out", methods=["GET", "POST"])
@login_required
def stock_out():
    form = StockOutForm()
    active_products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    form.product_id.choices = [(p.id, f"{p.sku} — {p.name} (Available: {p.quantity} units)") for p in active_products]

    preselect_id = request.args.get("product_id", type=int)
    if request.method == "GET" and preselect_id:
        form.product_id.data = preselect_id

    if form.validate_on_submit():
        try:
            tx = StockService.record_stock_out(
                product_id=form.product_id.data,
                quantity=form.quantity.data,
                user=current_user,
                reason=form.reason.data,
                reference=form.reference.data,
                notes=form.notes.data
            )
            flash(
                f"Successfully issued {tx.quantity} units from {tx.product.name} (SKU: {tx.product.sku}). "
                f"Remaining inventory balance: {tx.resulting_quantity} units.",
                "success"
            )
            return redirect(url_for("inventory.product_detail", product_id=tx.product_id))
        except StockServiceError as e:
            flash(f"Stock-out failed: {str(e)}", "danger")

    return render_template("inventory/stock_out.html", form=form)


@bp.route("/stock/adjust", methods=["GET", "POST"])
@login_required
@admin_required
def stock_adjust():
    form = StockAdjustmentForm()
    active_products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    form.product_id.choices = [(p.id, f"{p.sku} — {p.name} (Current: {p.quantity} units)") for p in active_products]

    preselect_id = request.args.get("product_id", type=int)
    if request.method == "GET" and preselect_id:
        form.product_id.data = preselect_id

    if form.validate_on_submit():
        try:
            tx = StockService.record_adjustment(
                product_id=form.product_id.data,
                resulting_quantity=form.resulting_quantity.data,
                user=current_user,
                reason=form.reason.data,
                notes=form.notes.data
            )
            flash(
                f"Physical inventory reconciled for {tx.product.name} (SKU: {tx.product.sku}). "
                f"Adjusted from {tx.previous_quantity} to {tx.resulting_quantity} units.",
                "success"
            )
            return redirect(url_for("inventory.product_detail", product_id=tx.product_id))
        except StockServiceError as e:
            flash(f"Stock adjustment failed: {str(e)}", "danger")

    return render_template("inventory/adjustment.html", form=form)


# =========================================================================
# TRANSACTION HISTORY
# =========================================================================

@bp.route("/transactions")
@login_required
def transactions():
    search = request.args.get("search", "").strip()
    tx_type = request.args.get("type", "").strip()
    product_id = request.args.get("product_id", type=int)
    user_id = request.args.get("user_id", type=int)
    start_date_str = request.args.get("start_date", "").strip()
    end_date_str = request.args.get("end_date", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 20

    query = StockTransaction.query.join(Product).join(User)

    if search:
        query = query.filter(or_(
            Product.name.ilike(f"%{search}%"),
            Product.sku.ilike(f"%{search}%"),
            StockTransaction.reference.ilike(f"%{search}%"),
            StockTransaction.notes.ilike(f"%{search}%")
        ))

    if tx_type in TransactionType.CHOICES:
        query = query.filter(StockTransaction.transaction_type == tx_type)

    if product_id:
        query = query.filter(StockTransaction.product_id == product_id)

    if user_id and current_user.is_admin:
        query = query.filter(StockTransaction.user_id == user_id)

    # Date range filters
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

    pagination = query.order_by(StockTransaction.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    products_list = Product.query.order_by(Product.name).all()
    users_list = User.query.order_by(User.username).all() if current_user.is_admin else []

    return render_template(
        "inventory/transactions.html",
        transactions=pagination.items,
        pagination=pagination,
        products=products_list,
        users=users_list,
        search=search,
        selected_type=tx_type,
        selected_product=product_id,
        selected_user=user_id,
        start_date=start_date_str,
        end_date=end_date_str
    )
