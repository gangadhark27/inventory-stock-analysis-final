from functools import wraps
from flask import abort, flash, redirect, url_for, Response
from flask_login import current_user
import io
import csv

def admin_required(f):
    """Decorator to enforce Admin role on sensitive views."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not current_user.is_admin:
            flash("Administrator privileges are required to access this resource.", "danger")
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def sanitize_csv_cell(value) -> str:
    """
    Prevents CSV Formula Injection (CWE-1236).
    If a cell starts with =, +, -, @, tab, or newline, escape it with a leading apostrophe.
    """
    if value is None:
        return ""
    val_str = str(value)
    if val_str and val_str[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{val_str}"
    return val_str


def generate_csv_response(headers: list, rows: list, filename: str) -> Response:
    """Generates an RFC-4180 compliant CSV stream with formula sanitization."""
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    # Write headers
    writer.writerow([sanitize_csv_cell(h) for h in headers])

    # Write sanitized rows
    for row in rows:
        writer.writerow([sanitize_csv_cell(cell) for cell in row])

    csv_data = output.getvalue()
    output.close()

    response = Response(csv_data, mimetype="text/csv")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response
