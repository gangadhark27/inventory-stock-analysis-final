from urllib.parse import urlparse
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import bp
from app.extensions import db
from app.models.user import User, Role
from app.models.audit_log import AuditLog
from app.forms import LoginForm, UserForm
from app.utils import admin_required


def is_safe_redirect_url(target: str) -> bool:
    """Verifies that redirect URL is strictly on the same host."""
    ref_url = urlparse(request.host_url)
    test_url = urlparse(target)
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip()).first()
        if user is None or not user.check_password(form.password.data):
            flash("Invalid username or password.", "danger")
            return render_template("auth/login.html", form=form)

        if not user.is_active:
            flash("This account has been deactivated. Please contact an Administrator.", "danger")
            return render_template("auth/login.html", form=form)

        login_user(user, remember=form.remember.data)
        
        # Log successful authentication
        audit = AuditLog(
            user_id=user.id,
            action="USER_LOGIN",
            entity_type="User",
            entity_id=str(user.id),
            details=f"User {user.username} ({user.role}) logged in successfully."
        )
        db.session.add(audit)
        db.session.commit()

        flash(f"Welcome back, {user.full_name}!", "success")

        next_page = request.args.get("next")
        if next_page and is_safe_redirect_url(next_page):
            return redirect(next_page)
        return redirect(url_for("dashboard.index"))

    return render_template("auth/login.html", form=form)


@bp.route("/logout")
@login_required
def logout():
    audit = AuditLog(
        user_id=current_user.id,
        action="USER_LOGOUT",
        entity_type="User",
        entity_id=str(current_user.id),
        details=f"User {current_user.username} logged out."
    )
    db.session.add(audit)
    db.session.commit()

    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/users")
@login_required
@admin_required
def users():
    all_users = User.query.order_by(User.id.asc()).all()
    return render_template("auth/users.html", users=all_users)


@bp.route("/users/new", methods=["GET", "POST"])
@login_required
@admin_required
def new_user():
    form = UserForm()
    if form.validate_on_submit():
        existing = User.query.filter_by(username=form.username.data.strip()).first()
        if existing:
            flash(f"Username '{form.username.data.strip()}' is already taken.", "danger")
            return render_template("auth/user_form.html", form=form, title="Create New User")

        if not form.password.data:
            flash("A password is required when creating a new user account.", "danger")
            return render_template("auth/user_form.html", form=form, title="Create New User")

        user = User(
            username=form.username.data.strip(),
            full_name=form.full_name.data.strip(),
            role=form.role.data,
            is_active=form.is_active.data
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        audit = AuditLog(
            user_id=current_user.id,
            action="CREATE_USER",
            entity_type="User",
            entity_id=str(user.id),
            details=f"Created {user.role} user '{user.username}'."
        )
        db.session.add(audit)
        db.session.commit()

        flash(f"User account '{user.username}' created successfully.", "success")
        return redirect(url_for("auth.users"))

    return render_template("auth/user_form.html", form=form, title="Create New User")


@bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        abort(404)

    form = UserForm(obj=user)
    if form.validate_on_submit():
        # Prevent self-deactivation of current admin account
        if user.id == current_user.id and not form.is_active.data:
            flash("You cannot deactivate your own current Administrator account.", "danger")
            return render_template("auth/user_form.html", form=form, title=f"Edit User: {user.username}", user=user)

        # Check unique username if altered
        if form.username.data.strip() != user.username:
            existing = User.query.filter_by(username=form.username.data.strip()).first()
            if existing:
                flash(f"Username '{form.username.data.strip()}' is already taken.", "danger")
                return render_template("auth/user_form.html", form=form, title=f"Edit User: {user.username}", user=user)

        user.username = form.username.data.strip()
        user.full_name = form.full_name.data.strip()
        user.role = form.role.data
        user.is_active = form.is_active.data

        if form.password.data:
            user.set_password(form.password.data)

        db.session.commit()

        audit = AuditLog(
            user_id=current_user.id,
            action="UPDATE_USER",
            entity_type="User",
            entity_id=str(user.id),
            details=f"Updated profile/role for user '{user.username}' (Active: {user.is_active})."
        )
        db.session.add(audit)
        db.session.commit()

        flash(f"User '{user.username}' updated successfully.", "success")
        return redirect(url_for("auth.users"))

    return render_template("auth/user_form.html", form=form, title=f"Edit User: {user.username}", user=user)
